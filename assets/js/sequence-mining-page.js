import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {initAudioContext} from './audio-handler';
import {debug, deepCopy} from './utils';
import d3 from './d3-importer';
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
}

export const grid = new Grid();
let cls = $('#sequence-mining-grid').attr('cls');
let fromUser = $('#sequence-mining-grid').attr('from_user');
const gridStatus = $('#grid-status');
const gridStatusNTotal = gridStatus.find('#ntotal');

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
    grid.initMainGridContent({}, extraArgs, function() {
        focusOnGridOnInit();
        let graph = constructGraphContent(grid.mainGrid);
        displayGraph(graph);
    });
    subscribeSlickEvents();
    subscribeFlexibleEvents();
};

export const run = function () {
    initAudioContext();

    grid.init(cls);
    grid.initMainGridHeader({}, extraArgs, function () {
        loadGrid();
    });

    initSlider();
};

/**
 * For all 2-syllable sequences in the grid, extract their two nodes, lift and occurrence count
 * Use these information to construct graph content, which is a dict(nodes=[], links=[])
 * @param slickGrid
 * @returns {{nodes: Array, links: Array}}
 */
const constructGraphContent = function(slickGrid) {
    let items = slickGrid.getData().getItems();
    let nodesInfo = {};

    for (let i = 0; i < items.length; i++) {
        let item = items[i];
        if (item.chainlength == 2) {
            let ab = item.assocrule.split(' => ');
            let a = ab[0];
            let b = ab[1];
            let nodeInfo;
            let secondNodesInfo;

            if (!Object.prototype.hasOwnProperty.call(nodesInfo, b)) {
                nodesInfo[b] = {nOccurs: 0,
                    inLinkCount: 0,
                    outLinkCount: 0,
                    secondNodesInfo: []};
            }

            if (Object.prototype.hasOwnProperty.call(nodesInfo, a)) {
                nodeInfo = nodesInfo[a];
                secondNodesInfo = nodeInfo.secondNodesInfo;
            }
            else {
                secondNodesInfo = [];
                nodeInfo = {nOccurs: 0,
                    inLinkCount: 0,
                    outLinkCount: 0,
                    secondNodesInfo};
                nodesInfo[a] = nodeInfo;
            }

            nodeInfo.nOccurs += item.transcount;
            nodeInfo.outLinkCount++;
            nodesInfo[b].inLinkCount++;

            secondNodesInfo.push({
                'secondNode': b,
                'lift': item.lift
            });
        }
    }

    let maxnOccurs = 0;
    let maxLift = 0;
    let maxSize = 20;
    let minSize = 10;
    let maxValue = 10;
    let minValue = 1;
    let maxInLinkCount = 0;
    let maxOutLinkCount = 0;
    let maxTotalLinkCount = 0;

    for (let node in nodesInfo) {
        if (Object.prototype.hasOwnProperty.call(nodesInfo, node)) {
            let nodeInfo = nodesInfo[node];

            let inLinkCount = nodeInfo.inLinkCount;
            let outLinkCount = nodeInfo.outLinkCount;
            let totalLinkCount = inLinkCount + outLinkCount;

            maxLift = Math.max(maxLift, Math.max(...nodeInfo.secondNodesInfo.map(function(o) {
                return o.lift;
            })));
            maxnOccurs = Math.max(maxnOccurs, nodeInfo.nOccurs);

            maxInLinkCount = Math.max(maxInLinkCount, inLinkCount);
            maxOutLinkCount = Math.max(maxOutLinkCount, outLinkCount);
            maxTotalLinkCount = Math.max(maxTotalLinkCount, totalLinkCount);
            nodeInfo.totalLinkCount = totalLinkCount;
        }
    }

    let nodes = [];
    let links = [];

    for (let node in nodesInfo) {
        if (Object.prototype.hasOwnProperty.call(nodesInfo, node)) {
            let nodeInfo = nodesInfo[node];
            let size = Math.round(minSize + (nodeInfo.nOccurs / maxnOccurs) * (maxSize - minSize));
            let inLinkCount = nodeInfo.inLinkCount;
            let outLinkCount = nodeInfo.outLinkCount;
            let totalLinkCount = inLinkCount + outLinkCount;
            let colourIntensity = nodeInfo.totalLinkCount / maxTotalLinkCount;

            nodes.push({
                id: node,
                name: node,
                size,
                inLinkCount,
                outLinkCount,
                totalLinkCount,
                colourIntensity
            });
            let secondNodesInfo = nodeInfo.secondNodesInfo;
            for (let i = 0; i < secondNodesInfo.length; i++) {
                let secondNodeInfo = secondNodesInfo[i];
                let lift = Math.round(minValue + (secondNodeInfo.lift / maxLift) * (maxValue - minValue));
                links.push({
                    'source': node,
                    'target': secondNodeInfo.secondNode,
                    'value': lift
                });
            }
        }
    }
    return {nodes,
        links};
};

export const handleDatabaseChange = function () {
    location.reload();
};

const displayGraph = function (data) {
    let svg = d3.select('#graph svg');
    svg.selectAll('*').remove();
    let width = $(svg._groups[0][0]).width();
    let height = $(svg._groups[0][0]).height();

    let color = d3.scaleSequential(d3.interpolateReds);

    svg.append('svg:defs').append('svg:marker').
        attr('id', 'arrowhead').
        attr('viewBox', '-0 -5 10 10').
        attr('refX', 16).
        attr('refY', -1).
        attr('orient', 'auto').
        attr('markerWidth', 6).
        attr('markerHeight', 6).
        attr('xoverflow', 'visible').
        append('svg:path').
        attr('d', 'M0,-5L10,0L0,5').
        attr('fill', '#999').
        style('stroke', 'none');

    let simulation = d3.forceSimulation().
        force('link', d3.forceLink().id(function (d) {
            return d.id;
        }).distance(100)).
        force('charge', d3.forceManyBody().strength(-30)).
        force('center', d3.forceCenter(width / 2, height / 2));

    let link = svg.selectAll('.link').data(data.links).enter().append('path').attr('class', 'link').attr('marker-end', 'url(#arrowhead)').
        attr('stroke-width', function (d) {
            return Math.sqrt(d.value);
        });

    let enterSelection = svg.append('g').
        attr('class', 'nodes').
        selectAll('circle').
        data(data.nodes).
        enter().append('g');

    enterSelection.append('circle').
        attr('r', function(d) {
            return d.size + 'px';
        }).
        attr('fill', function (d) {
            return color(d.colourIntensity);
        });

    enterSelection.
        append('text').
        text(function(d) {
            return d.name;
        }).
        style('font-size', '12px').
        attr('dy', '.35em');

    simulation.
        nodes(data.nodes).
        on('tick', tickAction);

    simulation.force('link').
        links(data.links);

    /**
     * This function is invoked for each node and link
     * This is where we draw the arc arrow
     */
    function tickAction() {
        link.attr('d', function(d) {
            let x1 = d.source.x,
                y1 = d.source.y,
                x2 = d.target.x,
                y2 = d.target.y,
                dx = x2 - x1,
                dy = y2 - y1,
                dr = Math.sqrt(dx * dx + dy * dy),

                // Defaults for normal edge.
                drx = dr,
                dry = dr,
                // degrees
                xRotation = 0,
                // 1 or 0
                largeArc = 0,
                // 1 or 0
                sweep = 1;

            // Self edge.
            if (x1 === x2 && y1 === y2) {
            // Fiddle with this angle to get loop oriented.
                xRotation = -45;

                // Needs to be 1.
                largeArc = 1;

                // Change sweep to change orientation of loop.
                // sweep = 0;

                // Make drx and dry different to get an ellipse
                // instead of a circle.
                drx = 30;
                dry = 20;

                // For whatever reason the arc collapses to a point if the beginning
                // and ending points of the arc are the same, so kludge it.
                x2 += 1;
                y2 += 1;
            }
            return 'M' + x1 + ',' + y1 + 'A' + drx + ',' + dry + ' ' + xRotation + ',' + largeArc + ',' + sweep + ' ' + x2 + ',' + y2;
        });

        enterSelection.attr('transform', function(d) {
            let x = Math.max(d.size, Math.min(width - d.size, d.x));
            let y = Math.max(d.size, Math.min(height - d.size, d.y));
            d.x = x;
            d.y = y;
            return 'translate(' + x + ',' + y + ')';
        });
        enterSelection.call(d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended));
    }

    /**
     * Fix (fx, fy) location of a node when starts being dragged to prevent it from wiggling
     * @param d
     */
    function dragstarted(d) {
        if (!d3.event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    /**
     * Update fixed coordinate as being dragged
     * @param d
     */
    function dragged(d) {
        d.fx = d3.event.x;
        d.fy = d3.event.y;
    }

    /**
     * Once the drag finishes, unset fixed coordinate to allow it move by gravity again
     * @param d
     */
    function dragended(d) {
        if (!d3.event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
};
