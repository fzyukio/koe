import { initSelectizeSimple } from "./selectize-formatter";
import {
  postRequest,
  downloadRequest,
  createSpinner,
  postPromise,
} from "./ajax-handler";
import { toJSONLocal, downloadBlob, getUrl } from "./utils";

let dataMatrixSelectEl;
let featuresSectionEl = $("#id_features");
let aggregationsSectionEl = $("#id_aggregations");
let nameSectionEl = $("#id_name");
let scheduleBtn = $("#schedule-btn");
let recreateBtn = $("#recreate-btn");
let downloadBtn = $("#download-btn");

let dataMatrixSelectizeHandler;

let form = $("#feature-extraction-form");
let database = form.attr("database");
let tmpdb = form.attr("tmpdb");

const dms = {};

const switchRecreateSubmitBtns = function (dmExists) {
  // If dm already exists, the submit button is hidden and recreate button shown
  // Otherwise, reverse
  if (dmExists) {
    scheduleBtn.parent().hide();
    recreateBtn.parent().show();

    scheduleBtn.prop("disabled", true);
    recreateBtn.prop("disabled", false);
    downloadBtn.prop("disabled", false);
  } else {
    scheduleBtn.parent().show();
    recreateBtn.parent().hide();

    scheduleBtn.prop("disabled", false);
    recreateBtn.prop("disabled", true);
    downloadBtn.prop("disabled", true);
  }
};

export const run = function () {
  readHiddenData();
  removeDisabledData();
  initSelectize();
  initCheckboxes();
  return Promise.resolve();
};

const readHiddenData = function () {
  $('#hidden-data div[name="dms"] div[type="entry"]').each(function (idx, el) {
    let key = el.getAttribute("key");
    let fts = el.getAttribute("fts");
    let ags = el.getAttribute("ags");
    let name = el.getAttribute("name");
    dms[key] = { fts, ags, name };
  });
  $("#hidden-data").remove();
};

const removeDisabledData = function () {
  let features = [];
  featuresSectionEl.find("input").each(function (idx, el) {
    features.push(parseInt(el.value));
  });
  let aggregations = [];
  aggregationsSectionEl.find("input").each(function (idx, el) {
    aggregations.push(parseInt(el.value));
  });
  $.each(Object.keys(dms), function (idx, id) {
    let dm = dms[id];
    let name = dm.name;
    let fts = dm.fts.split("-").map(function (x) {
      return parseInt(x);
    });

    let ags = dm.ags.split("-").map(function (x) {
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

    dms[id] = { fts: fts.join("-"), ags: ags.join("-"), name };
  });
};

const initCheckboxes = function () {
  const detectDataMatrix = function () {
    let features = [];
    featuresSectionEl.find("input:checked").each(function (idx, el) {
      features.push(parseInt(el.value));
    });
    let aggregations = [];
    aggregationsSectionEl.find("input:checked").each(function (idx, el) {
      aggregations.push(parseInt(el.value));
    });
    features.sort(function (a, b) {
      return a - b;
    });
    aggregations.sort(function (a, b) {
      return a - b;
    });
    let fts = features.join("-");
    let ags = aggregations.join("-");
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
      switchRecreateSubmitBtns(true);
    } else {
      dataMatrixSelectizeHandler.setValue(null, true);
      switchRecreateSubmitBtns(false);
    }
  };

  featuresSectionEl.find("input").change(detectDataMatrix);
  aggregationsSectionEl.find("input").change(detectDataMatrix);
};

const initSelectize = function () {
  dataMatrixSelectEl = $("#id_data_matrix");

  dataMatrixSelectizeHandler = initSelectizeSimple(dataMatrixSelectEl);

  dataMatrixSelectEl.change(function () {
    let dmId = dataMatrixSelectEl.val();
    let dm = dms[dmId];
    let features = dm.fts.split("-");
    let aggregations = dm.ags.split("-");
    let name = dm.name;

    featuresSectionEl.find("input").prop("checked", false);
    aggregationsSectionEl.find("input").prop("checked", false);

    for (let i = 0; i < features.length; i++) {
      let feature = features[i];
      featuresSectionEl.find(`input[value=${feature}]`).prop("checked", true);
    }

    for (let i = 0; i < aggregations.length; i++) {
      let aggregation = aggregations[i];
      aggregationsSectionEl
        .find(`input[value=${aggregation}]`)
        .prop("checked", true);
    }

    nameSectionEl.val(name);
    switchRecreateSubmitBtns(true);
  });
};

/**
 * Download tensor's binary and ids, then turn them into a csv file.
 * The CSV can be HUGE - because it's text, but the binaries are relative small and are static.
 * @param tensorInfo
 */
const downloadDataMatrixAsCsv = function (tensorInfo) {
  let spinner = createSpinner();
  spinner.start();

  let bytesPath = "/" + tensorInfo["bytes-path"];
  let sidsPath = "/" + tensorInfo["sids-path"];
  let colPath = "/" + tensorInfo["cols-path"];

  let dbname = tensorInfo["database-name"];
  let d = new Date();
  let dateString = toJSONLocal(d);
  let filename = `${dbname}-${dateString}.csv`;

  let downloadSids = downloadRequest(sidsPath, Int32Array);
  let downloadBytes = downloadRequest(bytesPath, Float32Array);
  let downloadCols = downloadRequest(colPath, null);

  let downloadSegmentInfo = postPromise({
    url: getUrl("send-request", "koe/get-sid-info"),
    data: { path: sidsPath },
  });

  /**
   * Create a list of column names to use as header of the CSV file
   * @param ncols number of measurement columns
   * @param columnsInfo a dictionary of features and the columns they occupy
   * @returns {Array}
   */
  function createCsvHeader(ncols, columnsInfo) {
    let headers = new Array(ncols);
    $.each(columnsInfo, function (featureName, colIndices) {
      let colIndBeg = colIndices[0];
      let colIndEnd = colIndices[1];
      if (colIndEnd - colIndBeg == 1) {
        headers[colIndBeg] = featureName;
      } else {
        let dimInd = 0;
        for (let colInd = colIndBeg; colInd < colIndEnd; colInd++) {
          let colName = `${featureName}/${dimInd}`;
          dimInd++;
          headers[colInd] = colName;
        }
      }
    });
    return headers;
  }

  Promise.all([
    downloadSegmentInfo,
    downloadSids,
    downloadBytes,
    downloadCols,
  ]).then(function (values) {
    let segInfo = values[0][0];
    let songInfo = values[0][1];
    let sids = values[1];
    let bytes = values[2];
    let cols = values[3];
    let columnsInfo = JSON.parse(cols);
    let ncols = bytes.length / sids.length;
    let measurementColumnsHeader = createCsvHeader(ncols, columnsInfo);
    let firstColumnsHeaders = [
      "Song name",
      "Unique ID",
      "Start (ms)",
      "End (ms)",
    ];
    let csvHeader = firstColumnsHeaders.concat(measurementColumnsHeader);
    csvHeader = csvHeader.join(",");

    let csvRows = [csvHeader];
    let byteStart = 0;
    let byteEnd = ncols;
    for (let i = 0; i < sids.length; i++) {
      let sid = sids[i];
      let info = segInfo[i];
      let songId = info[0];
      let startMs = info[1];
      let endMs = info[2];
      let songName = songInfo[songId];
      let measurements = bytes.slice(byteStart, byteEnd);
      let csvRow = `${songName},${sid},${startMs},${endMs},${measurements.join(
        ","
      )}`;
      csvRows.push(csvRow);
      byteStart += ncols;
      byteEnd += ncols;
    }
    let csvContent = csvRows.join("\n");
    let blob = new Blob([csvContent], { type: "text/csv;charset=ascii;" });

    spinner.clear();
    downloadBlob(blob, filename, true);
  });
};

export const postRun = function () {
  scheduleBtn.click(function () {
    form.submit();
  });
  recreateBtn.click(function () {
    form.submit();
  });
  downloadBtn.click(function () {
    let dmId = dataMatrixSelectEl.val();
    postRequest({
      url: getUrl("send-request", "koe/get-datamatrix-file-paths"),
      data: { dmid: dmId },
      onSuccess(data) {
        downloadDataMatrixAsCsv(data);
      },
    });
  });
  form.submit(function (e) {
    e.preventDefault();
    let formData = new FormData(this);
    // let formData = form.serialize();
    if (database) {
      formData.append("database", database);
    } else {
      formData.append("tmpdb", tmpdb);
    }

    let url = this.getAttribute("url");

    postRequest({
      url,
      data: formData,
      onSuccess(data) {
        if (data.success) {
          $("#replaceable-on-success").html(data.html);
        } else {
          form.find("#replaceable-on-failure").html(data.html);
          initSelectize();
        }
      },
    });
    return false;
  });
  switchRecreateSubmitBtns(false);
  return Promise.resolve();
};
