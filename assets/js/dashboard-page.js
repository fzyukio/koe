import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {deepCopy, getUrl, getCache, setCache} from './utils';
import {postRequest, uploadRequest} from './ajax-handler';
import {replaceSidebar} from './sidebar';
import ReactDOM from "react-dom";
import React from "react";
import NewDatabaseButton from "react-components/NewDatabaseButton";

const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 50;

const databaseGrid = new FlexibleGrid();
const collectionGrid = new FlexibleGrid();
const dbAssignmentGrid = new FlexibleGrid();
const versionGrid = new FlexibleGrid();
const syllableGrid = new FlexibleGrid();

const deleteCollections = $('#delete-selected');
const backupBtns = $('.back-up-data');
const applyVersionBtn = $('#apply-version-btn');
const deleteVersionBtn = $('#delete-version-btn');
const importZipBtn = $('#import-zip-btn');
const fileUploadForm = $('#file-upload-form');
const fileUploadBtn = fileUploadForm.find('input[type=submit]');
const fileUploadInput = fileUploadForm.find('input[type=file]');
const addCollaborator = $('#add-collaborator');
const removeCollaborator = $('#remove-collaborator');
// const createDatabaseBtn = $('#create-database-btn');
const deleteDatabaseBtn = $('#delete-database-btn');
const enterInvitationCodeBtn = $('#enter-invitation-code-btn');

const selected = {
    databaseId: undefined
};

let databaseExtraArgs = {};
let collectionExtraArgs = {};
let dbAssignmentExtraArgs = {};
let versionExtraArgs = {};
let syllableExtraArgs = {};

let databaseGridArgs = {
    radioSelect: true,
};

let collectionGridArgs = {
    multiSelect: true,
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
            deleteVersionBtn.prop('disabled', true);
        }
    });

    /**
     * When collections are selected/deselected, enable delete button if there is at least 1 selected, otherwise disable
     */
    function onCollectionSelectionChange(e, args) {
        let grid_ = args.grid;
        deleteCollections.prop('disabled', grid_.getSelectedRows().length == 0);
    }


    /**
     * When collaborators are selected/deselected:
     * enable delete button if there is at least 1 selected, and the user has admin privileges
     * otherwise disable
     */
    function onCollaboratorSelectionChange(e, args) {
        let grid_ = args.grid;
        let canRemoveCollaborator = removeCollaborator.hasAdminPrivileges && grid_.getSelectedRows().length > 0;
        removeCollaborator.prop('disabled', !canRemoveCollaborator);
    }

    collectionGrid.on('row-added', onCollectionSelectionChange);
    collectionGrid.on('rows-added', onCollectionSelectionChange);
    collectionGrid.on('row-removed', onCollectionSelectionChange);
    collectionGrid.on('rows-removed', onCollectionSelectionChange);

    dbAssignmentGrid.on('row-added', onCollaboratorSelectionChange);
    dbAssignmentGrid.on('rows-added', onCollaboratorSelectionChange);
    dbAssignmentGrid.on('row-removed', onCollaboratorSelectionChange);
    dbAssignmentGrid.on('rows-removed', onCollaboratorSelectionChange);
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
        });
    });
};


const reloadSyllableGrid = function () {
    return syllableGrid.initMainGridHeader(syllableGridArgs, syllableExtraArgs).then(function () {
        return syllableGrid.initMainGridContent(syllableGridArgs, syllableExtraArgs);
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

    collectionGrid.init({
        'grid-name': 'collection',
        'grid-type': 'collection-grid',
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

    let collectionPromise = collectionGrid.initMainGridHeader(collectionGridArgs, collectionExtraArgs).
        then(function () {
            return collectionGrid.initMainGridContent(collectionGridArgs, collectionExtraArgs);
        });

    let dbGridPromise = databaseGrid.initMainGridHeader(databaseGridArgs, databaseExtraArgs).then(function () {
        databaseGrid.on('row-added', function (e, args) {
            selected.databaseId = args.item.id;
            dbAssignmentExtraArgs.database = selected.databaseId;
            versionExtraArgs.database = selected.databaseId;
            syllableExtraArgs.database = selected.databaseId;

            backupBtns.prop('disabled', false);

            let hasAdminPrivileges = args.item.__name_editable;

            addCollaborator.prop('disabled', !hasAdminPrivileges);
            removeCollaborator.hasAdminPrivileges = hasAdminPrivileges;
            dbAssignmentGridArgs.multiSelect = hasAdminPrivileges;

            dbAssignmentGrid.refresh();

            return Promise.all([
                dbAssignmentGrid.initMainGridHeader(dbAssignmentGridArgs, dbAssignmentExtraArgs),
                versionGrid.initMainGridHeader(versionGridArgs, versionExtraArgs),
                syllableGrid.initMainGridHeader(syllableGridArgs, syllableExtraArgs)
            ]).then(function() {
                return Promise.all([
                    dbAssignmentGrid.initMainGridContent(dbAssignmentGridArgs, dbAssignmentExtraArgs),
                    versionGrid.initMainGridContent(versionGridArgs, versionExtraArgs)
                ])
            }).then(function () {
                let hasNoCollaborators = dbAssignmentGrid.mainGrid.getData().getItems().length == 1;

                let allowDeleteDatabase = hasAdminPrivileges && hasNoCollaborators;
                deleteDatabaseBtn.prop('disabled', !allowDeleteDatabase);

                return syllableGrid.initMainGridContent(syllableGridArgs, syllableExtraArgs);
            });
        });

        return databaseGrid.initMainGridContent(databaseGridArgs, databaseExtraArgs);
    });

    return Promise.all([collectionPromise, dbGridPromise]);
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

    ReactDOM.render(<NewDatabaseButton databaseGrid={databaseGrid} />, document.getElementById('create-database-button-wrapper'));


    deleteDatabaseBtn.on('click', function () {
        let grid_ = databaseGrid.mainGrid;
        let selectedRow = grid_.getSelectedRows()[0];
        let dataView = grid_.getData();
        let item = dataView.getItem(selectedRow);

        ce.dialogModalTitle.html(`Confirm delete database ${item.name}`);
        ce.dialogModalBody.html('Are you sure you want to delete this database?');

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.on('click', function () {
            let onSuccess = function () {
                dataView.deleteItem(item.id);
            };
            ce.dialogModal.modal('hide');
            postRequest({
                requestSlug: 'koe/delete-database',
                data: {
                    'database-id': JSON.stringify(item.id)
                },
                onSuccess
            });
        })
    });
}


const initEnterInvitationCodeBtn = function () {

    /**
     * Repeat showing the dialog until the invitation code is valid
     * param error to be shown in the modal if not undefined
     */
    function showDialog(error) {
        dialogModalTitle.html('So you got invited to a database...');
        dialogModalBody.html('<label>Enter your code (case sensitive)</label>');
        dialogModalBody.append(inputText);
        if (error) {
            dialogModalBody.append(`<p>${error.message}</p>`);
        }

        dialogModal.modal('show');

        dialogModalOkBtn.one('click', function () {
            dialogModal.modal('hide');
            let url = getUrl('send-request', 'koe/redeem-invitation-code');
            let invitationCode = inputText.val();
            inputText.val('');

            $.post(url, {code: invitationCode}).done(function (data) {
                data = JSON.parse(data);
                let row = data.message;
                dialogModal.one('hidden.bs.modal', function () {
                    let existedItem = databaseGrid.mainGrid.getData().getItemById(row.id);
                    if (existedItem) {
                        databaseGrid.updateRowAndHighlight(row);
                    }
                    else {
                        databaseGrid.appendRowAndHighlight(row);
                    }
                });
                replaceSidebar(viewPortChangeHandler);
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

    enterInvitationCodeBtn.click(function (e) {
        e.preventDefault();
        showDialog();
    });
};

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

/**
 * To delete selected collections
 */
function initDeleteCollectionsBtn() {
    deleteCollections.click(function () {
        let grid_ = collectionGrid.mainGrid;
        let selectedRows = grid_.getSelectedRows();
        let dataView = grid_.getData();

        let itemIds = [];
        let itemNames = [];

        $.each(selectedRows, function (idx, selectedRow) {
            let item = dataView.getItem(selectedRow);
            itemIds.push(item.id);
            itemNames.push(item.name);
        });

        ce.dialogModalTitle.html(`Confirm delete ${itemIds.length} collection(s)`);
        ce.dialogModalBody.html(`Are you sure you want to delete the following collections?<br>${itemNames.join('<br>')}`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.on('click', function () {
            let onSuccess = function () {
                collectionGrid.deleteRows(itemIds);
            };
            ce.dialogModal.modal('hide');
            postRequest({
                requestSlug: 'koe/delete-collections',
                data: {
                    ids: JSON.stringify(itemIds)
                },
                onSuccess
            });
        })
    });
}

/**
 *
 */
function initRemoveCollaboratorBtn() {
    removeCollaborator.click(function () {
        let grid_ = dbAssignmentGrid.mainGrid;
        let selectedRows = grid_.getSelectedRows();
        let dataView = grid_.getData();

        let itemIds = [];
        let itemNames = [];

        $.each(selectedRows, function (idx, selectedRow) {
            let item = dataView.getItem(selectedRow);
            itemIds.push(item.id);
            itemNames.push(item.username);
        });

        ce.dialogModalTitle.html(`Confirm removing ${itemIds.length} collaborator(s)`);
        ce.dialogModalBody.html(`Are you sure you want to remove the following collaborator?<br>${itemNames.join('<br>')}`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.on('click', function () {
            let onSuccess = function () {
                dbAssignmentGrid.deleteRows(itemIds);
            };
            ce.dialogModal.modal('hide');
            postRequest({
                requestSlug: 'koe/remove-collaborators',
                data: {
                    ids: JSON.stringify(itemIds),
                    database: selected.databaseId
                },
                onSuccess
            });
        })
    });
}

export const postRun = function () {
    initCreateDatabaseButton();
    initEnterInvitationCodeBtn();
    initDeleteCollectionsBtn();
    initAddCollaboratorBtn();
    initRemoveCollaboratorBtn();
    initSaveVersionBtns();
    initApplyVersionBtn();
    initDeleteVersionBtn();
    initImportZipBtn();
    subscribeFlexibleEvents();
    return Promise.resolve();
};

export const viewPortChangeHandler = function () {
    databaseGrid.mainGrid.resizeCanvas();
    dbAssignmentGrid.mainGrid.resizeCanvas();
    versionGrid.mainGrid.resizeCanvas();
    syllableGrid.mainGrid.resizeCanvas();
};
