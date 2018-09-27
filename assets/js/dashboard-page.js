import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {deepCopy, getUrl, getCache, setCache} from './utils';
import {postRequest, uploadRequest} from './ajax-handler';

const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 50;

const databaseGrid = new FlexibleGrid();
const dbAssignmentGrid = new FlexibleGrid();
const versionGrid = new FlexibleGrid();
const syllableGrid = new FlexibleGrid();

const backupBtns = $('.back-up-data');
const applyVersionBtn = $('#apply-version-btn');
const deleteVersionBtn = $('#delete-version-btn');
const importZipBtn = $('#import-zip-btn');
const fileUploadForm = $('#file-upload-form');
const fileUploadBtn = fileUploadForm.find('input[type=submit]');
const fileUploadInput = fileUploadForm.find('input[type=file]');
const addCollaborator = $('#add-collaborator');
const createDatabaseBtn = $('#create-database-btn');

const selected = {
    databaseId: undefined
};

let databaseExtraArgs = {};
let dbAssignmentExtraArgs = {};
let versionExtraArgs = {};
let syllableExtraArgs = {};

let databaseGridArgs = {
    radioSelect: true,
};

let dbAssignmentGridArgs = {
    doCacheSelectableOptions: false
};

let versionGridArgs = {
    radioSelect: true,
    doCacheSelectableOptions: false
};

let syllableGridArgs = {};

let ce;

/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    versionGrid.on('row-added', function (e, args) {
        let item = args.item;
        if (item.__can_import) {
            applyVersionBtn.prop('disabled', false);
        }
        else {
            applyVersionBtn.prop('disabled', true);
        }
        if (item.__can_delete) {
            deleteVersionBtn.prop('disabled', false);
        }
        else {
            applyVersionBtn.prop('disabled', true);
        }
    });
};


const initApplyVersionBtn = function () {
    applyVersionBtn.click(function () {
        let grid_ = versionGrid.mainGrid;
        let selectedRow = grid_.getSelectedRows()[0];
        let dataView = grid_.getData();
        let item = dataView.getItem(selectedRow);

        ce.dialogModalTitle.html('Confirm import history');
        ce.dialogModalBody.html(`Importing history from will erase your current data.
             Make sure you have saved the current version before doing this.
             Are you sure you want to import ${item.url}?`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.on('click', function () {
            let msgGen = function (isSuccess, response) {
                return isSuccess ?
                    `Verison ${item.url} successfully imported` :
                    `Something's wrong. The server says ${response}. Version not imported. 
                    But good news is your current data is still intact.`;
            };
            ce.dialogModal.modal('hide');
            postRequest({
                requestSlug: 'koe/import-history',
                data: {'version-id': item.id},
                msgGen,
                onSuccess: reloadSyllableGrid
            });
        })
    });
};


const initDeleteVersionBtn = function () {
    deleteVersionBtn.click(function () {
        let grid_ = versionGrid.mainGrid;
        let selectedRow = grid_.getSelectedRows()[0];
        let dataView = grid_.getData();
        let item = dataView.getItem(selectedRow);

        ce.dialogModalTitle.html('Confirm delete history');
        ce.dialogModalBody.html(`Are you sure you want to delete ${item.url}?`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.on('click', function () {
            let onSuccess = function () {
                dataView.deleteItem(item.id);
            };
            ce.dialogModal.modal('hide');
            postRequest({
                requestSlug: 'koe/delete-history',
                data: {'version-id': item.id},
                onSuccess
            });
        })
    });
};


const reloadSyllableGrid = function () {
    syllableGrid.initMainGridHeader(syllableGridArgs, syllableExtraArgs, function () {
        syllableGrid.initMainGridContent(syllableGridArgs, syllableExtraArgs);
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

        let msgGen = function (isSuccess, response) {
            return isSuccess ?
                `File ${filename} successfully imported` :
                `Something's wrong. The server says "${response}". Version not imported. 
                But good news is your current data is still intact.`;
        };

        uploadRequest({
            requestSlug: 'koe/import-history',
            data: formData,
            msgGen,
            onSuccess: reloadSyllableGrid
        });
    });
};


const injectSelectableOptions = function () {
    let permissionConstants = getCache('literals', 'DatabasePermission');
    let options = [];
    $.each(permissionConstants, function (label, value) {
        options.push({
            label,
            value
        });
    });

    let selectizeOptions = {
        valueField: 'value',
        labelField: 'label',
        searchField: 'label',
        create: false,
        selectOnTab: false,
        openOnFocus: true,
        dropdownDirection: 'auto',
        render: {
            option (item) {
                return `<div>${item.label}</div>`;
            }
        },
    };

    let renderOptions = {
        options,
        selectizeOptions
    };

    setCache('selectableOptions', '__render-options__permission', renderOptions);
};

export const run = function (commonElements) {
    ce = commonElements;
    injectSelectableOptions();

    databaseGrid.init({
        'grid-name': 'database',
        'grid-type': 'database-grid',
        'default-field': 'name',
        gridOptions
    });

    dbAssignmentGrid.init({
        'grid-name': 'database-assignment',
        'grid-type': 'database-assignment-grid',
        'default-field': 'username',
        gridOptions
    });

    versionGrid.init({
        'grid-name': 'version',
        'grid-type': 'version-grid',
        'default-field': 'note',
        gridOptions
    });

    syllableGrid.init({
        'grid-name': 'concise-syllables',
        'grid-type': 'concise-syllables-grid',
        'default-field': 'label',
        gridOptions
    });

    databaseGrid.initMainGridHeader(databaseGridArgs, databaseExtraArgs, function () {
        databaseGrid.initMainGridContent(databaseGridArgs, databaseExtraArgs);
    });

    databaseGrid.on('row-added', function (e, args) {
        selected.databaseId = args.item.id;
        dbAssignmentExtraArgs.database = selected.databaseId;
        versionExtraArgs.database = selected.databaseId;
        syllableExtraArgs.database = selected.databaseId;

        backupBtns.prop('disabled', false);
        addCollaborator.prop('disabled', false);

        dbAssignmentGrid.initMainGridHeader(dbAssignmentGridArgs, dbAssignmentExtraArgs, function () {
            dbAssignmentGrid.initMainGridContent(dbAssignmentGridArgs, dbAssignmentExtraArgs);
        });

        versionGrid.initMainGridHeader(versionGridArgs, versionExtraArgs, function () {
            versionGrid.initMainGridContent(versionGridArgs, versionExtraArgs);
        });

        reloadSyllableGrid();
    });
};

const inputText = $('<input type="text" class="form-control"/>');

const dialogModal = $('#dialog-modal');
const dialogModalTitle = dialogModal.find('.modal-title');
const dialogModalBody = dialogModal.find('.modal-body');
const dialogModalOkBtn = dialogModal.find('#dialog-modal-yes-button');


/**
 * When user clicks on the "create new database" button from the drop down menu, show a dialog
 * asking for name. Send the name to the server to check for duplicate. If there exists a database with the same name,
 * repeat this process. Only dismiss the dialog if a new database is created.
 */
function initCreateDatabaseButton() {

    /**
     * Repeat showing the dialog until the database name is valid
     * param error to be shown in the modal if not undefined
     */
    function showDialog(error) {
        dialogModalTitle.html('Creating a new database...');
        dialogModalBody.html('<label>Give it a name</label>');
        dialogModalBody.append(inputText);
        if (error) {
            dialogModalBody.append(`<p>${error.message}</p>`);
        }

        dialogModal.modal('show');

        dialogModalOkBtn.one('click', function () {
            dialogModal.modal('hide');
            let url = getUrl('send-request', 'koe/create-database');
            let databaseName = inputText.val();
            inputText.val('');

            $.post(url, {name: databaseName}).done(function (data) {
                data = JSON.parse(data);
                let row = data.message;
                dialogModal.one('hidden.bs.modal', function () {
                    databaseGrid.appendRowAndHighlight(row);
                });
                dialogModal.modal('hide');
            }).fail(function (response) {
                dialogModal.one('hidden.bs.modal', function () {
                    let errorMessage = JSON.parse(response.responseText);
                    showDialog(errorMessage);
                });
                dialogModal.modal('hide');
            });
        });
    }

    createDatabaseBtn.on('click', function (e) {
        e.preventDefault();
        showDialog();
    });
}


const initSaveVersionBtns = function () {
    backupBtns.click(function () {
        let backUpType = $(this).data('backup-type');

        ce.inputText.val('');

        ce.dialogModalTitle.html('Backing up your data...');
        ce.dialogModalBody.html('<label>Give it a comment (optional)</label>');
        ce.dialogModalBody.append(ce.inputText);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.on('click', function () {
            let value = ce.inputText.val();
            ce.inputText.val('');

            ce.dialogModal.modal('hide');
            let postData = {
                comment: value,
                database: selected.databaseId,
                type: backUpType
            };
            let msgGen = function (isSuccess, response) {
                return isSuccess ?
                    'History saved successfully' :
                    `Something's wrong, server says ${response}. Version not saved.`;
            };
            postRequest({
                requestSlug: 'koe/save-history',
                data: postData,
                msgGen,
                onSuccess(row) {
                    versionGrid.appendRowAndHighlight(row);
                }
            });
        });
    });
};

/**
 * When user clicks on the "Add collaborator" button, show a dialog asking for user's name or email.
 * Send this name back to the server, if everything checks out, add the new database assignment to the table.
 * Otherwise repeat this process. Only dismiss the dialog if successful.
 */
function initAddCollaboratorBtn() {

    /**
     * Repeat showing the dialog until the database name is valid
     * param error to be shown in the modal if not undefined
     */
    function showDialog(error) {
        dialogModalTitle.html('Add user as collaborator...');
        dialogModalBody.html('<label>Name or email address of your collaborator</label>');
        dialogModalBody.append(inputText);
        if (error) {
            dialogModalBody.append(`<p>${error.message}</p>`);
        }

        dialogModal.modal('show');

        dialogModalOkBtn.one('click', function () {
            dialogModal.modal('hide');
            let url = getUrl('send-request', 'koe/add-collaborator');
            let userNameOrEmail = inputText.val();
            inputText.val('');
            let postData = {
                user: userNameOrEmail,
                database: selected.databaseId
            };

            $.post(url, postData).done(function (data) {
                data = JSON.parse(data);
                let row = data.message;
                dialogModal.one('hidden.bs.modal', function () {
                    dbAssignmentGrid.appendRowAndHighlight(row);
                });
                dialogModal.modal('hide');
            }).fail(function (response) {
                dialogModal.one('hidden.bs.modal', function () {
                    let errorMessage = JSON.parse(response.responseText);
                    showDialog(errorMessage);
                });
                dialogModal.modal('hide');
            });
        });
    }

    addCollaborator.click(function (e) {
        e.preventDefault();
        showDialog();
    })
}

export const postRun = function () {
    initCreateDatabaseButton();
    initAddCollaboratorBtn();
    initSaveVersionBtns();
    initApplyVersionBtn();
    initDeleteVersionBtn();
    initImportZipBtn();
    subscribeFlexibleEvents();
};
