import { initSelectizeSimple } from "./selectize-formatter";
import { postRequest } from "./ajax-handler";

let dataMatrixSelectEl;
let ordinationSelectEl;
let scheduleBtn = $("#schedule-btn");
let methodSectionEl = $("#id_method");
let ndimsSectionEl = $("#id_ndims");
let paramsSectionEl = $("#id_params");

let dataMatrixSelectizeHandler;
let ordinationSelectizeHandler;

let form = $("#ordination-extraction-form");

const dm2ords = {};
const ordDetails = {};
const ordOptionEls = {};

export const run = function () {
  readHiddenData();
  storeOrdinationOptions();
  initSelectize();
  initMethodNDims();
  return Promise.resolve();
};

const storeOrdinationOptions = function () {
  $("#id_ordination option").each(function (idx, el) {
    let ordId = el.getAttribute("value");
    let wrapper = $("<div>").append($(el).clone()).html();
    ordOptionEls[ordId] = wrapper;
  });
};

const readHiddenData = function () {
  $('#hidden-data div[name="ords"] div[type="entry"]').each(function (idx, el) {
    let ordId = el.getAttribute("key");
    let dmId = el.getAttribute("dm");
    let method = el.getAttribute("method");
    let ndims = el.getAttribute("ndims");
    let params = el.getAttribute("params");
    params = cleanSortParams(params);
    ordDetails[ordId] = { dmId, method, ndims, params };

    if (dmId in dm2ords) {
      dm2ords[dmId].push(ordId);
    } else {
      dm2ords[dmId] = [ordId];
    }
  });
  $("#hidden-data").remove();
};

/**
 * Assert the 'params' value is correctly formatted
 * @param params
 * @returns {*} a sorted, comma separated param string in case the params value is correct
 *              otherwise the original string is returned
 */
function cleanSortParams(params) {
  try {
    let dict = JSON.parse(`x = {${params}`);
    let paramNames = Object.keys(dict);
    paramNames.sort();
    let paramStrings = [];
    $.each(paramNames, function (i, paramName) {
      paramStrings.push(`${paramName}=${dict[paramName]}`);
    });
    return paramStrings.join(",");
  } catch (e) {
    return params;
  }
}

const initMethodNDims = function () {
  const detectOrdination = function () {
    let method_ = methodSectionEl.find("input:checked")[0].value;
    let ndims_ = ndimsSectionEl.val();
    let params_ = paramsSectionEl.val();
    let dmId_ = dataMatrixSelectizeHandler.getValue();
    params_ = cleanSortParams(params_);

    let ordId_;
    $.each(ordDetails, function (ordId, { dmId, method, ndims, params }) {
      if (
        dmId_ == dmId &&
        method_ === method &&
        ndims_ === ndims &&
        params_ === params
      ) {
        ordId_ = ordId;
        return false;
      }
      return true;
    });

    if (ordId_) {
      ordinationSelectizeHandler.setValue(ordId_, true);
      scheduleBtn.prop("disabled", true);
    } else {
      ordinationSelectizeHandler.setValue(null, true);
      scheduleBtn.prop("disabled", false);
    }
  };

  methodSectionEl.find("input").change(detectOrdination);
  ndimsSectionEl.change(detectOrdination);
  paramsSectionEl.change(detectOrdination);
};

const initSelectize = function () {
  dataMatrixSelectEl = $("#id_data_matrix");
  ordinationSelectEl = $("#id_ordination");

  dataMatrixSelectizeHandler = initSelectizeSimple(dataMatrixSelectEl);
  ordinationSelectizeHandler = initSelectizeSimple(ordinationSelectEl);

  dataMatrixSelectEl.change(function () {
    let dmId = dataMatrixSelectEl.val();
    ordinationSelectizeHandler.destroy();
    let selectableOrds;
    if (dmId) {
      selectableOrds = dm2ords[dmId];
    } else {
      selectableOrds = [];
      $.each(dm2ords, function (dm, ords) {
        selectableOrds = selectableOrds.concat(ords);
      });
    }

    let selectEl = '<option value="">---------</option>';
    $.each(selectableOrds, function (idx, ord) {
      selectEl += ordOptionEls[ord];
    });
    ordinationSelectEl.html(selectEl);
    ordinationSelectizeHandler = initSelectizeSimple(ordinationSelectEl);
  });

  ordinationSelectEl.change(function () {
    let ordId = ordinationSelectEl.val();
    let { dmId, method, ndims, params } = ordDetails[ordId];
    dataMatrixSelectizeHandler.setValue(dmId, true);
    methodSectionEl.find("input").prop("checked", false);
    methodSectionEl.find(`input[value=${method}]`).prop("checked", true);
    ndimsSectionEl.val(ndims);
    paramsSectionEl.val(params);
    scheduleBtn.prop("disabled", true);
  });
};

export const postRun = function () {
  scheduleBtn.click(function () {
    form.submit();
  });

  form.submit(function (e) {
    e.preventDefault();
    let formData = new FormData(this);

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
  return Promise.resolve();
};
