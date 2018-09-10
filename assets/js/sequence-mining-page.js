import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {initAudioContext} from './audio-handler';
import {debug, deepCopy, updateSlickGridData, argmax} from './utils';
import d3 from './d3-importer';
import {postRequest} from './ajax-handler';
require('bootstrap-slider/dist/bootstrap-slider.js');

const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 25;

class Grid extends FlexibleGrid {
    init(cls) {

        super.init({
            'grid-name': 'sequences',
            'grid-type': 'sequence-mining-grid',
            'default-field': 'assocrule',
            gridOptions
        });

        this.cls = cls;
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
            fillInSecondNodesInfo(self.nodesDict, pseudoRows);

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
let cls = $('#sequence-mining-grid').attr('cls');
let fromUser = $('#sequence-mining-grid').attr('from_user');
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
        else if (sequence.startsWith('__PSEUDO_BEGIN__')) {
            pseudoRows.push(row);
        }
        else {
            realRows.push(row)
        }
    });

    return {singletRows,
        realRows,
        pseudoRows};
};

/**
 * Reload the grid if the slider configurations change
 */
const initSlider = function () {
    let names = ['mingap', 'maxgap'];
    let sliders = {};
    names.forEach(function (name) {
        let slider = $(`#${name}-slider`);
        slider.slider({
            scale: 'logarithmic',
        });
        slider.on('slide', function (slideEvt) {
            document.getElementById(`${name}-slider-value`).textContent = slideEvt.value;
        });

        slider.on('slideStop', function (slideEvt) {
            document.getElementById(`${name}-slider-value`).textContent = slideEvt.value;
            extraArgs[name] = slideEvt.value;
            loadGrid();
        });
        sliders[name] = slider;
    });

    $('#slider-enabled').click(function () {

        for (let name in sliders) {
            if (Object.prototype.hasOwnProperty.call(sliders, name)) {
                let slider = sliders[name];
                if (this.checked) {
                    slider.slider('enable');
                    extraArgs.usegap = true;
                    extraArgs[name] = parseInt(slider.val());
                }
                else {
                    slider.slider('disable');
                    extraArgs.usegap = false;
                    extraArgs[name] = undefined;
                }
            }
        }
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
            fillInSecondNodesInfo(grid.nodesDict, rows);
            let graph = constructRealGraphContent({
                nodesDict: grid.nodesDict,
                withCentres: true,
                removeOrphans: true
            });
            displayGraph(graph);
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
    cls,
    'from_user': fromUser,
    'usegap': false,
    'maxgap': null,
    'mingap': null,
};

/**
 * Query grid content, extract graph content, display graph, and resubscribe events
 */
const loadGrid = function () {
    grid.initMainGridContent({}, extraArgs);
};

export const run = function () {
    initAudioContext();

    grid.init(cls);
    grid.initMainGridHeader({}, extraArgs, function () {
        loadGrid();
        subscribeSlickEvents();
        subscribeFlexibleEvents();
    });

    initSlider();
};

const constructNodeDictionary = function(singletRows) {
    let nodesDict = {};
    let pseudoStartFound = false;
    $.each(singletRows, function(idx, row) {
        let name = row.assocrule;
        let node = {
            id: idx,
            name,
            nOccurs: row.transcount,
            inLinkCount: 0,
            outLinkCount: 0,
        };

        if (!pseudoStartFound) {
            if (name === '__PSEUDO_BEGIN__') {
                pseudoStartFound = true;
                node.isPseudoStart = true;
                node.nOccurs = 0;
                node.secondNodesInfo = {}
            }
        }

        nodesDict[name] = node;
    });
    return nodesDict;
};

const fillInSecondNodesInfo = function(nodesDict, rows) {
    $.each(nodesDict, function (firstNodeName, firstNode) {
        if (!firstNode.isPseudoStart) {
            firstNode.secondNodesInfo = {};
            firstNode.isOrphan = true;
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
            if (nodeA.isPseudoStart) {
                nodeA.isOrphan = false;
            }
            else {
                nodeA.outLinkCount += row.transcount;
                nodeB.inLinkCount += row.transcount;
                nodeB.isOrphan = false;
                nodeA.isOrphan = false;
            }
            if (b in secondNodesInfo) {
                secondNodesInfo[b].lift = Math.max(secondNodesInfo[b].lift, row.lift);
            }
            else {
                secondNodesInfo[b] = {
                    secondNode: nodeB,
                    lift: row.lift
                }
            }
        }
    });
};

const findRadialCentres = function(nodesDict) {
    // Designate a center of orbit for each node to make them locate around that point.
    // The CoO is the source points with highest lift.
    let centreDict = {};

    $.each(nodesDict, function(firstNodeName, firstNode) {
        $.each(firstNode.secondNodesInfo, function(secondNodeName, {lift}) {
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
            centres.nodes.push(firstNode);
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

    $.each(nodesDict, function(firstNodeName, firstNode) {
        let totalLinkCount = firstNode.inLinkCount + firstNode.outLinkCount;
        if (totalLinkCount > 0 || firstNode.isPseudoStart) {
            firstNode.totalLinkCount = totalLinkCount;

            if (!(removeOrphans && firstNode.isOrphan)) {
                nodes.push(firstNode);
            }
        }
    });

    $.each(nodes, function(idx, firstNode) {
        $.each(firstNode.secondNodesInfo, function(secondNodeName, {secondNode, lift}) {
            if (!firstNode.isPseudoStart || (firstNode.isPseudoStart && secondNode.totalLinkCount)) {
                if (!(removeOrphans && secondNode.isOrphan)) {
                    links.push({
                        source: firstNode.id,
                        target: secondNode.id,
                        selfLink: firstNode == secondNode,
                        lift,
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

export const handleDatabaseChange = function () {
    location.reload();
};

const extractRanges = function(nodes) {
    let maxLift = 0;
    let minLift = 999999;
    let maxRadius = 40;
    let minRadius = 20;
    let maxLinkThickness = 5;
    let minLinkThickness = 1;
    let maxInLinkCount = 0;
    let maxOutLinkCount = 0;
    let maxTotalLinkCount = 0;
    let maxOccurs = 0;
    let minOccurs = 999999;
    let minDistance = 70;
    let maxDistance = 500;
    let minCharge = -10;
    let maxCharge = -50;

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

    let thickness = d3.scaleLinear().domain([minLift, maxLift]).range([minLinkThickness, maxLinkThickness]);
    let distance = d3.scaleLinear().domain([minOccurs, maxOccurs]).range([maxDistance, minDistance]);
    let charge = d3.scaleLinear().domain([minOccurs, maxOccurs]).range([minCharge, maxCharge]);
    let radius = d3.scaleLinear().domain([minOccurs, maxOccurs]).range([minRadius, maxRadius]);
    // let colourIntensity = d3.scaleLinear().domain([0, maxTotalLinkCount]).range([0, 1]);
    let nodeColour = d3.scaleSequential(d3.interpolateViridis).domain([maxTotalLinkCount * 2, 0]);
    let linkColour = d3.scaleSequential(d3.interpolatePlasma).domain([Math.log10(maxLift), 0]);

    return {thickness,
        distance,
        charge,
        radius,
        nodeColour,
        linkColour}
};

const displayGraph = function (graph) {
    let svg = d3.select('#graph svg');
    svg.selectAll('*').remove();
    let width = $(svg._groups[0][0]).width();
    let height = $(svg._groups[0][0]).height();
    let margin = 20;

    let {thickness, distance, radius, nodeColour, linkColour} = extractRanges(graph.nodes);

    $.each(graph.nodes, function(idx, node) {
        if (node.isPseudoStart) {
            node.fy = height / 2;
            node.fx = width / 2;
        }
    });

    let radial = d3.forceRadial();
    radial.radius(function(node) {
        if (node.isPseudoStart) {
            return null;
        }
        return distance(node.nOccurs);
    });
    radial.x(function(node) {
        if (node.isPseudoStart) {
            return null;
        }
        return node.centre ? node.centre.x : (width / 2)
    });
    radial.y(function(node) {
        if (node.isPseudoStart) {
            return null;
        }
        return node.centre ? node.centre.y : (height / 2)
    });

    let simulation = d3.forceSimulation();
    simulation.nodes(graph.nodes);
    simulation.
        force('link', d3.forceLink().
            id(function (node) {
                return node.id;
            })).
        // distance(function (node) {
        //     if (node.isPseudoStart) {
        //         return Math.min(width, height) / 4;
        //     }
        //     return 100;
        // })).
        force('collide', d3.forceCollide(function (node) {
            return radius(node.nOccurs) * 2;
        })).
        // force('charge', d3.forceManyBody().strength(function (node) {
        //     if (node.isPseudoStart) {
        //         return -500;
        //     }
        //     return charge(node.nOccurs);
        // })).
        force('center', d3.forceCenter(width / 2, height / 2));

    simulation.on('tick', tickAction);

    simulation.force('link').
        links(graph.links);
    svg.append('svg:defs').selectAll('.x').data(graph.links).enter().
        append('svg:marker').
        attr('id', function (link) {
            return `marker-${link.source.id}-${link.target.id}`;
        }).
        attr('viewBox', '0 0 10 10').

        attr('refX', function (link) {
            return radius(link.target.nOccurs) + 15;
        }).
        attr('refY', 5).
        attr('markerWidth', 8).
        attr('markerHeight', 8).
        attr('orient', 'auto').
        attr('markerUnits', 'userSpaceOnUse').
        append('svg:polyline').
        attr('points', '0,0 10,5 0,10 1,5').
        style('fill', function(link) {
            return linkColour(Math.log10(link.lift));
        }).
        style('opacity', 1);

    let links = svg.selectAll('.link').data(graph.links).enter().append('path').
        attr('class', 'link').
        attr('marker-end', function (link) {
            if (!link.selfLink && !link.source.isPseudoStart) {
                return `url(#marker-${link.source.id}-${link.target.id})`;
            }
            return null;
        }).
        attr('stroke-width', function (link) {
            return thickness(link.lift);
        }).
        attr('stroke', function (link) {
            if (link.source.isPseudoStart) {
                return '#eee';
            }
            return linkColour(Math.log10(link.lift));
        });

    simulation.force('radial', radial);

    let enterSelection = svg.append('g').
        attr('class', 'nodes').
        selectAll('circle').
        data(graph.nodes).enter().filter(function(node) {
            return !node.isPseudoStart;
        }).
        append('g');

    enterSelection.append('circle').
        attr('r', function(node) {
            return radius(node.nOccurs)
        }).
        attr('fill', function (node) {
            return nodeColour(node.totalLinkCount);
        });

    enterSelection.
        append('text').
        text(function(node) {
            return node.name;
        }).
        style('font-size', '12px').
        attr('dy', '.35em');

    let xRotation = 45;
    let theta = 90 - (180 - Math.abs(xRotation)) / 2;
    let sinTheta = Math.abs(Math.sin(theta));

    /**
     * This function is invoked for each node and link
     * This is where we draw the arc arrow
     */
    function tickAction() {

        links.attr('d', function(link) {
            let x1 = Math.round(link.source.x);
            let y1 = Math.round(link.source.y);
            let r = radius(link.source.nOccurs);
            let offset = sinTheta * (r);
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
                let drx = 10;
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
        });

        enterSelection.
            filter(function (node) {
                return !node.isPseudoStart;
            }).
            attr('transform', function(node) {
                let r = radius(node.nOccurs);
                let x = Math.max(r + margin, Math.min(width - r - margin, node.x));
                let y = Math.max(r + margin, Math.min(height - r - margin, node.y));
                node.x = x;
                node.y = y;

                if (isNaN(x) || isNaN(y)) {
                    throw Error('Here');
                }

                return 'translate(' + x + ',' + y + ')';
            });
        enterSelection.filter(function (node) {
            return !node.isPseudoStart;
        }).
            call(d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended));
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
        let r = radius(node.nOccurs);
        let x = Math.max(r + margin, Math.min(width - r - margin, d3.event.x));
        let y = Math.max(r + margin, Math.min(height - r - margin, d3.event.y));

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
