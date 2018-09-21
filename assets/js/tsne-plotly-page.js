/* global Plotly */
import {downloadRequest} from './ajax-handler';
import {initSelectizeSimple} from './selectize-formatter';
import d3 from './d3-importer';
import {queryAndPlayAudio, initAudioContext} from "./audio-handler";
import {getUrl} from "./utils";

let plotDiv = $('#plotly-plot');
let metaPath = plotDiv.attr('metadata');
let bytesPath = plotDiv.attr('bytes');
let database = plotDiv.attr('database');
let annotator = plotDiv.attr('annotator');
let body = $('body');
let sylSpects = $('#syl-spects');


let plotlyOptions = {
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

const plot = function (matrix, rowsMetadata, labelDatum, classType) {
    let traces = [];
    let class2RowIdx = labelDatum[classType];
    let nClasses = Object.keys(class2RowIdx).length;
    let colour = d3.scaleSequential(d3.interpolateRainbow).domain([0, nClasses]);
    let ncols = matrix[0].length;
    let plotType = 'scatter3d';
    if (ncols == 2) {
        plotType = 'scatter';
    }

    let plotTopBottomMargin = 40;
    let plotWidth = plotDiv.width();
    let plotDivHeight = plotDiv.height();
    let plotRightMargin = 50;
    let plotLeftMargin = plotWidth - plotDivHeight - plotRightMargin + plotTopBottomMargin;


    let classNames = Object.keys(class2RowIdx);
    // classNames.sort();

    $.each(classNames, function (classNo, className) {
        let ids = class2RowIdx[className];
        let x = [];
        let y = [];
        let z = [];
        let rowsMetadataStr = [];
        $.each(ids, function (idx, rowIdx) {
            let row = matrix[rowIdx];
            let rowMetadata = rowsMetadata[rowIdx];
            rowsMetadataStr.push(rowMetadata.join(', '));
            x.push(row[0]);
            y.push(row[1]);
            if (ncols > 2) {
                z.push(row[2]);
            }
        });

        let trace = {
            x,
            y,
            text: rowsMetadataStr,
            name: className,
            mode: 'markers',
            marker: {
                size: 5,
                color: colour(classNo),
                opacity: 1
            },
            type: plotType
        };

        if (ncols > 2) {
            trace.z = z;
        }

        traces.push(trace);
    });

    let layout = {
        title: `T-SNE on ${database}, annotated by ${annotator}`,
        hovermode: 'closest',
        width: plotWidth,
        height: plotDivHeight,
        margin: {
            l: plotLeftMargin,
            r: plotRightMargin,
            b: plotTopBottomMargin,
            t: plotTopBottomMargin
        }
    };
    Plotly.newPlot('plotly-plot', traces, layout, plotlyOptions);
};

const initSelectize = function ({dataMatrix, rowsMetadata, labelDatum}) {
    let labelTyleSelectEl = $('#label-type');
    let options = [];
    $.each(labelDatum, function (labelType) {
        options.push({
            value: labelType,
            text: labelType
        });
    });

    let labelTyleSelecthandler = initSelectizeSimple(labelTyleSelectEl, options);

    labelTyleSelectEl.change(function () {
        let labelType = labelTyleSelectEl.val();
        plot(dataMatrix, rowsMetadata, labelDatum, labelType);
    });

    labelTyleSelecthandler.setValue('label');
};

const handleClick = function ({points, event}) {
    let pointText = points[0].text;
    let pointId = parseInt(pointText.substr(0, pointText.indexOf(',')));
    console.log(pointId);
    let data = {'segment-id': pointId};

    let args_ = {
        url: getUrl('send-request', 'koe/get-segment-audio-data'),
        cacheKey: pointId,
        postData: data
    };

    queryAndPlayAudio(args_);
};

const handleHover = function ({points}) {
    let pointText = points[0].text;
    let pointId = pointText.substr(0, pointText.indexOf(','));
    let children = sylSpects.children();
    let nChildren = children.length;
    if (nChildren>5) {
        for (let i=5; i<nChildren; i++) {
            children[i].remove();
        }
    }
    sylSpects.prepend(`<img src="/user_data/spect/fft/syllable/${pointId}.png">`);
};

export const run = function () {
    initAudioContext();

    downloadTensorData()
    .then(initSelectize)
    .then(function () {
        plotDiv[0].
            on('plotly_click', handleClick).
            on('plotly_hover', handleHover);
    });
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
