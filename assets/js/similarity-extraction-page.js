import { initSelectizeSimple } from "./selectize-formatter";
import { postRequest } from "./ajax-handler";

let dataMatrixSelectEl;
let ordinationSelectEl;
let scheduleBtn = $("#schedule-btn");

let dataMatrixSelectizeHandler;
let ordinationSelectizeHandler;

let form = $("#similarity-extraction-form");

export const run = function () {
  initSelectize();
  return Promise.resolve();
};

const initSelectize = function () {
  dataMatrixSelectEl = $("#id_data_matrix");
  ordinationSelectEl = $("#id_ordination");

  dataMatrixSelectizeHandler = initSelectizeSimple(dataMatrixSelectEl);
  ordinationSelectizeHandler = initSelectizeSimple(ordinationSelectEl);

  dataMatrixSelectEl.change(function () {
    ordinationSelectizeHandler.setValue(null, true);
    scheduleBtn.prop("disabled", false);
  });

  ordinationSelectEl.change(function () {
    dataMatrixSelectizeHandler.setValue(null, true);
    scheduleBtn.prop("disabled", false);
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
