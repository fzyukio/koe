import * as fg from "flexible-grid";
import {defaultGridOptions} from "./flexible-grid";
import {getUrl, deepCopy, log} from "./utils";

const gridOptions = deepCopy(defaultGridOptions);

class SegmentGrid extends fg.FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'version-grid',
            'grid-type': 'version-grid',
            'default-field': 'label_family',
            gridOptions: gridOptions
        });
    };

    rowChangeHandler(e, args) {
        super.rowChangeHandler(e, args, generalResponseHandler);
    }
}

const grid = new SegmentGrid();
const applyVersionBtn = $('#apply-version-btn');
const deleteVersionBtn = $('#delete-version-btn');
const importZipBtn = $('#import-zip-btn');
const fileUploadForm = $('#file-upload-form');
const fileUploadBtn = fileUploadForm.find('input[type=submit]');
const fileUploadInput = fileUploadForm.find('input[type=file]');
let ce;

/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    grid.on('row-added', function (e, args) {
        applyVersionBtn.prop('disabled', false);
        deleteVersionBtn.prop('disabled', false);

        let versionId = args.item.id;
        let versionName = args.item.url;

        ce.dialogModal
            .data("versionId", versionId)
            .data("versionName", versionName);

    });
};

/**
 * Display error in the alert box if a request failed, and vice versa
 * @param response
 */
const generalResponseHandler = function (response) {
    let message = `Success`;
    let alertEl = ce.alertSuccess;
    if (response != 'ok') {
        message = `Something's wrong. The server says "${response}".`;
        alertEl = ce.alertFailure;
    }
    alertEl.html(message);
    alertEl.fadeIn().delay(4000).fadeOut(400);
};

/**
 * Redraw the table on orientation changed
 */
export const orientationChange = function () {
    grid.redrawMainGrid({rowMoveable: false, radioSelect: true});
};


const initApplyVersionBtn = function () {
    applyVersionBtn.click(function () {
        let versionId = ce.dialogModal.data("versionId");
        let versionName = ce.dialogModal.data("versionName");

        ce.dialogModalTitle.html("Confirm import history");
        ce.dialogModalBody.html(
            `Importing history from will erase your current data.
             Make sure you have saved the current version before doing this.
             Are you sure you want to import ${versionName}?`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.one('click', function (e) {
            let url = getUrl('send-request', 'koe/import-history');
            $.post(url, {'version-id': versionId}, function (response) {
                let message = `Verison ${versionName} successfully imported`;
                let alertEl = ce.alertSuccess;
                if (response != 'ok') {
                    message = `Something's wrong. The server says ${response}. Version not imported.
                     But good news is your current data is still intact.`
                    alertEl = ce.alertFailure
                }
                alertEl.html(message);
                alertEl.fadeIn().delay(4000).fadeOut(400);
            });
            ce.dialogModal.modal('hide');
        })
    });
};


const initDeleteVersionBtn = function () {
    deleteVersionBtn.click(function () {
        let versionId = ce.dialogModal.data("versionId");
        let versionName = ce.dialogModal.data("versionName");

        ce.dialogModalTitle.html("Confirm delete history");
        ce.dialogModalBody.html(
            `Are you sure you want to delete ${versionName}?`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.one('click', function (e) {
            let url = getUrl('send-request', 'koe/delete-history');
            $.post(url, {'version-id': versionId}, function (response) {
                let message = `Verison ${versionName} successfully deleted. This page will reload`;
                let alertEl = ce.alertSuccess;
                let callback = function () {
                    location.reload();
                };
                if (response != 'ok') {
                    message = `Something's wrong. The server says ${response}. Version might have been deleted.`;
                    alertEl = ce.alertFailure;
                    callback = undefined;
                }
                alertEl.html(message);
                alertEl.fadeIn().delay(4000).fadeOut(400, callback);
            });
            ce.dialogModal.modal('hide');
        })
    });
};


/**
 * On click the user can chose a file that contains the history to upload and replace the current workspace
 */
const initImportZipBtn = function () {
    let url = getUrl('send-request', 'koe/import-history');
    importZipBtn.click(function (e) {
        fileUploadInput.click();
    });

    fileUploadInput.change(function (e) {
        fileUploadBtn.click();
    });

    const responseHandler = function (response) {
        let message = `File ${this.filename} successfully imported`;
        let alertEl = ce.alertSuccess;
        if (response != 'ok') {
            message = `Something's wrong. The server says "${response}". Version not imported.
                       But good news is your current data is still intact.`;
            alertEl = ce.alertFailure;
        }
        alertEl.html(message);
        alertEl.fadeIn().delay(4000).fadeOut(400);
    };

    fileUploadForm.submit(function (e) {
        e.preventDefault();
        let filename = fileUploadInput.val();
        let formData = new FormData(this);
        $.ajax({
            url: url,
            type: 'POST',
            data: formData,
            success: responseHandler.bind({filename: filename}),
            // !IMPORTANT: this tells jquery to not set expectation of the content type.
            // If not set to false it will not send the file
            contentType: false,

            // !IMPORTANT: this tells jquery to not convert the form data into string.
            // If not set to false it will raise "IllegalInvocation" exception
            processData: false
        });
    });

};

export const run = function (commonElements) {
    console.log("History page is now running.");
    ce = commonElements;

    grid.init();
    grid.initMainGridHeader({rowMoveable: false, radioSelect: true}, function () {
        grid.initMainGridContent();
    });
};

export const postRun = function () {
    subscribeFlexibleEvents();
    initApplyVersionBtn();
    initDeleteVersionBtn();
    initImportZipBtn();
};