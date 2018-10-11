/* global d3*/
import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {initAudioContext} from './audio-handler';
import {debug, deepCopy, argmax} from './utils';
import {updateSlickGridData} from './grid-utils'
import {postRequest} from './ajax-handler';
require('bootstrap-slider/dist/bootstrap-slider.js');

const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 25;

const pseudoStartName = '__PSEUDO_START__';
const pseudoEndName = '__PSEUDO_END__';

let svg = d3.select('#graph svg');
let graph;
let margin = 20;
let circleRadius = 10;
let xRotation = 45;
let theta = 90 - (180 - Math.abs(xRotation)) / 2;
let sinTheta = Math.abs(Math.sin(theta));
let offset = sinTheta * (circleRadius);

let simulation;

const settings = {
    // If false the pseudo nodes don't have any real effect on the nodes as normal
    // otherwise they will exert a force and gravity pull on the other node
    reactivePseudoStart: false,
    reactivePseudoEnd: false,
    showLabels: true,
    charge: 10,
    distanceRangePercent: 100,
    centering: true
};

class Grid extends FlexibleGrid {
    init(granularity) {

        super.init({
            'grid-name': 'sequences',
            'grid-type': 'sequence-mining-grid',
            'default-field': 'assocrule',
            gridOptions
        });

        this.granularity = granularity;
    }

    /**
     * Highlight the active row on mouse over (super) and also highlight the corresponding segment on the spect
     * @param e
     * @param args
     */
    mouseHandler(e, args) {
        super.mouseHandler(e, args);

        const self = this;
        let eventType = e.type;
        let grid = args.grid;
        let dataView = grid.getData();
        let cell = grid.getCellFromEvent(e);
        if (cell) {
            let row = cell.row;
            let col = cell.cell;
            let coldef = grid.getColumns()[col];
            let rowElement = $(e.target.parentElement);
            let songId = dataView.getItem(row).id;
            self.eventNotifier.trigger(eventType, {
                e,
                songId,
                rowElement,
                coldef
            });
        }
    }

    initMainGridContent(defaultArgs, extraArgs) {
        let self = this;
        self.defaultArgs = defaultArgs || {};
        let doCacheSelectableOptions = self.defaultArgs.doCacheSelectableOptions || true;

        let args = deepCopy(self.defaultArgs);
        args['grid-type'] = self.gridType;

        if (extraArgs) {
            args.extras = JSON.stringify(extraArgs);
        }

        let onSuccess = function (rows) {
            let {singletRows, realRows, pseudoRows} = separateRows(rows);
            self.rows = realRows;

            self.nodesDict = constructNodeDictionary(singletRows);
            fillInNodesInfo(self.nodesDict, pseudoRows);
            // fillInRealEndNodesInfo(self.nodesDict, pseudoEndRows);

            updateSlickGridData(self.mainGrid, realRows);
            if (doCacheSelectableOptions) {
                self.cacheSelectableOptions();
            }
            focusOnGridOnInit();
        };

        postRequest({
            requestSlug: 'get-grid-content',
            data: args,
            onSuccess
        });
    }
}

export const grid = new Grid();
let granularity = $('#sequence-mining-grid').attr('granularity');
let viewas = $('#sequence-mining-grid').attr('viewas');
const gridStatus = $('#grid-status');
const gridStatusNTotal = gridStatus.find('#ntotal');


/**
 * There are 3 pieces of useful info we wanna process separately:
 * - Rows that contains only one syllable will be used to construct a dictionary of all syllables
 * - Rows that starts with a pseudo start will be used to visualise node's probability to be a start
 * - Anything else will be used to display in the table and visualis node's connectivity
 * @param rows
 * @returns {{singletRows: Array, realRows: Array, pseudoRows: Array}}
 */
const separateRows = function(rows) {
    let singletRows = [];
    let realRows = [];
    let pseudoRows = [];

    $.each(rows, function(idx, row) {
        let sequence = row.assocrule;
        if (row.chainlength == 1) {
            singletRows.push(row);
        }
        else if (sequence.startsWith(pseudoStartName) || sequence.endsWith(pseudoEndName)) {
            pseudoRows.push(row);
        }
        else {
            realRows.push(row)
        }
    });

    return {
        singletRows,
        realRows,
        pseudoRows
    };
};

let resetOnGapSlider = function(val, name) {
    extraArgs[name] = val;
    loadGrid();
};

let restartSimulationOnChargeChanges = function(val) {
    settings.charge = val;
    let forceCharge = constructForceCharge();
    applyForces({forceCharge});
    simulation.alpha(1).restart();
};

let restartSimulationOnDistanceChanges = function(val) {
    settings.distanceRangePercent = val;
    let {thickness, distance} = extractRanges();
    let forceLink = constructForceLink(thickness, distance);
    applyForces({forceLink});
    simulation.alpha(1).restart();
};

/**
 * Reload the grid if the slider configurations change
 */
const initSlider = function () {
    let gapSliderNames = ['mingap', 'maxgap'];
    let sliderNames = ['mingap', 'maxgap', 'charge', 'distance'];
    let sliders = {};

    let handlers = {
        'mingap': resetOnGapSlider,
        'maxgap': resetOnGapSlider,
        'charge': restartSimulationOnChargeChanges,
        'distance': restartSimulationOnDistanceChanges,
    };

    sliderNames.forEach(function (name) {
        let slider = $(`#${name}-slider`);
        slider.slider({
            scale: 'logarithmic',
        });
        slider.on('slide', function (slideEvt) {
            document.getElementById(`${name}-slider-value`).textContent = slideEvt.value;
        });

        slider.on('slideStop', function (slideEvt) {
            document.getElementById(`${name}-slider-value`).textContent = slideEvt.value;
            let callback = handlers[name];
            callback(slideEvt.value, name);
        });

        sliders[name] = slider;
    });

    $('#slider-enabled').click(function () {
        let self = this;
        gapSliderNames.forEach(function (name) {
            let slider = sliders[name];
            if (self.checked) {
                slider.slider('enable');
                extraArgs.usegap = true;
                extraArgs[name] = parseInt(slider.val());
            }
            else {
                slider.slider('disable');
                extraArgs.usegap = false;
                extraArgs[name] = undefined;
            }
        });
        loadGrid();
    });
};

/**
 * Triggered on click. If the cell is not editable and is of type text, integer, float, highlight the entire cell
 * for Ctrl + C
 *
 * @param e
 * @param args
 */
const selectTextForCopy = function (e, args) {
    let coldef = args.coldef;
    let editable = coldef.editable;
    let copyable = coldef.copyable;

    if (!editable && copyable) {
        let cellElement = $(args.e.target);
        cellElement.selectText();
    }
};

/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    debug('subscribeFlexibleEvents called from songs-pages');
    grid.on('click', function (...args) {
        let e = args[0];
        e.preventDefault();
        selectTextForCopy(...args);
    });
};

/**
 * Subscribe to events on the slick grid. This must be called everytime the slick is reconstructed, e.g. when changing
 * screen orientation or size
 */
const subscribeSlickEvents = function () {
    grid.subscribeDv('onRowCountChanged', function (e, args) {
        let currentRowCount = args.current;
        gridStatusNTotal.html(currentRowCount);


        // Update the graph when the table changes because of filtering
        let rows = [];
        let dataView = args.dataView;
        let nItems = dataView.getLength();
        if (nItems > 0) {
            for (let i = 0; i < nItems; i++) {
                rows.push(dataView.getItem(i));
            }
            fillInNodesInfo(grid.nodesDict, rows);
            graph = constructRealGraphContent({
                nodesDict: grid.nodesDict,
                withCentres: true,
                removeOrphans: true
            });
            constructGraph();
        }
    });
};

/**
 * Set the focus on the grid right after page is loaded.
 * This is mainly so that user can use Page Up and Page Down right away
 */
const focusOnGridOnInit = function () {
    $($('div[hidefocus]')[0]).focus();
};

let extraArgs = {
    granularity,
    viewas,
    usegap: false,
    maxgap: null,
    mingap: null,
};

/**
 * Query grid content, extract graph content, display graph, and resubscribe events
 */
const loadGrid = function () {
    grid.initMainGridContent({}, extraArgs);
};

export const run = function () {
    initAudioContext();

    grid.init(granularity);
    grid.initMainGridHeader({}, extraArgs, function () {
        loadGrid();
        subscribeSlickEvents();
        subscribeFlexibleEvents();
    });

    initSlider();
    initOptions();
};

/**
 * Bind event handlers to the buttons/checkboxes/sliders in the control panel
 */
function initOptions() {
    let $graph = $('#graph');

    $('#toggle-pseudo-nodes').click(function() {
        let pseudoThings = $graph.find('.pseudo');
        let enabled = this.checked;
        if (enabled) {
            pseudoThings.removeClass('hide');
        }
        else {
            pseudoThings.addClass('hide');
        }
    });

    $('#toggle-labels').click(function() {
        let texts = $graph.find('.node text');
        settings.showLabels = this.checked;
        if (settings.showLabels) {
            texts.removeClass('hide');
        }
        else {
            texts.addClass('hide');
        }
    });

    $('#toggle-centering').click(function () {
        settings.centering = this.checked;
        simulation.alpha(1).restart();
        applyForces({});
    });

    let toggleBtnAndSettings = {
        '#toggle-pseudo-end-reactive': 'reactivePseudoEnd',
        '#toggle-pseudo-start-reactive': 'reactivePseudoStart',
    };

    $.each(toggleBtnAndSettings, function(btn, key) {
        $(btn).click(function() {
            settings[key] = this.checked;

            let {thickness, distance} = extractRanges();
            let forceLink = constructForceLink(thickness, distance);
            applyForces({forceLink});
            simulation.alpha(1).restart();
        });
    });
}

const constructNodeDictionary = function(singletRows) {
    let nodesDict = {};
    let pseudoStartFound = false;
    let speudoEndFound = false;
    $.each(singletRows, function(idx, row) {
        let name = row.assocrule;
        let node = {
            id: idx,
            name,
            nOccurs: row.transcount,
            inLinkCount: 0,
            outLinkCount: 0,
            secondNodesInfo: {}
        };

        if (!pseudoStartFound) {
            if (name === pseudoStartName) {
                pseudoStartFound = true;
                node.isPseudoStart = true;
                node.nOccurs = 0;
            }
        }
        if (!speudoEndFound) {
            if (name === pseudoEndName) {
                speudoEndFound = true;
                node.isPseudoEnd = true;
                node.nOccurs = 0;
            }
        }

        nodesDict[name] = node;
    });
    return nodesDict;
};


const fillInNodesInfo = function(nodesDict, rows) {
    $.each(nodesDict, function (nodeName, node) {
        if (!node.isPseudoStart && !node.isPseudoEnd) {
            let pseudoEndNode = node.secondNodesInfo[pseudoEndName];
            node.secondNodesInfo = {};
            if (pseudoEndNode) {
                node.secondNodesInfo[pseudoEndName] = pseudoEndNode;
            }
            node.isOrphan = true;
        }
    });
    $.each(rows, function(idx, row) {
        if (row.chainlength == 2) {
            let ab = row.assocrule.split(' => ');
            let a = ab[0];
            let b = ab[1];
            let nodeA = nodesDict[a];
            let nodeB = nodesDict[b];

            let secondNodesInfo = nodeA.secondNodesInfo;

            // We want to keep the start node on the graph even if it isn't connected to any other node.
            // Thus, the start node can never be orphan
            if (nodeA.isPseudoStart) {
                nodeA.isOrphan = false;
            }
            else if (nodeB.isPseudoEnd) {
                nodeB.isOrphan = false;
            }
            else {
                nodeA.outLinkCount += row.transcount;
                nodeB.inLinkCount += row.transcount;
                nodeB.isOrphan = false;
                nodeA.isOrphan = false;
            }

            if (b in secondNodesInfo) {
                secondNodesInfo[b].transcount = row.transcount;
            }
            else {
                secondNodesInfo[b] = {
                    secondNode: nodeB,
                    lift: Math.max(0, row.lift),
                    transcount: row.transcount
                }
            }
        }
    });
};

const findRadialCentres = function(nodesDict) {
    // Designate a center of orbit for each node to make them locate around that point.
    // The CoO is the source points with highest lift.
    let centreDict = {};

    $.each(nodesDict, function(nodeName, node) {
        $.each(node.secondNodesInfo, function(secondNodeName, {lift}) {
            let centres;
            if (secondNodeName in centreDict) {
                centres = centreDict[secondNodeName];
            }
            else {
                centres = {
                    nodes: [],
                    lifts: []
                };
                centreDict[secondNodeName] = centres;
            }
            centres.nodes.push(node);
            centres.lifts.push(lift);
        });
    });

    $.each(centreDict, function(name, centres) {
        let maxLiftIndex = argmax(centres.lifts);
        if (maxLiftIndex >= 0) {
            centres.centre = centres.nodes[maxLiftIndex];
        }
        else {
            centres.centre = null;
        }
    });

    return centreDict;
};

/**
 * For all 2-syllable sequences in the grid, extract their two nodes, lift and occurrence count
 * Use these information to construct graph content, which is a dict(nodes=[], links=[])
 * @returns {{nodes: Array, links: Array}}
 * @param nodesDict
 * @param removeOrphans if true, nodes without links to other nodes or only has link to the pseudo start node will
 *                      be removed
 * @param withCentres if true, designate the parent node with highest lift to be the centre of orbit for each child node
 */
const constructRealGraphContent = function({nodesDict, removeOrphans = false, withCentres = true}) {
    let nodes = [];
    let links = [];

    $.each(nodesDict, function(nodeName, node) {
        let totalLinkCount = node.inLinkCount + node.outLinkCount;
        if (totalLinkCount > 0 || node.isPseudoStart || node.isPseudoEnd) {
            node.totalLinkCount = totalLinkCount;

            if (!(removeOrphans && node.isOrphan)) {
                nodes.push(node);
            }
        }
    });

    $.each(nodes, function(idx, firstNode) {
        $.each(firstNode.secondNodesInfo, function(secondNodeName, {secondNode, lift, transcount}) {
            if (!firstNode.isPseudoStart || (firstNode.isPseudoStart && secondNode.totalLinkCount)) {
                if (!(removeOrphans && secondNode.isOrphan)) {
                    links.push({
                        source: firstNode.id,
                        target: secondNode.id,
                        selfLink: firstNode == secondNode,
                        lift,
                        transcount
                    });
                }
            }
        });
    });

    if (withCentres) {
        let centres = findRadialCentres(nodesDict);

        if (withCentres) {
            $.each(nodes, function (idx, node) {
                let centreInfo = centres[node.name];
                if (centreInfo) {
                    node.centre = centres[node.name].centre;
                }
                else {
                    node.centre = null;
                }
            });
        }
    }

    return {
        nodes,
        links
    };
};

const extractRanges = function() {
    let width = $(svg._groups[0][0]).width();
    let height = $(svg._groups[0][0]).height();
    let wiggleRoom = Math.min(width, height) - margin * 2;

    let nodes = graph.nodes;
    // let links = graph.links;
    let maxLift = 0;
    let minLift = 999999;
    // let maxRadius = 40;
    // let minRadius = 20;
    let thicknessRangeUpper = 5;
    let thicknessRangeLower = 1;
    let maxInLinkCount = 0;
    let maxOutLinkCount = 0;
    let maxTotalLinkCount = 0;
    let maxOccurs = 0;
    let minOccurs = 999999;
    // let maxTransCount = 0;
    // let minTransCount = 9999999;

    // let minCharge = -10;
    // let maxCharge = -50;
    // let minStrength = -0.001;
    // let maxStrength = 1;

    let nNodes = nodes.length;
    let averageDistance = wiggleRoom / Math.sqrt(nNodes);
    let distanceRangeUpper = settings.distanceRangePercent * Math.min(averageDistance, 250) / 100;
    let distanceRangeLower = distanceRangeUpper / 5;

    $.each(nodes, function(idx, node) {
        maxInLinkCount = Math.max(maxInLinkCount, node.inLinkCount);
        maxOutLinkCount = Math.max(maxOutLinkCount, node.outLinkCount);
        maxTotalLinkCount = Math.max(maxTotalLinkCount, node.totalLinkCount);

        maxOccurs = Math.max(maxOccurs, node.nOccurs);
        minOccurs = Math.min(minOccurs, node.nOccurs);

        $.each(node.secondNodesInfo, function (secondNodeName, {lift}) {
            maxLift = Math.max(maxLift, lift);
            minLift = Math.min(minLift, lift);
        });
    });

    // $.each(links, function (idx, link) {
    //     maxTransCount = Math.max(maxTransCount, link.transcount);
    //     minTransCount = Math.min(minTransCount, link.transcount);
    // });

    let thickness = d3.scaleLinear().domain([minLift, maxLift]).range([thicknessRangeLower, thicknessRangeUpper]);
    let distance = d3.scaleLinear().domain([maxLift, minLift]).range([distanceRangeLower, distanceRangeUpper]);
    // let charge = d3.scaleLinear().domain([minOccurs, maxOccurs]).range([minCharge, maxCharge]);
    // let radius = d3.scaleLinear().domain([minOccurs, maxOccurs]).range([minRadius, maxRadius]);
    let nodeColour = d3.scaleSequential(d3.interpolateYlOrRd).domain([minOccurs, maxOccurs]);
    let linkColour = d3.scaleSequential(d3.interpolateGreys).domain([-maxLift, maxLift]);
    // let linkStrength = d3.scaleLinear().domain([minTransCount, maxTransCount]).range([minStrength, maxStrength]);

    return {thickness,
        distance,
        // radius,
        nodeColour,
        linkColour,
        // linkStrength
    }
};

const constructForceLink = function(thickness, distance) {
    let forceLink = d3.forceLink();
    let defaultLinkStrength = forceLink.strength();
    forceLink.id(function (node) {
        return node.id;
    });
    forceLink.strength(function (link) {
        if (settings.reactivePseudoStart && link.source.isPseudoStart) {
            return defaultLinkStrength(link);
        }

        if (settings.reactivePseudoEnd && link.target.isPseudoEnd) {
            return defaultLinkStrength(link);
        }

        if (link.source.isPseudoStart || link.target.isPseudoEnd) {
            return null;
        }

        return defaultLinkStrength(link);
    });

    forceLink.distance(function (link) {
        if (settings.reactivePseudoStart && link.source.isPseudoStart) {
            return distance(link.lift);
        }

        if (settings.reactivePseudoEnd && link.target.isPseudoEnd) {
            return distance(link.lift);
        }

        if (link.source.isPseudoStart || link.target.isPseudoEnd) {
            return null;
        }

        return distance(link.lift);
    });
    forceLink.links(graph.links);
    return forceLink;
};

const applyForces = function({forceCharge, forceLink, forceColide, tickAction}) {
    if (forceCharge) {
        simulation.force('charge', forceCharge);
    }
    if (forceLink) {
        simulation.force('link', forceLink);
    }
    if (forceColide) {
        simulation.force('collide', forceColide);
    }

    let forceCenter = null;
    if (settings.centering) {
        let width = $(svg._groups[0][0]).width();
        let height = $(svg._groups[0][0]).height();
        forceCenter = d3.forceCenter((width - margin) / 2, (height - margin) / 2);
    }
    simulation.force('center', forceCenter);

    if (tickAction) {
        simulation.on('tick', tickAction);
    }
};


/**
 * This function is called every tick event to redraw the arrow lines for a given link
 * @param link
 * @returns {string}
 */
function connect(link) {
    let x1 = Math.round(link.source.x);
    let y1 = Math.round(link.source.y);
    let startX = Math.round(x1 - offset);
    let startY = Math.round(y1 - offset);

    if (link.selfLink) {


        let sweep = 1;

        // Needs to be 1.
        let largeArc = 1;

        // Change sweep to change orientation of loop.
        // sweep = 0;

        // Make drx and dry different to get an ellipse
        // instead of a circle.
        let drx = 15;
        let dry = 10;

        // For whatever reason the arc collapses to a point if the beginning
        // and ending points of the arc are the same, so kludge it.
        // return 'M' + x1 + ',' + y1 + 'A' + drx + ',' + dry + ' ' + xRotation + ',' + largeArc + ',' + sweep + ' ' + x2 + ',' + y2;
        return `M${startX},${startY}A${drx},${dry} ${xRotation},${largeArc},${sweep} ${startX + 1},${startY - 1}`
    }
    else {
        let x2 = Math.round(link.target.x);
        let y2 = Math.round(link.target.y);
        return `M${x1},${y1}L${x2},${y2}`
    }
}


/**
 * This is called once to create the path elements for all the links, including the arrow head style
 * The actual arrow bodies are drawn using connect()
 * @param thickness
 * @param linkColour
 */
function drawLinks(thickness, linkColour) {
    svg.append('svg:defs').selectAll('.x').data(graph.links).enter().
        append('svg:marker').
        attr('id', function (link) {
            return `marker-${link.source.id}-${link.target.id}`;
        }).
        attr('viewBox', '0 0 10 10').
        attr('refX', 21).
        attr('refY', 5).
        attr('markerWidth', 8).
        attr('markerHeight', 8).
        attr('orient', 'auto').
        attr('markerUnits', 'userSpaceOnUse').
        append('svg:polyline').
        attr('points', '0,0 10,5 0,10 1,5').
        style('fill', function(link) {
            return linkColour(link.lift);
        }).
        style('opacity', 1);

    let links = svg.selectAll('.link').data(graph.links).enter().append('path').
        attr('class', function(link) {
            if (link.source.isPseudoStart || link.target.isPseudoEnd) {
                return 'link pseudo';
            }
            return 'link'
        }).
        attr('marker-end', function (link) {
            if (!link.selfLink && !link.source.isPseudoStart && !link.target.isPseudoEnd) {
                return `url(#marker-${link.source.id}-${link.target.id})`;
            }
            return null;
        }).
        attr('stroke-width', function (link) {
            return thickness(link.lift);
        }).
        attr('stroke', function (link) {
            if (link.source.isPseudoStart || link.target.isPseudoEnd) {
                return undefined;
            }
            return linkColour(link.lift);
        });
    return links;
}

/**
 * Draw nodes, both normal and pseudo
 * @param nodeColour
 * @returns {{normalNodes, pseudoNodes}}
 */
function drawNodes(nodeColour) {
    let circles = svg.append('g').
        attr('class', 'nodes').
        selectAll('circle').
        data(graph.nodes).enter();

    let normalNodes = circles.
        filter(function(node) {
            return !node.isPseudoStart && !node.isPseudoEnd;
        }).
        append('g').attr('class', 'node');

    let pseudoNodes = circles.
        filter(function(node) {
            return node.isPseudoStart || node.isPseudoEnd;
        }).
        append('g').attr('class', 'node');

    normalNodes.append('circle').
        attr('r', circleRadius).
        attr('fill', function (node) {
            return nodeColour(node.nOccurs);
        }).
        attr('border', 'black');

    normalNodes.
        append('text').
        text(function(node) {
            return node.name;
        }).
        style('font-size', '12px').attr('dy', '.35em').attr('dx', '1em');

    pseudoNodes.append('circle').attr('r', 0);

    pseudoNodes.
        append('text').attr('class', 'pseudo').
        text(function(node) {
            if (node.isPseudoStart) {
                return 'START';
            }
            return 'END';
        });
    return {normalNodes, pseudoNodes};
}

/**
 * Create a force field. The pseudo nodes have no force
 */
function constructForceCharge() {
    return d3.forceManyBody().strength(function (node) {
        if (node.isPseudoStart || node.isPseudoEnd) {
            return null;
        }
        return -settings.charge;
    });
}

const constructGraph = function () {
    svg.selectAll('*').remove();
    let width = $(svg._groups[0][0]).width();
    let height = $(svg._groups[0][0]).height();

    $.each(graph.nodes, function(idx, node) {
        if (node.isPseudoStart) {
            node.fy = margin;
            node.fx = margin;
        }
        else if (node.isPseudoEnd) {
            node.fy = height - margin;
            node.fx = width - margin;
        }
    });

    let {thickness, distance, nodeColour, linkColour} = extractRanges();
    let forceLink = constructForceLink(thickness, distance);
    let forceColide = d3.forceCollide(circleRadius);
    let forceCharge = constructForceCharge();

    simulation = d3.forceSimulation();
    simulation.velocityDecay(0.1);
    simulation.nodes(graph.nodes);

    applyForces({forceCharge, forceLink, forceColide, tickAction});
    let links = drawLinks(thickness, linkColour);
    let {normalNodes, pseudoNodes} = drawNodes(nodeColour);

    /**
     * This function is invoked for each node and link
     * This is where we draw the arc arrow
     */
    function tickAction() {
        links.attr('d', connect);

        normalNodes.
            attr('transform', function(node) {
                let x = Math.max(circleRadius + margin, Math.min(width - circleRadius - margin, node.x));
                let y = Math.max(circleRadius + margin, Math.min(height - circleRadius - margin, node.y));
                node.x = x;
                node.y = y;

                return 'translate(' + x + ',' + y + ')';
            }).
            call(d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended));

        normalNodes.
            on('mouseover', function() {
                if (!settings.showLabels) {
                    $(this).find('text').removeClass('hide');
                }
            }).
            on('mouseleave', function() {
                if (!settings.showLabels) {
                    $(this).find('text').addClass('hide');
                }
            });

        pseudoNodes.attr('transform', function(node) {
            let offsetRight = 0;
            if (node.isPseudoEnd) {
                offsetRight = 50;
            }
            let x = Math.max(0, Math.min(width - offsetRight, node.x));
            let y = Math.max(0, Math.min(height, node.y));
            return 'translate(' + x + ',' + y + ')';
        });
    }

    /**
     * Fix (fx, fy) location of a node when starts being dragged to prevent it from wiggling
     * @param node
     */
    function dragstarted(node) {
        if (!d3.event.active) simulation.alphaTarget(0.3).restart();
        node.fx = node.x;
        node.fy = node.y;
    }

    /**
     * Update fixed coordinate as being dragged
     * @param node
     */
    function dragged(node) {
        let x = Math.max(circleRadius + margin, Math.min(width - circleRadius - margin, d3.event.x));
        let y = Math.max(circleRadius + margin, Math.min(height - circleRadius - margin, d3.event.y));

        node.fx = x;
        node.fy = y;
    }

    /**
     * Once the drag finishes, unset fixed coordinate to allow it move by gravity again
     * @param node
     */
    function dragended(node) {
        if (!d3.event.active) simulation.alphaTarget(0);
        node.fx = null;
        node.fy = null;
    }

};

export const viewPortChangeHandler = function () {
    grid.mainGrid.resizeCanvas();
};
