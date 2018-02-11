import * as fg from "flexible-grid";
import * as utils from "./utils";
import {defaultGridOptions} from "./flexible-grid";

const gridOptions = utils.deepCopy(defaultGridOptions);


class SegmentGrid extends fg.FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'version-grid',
            'grid-type': 'version-grid',
            'default-field': 'label_family',
            gridOptions: gridOptions
        });
    };
}

const grid = new SegmentGrid();
const applyVersionBtn = $('#apply-version-btn');
const deleteVersionBtn = $('#delete-version-btn');
const dialogModal = $('#dialog-modal');
const dialogModalTitle = dialogModal.find('.modal-title');
const dialogModalBody = dialogModal.find('.modal-body');
const dialogModalOkBtn = dialogModal.find("#dialog-modal-yes-button");
const alertSuccess = $('.alert-success');
const alertFailure = $('.alert-danger');


/**
 *
 */
const subscribeEvents = function () {
    grid.on('row-added', function (e, args) {
        applyVersionBtn.prop('disabled', false);
        deleteVersionBtn.prop('disabled', false);

        let versionId = args.item.id;
        let versionName = args.item.url;

        dialogModal
            .data("versionId", versionId)
            .data("versionName", versionName);

    });
};

/**
 * Redraw the table on orientation changed
 */
export const orientationChange = function () {
    grid.redrawMainGrid({rowMoveable: false, radioSelect: true});
    subscribeEvents();
};


export const run = function () {
    console.log("History page is now running.");

    grid.init();
    grid.initMainGridHeader({rowMoveable: false, radioSelect: true}, function () {
        grid.initMainGridContent();
    });

    applyVersionBtn.click(function () {
        let versionId = dialogModal.data("versionId");
        let versionName = dialogModal.data("versionName");

        dialogModalTitle.html("Confirm import history");
        dialogModalBody.html(
            `Importing history from will erase your current data.
             Make sure you have saved the current version before doing this.
             Are you sure you want to import ${versionName}?`);

        dialogModal.modal('show');

        dialogModalOkBtn.one('click', function (e) {
            let url = utils.getUrl('fetch-data', 'koe/import-history');
            $.post(url, {'version-id': versionId}, function (response) {
                let message = `Verison ${versionName} successfully imported`;
                let alertEl = alertSuccess;
                if (response != 'ok') {
                    message = `Something's wrong. The server says ${response}. Version not imported.
                     But good news is your current data is still intact.`
                    alertEl = alertFailure
                }
                alertEl.html(message);
                alertEl.fadeIn().delay(4000).fadeOut(400);
            });
            dialogModal.modal("hide");
        })
    });

    deleteVersionBtn.click(function () {
        let versionId = dialogModal.data("versionId");
        let versionName = dialogModal.data("versionName");

        dialogModalTitle.html("Confirm delete history");
        dialogModalBody.html(
            `Are you sure you want to delete ${versionName}?`);

        dialogModal.modal('show');

        dialogModalOkBtn.one('click', function (e) {
            let url = utils.getUrl('fetch-data', 'koe/delete-history');
            $.post(url, {'version-id': versionId}, function (response) {
                let message = `Verison ${versionName} successfully deleted. This page will reload`;
                let alertEl = alertSuccess;
                let callback = function () {location.reload();};
                if (response != 'ok') {
                    message = `Something's wrong. The server says ${response}. Version might have been deleted.`;
                    alertEl = alertFailure;
                    callback = undefined;
                }
                alertEl.html(message);
                alertEl.fadeIn().delay(4000).fadeOut(400, callback);
            });
            dialogModal.modal("hide");
        })
    });
};

export const postRun = function () {
    subscribeEvents();
};