/* global Plotly */
require('bootstrap-slider/dist/bootstrap-slider.js');
require('jquery.scrollintoview/jquery.scrollintoview.js');
const nj = require('numjs');
const ResizeSensor = require('css-element-queries/src/ResizeSensor');

import {queryAndPlayAudio, changePlaybackSpeed} from './audio-handler';
import {updateSlickGridData} from './grid-utils';
import {FlexibleGrid, defaultGridOptions} from './flexible-grid';
import {getUrl, getCache, setCache, isEmpty, logError, debug, deepCopy, pdist, argsort, isNumber, isNull, normalise,
    PAGE_CAPACITY
} from './utils';
import {downloadRequest, postRequest, createSpinner} from './ajax-handler';
import {constructSelectizeOptionsForLabellings, initSelectize} from './selectize-formatter';

const speedSlider = $('#speed-slider');
const plotId = 'plotly-plot';
const plotDiv = $(`#${plotId}`);
const metaPath = plotDiv.attr('metadata');
const bytesPath = plotDiv.attr('bytes');
const databaseId = plotDiv.attr('database');
const tmpDbId = plotDiv.attr('tmpdb');
const sylSpects = $('#class1n2-syl-spects');
const class1SylSpects = $('#class-1-syl-spects');
const class1SylSpectsName = class1SylSpects.find('.subTitle');
const class1SylSpectsDisplay = class1SylSpects.find('.display');

const class2SylSpects = $('#class-2-syl-spects');
const class2SylSpectsName = class2SylSpects.find('.subTitle');
const class2SylSpectsDisplay = class2SylSpects.find('.display');

const classType = 'label';

let rightContainer = plotDiv.parents('.contain-panel');
let rightPanel = plotDiv.parents('.panel');
let leftContainer = sylSpects.parents('.contain-panel');
let leftPanel = sylSpects.parents('.panel');

let minLeftWidth = leftContainer.innerWidth();
let layoutParams = {};

let ce;
let highlighted = {};
let highlightedInfo = {};
const dataMatrix = [];
const rowsMetadata = [];
const labelDatum = {};
let plotObj;
let spinner;

const syntaxData = {};
const rowIdxNewClass = {};
let class1Name, class2Name;

const plotlyOptions = {
    modeBarButtonsToRemove: [
        'toImage', 'pan2d', 'select2d', 'zoomIn2d', 'zoomOut2d', 'resetScale2d', 'hoverClosestCartesian',
        'hoverCompareCartesian', 'zoom3d', 'pan3d', 'orbitRotation',
        'tableRotation', 'resetCameraDefault3d', 'resetCameraLastSave3d', 'hoverClosest3d', 'zoomInGeo',
        'zoomOutGeo', 'resetGeo', 'hoverClosestGeo', 'hoverClosestGl2d', 'hoverClosestPie', 'toggleHover',
        'resetViews', 'toggleSpikelines', 'resetViewMapbox', 'lasso2d', 'zoom2d', 'zoom3d'
    ],
    modeBarButtonsToAdd: [],
};

const unhighlightedMarker = {
    symbol: 'circle',
    size: 5,
    color: 'black',
    opacity: 0.1,
};

const class1Marker = {
    symbol: 'circle',
    size: 20,
    color: 'red',
    opacity: 0.8,
    line: {
        width: 0.5
    },
};

const class2Marker = {
    symbol: 'circle',
    size: 20,
    color: 'blue',
    opacity: 0.8,
    line: {
        width: 0.5
    },
};

const gridOptions = deepCopy(defaultGridOptions);

const initSlider = function () {
    speedSlider.slider();

    speedSlider.on('slide', function (slideEvt) {
        changePlaybackSpeed(slideEvt.value);
    });

    $('.slider').on('click', function () {
        let newvalue = $('.tooltip-inner').text();
        changePlaybackSpeed(parseInt(newvalue));
    });
};

/**
 * Decide the render class: WebGL/SVG for 2D, Scatter3d for 3D
 * @returns {*}
 */
function getRenderOptions() {
    let ndims = dataMatrix[0].length;
    let renderClass;
    let renderOptions = plotlyOptions;

    if (ndims === 2) {
        renderClass = 'scattergl';
    }
    else {
        renderClass = 'scatter3d';
    }

    return {renderClass, renderOptions};
}

/**
 * Attach click event handlers to the three buttons and the panel-body in highlighted panel
 */
function initClickHandlers() {
    $('#merge-btn').click(handleMergeBtn);
    $('#save-btn').click(handleSaveBtn);

    sylSpects.click(function (e) {
        let target = $(e.target);
        let isSpectrogram;
        if (target.hasClass('syl-spect')) {
            isSpectrogram = target;
        }
        else {
            isSpectrogram = target.parents('.syl-spect');
        }
        if (isSpectrogram.length) {
            let spectrogram = isSpectrogram[0];
            let sylId = spectrogram.getAttribute('id');
            highlightSyl(highlighted[sylId]);
            playSyl(sylId);
        }
    });
}

/**
 * Adjust the plot's div such that the plot is always a square & the height is always 100%
 * @returns {{l: number, r: number, b: number, t: number}}
 */
function calcLayout1() {
    let windowWidth = $('.main-content').width();
    let plotHeight = plotDiv.height();
    let lW = leftPanel.innerWidth();

    let r = 0;
    let b = 0;
    let t = 0;
    let l = 0;

    let h = plotHeight - t - b;
    let plotWidth = h + r + l;

    let offset = windowWidth - (plotWidth + lW);

    let newLW = Math.max(minLeftWidth, lW + offset);
    offset = newLW - lW;

    /**
     * Jquery's resizing functions don't have callback. We make them promiseable by
     * using ResizeSensor to detect action completed
     * @param element
     * @param args
     * @returns {Promise}
     */
    function makeResizePromise(element, args) {
        return new Promise(function (resolve) {
            new ResizeSensor(leftPanel, function () {
                resolve();
            });
            element.innerWidth(args);
        });
    }

    return Promise.all([
        makeResizePromise(leftPanel, leftPanel.innerWidth() + offset - 2),
        makeResizePromise(leftContainer, leftContainer.innerWidth() + offset - 2),
        makeResizePromise(rightPanel, plotWidth - 2),
        makeResizePromise(rightContainer, rightContainer.innerWidth() - offset - 2),
    ]).then(function () {
        return new Promise(function (resolve) {
            resolve({l, r, t, b, plotWidth, plotHeight});
        })
    });
}

/**
 * Relayout without redrawing the plot, when the width of the plot panel changes.
 * E.g. when the user changes the window's size
 */
function relayout() {
    let {l, r, t, b, plotWidth, plotHeight} = layoutParams;
    let plotDivLayout = $('#' + plotId)[0].layout;

    let layout = {
        width: plotWidth,
        height: plotHeight,
        margin: {l, r, b, t},
    };

    let xaxis = plotDivLayout.xaxis;
    if (xaxis) {
        let xaxisRange = plotDivLayout.xaxis.range;
        let yaxisRange = plotDivLayout.yaxis.range;

        layout.xaxis = {
            range: xaxisRange,
            autorange: false,
        };

        layout.yaxis = {
            range: yaxisRange,
            autorange: false,
        };
    }

    Plotly.relayout(plotId, layout);
}

const classToTraceInd = {};

const plot = function (highlights = [], markers = []) {
    let traces = [];
    let classToRowIdx = labelDatum[classType];
    let ncols = dataMatrix[0].length;
    let {renderClass, renderOptions} = getRenderOptions();

    let {l, r, t, b, plotWidth, plotHeight} = layoutParams;

    let classNames = Object.keys(classToRowIdx);
    let allX = [];
    let allY = [];
    let allZ = [];

    let traceCount = 0;
    $.each(classNames, function (classNo, className) {
        let ids = classToRowIdx[className];
        let xs = [];
        let ys = [];
        let zs = [];
        let x, y, z;
        let rowsText = [];

        let groupMetadata = [];
        $.each(ids, function (idx, rowIdx) {
            let row = dataMatrix[rowIdx];
            let metadata = rowsMetadata[rowIdx];
            groupMetadata.push(metadata);
            let rowText = makeText(metadata);
            rowsText.push(rowText);
            x = row[0];
            y = row[1];
            xs.push(x);
            ys.push(y);
            allX.push(x);
            allY.push(y);
            if (ncols > 2) {
                z = row[2];
                zs.push(z);
                allZ.push(z);
            }
        });

        let markerInd = highlights.indexOf(className);
        let marker, hovertext, hoverinfo;
        if (markerInd == -1) {
            marker = unhighlightedMarker;
            hovertext = 'none';
            hoverinfo = 'none';
        }
        else {
            marker = markers[markerInd];
            hovertext = rowsText;
            hoverinfo = 'text';
        }

        let trace = {
            x: xs,
            y: ys,

            // plotly does not allow custom field here so we have no choice but to use 'text' to store metadata
            text: groupMetadata,
            hovertext,
            hoverinfo,
            name: className,
            mode: 'markers',
            marker,
            type: renderClass
        };

        if (ncols > 2) {
            trace.z = zs;
        }

        traces.push(trace);
        classToTraceInd[className] = traceCount;
        traceCount++;
    });

    let layout;
    if (plotObj === undefined) {
        layout = {
            showlegend: false,
            hovermode: 'closest',
            width: plotWidth,
            height: plotHeight,
            margin: {l, r, b, t},
        };
    }
    else {
        layout = plotObj._result.layout;
    }

    plotObj = Plotly.newPlot(plotId, traces, layout, renderOptions);
    plotDiv.find('.modebar').css('position', 'relative');
    relayout();
};


/**
 * Listen to some events on the plotly chart
 */
function registerPlotlyEvents() {
    plotDiv[0].
        on('plotly_click', handleClick).
        on('plotly_hover', handleHover).
        on('plotly_afterplot', function () {
            if (spinner) {
                spinner.clear();
            }
        });
}


const initCategorySelection = function () {
    plot();
    registerPlotlyEvents();
};

/**
 * Play the audio segment of the syllable, given its ID
 * @param sylId
 */
function playSyl(sylId) {
    let data = {'segment-id': sylId};

    let args_ = {
        url: getUrl('send-request', 'koe/get-segment-audio-data'),
        cacheKey: sylId,
        postData: data
    };
    queryAndPlayAudio(args_);
}

const handleClick = function ({points}) {
    let metadata = points[0].text;
    let sylId = parseInt(metadata.id);
    playSyl(sylId);
};

/**
 * When mouse overs a syllable, add it to the highlighted list (if not already)
 * Then highlight its border with glowing red
 * @param points
 */
function handleHover({points}) {
    let point = points[0];
    let rowMetadata = point.text;
    let label = rowMetadata[classType];
    let container = null;
    if (label === class1Name) {
        container = class1SylSpectsDisplay;
    }
    else if (label === class2Name) {
        container = class2SylSpectsDisplay
    }
    if (container) {
        let element = addSylToHighlight(rowMetadata, container);
        highlightSyl(element);
    }
}

/**
 * Make the active element (mouse hovered, or spectrogram clicked) glow red at the border
 * @param element
 */
function highlightSyl(element) {
    $.each(highlighted, function (id, el) {
        el.removeClass('active');
    });

    if (element) {
        element.scrollintoview({
            duration: 'normal',
            direction: 'vertical',
        });
        element.addClass('active');
    }
}


const showError = function (title, body) {
    ce.dialogModalTitle.html(title);

    ce.dialogModalBody.children().remove();
    ce.dialogModalBody.append(`<div>${body}</div>`);
    ce.dialogModal.modal('show');

    ce.dialogModalCancelBtn.html('Dismiss');
    ce.dialogModalOkBtn.parent().hide();
    ce.dialogModal.on('hidden.bs.modal', function () {
        ce.dialogModalOkBtn.parent().show();
        ce.dialogModalCancelBtn.html('No');
    });
};


const divideRowWise = function (x, y) {
    let nrows = x.length;
    let ncols = x[0].length;

    let z = [];
    for (let i = 0; i < nrows; i++) {
        let zrow = new Array(ncols);
        let xrow = x[i];
        let ycol = y[i];
        for (let j = 0; j < ncols; j++) {
            zrow[j] = xrow[j] / ycol;
        }
        z.push(zrow);
    }
    return z;
};


const calcClassDistByAdjacency = function (adjMat, freqs) {
    let adjMatNorm = divideRowWise(adjMat, freqs);
    return pdist(adjMatNorm, 'cosine');
};


const calcClassDistByMedoids = function (classMedoids) {
    return pdist(classMedoids, 'euclidean');
};

/**
 * Given a distance matrix, find n nearest neighbours and return their distances + names
 *
 * @param stxDistmat
 * @param acsDistmat
 * @param nNeighbours must be less than or equal to the number of neighbours.
 *                    So this value can change and will be returned
 * @returns {{nearestNeigbours: Array, nearestStxDistances: Array, nearestAcsDistances: Array, nNeighbours: number}}
 */
function getClosestNeighbours(stxDistmat, acsDistmat, nNeighbours = 3) {
    let numObservers = stxDistmat.length;
    nNeighbours = Math.min(nNeighbours, numObservers - 1);
    let nearestStxDistances = [];
    let nearestAcsDistances = [];
    let nearestNeigbours = [];

    for (let i = 0; i < numObservers; i++) {
        let stxDistRow = stxDistmat[i];
        let acsDistRow = acsDistmat[i];
        let sortedInds = argsort(stxDistRow);
        let thisNearestStxDistances = [];
        let thisNearestAcsDistances = [];
        let thisNearestNeigbours = [];
        for (let j = 0; j < nNeighbours; j++) {
            let neighbourInd = sortedInds[j];
            let neighbourStxDist = stxDistRow[neighbourInd];
            let neighbourAcsDist = acsDistRow[neighbourInd];
            if (isNumber(neighbourStxDist)) {
                thisNearestStxDistances.push(neighbourStxDist);
                thisNearestAcsDistances.push(neighbourAcsDist);
                thisNearestNeigbours.push(neighbourInd);
            }
        }
        nearestStxDistances.push(thisNearestStxDistances);
        nearestAcsDistances.push(thisNearestAcsDistances);
        nearestNeigbours.push(thisNearestNeigbours);
    }
    return {nearestNeigbours, nearestStxDistances, nearestAcsDistances, nNeighbours};
}


/**
 * Given the neighbours' distances and labels, create rows data for the table
 * @returns {Array}
 */
function calcGridData() {
    let {adjMat, freqs, classLabels, classMedoids} = syntaxData;
    let adjDistMat = calcClassDistByAdjacency(adjMat, freqs);
    let acsDistMat = normalise(calcClassDistByMedoids(classMedoids));
    let nNearest = classLabels.length - 1;
    let {nearestNeigbours, nearestStxDistances, nearestAcsDistances, nNeighbours} =
            getClosestNeighbours(adjDistMat, acsDistMat, nNearest);
    nNearest = nNeighbours;

    let rows = [];
    let existingPairs = [];

    let nClasses = classLabels.length;
    for (let i = 0; i < nClasses; i++) {
        let class1Label = classLabels[i];
        if (isEmpty(class1Label)) {
            continue
        }

        let class1Count = freqs[i];
        let class1Neighbours = nearestNeigbours[i];
        let class1StxDistances = nearestStxDistances[i];
        let class1AcsDistances = nearestAcsDistances[i];

        for (let j = 0; j < nNearest; j++) {
            let neighbourInd = class1Neighbours[j];
            let class2Count = freqs[neighbourInd];
            let neighbourName = classLabels[neighbourInd];

            if (isEmpty(neighbourName) || isNull(neighbourInd)) {
                continue
            }
            let stxDistance = class1StxDistances[j];
            let acsDistance = class1AcsDistances[j];
            let weightedDistance = (stxDistance + acsDistance) / 2;

            if (existingPairs.indexOf(`${class1Label}-${neighbourName}`) == -1) {
                let pairId = `${neighbourName}-${class1Label}`;
                rows.push({'id': pairId, 'class-1-name': class1Label, 'class-2-name': neighbourName,
                    'syntax-distance': stxDistance, 'acoustic-distance': acsDistance,
                    'weighted-distance': weightedDistance,
                    'class-1-count': class1Count, 'class-2-count': class2Count
                });
                existingPairs.push(pairId);
            }
        }
    }
    return rows;
}


class Grid extends FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'syntax',
            'grid-type': 'syntax-grid',
            'default-field': 'class-1-name',
            gridOptions
        });
    }

    initMainGridContent(defaultArgs, extraArgs) {
        let self = this;
        self.defaultArgs = defaultArgs || {};

        let args = deepCopy(self.defaultArgs);
        args['grid-type'] = self.gridType;

        if (extraArgs) {
            args.extras = JSON.stringify(extraArgs);
        }

        return Promise.resolve();
    }
}

export const grid = new Grid();
const $grid = $('#syntax-grid');
const granularity = $grid.attr('granularity');
const database = $grid.attr('database');
const tmpdb = $grid.attr('tmpdb');

let defaultArgs = {};

let extraArgs = {
    granularity,
    database,
    tmpdb,
};


const adjustPlotlySize = function () {
    return calcLayout1().then(function ({l, r, t, b, plotWidth, plotHeight}) {
        layoutParams.l = l;
        layoutParams.r = r;
        layoutParams.t = t;
        layoutParams.b = b;
        layoutParams.plotWidth = plotWidth;
        layoutParams.plotHeight = plotHeight;

        return Promise.resolve();
    });
};

export const run = function (commonElements) {
    ce = commonElements;
    initSlider();
    grid.init();

    if (isEmpty(metaPath) || isEmpty(bytesPath)) {
        showError('This database has no ordination', 'You need to extract an ordination first');
    }
    else {
        adjustPlotlySize().then(function () {
            return grid.initMainGridHeader(defaultArgs, extraArgs).then(function () {
                return grid.initMainGridContent(defaultArgs, extraArgs).then(function () {
                    subscribeFlexibleEvents();
                    initClickHandlers();
                });
            });
        });
        spinner = createSpinner();
        spinner.start();
        downloadTensorData().
            then(initCategorySelection).
            catch(function (e) {
                spinner.clear();
                logError(e);
                showError('Error loading ordination', e);
            });
    }
    return Promise.resolve();
};


const columnsMap = {};
const id2idx = {};

/**
 * Create a newline separated text to be displayed on mousehover from metadata, each field one line
 * @param rowMetadata
 * @returns {string}
 */
function makeText(rowMetadata) {
    let retval = [];
    $.each(rowMetadata, function (colName, colVal) {
        retval.push(`${colName}: ${colVal}`);
    });
    return retval.join('<br>');
}

/**
 * Create a dict from columns and rows. They must have the same number of elements and their order must match
 * @param columnNames: an array that contains at least: 'id', 'tid', 'label'
 * @param row an array that contains the values for the fields in columnNames
 * @returns {*}
 */
function makeMetadata(columnNames, row) {
    let nCols = columnNames.length;
    if (row.length !== nCols) {
        return {error: 'Can\'t render text due to number of columns and row length are different'};
    }
    let retval = {};
    for (let i = 0; i < nCols; i++) {
        retval[columnNames[i]] = row[i];
    }
    return retval;
}


/**
 * Promise to query syntax data
 * @returns {Promise}
 */
function promiseSyntaxData() {
    return new Promise(function (resolve) {
        let onSuccess = function (data) {
            let adjMat = data[0];
            let freqs = data[1];
            let classLabels = data[2];

            let syntaxData_ = {adjMat, freqs, classLabels};
            resolve(syntaxData_);
        };

        postRequest({
            requestSlug: 'koe/get-syntactically-similar-pairs',
            data: {extras: JSON.stringify(extraArgs)},
            onSuccess
        });
    });
}

const downloadTensorData = function () {
    let downloadMeta = downloadRequest(metaPath, null);
    let downloadBytes = downloadRequest(bytesPath, Float32Array);
    let downloadSyntaxData = promiseSyntaxData();

    return Promise.all([downloadMeta, downloadBytes, downloadSyntaxData]).then(function (values) {
        let meta = values[0];
        let bytes = values[1];
        let syntaxData_ = values[2];
        let ind2label = {};
        $.each(syntaxData_.classLabels, function (ind, label) {
            ind2label[ind] = label;
        });

        let metaRows = meta.split('\n');
        let csvHeaderRow = metaRows[0];
        let csvBodyRows = metaRows.slice(2);

        let columnNames = csvHeaderRow.split('\t');

        for (let i = 0; i < columnNames.length; i++) {
            let columnName = columnNames[i];
            labelDatum[columnName] = {};
            columnsMap[columnName] = i;
        }

        for (let rowIdx = 0; rowIdx < csvBodyRows.length; rowIdx++) {
            let csvRow = csvBodyRows[rowIdx].split('\t');
            let rowMetadata = makeMetadata(columnNames, csvRow);
            rowsMetadata.push(rowMetadata);

            id2idx[csvRow[0]] = rowIdx;
            for (let colIdx = 1; colIdx < csvRow.length; colIdx++) {
                let columnType = columnNames[colIdx];
                let labelData = labelDatum[columnType];
                let label = csvRow[colIdx];
                if (labelData[label] === undefined) {
                    labelData[label] = [rowIdx];
                }
                else {
                    labelData[label].push(rowIdx);
                }
            }
        }

        let ncols = bytes.length / csvBodyRows.length;
        let byteStart = 0;
        let byteEnd = ncols;
        for (let i = 0; i < csvBodyRows.length; i++) {
            dataMatrix.push(Array.from(bytes.slice(byteStart, byteEnd)));
            byteStart += ncols;
            byteEnd += ncols;
        }

        let classLabels = syntaxData_.classLabels;
        let nClasses = classLabels.length;
        let labelData = labelDatum[classType];

        let classMedoids = [];

        for (let i = 0; i < nClasses; i++) {
            let className = classLabels[i];
            let classSylInds = labelData[className];
            let classSylCount = classSylInds.length;
            let classSylCoords = [];
            for (let j = 0; j < classSylCount; j++) {
                let sylInd = classSylInds[j];
                classSylCoords.push(dataMatrix[sylInd]);
            }
            let medoid = [];
            for (let j = 0; j < ncols; j++) {
                medoid.push(nj.array(classSylCoords).slice(null, [j, j + 1]).mean());
            }
            classMedoids.push(medoid);
        }

        syntaxData.classLabels = syntaxData_.classLabels;
        syntaxData.adjMat = syntaxData_.adjMat;
        syntaxData.freqs = syntaxData_.freqs;
        syntaxData.classMedoids = classMedoids;

        let rows = calcGridData();
        grid.rows = rows;
        updateSlickGridData(grid.mainGrid, rows);
    });
};


export const viewPortChangeHandler = function () {
    relayout();
};


export const postRun = function () {

    /*
     * Query database for all existing labels of all granularities
     * Construct selectable options to facilitate selectize's dropdown display
     */
    return new Promise(function (resolve) {
        postRequest({
            requestSlug: 'koe/get-label-options',
            data: {'database-id': databaseId, 'tmpdb-id': tmpDbId},
            onSuccess(selectableOptions) {
                setCache('selectableOptions', undefined, selectableOptions);
                resolve();
            },
            spinner: null
        });
    });
};

/**
 * Save merge info to database
 * @param newClassName
 * @returns {string}
 */
function recordMergeInfo(newClassName) {
    let classToRowIdx = labelDatum[classType];
    let class1RowIdx = classToRowIdx[class1Name];
    let class2RowIdx = classToRowIdx[class2Name];

    let class1RowIds = [];
    let class2RowIds = [];

    $.each(class1RowIdx, function (className, rowIdx) {
        let rowMetadata = rowsMetadata[rowIdx];
        class1RowIds.push(rowMetadata.id)
    });

    $.each(class2RowIdx, function (className, rowIdx) {
        let rowMetadata = rowsMetadata[rowIdx];
        class2RowIds.push(rowMetadata.id);
    });

    postRequest({
        requestSlug: 'koe/record-merge-classes',
        data: {'class1-name': class1Name, 'class2-name': class2Name, 'class1-ids': JSON.stringify(class1RowIds),
            'class2-ids': JSON.stringify(class2RowIds), 'class1n2-name': newClassName},
        msgGen(isSuccess, response) {
            return isSuccess ?
                `Successfully merged class ${class1Name} and ${class2Name}.` :
                `Something's wrong. The server says ${response}. Files might have been deleted.`;
        }
    });
}

/**
 * Merge classes on client side and change the syntax data for the table, accordingly
 * @param newClassName
 */
function mergeClasses(newClassName) {
    let {adjMat, freqs, classLabels} = syntaxData;
    let class1Ind = classLabels.indexOf(class1Name);
    let class2Ind = classLabels.indexOf(class2Name);

    if (class1Ind > class2Ind) {
        let temp = class1Ind;
        class1Ind = class2Ind;
        class2Ind = temp;
    }

    let nClasses = classLabels.length;
    let adjMatRowMerged = [];
    let newAdjMat = [];
    let newFreqs = [];
    let newClassLabels = [];

    let mergedClassAdjRow = nj.array(adjMat[class1Ind]).add(nj.array(adjMat[class2Ind])).tolist();

    for (let i = 0; i < class1Ind; i++) {
        let currentAdjRow = adjMat[i];
        adjMatRowMerged.push(currentAdjRow);
    }
    adjMatRowMerged.push(mergedClassAdjRow);
    for (let i = class1Ind + 1; i < class2Ind; i++) {
        let currentAdjRow = adjMat[i];
        adjMatRowMerged.push(currentAdjRow);
    }
    for (let i = class2Ind + 1; i < nClasses; i++) {
        let currentAdjRow = adjMat[i];
        adjMatRowMerged.push(currentAdjRow);
    }

    adjMatRowMerged = nj.array(adjMatRowMerged).T.tolist();

    let mergedClassAdjRowCol = nj.array(adjMatRowMerged[class1Ind]).add(nj.array(adjMatRowMerged[class2Ind])).tolist();

    for (let i = 0; i < class1Ind; i++) {
        let currentAdjRow = adjMatRowMerged[i];
        newAdjMat.push(currentAdjRow);
    }
    newAdjMat.push(mergedClassAdjRowCol);
    for (let i = class1Ind + 1; i < class2Ind; i++) {
        let currentAdjRow = adjMatRowMerged[i];
        newAdjMat.push(currentAdjRow);
    }
    for (let i = class2Ind + 1; i < nClasses; i++) {
        let currentAdjRow = adjMatRowMerged[i];
        newAdjMat.push(currentAdjRow);
    }

    newAdjMat = nj.array(newAdjMat).T.tolist();

    for (let i = 0; i < class2Ind; i++) {
        newFreqs.push(freqs[i]);
        newClassLabels.push(classLabels[i]);
    }
    newClassLabels[class1Ind] = newClassName;
    newFreqs[class1Ind] = freqs[class1Ind] + freqs[class2Ind];
    for (let i = class2Ind + 1; i < nClasses; i++) {
        newFreqs.push(freqs[i]);
        newClassLabels.push(classLabels[i]);
    }

    newAdjMat[class1Ind][class1Ind] = 0;

    syntaxData.adjMat = newAdjMat;
    syntaxData.freqs = newFreqs;
    syntaxData.classLabels = newClassLabels;
}


/**
 * Merge classes on client side and change the syllable labels for the plot, accordingly
 * @param newClassName
 */
function mergeClassesChangeSyllableLabels(newClassName) {
    let classToRowIdx = labelDatum[classType];
    let class1RowIdx = classToRowIdx[class1Name];
    let class2RowIdx = classToRowIdx[class2Name];
    let mergedRowInx = class1RowIdx.concat(class2RowIdx);
    classToRowIdx[class1Name] = undefined;
    classToRowIdx[class2Name] = undefined;
    classToRowIdx[newClassName] = mergedRowInx;

    if (class1Name in rowIdxNewClass) delete rowIdxNewClass[class1Name];
    if (class2Name in rowIdxNewClass) delete rowIdxNewClass[class2Name];
    rowIdxNewClass[newClassName] = mergedRowInx;
}


const handleMergeBtn = function () {
    let selectedSyls = Object.keys(highlighted);
    let numRows = selectedSyls.length;
    if (numRows > 0) {
        ce.dialogModalTitle.html(`Merge class ${class1Name} and ${class2Name}`);

        let selectableColumns = getCache('selectableOptions');
        let selectableOptions = selectableColumns[classType];

        const isSelectize = Boolean(selectableOptions);
        let inputEl = isSelectize ? ce.inputSelect : ce.inputText;
        ce.dialogModalBody.children().remove();
        ce.dialogModalBody.append(inputEl);
        let defaultValue = inputEl.val();

        if (isSelectize) {
            let control = inputEl[0].selectize;
            if (control) control.destroy();

            let selectizeOptions = constructSelectizeOptionsForLabellings(classType, defaultValue);
            initSelectize(inputEl, selectizeOptions);

            ce.dialogModal.on('shown.bs.modal', function () {
                inputEl[0].selectize.focus();
            });
        }
        else {
            ce.dialogModal.on('shown.bs.modal', function () {
                inputEl.focus();
            });
        }

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.off('click').one('click', function () {
            let value = inputEl.val();
            if (selectableOptions) {
                selectableOptions[value] = (selectableOptions[value] || 0) + numRows;
            }
            recordMergeInfo(value);
            mergeClasses(value);
            mergeClassesChangeSyllableLabels(value);

            let rows = calcGridData();
            grid.rows = rows;
            updateSlickGridData(grid.mainGrid, rows);
            ce.dialogModal.modal('hide');
        });
    }
};


/**
 * When user clicks save, send the syllables that have label changed as the result of merging to the server
 */
function handleSaveBtn() {
    let sylNewClass = {};
    $.each(rowIdxNewClass, function (className, rowIdxs) {
        let sids = [];
        $.each(rowIdxs, function (_, rowIdx) {
            let rowMetadata = rowsMetadata[rowIdx];
            sids.push(rowMetadata.id)
        });
        sylNewClass[className] = sids;
    });

    postRequest({
        requestSlug: 'koe/bulk-merge-classes',
        data: {'new-classes': JSON.stringify(sylNewClass)},
        msgGen(isSuccess, response) {
            return isSuccess ?
                `Successfully merged class ${class1Name} and ${class2Name}.` :
                `Something's wrong. The server says ${response}. Files might have been deleted.`;
        }
    });
}


/**
 * Remove all highlighted syllables from the list
 */
function clearHighlighted() {
    $.each(highlighted, function (id, el) {
        el.remove();
    });
    highlighted = {};
    highlightedInfo = {};
}


/**
 * Add a syllable to the highlighted list
 * @param rowMetadata
 * @param container
 */
function addSylToHighlight(rowMetadata, container) {
    let segId = rowMetadata.id;
    let segTid = rowMetadata.tid;

    let page = Math.floor(segTid / PAGE_CAPACITY);

    let element = highlighted[segId];
    if (element === undefined) {

        element = $(`
<div class="syl-spect" id="${segId}">
    <img src="/user_data/spect/syllable/${page}/${segTid}.png"/>
    <div class="syl-details">
        <span>${segId}</span>
    </div>
</div>`);
        highlighted[segId] = element;
        highlightedInfo[segId] = rowMetadata;
        container.prepend(element);
    }
    return element;
}


const subscribeFlexibleEvents = function () {
    debug('subscribeFlexibleEvents called from syntax-pages');
    grid.on('click', function (e, args) {
        e.preventDefault();
        let rowId = args.songId;
        let grid_ = grid.mainGrid;
        let dataView = grid_.getData();
        let item = dataView.getItemById(rowId);

        class1Name = item['class-1-name'];
        class2Name = item['class-2-name'];

        let classToRowIdx = labelDatum[classType];
        let class1RowIdx = classToRowIdx[class1Name];
        let class2RowIdx = classToRowIdx[class2Name];

        plot([class1Name, class2Name], [class1Marker, class2Marker]);
        registerPlotlyEvents();

        class1SylSpectsName.html(class1Name);
        class2SylSpectsName.html(class2Name);

        clearHighlighted();

        $.each(class1RowIdx, function (idx, rowInd) {
            let rowMetadata = rowsMetadata[rowInd];
            addSylToHighlight(rowMetadata, class1SylSpectsDisplay);
        });
        $.each(class2RowIdx, function (idx, rowInd) {
            let rowMetadata = rowsMetadata[rowInd];
            addSylToHighlight(rowMetadata, class2SylSpectsDisplay);
        });
    });
};
