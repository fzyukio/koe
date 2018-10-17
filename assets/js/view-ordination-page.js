/* global Plotly, d3 */
import {queryAndPlayAudio, changePlaybackSpeed} from './audio-handler';
import {getUrl, getCache, setCache, isEmpty} from './utils';
import {downloadRequest, postRequest} from './ajax-handler';
import {constructSelectizeOptionsForLabellings, initSelectize} from './selectize-formatter';
require('bootstrap-slider/dist/bootstrap-slider.js');

const speedSlider = $('#speed-slider');
const plotId = 'plotly-plot';
const plotDiv = $(`#${plotId}`);
const metaPath = plotDiv.attr('metadata');
const bytesPath = plotDiv.attr('bytes');
const databaseId = plotDiv.attr('database');
const tmpDbId = plotDiv.attr('tmpdb');
const body = $('body');
const sylSpects = $('#syl-spects');
const labelTyleSelectEl = $('#label-type');

let rightContainer = plotDiv.parents('.contain-panel');
let rightPanel = plotDiv.parents('.panel');
let leftContainer = sylSpects.parents('.contain-panel');
let leftPanel = sylSpects.parents('.panel');

let minLeftWidth;

const legendSymbols = {};
let ce;
let highlighted = {};
let highlightedInfo = {};
let inLassoSelectionMode = false;
const dataMatrix = [];
const rowsMetadata = [];
// const dataText = [];
const labelDatum = {};
let plotObj;

const saveSvgOption = {
    name: 'Save SVG',
    icon: Plotly.Icons.camera,
    click (gd) {
        Plotly.downloadImage(gd, {format: 'svg'})
    }
};

const savePngOption = {
    name: 'Save PNG',
    icon: Plotly.Icons.camera,
    click (gd) {
        Plotly.downloadImage(gd, {format: 'png'})
    }
};

const plotlyOptions = {
    modeBarButtonsToRemove: [
        'toImage', 'pan2d', 'select2d', 'zoomIn2d', 'zoomOut2d', 'resetScale2d', 'hoverClosestCartesian',
        'hoverCompareCartesian', 'zoom3d', 'pan3d', 'orbitRotation',
        'tableRotation', 'resetCameraDefault3d', 'resetCameraLastSave3d', 'hoverClosest3d', 'zoomInGeo',
        'zoomOutGeo', 'resetGeo', 'hoverClosestGeo', 'hoverClosestGl2d', 'hoverClosestPie', 'toggleHover',
        'resetViews', 'toggleSpikelines', 'resetViewMapbox'
    ],
    modeBarButtonsToAdd: []
};

const plotlyMarkerSymbols = ['circle', 'square', 'diamond', 'cross', 'triangle-up', 'star'];

const categoricalColourScale = d3.schemeCategory10;
const interpolativeColourScale = d3.interpolateRainbow;
const nCategoricalColours = categoricalColourScale.length;
const renderAsSvg = $('#render-as-svg');

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
        if (renderAsSvg[0].checked) {
            renderClass = 'scatter';
            plotlyOptions.modeBarButtonsToAdd = [saveSvgOption];
        }
        else {
            renderClass = 'scattergl';
            plotlyOptions.modeBarButtonsToAdd = [savePngOption];
        }
    }
    else {
        renderAsSvg.prop('disabled', true);
        renderClass = 'scatter3d';
        plotlyOptions.modeBarButtonsToAdd = [savePngOption];
    }

    return {renderClass, renderOptions};
}

/**
 * Toggle lasso selection mode. In lasso mode, mouseover has no effect (no syllable highlight), user can't clear the
 * highlighted list. User can change label or view details of the selected in the syllables view.
 * @param mode true for "on" or false for "off" mode
 */
function setLassoSelectionMode(mode) {
    inLassoSelectionMode = mode;
    $('.enable-on-lasso').prop('disabled', !mode);
    $('.disable-on-lasso').prop('disabled', mode);
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
 * Attach click event handlers to the three buttons and the panel-body in highlighted panel
 */
function initClickHandlers() {
    $('#clear-highlighted-btn').click(clearHighlighted);
    $('#show-highlighted-btn').click(function () {
        let url = this.getAttribute('syllables-view-url');
        let redirectUrl = `${url}?_holdout=true`;

        postRequest({
            requestSlug: 'koe/hold-ids',
            data: {ids: Object.keys(highlighted).join()},
            onSuccess() {
                window.open(redirectUrl);
            }
        });
    });

    $('.change-label').click(function () {
        let granularity = this.getAttribute('label-type');
        setLabel(granularity);
    });

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
    renderAsSvg.click(plot);
}

/**
 * Create list of most appropriate markers for the scatter plot.
 * If there isn't too many classes - use categorical colour for best visual.
 * Otherwise use as few interpolative colours as possible
 * @param nClasses number of distinctive classes
 * @returns {Array}
 */
function generateMarkers(nClasses) {
    let nColours;
    let nSymbols;
    let colour;

    /* Try to use categorical colours (max = 12) if there are less than 12 * nSymbols classes */
    if (nClasses <= (plotlyMarkerSymbols.length * nCategoricalColours)) {
        nColours = nCategoricalColours;
        nSymbols = Math.ceil(nClasses / nColours);
        colour = d3.scaleOrdinal(categoricalColourScale);
    }
    else {
        nSymbols = Math.min(Math.ceil(Math.sqrt(nClasses)), plotlyMarkerSymbols.length);
        nColours = Math.ceil(nClasses / nSymbols);
        colour = d3.scaleSequential(interpolativeColourScale).domain([0, nColours]);
    }

    let markers = [];
    for (let i = 0; i < nColours; i++) {
        let thisColour = colour(i);
        for (let j = 0; j < nSymbols; j++) {
            let thisSymbol = plotlyMarkerSymbols[j];

            markers.push({
                symbol: thisSymbol,
                size: 10,
                color: thisColour,
                opacity: 0.8,
                line: {
                    width: 0.5
                },
            });
        }
    }
    return markers;
}

/**
 * Adjust the plot's div such that the plot is always a square & the height is always 100%
 * @returns {{l: number, r: number, b: number, t: number}}
 */
function calcLayout() {
    let windowWidth = $('.main-content').width();
    let plotHeight = plotDiv.height();
    let lW = leftPanel.innerWidth();

    let legend = plotDiv.find('.legend')[0];
    let r = legend ? legend.getBoundingClientRect().width : 200;
    let b = 0;
    let t = 0;
    let l = 0;

    let h = plotHeight - t - b;
    let plotWidth = h + r + l;

    let offset = windowWidth - (plotWidth + lW);
    rightPanel.width(plotWidth);

    let newLW = Math.max(minLeftWidth, lW + offset);
    offset = newLW - lW;

    leftPanel.innerWidth(leftPanel.innerWidth() + offset - 2);
    leftContainer.innerWidth(leftContainer.innerWidth() + offset - 2);
    rightContainer.innerWidth(rightContainer.innerWidth() - offset);

    return {l, r, t, b, plotWidth, plotHeight}
}

/**
 * Relayout without redrawing the plot, when the width of the plot panel changes.
 * E.g. when the user changes the window's size
 */
function relayout() {
    let {l, r, t, b, plotWidth, plotHeight} = calcLayout();

    let layout = {
        width: plotWidth,
        height: plotHeight,
        margin: {l, r, b, t},
    };
    Plotly.relayout(plotId, layout);
}

/**
 * Construct a dictionary of label => thir symbol (on the legend).
 * We display these symbols in the panel of selected syllables
 */
function extractLegends() {
    $('.legend text.legendtext').each(function (idx, textEl) {
        let layer = $(textEl).parent().find('g.layers').clone();
        layer = layer.attr('transform', 'translate(-13, 7)');
        let layerStr = $('<div>').append(layer).html();
        let text = textEl.innerHTML;
        legendSymbols[text] = layerStr;
    });
}

const plot = function () {
    body.addClass('loading');
    let classType = labelTyleSelectEl.parent().find('#selected-label-type').html();
    let traces = [];
    let class2RowIdx = labelDatum[classType];
    let nClasses = Object.keys(class2RowIdx).length;
    let ncols = dataMatrix[0].length;
    let {renderClass, renderOptions} = getRenderOptions();

    let {l, r, t, b, plotWidth, plotHeight} = calcLayout();

    let classNames = Object.keys(class2RowIdx);
    let allX = [];
    let allY = [];
    let allZ = [];

    let markers = generateMarkers(nClasses);

    $.each(classNames, function (classNo, className) {
        let ids = class2RowIdx[className];
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

        let trace = {
            x: xs,
            y: ys,

            // plotly does not allow custom field here so we have no choice but to use 'text' to store metadata
            text: groupMetadata,
            hovertext: rowsText,
            hoverinfo: 'text',
            name: className,
            mode: 'markers',
            marker: markers[classNo],
            type: renderClass
        };

        if (ncols > 2) {
            trace.z = zs;
        }

        traces.push(trace);
    });

    let layout;
    if (plotObj === undefined) {
        layout = {
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
    extractLegends();
    body.removeClass('loading');
};


/**
 * Listen to some events on the plotly chart
 */
function registerPlotlyEvents() {
    plotDiv[0].on('plotly_click', handleClick).on('plotly_hover', handleHover).on('plotly_selected', handleSelected);

    plotDiv.find('.modebar-btn[data-title="Lasso Select"]').click(function () {
        setLassoSelectionMode(true);
    });

    plotDiv.find('.modebar-btn[data-title="Zoom"]').click(function () {
        setLassoSelectionMode(false);
    });

    plotDiv.find('.modebar-btn[data-title="Lasso Select"]')[0].click();
}


const initCategorySelection = function () {
    $.each(labelDatum, function (labelType) {
        if (labelType !== 'id' && labelType !== 'tid') {
            let option = `<li class="not-active"><a href="#" value="${labelType}">${labelType}</a></li>`;
            labelTyleSelectEl.append(option);
        }
    });

    /**
     * Change the granularity and replot
     * @param labelType
     */
    function setValue(labelType) {
        let locationOrigin = window.location.origin;
        let localtionPath = window.location.pathname;
        let currentSearch = window.location.search.substr(1);
        let labelTypeStart = currentSearch.indexOf('label-type');
        if (labelTypeStart > -1) {
            let labelTypeEnd = currentSearch.substr(labelTypeStart).indexOf('&');
            if (labelTypeEnd == -1) {
                labelTypeEnd = currentSearch.substr(labelTypeStart).length - 1;
            }
            labelTypeEnd += labelTypeStart + 1;
            currentSearch = currentSearch.substr(0, labelTypeStart) + currentSearch.substr(labelTypeEnd);
        }
        let newUrl = `${locationOrigin}${localtionPath}?label-type=${labelType}&${currentSearch}`;
        window.history.pushState('', '', newUrl);

        labelTyleSelectEl.parent().find('#selected-label-type').html(labelType);
        labelTyleSelectEl.find('li').removeClass('active').addClass('non-active');
        labelTyleSelectEl.find(`a[value="${labelType}"]`).parent().removeClass('non-active').addClass('active');
        plot();
        registerPlotlyEvents();
    }

    labelTyleSelectEl.find('li a').click(function () {
        setValue($(this).attr('value'));
    });

    minLeftWidth = leftContainer.innerWidth();

    let initialLabelType = ce.argDict['label-type'] || 'label';
    setValue(initialLabelType);
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
 * Add a syllable to the highlighted list
 * @param point a plotly point containing the syllable info
 * @param override if false, the function obeys the lasso mode. if true, the syllable will be added regardless
 * @returns {*}
 */
function addSylToHighlight(point, override = false) {
    let rowMetadata = point.text;
    let segId = rowMetadata.id;
    let segTid = rowMetadata.tid;
    let element = highlighted[segId];
    let allow = override || !inLassoSelectionMode;
    if (element === undefined && allow) {
        let legendSymbol = legendSymbols[point.data.name];

        element = $(`
<div class="syl-spect" id="${segId}">
    <img src="/user_data/spect/fft/syllable/${segTid}.png"/>
    <div class="syl-details">
        <svg width="13px" height="13px">${legendSymbol}</svg>
        <span>${segId}</span>
    </div>
</div>`);
        highlighted[segId] = element;
        highlightedInfo[segId] = rowMetadata;
        sylSpects.prepend(element);
    }
    return element;
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
        element[0].scrollIntoViewIfNeeded();
        element.addClass('active');
    }
}

/**
 * When mouse overs a syllable, add it to the highlighted list (if not already)
 * Then highlight its border with glowing red
 * @param points
 */
function handleHover({points}) {
    let point = points[0];
    let element = addSylToHighlight(point);
    highlightSyl(element);
}


/**
 * When lasso-select finishes, add ALL selected syllables to the highlighted list
 * @param eventData
 */
function handleSelected(eventData) {
    if (eventData) {
        clearHighlighted();

        $.each(eventData.points, function (idx, point) {
            addSylToHighlight(point, true);
        });
    }
}


const showNonDataReason = function () {
    ce.dialogModalTitle.html('This database has no ordination');

    ce.dialogModalBody.children().remove();
    ce.dialogModalBody.append('<div>You need to extract an ordination first</div>');
    ce.dialogModal.modal('show');

    ce.dialogModalCancelBtn.html('Dismiss');
    ce.dialogModalOkBtn.parent().hide();
    ce.dialogModal.on('hidden.bs.modal', function () {
        ce.dialogModalOkBtn.parent().show();
        ce.dialogModalCancelBtn.html('No');
    });
};


export const run = function (commonElements) {
    ce = commonElements;
    initSlider();

    if (isEmpty(metaPath) || isEmpty(bytesPath)) {
        showNonDataReason();
    }
    else {
        downloadTensorData().then(initCategorySelection);
        initClickHandlers();
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


const downloadTensorData = function () {
    body.addClass('loading');

    let downloadMeta = downloadRequest(metaPath, null);
    let downloadBytes = downloadRequest(bytesPath, Float32Array);

    return Promise.all([downloadMeta, downloadBytes]).then(function (values) {
        let meta = values[0];
        let bytes = values[1];

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
            // let rowText = makeText(rowsMetadata);
            // dataText.push(rowText);

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

        body.removeClass('loading');
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
    return new Promise(function(resolve) {
        postRequest({
            requestSlug: 'koe/get-label-options',
            data: {'database-id': databaseId, 'tmpdb-id': tmpDbId},
            onSuccess(selectableOptions) {
                setCache('selectableOptions', undefined, selectableOptions);
                resolve();
            }
        });
    });
};


const setLabel = function (field) {
    let selectedSyls = Object.keys(highlighted);
    let numRows = selectedSyls.length;
    if (numRows > 0) {
        ce.dialogModalTitle.html(`Set ${field} for ${numRows} rows`);

        let selectableColumns = getCache('selectableOptions');
        let selectableOptions = selectableColumns[field];

        const isSelectize = Boolean(selectableOptions);
        let inputEl = isSelectize ? ce.inputSelect : ce.inputText;
        ce.dialogModalBody.children().remove();
        ce.dialogModalBody.append(inputEl);
        let defaultValue = inputEl.val();

        if (isSelectize) {
            let control = inputEl[0].selectize;
            if (control) control.destroy();

            let selectizeOptions = constructSelectizeOptionsForLabellings(field, defaultValue);
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

            let postData = {
                ids: JSON.stringify(selectedSyls),
                field,
                value,
                'grid-type': 'segment-info'
            };

            ce.dialogModal.modal('hide');
            postRequest({
                requestSlug: 'set-property-bulk',
                data: postData,
                onSuccess() {
                    let labelData = labelDatum[field];
                    // let colIdx = columnsMap[field];
                    if (labelData[value] === undefined) {
                        labelData[value] = [];
                    }
                    let category = labelData[value];
                    $.each(highlightedInfo, function (id, metadata) {
                        let oldLabel = metadata[field];
                        let oldCategory = labelData[oldLabel];
                        let rowIdx = id2idx[id];
                        let pos = oldCategory.indexOf(rowIdx);
                        if (pos > -1) {
                            oldCategory.splice(pos, 1);
                            category.push(rowIdx);
                        }
                        rowsMetadata[rowIdx][field] = value;
                    });

                    plot();
                    registerPlotlyEvents();
                }
            });
        })
    }
};
