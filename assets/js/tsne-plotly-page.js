/* global Plotly, d3 */
import {queryAndPlayAudio, initAudioContext} from './audio-handler';
import {getUrl, getCache, setCache} from './utils';
import {downloadRequest, postRequest} from './ajax-handler';
import {constructSelectizeOptionsForLabellings, initSelectize} from './selectize-formatter';

const plotId = 'plotly-plot';
const plotDiv = $(`#${plotId}`);
const panel = plotDiv.parents('.panel');
const metaPath = plotDiv.attr('metadata');
const bytesPath = plotDiv.attr('bytes');
const databaseId = plotDiv.attr('database');
const body = $('body');
const sylSpects = $('#syl-spects');

const legendSymbols = {};
let ce;
let highlighted = {};
let inLassoSelectionMode = false;

const plotlyOptions = {
    modeBarButtonsToRemove: [
        'toImage', 'pan2d', 'select2d', 'zoomIn2d', 'zoomOut2d', 'resetScale2d', 'hoverClosestCartesian',
        'hoverCompareCartesian', 'zoom3d', 'pan3d', 'orbitRotation',
        'tableRotation', 'resetCameraDefault3d', 'resetCameraLastSave3d', 'hoverClosest3d', 'zoomInGeo',
        'zoomOutGeo', 'resetGeo', 'hoverClosestGeo', 'hoverClosestGl2d', 'hoverClosestPie', 'toggleHover',
        'resetViews', 'toggleSpikelines', 'resetViewMapbox'
    ],
    modeBarButtonsToAdd: [
        {
            name: 'saveSVG',
            icon: Plotly.Icons.camera,
            click (gd) {
                Plotly.downloadImage(gd, {format: 'svg'})
            }
        }
    ]
};

const plotlyMarkerSymbols = ['circle', 'square', 'diamond', 'cross', 'triangle-up', 'star'];

const categoricalColourScale = d3.schemeCategory10;
const interpolativeColourScale = d3.interpolateRainbow;
const nCategoricalColours = categoricalColourScale.length;

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
    let W = panel.innerWidth();
    let H = plotDiv.height();
    let legend = plotDiv.find('.legend')[0];
    let r = legend ? legend.getBoundingClientRect().width : 200;
    let b = 0;
    let t = 0;
    let l = 0;

    let w = W - r - l;
    let h = H - t - b;

    if (h > w) {
        w = h;
        W = w + r + l;
        panel.width(W);
    }
    return {l, r, t, b, W, H}
}

/**
 * Relayout without redrawing the plot, when the width of the plot panel changes.
 * E.g. when the user changes the window's size
 */
function relayout() {
    let {l, r, t, b, W, H} = calcLayout();

    let layout = {
        width: W,
        height: H,
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
        let layer = $(textEl).parent().find('g.layers').attr('transform', 'translate(-13, 7)');
        let layerStr = $('<div>').append(layer).clone().html();
        let text = textEl.innerHTML;
        legendSymbols[text] = layerStr;
    });
}

const plot = function (matrix, rowsMetadata, labelDatum, classType) {
    let traces = [];
    let class2RowIdx = labelDatum[classType];
    let nClasses = Object.keys(class2RowIdx).length;
    let ncols = matrix[0].length;
    let plotType = 'scatter3d';
    if (ncols == 2) {
        plotType = 'scattergl';
    }

    let {l, r, t, b, W, H} = calcLayout();

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
        let rowsMetadataStr = [];
        $.each(ids, function (idx, rowIdx) {
            let row = matrix[rowIdx];
            let rowMetadata = rowsMetadata[rowIdx];
            rowsMetadataStr.push(rowMetadata.join(', '));
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
            text: rowsMetadataStr,
            name: className,
            mode: 'markers',
            marker: markers[classNo],
            type: plotType
        };

        if (ncols > 2) {
            trace.z = zs;
        }

        traces.push(trace);
    });

    let layout = {
        hovermode: 'closest',
        width: W,
        height: H,
        margin: {l, r, b, t},
    };

    Plotly.newPlot(plotId, traces, layout, plotlyOptions);
    plotDiv.find('.modebar').css('position', 'relative');
    relayout();
    extractLegends();
};

const initCategorySelection = function ({dataMatrix, rowsMetadata, labelDatum}) {
    let labelTyleSelectEl = $('#label-type');
    $.each(labelDatum, function (labelType) {
        if (labelType !== 'id') {
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
        let newUrl = `${locationOrigin}${localtionPath}?label-type=${labelType}`;
        window.history.pushState('', '', newUrl);

        labelTyleSelectEl.parent().find('#selected-label-type').html(labelType);
        labelTyleSelectEl.find('li').removeClass('active').addClass('non-active');
        labelTyleSelectEl.find(`a[value="${labelType}"]`).parent().removeClass('non-active').addClass('active');
        plot(dataMatrix, rowsMetadata, labelDatum, labelType);
        plotDiv[0].
            on('plotly_click', handleClick).
            on('plotly_hover', handleHover).
            on('plotly_selected', handleSelected);

        plotDiv.find('.modebar-btn[data-title="Lasso Select"]').click(function () {
            setLassoSelectionMode(true);
        });

        plotDiv.find('.modebar-btn[data-title="Zoom"]').click(function () {
            setLassoSelectionMode(false);
        });

        plotDiv.find('.modebar-btn[data-title="Lasso Select"]')[0].click();
    }

    labelTyleSelectEl.find('li a').click(function () {
        setValue($(this).attr('value'));
    });

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
    let pointText = points[0].text;
    let sylId = parseInt(pointText.substr(0, pointText.indexOf(',')));
    playSyl(sylId);
};


/**
 * Add a syllable to the highlighted list
 * @param point a plotly point containing the syllable info
 * @param override if false, the function obeys the lasso mode. if true, the syllable will be added regardless
 * @returns {*}
 */
function addSylToHighlight(point, override = false) {
    let pointText = point.text;
    let pointId = pointText.substr(0, pointText.indexOf(','));
    let element = highlighted[pointId];
    let allow = override || !inLassoSelectionMode;
    if (element === undefined && allow) {
        let legendSymbol = legendSymbols[point.data.name];

        element = $(`
<div class="syl-spect" id="${pointId}">
    <img src="/user_data/spect/fft/syllable/${pointId}.png"/>
    <div class="syl-details">
        <svg width="13px" height="13px">${legendSymbol}</svg>
        <span>${pointText}</span>
    </div>
</div>`);
        highlighted[pointId] = element;
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


export const run = function (commonElements) {
    ce = commonElements;
    initAudioContext();
    downloadTensorData().then(initCategorySelection);
    initClickHandlers();
};


const downloadTensorData = function () {
    body.addClass('loading');

    let downloadMeta = downloadRequest(metaPath, null);
    let downloadBytes = downloadRequest(bytesPath, Float32Array);

    return Promise.all([downloadMeta, downloadBytes]).then(function (values) {
        let dataMatrix = [];
        let meta = values[0];
        let bytes = values[1];

        let metaRows = meta.split('\n');
        let csvHeaderRow = metaRows[0];
        let csvBodyRows = metaRows.slice(2);
        let rowsMetadata = [];

        let columnNames = csvHeaderRow.split('\t');
        let labelDatum = {};

        for (let i = 0; i < columnNames.length; i++) {
            let columnName = columnNames[i];
            labelDatum[columnName] = {};
        }

        for (let rowIdx = 0; rowIdx < csvBodyRows.length; rowIdx++) {
            let rowMetadata = csvBodyRows[rowIdx].split('\t');
            rowsMetadata.push(rowMetadata);
            for (let colIdx = 1; colIdx < rowMetadata.length; colIdx++) {
                let columnType = columnNames[colIdx];
                let labelData = labelDatum[columnType];
                let label = rowMetadata[colIdx];
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
        return {
            dataMatrix,
            rowsMetadata,
            labelDatum
        }
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
    postRequest({
        requestSlug: 'koe/get-label-options',
        data: {'database-id': databaseId},
        onSuccess(selectableOptions) {
            setCache('selectableOptions', undefined, selectableOptions)
        }
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
                data: postData
            });
        })
    }
};
