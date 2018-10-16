import {initSelectizeSimple} from './selectize-formatter';
import {postRequest} from './ajax-handler';

let dataMatrixSelectEl;
let featuresSectionEl = $('#id_features');
let aggregationsSectionEl = $('#id_aggregations');
let scheduleBtn = $('#schedule-btn');

let dataMatrixSelectizeHandler;

let form = $('#feature-extraction-form');
let database = form.attr('database');
let tmpdb = form.attr('tmpdb');

const dms = {};

export const run = function () {
    readHiddenData();
    removeDisabledData();
    initSelectize();
    initCheckboxes();
    return Promise.resolve();
};

const readHiddenData = function () {
    $('#hidden-data div[name="dms"] div[type="entry"]').each(function (idx, el) {
        let key = el.getAttribute('key');
        let fts = el.getAttribute('fts');
        let ags = el.getAttribute('ags');
        dms[key] = {fts, ags}
    });
    $('#hidden-data').remove();
};

const removeDisabledData = function () {
    let features = [];
    featuresSectionEl.find('input').each(function (idx, el) {
        features.push(parseInt(el.value));
    });
    let aggregations = [];
    aggregationsSectionEl.find('input').each(function (idx, el) {
        aggregations.push(parseInt(el.value));
    });
    $.each(Object.keys(dms), function (idx, id) {
        let dm = dms[id];
        let fts = dm.fts.split('-').map(function (x) {
            return parseInt(x);
        });

        let ags = dm.ags.split('-').map(function (x) {
            return parseInt(x);
        });


        // Intersect, see https://stackoverflow.com/a/1885569/1302520
        fts = fts.filter((value) => features.indexOf(value) !== -1);
        ags = ags.filter((value) => aggregations.indexOf(value) !== -1);

        fts.sort(function (a, b) {
            return a - b;
        });

        ags.sort(function (a, b) {
            return a - b;
        });

        dms[id] = {fts: fts.join('-'), ags: ags.join('-')};
    });
};


const initCheckboxes = function () {
    const detectDataMatrix = function () {
        let features = [];
        featuresSectionEl.find('input:checked').each(function (idx, el) {
            features.push(parseInt(el.value));
        });
        let aggregations = [];
        aggregationsSectionEl.find('input:checked').each(function (idx, el) {
            aggregations.push(parseInt(el.value));
        });
        features.sort(function (a, b) {
            return a - b;
        });
        aggregations.sort(function (a, b) {
            return a - b;
        });
        let fts = features.join('-');
        let ags = aggregations.join('-');
        let dm;
        $.each(dms, function (id, data) {
            if (fts === data.fts && ags === data.ags) {
                dm = id;
                return false;
            }
            return true;
        });

        if (dm) {
            dataMatrixSelectizeHandler.setValue(dm, true);
            scheduleBtn.prop('disabled', true);
        }
        else {
            dataMatrixSelectizeHandler.setValue(null, true);
            scheduleBtn.prop('disabled', false);
        }
    };

    featuresSectionEl.find('input').change(detectDataMatrix);
    aggregationsSectionEl.find('input').change(detectDataMatrix);
};

const initSelectize = function () {
    dataMatrixSelectEl = $('#id_data_matrix');

    dataMatrixSelectizeHandler = initSelectizeSimple(dataMatrixSelectEl);

    dataMatrixSelectEl.change(function () {
        let dmId = dataMatrixSelectEl.val();
        let dm = dms[dmId];
        let features = dm.fts.split('-');
        let aggregations = dm.ags.split('-');

        featuresSectionEl.find('input').prop('checked', false);
        aggregationsSectionEl.find('input').prop('checked', false);

        for (let i = 0; i < features.length; i++) {
            let feature = features[i];
            featuresSectionEl.find(`input[value=${feature}]`).prop('checked', true);
        }

        for (let i = 0; i < aggregations.length; i++) {
            let aggregation = aggregations[i];
            aggregationsSectionEl.find(`input[value=${aggregation}]`).prop('checked', true);
        }
    });
};

export const postRun = function () {
    scheduleBtn.click(function () {
        form.submit();
    });
    form.submit(function (e) {
        e.preventDefault();
        let formData = new FormData(this);
        // let formData = form.serialize();
        if (database) {
            formData.append('database', database);
        }
        else {
            formData.append('tmpdb', tmpdb);
        }

        let url = this.getAttribute('url');

        postRequest({
            url,
            data: formData,
            onSuccess (data) {
                if (data.success) {
                    $('#replaceable-on-success').html(data.html);
                }
                else {
                    form.find('#replaceable-on-failure').html(data.html);
                    initSelectize();
                }
            }
        });
        return false;
    });
    return Promise.resolve();
};
