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
let ce;

/**
 *
 */
const subscribeEvents = function () {
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
 * Redraw the table on orientation changed
 */
export const orientationChange = function () {
    grid.redrawMainGrid({rowMoveable: false, radioSelect: true});
    subscribeEvents();
};


export const run = function (commonElements) {
    console.log("History page is now running.");
    ce = commonElements;

    grid.init();
    grid.initMainGridHeader({rowMoveable: false, radioSelect: true}, function () {
        grid.initMainGridContent();
    });

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
            let url = utils.getUrl('fetch-data', 'koe/import-history');
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
            ce.dialogModal.modal("hide");
        })
    });

    deleteVersionBtn.click(function () {
        let versionId = ce.dialogModal.data("versionId");
        let versionName = ce.dialogModal.data("versionName");

        ce.dialogModalTitle.html("Confirm delete history");
        ce.dialogModalBody.html(
            `Are you sure you want to delete ${versionName}?`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.one('click', function (e) {
            let url = utils.getUrl('fetch-data', 'koe/delete-history');
            $.post(url, {'version-id': versionId}, function (response) {
                let message = `Verison ${versionName} successfully deleted. This page will reload`;
                let alertEl = ce.alertSuccess;
                let callback = function () {location.reload();};
                if (response != 'ok') {
                    message = `Something's wrong. The server says ${response}. Version might have been deleted.`;
                    alertEl = ce.alertFailure;
                    callback = undefined;
                }
                alertEl.html(message);
                alertEl.fadeIn().delay(4000).fadeOut(400, callback);
            });
            ce.dialogModal.modal("hide");
        })
    });
};

export const postRun = function () {
    subscribeEvents();
};