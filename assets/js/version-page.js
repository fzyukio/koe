import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {deepCopy} from './utils';
import {postRequest, uploadRequest} from './ajax-handler';

const gridOptions = deepCopy(defaultGridOptions);

class SegmentGrid extends FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'versions',
            'grid-type': 'version-grid',
            'default-field': 'label_family',
            gridOptions
        });
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
    grid.on('row-added', function () {
        applyVersionBtn.prop('disabled', false);
        deleteVersionBtn.prop('disabled', false);
    });
};

/**
 * Redraw the table on orientation changed
 */
export const orientationChange = function () {
    grid.redrawMainGrid({
        rowMoveable: false,
        radioSelect: true
    });
};


const initApplyVersionBtn = function () {
    applyVersionBtn.click(function () {
        let grid_ = grid.mainGrid;
        let selectedRow = grid_.getSelectedRows()[0];
        let dataView = grid_.getData();
        let item = dataView.getItem(selectedRow);

        ce.dialogModalTitle.html('Confirm import history');
        ce.dialogModalBody.html(`Importing history from will erase your current data.
             Make sure you have saved the current version before doing this.
             Are you sure you want to import ${item.url}?`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.one('click', function () {
            let postData = {'version-id': item.id};
            let msgGen = function (res) {
                return res.success ?
                    `Verison ${item.url} successfully imported` :
                    `Something's wrong. The server says ${res.error}. Version not imported.
                       But good news is your current data is still intact.`;
            };
            ce.dialogModal.modal('hide');
            postRequest({requestSlug: 'koe/import-history',
                data: postData,
                msgGen});
        })
    });
};


const initDeleteVersionBtn = function () {
    deleteVersionBtn.click(function () {
        let grid_ = grid.mainGrid;
        let selectedRow = grid_.getSelectedRows()[0];
        let dataView = grid_.getData();
        let item = dataView.getItem(selectedRow);

        ce.dialogModalTitle.html('Confirm delete history');
        ce.dialogModalBody.html(`Are you sure you want to delete ${item.url}?`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.one('click', function () {
            let postData = {'version-id': item.id};
            let onSuccess = function () {
                dataView.deleteItem(item.id);
            };
            ce.dialogModal.modal('hide');
            postRequest({requestSlug: 'koe/delete-history',
                data: postData,
                onSuccess});
        })
    });
};


/**
 * On click the user can chose a file that contains the history to upload and replace the current workspace
 */
const initImportZipBtn = function () {
    importZipBtn.click(function () {
        fileUploadInput.click();
    });

    fileUploadInput.change(function () {
        fileUploadBtn.click();
    });

    fileUploadForm.submit(function (e) {
        e.preventDefault();
        let filename = fileUploadInput.val();
        let formData = new FormData(this);

        let msgGen = function (res) {
            return res.success ?
                `File ${filename} successfully imported` :
                `Something's wrong. The server says "${res.error}". Version not imported. 
                But good news is your current data is still intact.`;
        };

        uploadRequest({requestSlug: 'koe/import-history',
            data: formData,
            msgGen});
    });

};

export const run = function (commonElements) {
    ce = commonElements;

    grid.init();
    grid.initMainGridHeader({
        rowMoveable: false,
        radioSelect: true
    }, function () {
        grid.initMainGridContent();
    });
};

export const postRun = function () {
    subscribeFlexibleEvents();
    initApplyVersionBtn();
    initDeleteVersionBtn();
    initImportZipBtn();
};
