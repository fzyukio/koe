import {initSelectizeSimple} from './selectize-formatter';
import {postRequest, downloadRequest} from './ajax-handler';
import {getUrl, downloadBlob} from './utils';

let databaseSelectEl;
let annotatorSelectEl;
let presetSelectEl;
let featuresSectionEl = $('#id_features');
let aggregationsSectionEl = $('#id_aggregations');
let dimreduceSectionEl = $('#id_dimreduce');
let ndimsSectionEl = $('#id_ndims');
let visualiseBtn = $('#visualise-btn');
let downloadBtn = $('#download-btn');

let annotatorSelectizeHandler;
let presetSelectizeHandler;

let form = $('#feature-extraction-form');

export const run = function () {
    initSelectize();
};

const disableEnableSelections = function (disable) {
    if (disable) {
        annotatorSelectizeHandler.disable();
    }
    featuresSectionEl.find('input').prop('checked', false).prop('disabled', disable);
    aggregationsSectionEl.find('input').prop('checked', false).prop('disabled', disable);
    dimreduceSectionEl.find('input').prop('checked', false).prop('disabled', disable);
    ndimsSectionEl.prop('disabled', disable);
    visualiseBtn.prop('disabled', disable);
    downloadBtn.prop('disabled', disable);
};

const initSelectize = function () {
    databaseSelectEl = $('#id_database');
    annotatorSelectEl = $('#id_annotator');
    presetSelectEl = $('#id_preset');

    initSelectizeSimple(databaseSelectEl);
    annotatorSelectizeHandler = initSelectizeSimple(annotatorSelectEl);
    presetSelectizeHandler = initSelectizeSimple(presetSelectEl);

    databaseSelectEl.change(function () {
        let databaseId = databaseSelectEl.val();
        annotatorSelectizeHandler.enable();

        postRequest({
            requestSlug: 'koe/get-annotators-and-presets',
            data: {'database-id': databaseId},
            onSuccess (data) {
                let annotators = data.annotation;
                let preset = data.preset;
                let ntensors = data.ntensors;

                annotatorSelectizeHandler.destroy();
                annotatorSelectEl.html(annotators);
                annotatorSelectizeHandler = initSelectizeSimple(annotatorSelectEl);

                presetSelectizeHandler.destroy();
                presetSelectEl.html(preset);
                presetSelectizeHandler = initSelectizeSimple(presetSelectEl);

                let noDataFound = ntensors == 0;
                disableEnableSelections(noDataFound);
            },
            immediate: true
        });
    });

    presetSelectEl.change(function () {
        let presetId = presetSelectEl.val();

        postRequest({
            requestSlug: 'koe/get-preset-config',
            data: {
                'preset-id': presetId
            },
            onSuccess (data) {
                disableEnableSelections(true);

                annotatorSelectizeHandler.setValue(data.annotator);
                let features = data.features;
                for (let i = 0; i < features.length; i++) {
                    let feature = features[i];
                    featuresSectionEl.find(`input[value=${feature}]`).prop('checked', true);
                }

                let aggregations = data.aggregations;
                for (let i = 0; i < aggregations.length; i++) {
                    let aggregation = aggregations[i];
                    aggregationsSectionEl.find(`input[value=${aggregation}]`).prop('checked', true);
                }

                ndimsSectionEl.val(data.ndims);
                visualiseBtn.prop('disabled', false);
                downloadBtn.prop('disabled', false);
                dimreduceSectionEl.find(`input[value=${data.dimreduce}]`).prop('checked', true);
            },
            immediate: true
        });
    });
};

/**
 * Download tensor's binary and ids, then turn them into a csv file.
 * The CSV can be HUGE - because it's text, but the binaries are relative small and are static.
 * @param tensorInfo
 */
const downloadTensorDataAsCsv = function (tensorInfo) {
    let body = $('body');
    body.addClass('loading');

    let bytesPath = '/' + tensorInfo['bytes-path'];
    let sidsPath = '/' + tensorInfo['sids-path'];
    let dbname = tensorInfo['database-name'];
    let d = new Date();
    let nowStr = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}_${d.getHours()}-${d.getMinutes()}-${d.getSeconds()}`;
    let filename = `${dbname}-${nowStr}.csv`;

    let downloadSids = downloadRequest(sidsPath, Int32Array);
    let downloadBytes = downloadRequest(bytesPath, Float32Array);

    Promise.all([downloadSids, downloadBytes]).then(function (values) {
        let sids = values[0];
        let bytes = values[1];
        let ncols = bytes.length / sids.length;
        let csvRows = [];
        let byteStart = 0;
        let byteEnd = ncols;
        for (let i = 0; i < sids.length; i++) {
            let sid = sids[i];
            let measurements = bytes.slice(byteStart, byteEnd);
            let csvRow = `${sid},${measurements.join(',')}`;
            csvRows.push(csvRow);
            byteStart += ncols;
            byteEnd += ncols;
        }
        let csvContent = csvRows.join('\n');
        let blob = new Blob([csvContent], {type: 'text/csv;charset=ascii;'});
        body.removeClass('loading');
        downloadBlob(blob, filename);
    });
};

export const postRun = function () {

    form.submit(function (e) {
        e.preventDefault();
        let disabled = form.find(':input:disabled').removeAttr('disabled');
        let formData = form.serialize();
        // re-disabled the set of inputs that you previously enabled
        disabled.attr('disabled', 'disabled');

        let url = this.getAttribute('url');

        postRequest({
            url,
            data: formData,
            onSuccess (data) {
                let formHtml = data.html;

                if (formHtml) {
                    form.find('.replaceable').html(formHtml);
                    initSelectize();
                    return;
                }

                form.callback(data);
            }
        });
        return false;
    });


    let visualiseCallback = function (visualisationUrl) {
        let baseUrl = location.protocol + '//' + location.hostname + (location.port ? ':' + location.port : '');
        let tensorUrl = baseUrl + visualisationUrl;
        window.open(tensorUrl, '_blank');
    };

    let downloadCallback = function (tensorName) {
        postRequest({
            url: getUrl('send-request', 'koe/get-tensor-data-file-paths'),
            data: {'tensor-name': tensorName},
            onSuccess (data) {
                downloadTensorDataAsCsv(data);
            }
        });
    };

    visualiseBtn.click(function () {
        form.callback = visualiseCallback;
        form.submit();

    });

    downloadBtn.click(function () {
        form.callback = downloadCallback;
        form.submit();
    });
};
