import {initSelectizeSimple} from './selectize-formatter';
import {postRequest} from './ajax-handler';

let databaseSelectEl;
let annotatorSelectEl;
let presetSelectEl;
let featuresSectionEl = $('#id_features');
let aggregationsSectionEl = $('#id_aggregations');
let dimreduceSectionEl = $('#id_dimreduce');
let ndimsSectionEl = $('#id_ndims');
let visualiseBtn = $('#visualise-btn');

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
                dimreduceSectionEl.find(`input[value=${data.dimreduce}]`).prop('checked', true);
            },
            immediate: true
        });
    });
};

export const postRun = function () {
    visualiseBtn.click(function () {
        form.submit();
    });

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

                let tensorName = data;

                let baseUrl = location.protocol + '//' + location.hostname + (location.port ? ':' + location.port : '');
                let pageUrl = visualiseBtn.attr('page-url');
                let tensorUrl = baseUrl + pageUrl.replace('replaceme', tensorName);

                window.open(tensorUrl, '_blank');
            }
        });
        return false;
    });

};
