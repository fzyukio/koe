import {downloadRequest} from './ajax-handler';
import {initSelectizeSimple} from './selectize-formatter';
const plotly = require('plotly.js');
import d3 from './d3-importer';

let plotDiv = $('#plotly-plot');
let metaPath = plotDiv.attr('metadata');
let bytesPath = plotDiv.attr('bytes');
let body = $('body');

const plot = function (matrix3d, rowsMetadata, labelDatum, classType) {
    let traces = [];
    let class2RowIdx = labelDatum[classType];
    let nClasses = Object.keys(class2RowIdx).length;
    let colour = d3.scaleSequential(d3.interpolateRainbow).domain([0, nClasses]);

    let classNames = Object.keys(class2RowIdx);
    classNames.sort();

    $.each(classNames, function (classNo, className) {
        let ids = class2RowIdx[className];
        let x = [];
        let y = [];
        let z = [];
        let rowsMetadataStr = [];
        $.each(ids, function (idx, rowIdx) {
            let row = matrix3d[rowIdx];
            let rowMetadata = rowsMetadata[rowIdx];
            rowsMetadataStr.push(rowMetadata.join(', '));
            x.push(row[0]);
            y.push(row[1]);
            z.push(row[2]);
        });

        let trace = {
            x,
            y,
            z,
            text: rowsMetadataStr,
            name: className,
            mode: 'markers',
            marker: {
                size: 5,
                color: colour(classNo),
                line: {
                    color: '#ffffff',
                    width: 0.5
                },
                opacity: 1
            },
            type: 'scatter3d'
        };
        traces.push(trace);
    });

    let layout = {
        title: 'Blah',
        margin: {
            l: 0,
            r: 0,
            b: 0,
            t: 0
        }
    };
    plotly.newPlot('plotly-plot', traces, layout);
};

const initSelectize = function (dataMatrix, rowsMetadata, labelDatum) {
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

export const run = function () {
    downloadTensorData().
        then(function ({dataMatrix, rowsMetadata, labelDatum}) {
            initSelectize(dataMatrix, rowsMetadata, labelDatum);
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
        return {dataMatrix,
            rowsMetadata,
            labelDatum}
    });
};
