/* global Dropzone */

import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {changePlaybackSpeed, initAudioContext, queryAndPlayAudio} from './audio-handler';
import {debug, deepCopy, getUrl} from './utils';
import {postRequest, uploadRequest} from './ajax-handler';
require('bootstrap-slider/dist/bootstrap-slider.js');


const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 30;


class Grid extends FlexibleGrid {
    init(granularity) {

        super.init({
            'grid-name': 'sequences',
            'grid-type': 'songs-grid',
            'default-field': 'filename',
            gridOptions
        });

        this.granularity = granularity;
    }

    /**
     * Highlight the active row on mouse over (super) and also highlight the corresponding segment on the spect
     * @param e
     * @param args
     */
    mouseHandler(e, args) {
        super.mouseHandler(e, args);

        const self = this;
        let eventType = e.type;
        let grid = args.grid;
        let dataView = grid.getData();
        let cell = grid.getCellFromEvent(e);
        if (cell) {
            let row = cell.row;
            let col = cell.cell;
            let coldef = grid.getColumns()[col];
            let rowElement = $(e.target.parentElement);
            let songId = dataView.getItem(row).id;
            self.eventNotifier.trigger(eventType, {
                e,
                songId,
                rowElement,
                coldef
            });
        }
    }
}

export const grid = new Grid();
let granularity = $('#songs-grid').attr('granularity');
let viewas = $('#songs-grid').attr('viewas');

const tooltip = $('#spectrogram-details-tooltip');
const tooltipImg = tooltip.find('img');
const speedSlider = $('#speed-slider');
const gridStatus = $('#grid-status');
const gridStatusNSelected = gridStatus.find('#nselected');
const gridStatusNTotal = gridStatus.find('#ntotal');

const uploadSongsBtn = $('#upload-songs-btn');
const uploadCsvBtn = $('#upload-csv-btn');
const deleteSongsBtn = $('#delete-songs-btn');
const copySongsBtn = $('#copy-songs-btn');

const csvUploadForm = $('#csv-upload-form');
const csvUploadInput = csvUploadForm.find('input[type=file]');
const csvUploadSubmitBtn = csvUploadForm.find('input[type=submit]');

const uploadSongsModal = $('#upload-songs-modal');

let ce;

const initSlider = function () {
    speedSlider.slider();

    speedSlider.on('slide', function (slideEvt) {
        changePlaybackSpeed(slideEvt.value);
    });

    $('.slider').on('click', function () {
        let newvalue = $('.tooltip-inner').text();
        changePlaybackSpeed(parseInt(newvalue));
    });
};

const playAudio = function (e, args) {
    let cellElement = $(args.e.target);
    let hasSyllable = cellElement.closest('.syllable');
    if (hasSyllable.length == 1) {
        let fileId = args.songId;
        let start = parseInt(hasSyllable.attr('start')) / 1000.0;
        let end = parseInt(hasSyllable.attr('end')) / 1000.0;

        let args_ = {
            url: getUrl('send-request', 'koe/get-file-audio-data'),
            postData: {'file-id': fileId},
            cacheKey: fileId,
            playAudioArgs: {
                beginSec: start,
                endSec: end
            }
        };

        queryAndPlayAudio(args_);
    }
};

/**
 * Triggered on click. If the cell is not editable and is of type text, integer, float, highlight the entire cell
 * for Ctrl + C
 *
 * @param e
 * @param args
 */
const selectTextForCopy = function (e, args) {
    let coldef = args.coldef;
    let editable = coldef.editable;
    let copyable = coldef.copyable;

    if (!editable && copyable) {
        let cellElement = $(args.e.target);
        cellElement.selectText();
    }
};

const resetStatus = function (e, args) {
    e.preventDefault();
    let nRowChanged = 0;
    if (e.type == 'row-added') {
        nRowChanged = 1;
    }
    else if (e.type == 'rows-added') {
        nRowChanged = args.rows.length;
    }
    else if (e.type == 'row-removed') {
        nRowChanged = -1;
    }
    else if (e.type == 'rows-removed') {
        nRowChanged = -args.rows.length;
    }
    let nSelectedRows = parseInt(gridStatusNSelected.html());
    gridStatusNSelected.html(nSelectedRows + nRowChanged);

    // Restore keyboard navigation to the grid
    $($('div[hidefocus]')[0]).focus();
};

/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    debug('subscribeFlexibleEvents called from songs-pages');
    grid.on('click', function (...args) {
        let e = args[0];
        e.preventDefault();
        playAudio(...args);
        selectTextForCopy(...args);
        clearSpectrogram(...args);
        showBigSpectrogram(...args);
    });

    /**
     * When songs are selected, enable delete and copy button
     */
    function onSongsAdded(e, args) {
        resetStatus(e, args);
        deleteSongsBtn.prop('disabled', false);
        copySongsBtn.prop('disabled', false);
    }

    /**
     * When songs are removed, if there is songs left, disable the delete button
     * @param e event
     * @param args contains 'grid' - the main SlickGrid
     */
    function onSongsRemoved(e, args) {
        resetStatus(e, args);
        let grid_ = args.grid;
        if (grid_.getSelectedRows().length == 0) {
            deleteSongsBtn.prop('disabled', true);
            copySongsBtn.prop('disabled', true);
        }
    }

    grid.on('row-added', onSongsAdded);
    grid.on('rows-added', onSongsAdded);

    grid.on('row-removed', onSongsRemoved);
    grid.on('rows-removed', onSongsRemoved);
};


/**
 * Subscribe to events on the slick grid. This must be called everytime the slick is reconstructed, e.g. when changing
 * screen orientation or size
 */
const subscribeSlickEvents = function () {

    grid.subscribeDv('onRowCountChanged', function (e, args) {
        let currentRowCount = args.current;
        gridStatusNTotal.html(currentRowCount);
    });

    grid.on('mouseleave', clearSpectrogram);
};


const showBigSpectrogram = function (e, args) {
    e.preventDefault();
    let cellElement = $(args.e.target);
    let isSyllable = cellElement.closest('.syllable');
    if (isSyllable.length == 1) {
        const imgSrc = isSyllable.attr('imgsrc');
        if (imgSrc) {
            tooltipImg.attr('src', imgSrc);
            tooltip.removeClass('hidden');

            const panelHeight = $('#songs-grid').height();
            const imgWidth = tooltipImg.width();
            const imgHeight = tooltipImg.height();

            const pos = isSyllable.offset();
            const cellTop = pos.top;
            const cellLeft = pos.left;

            let cellBottom = cellTop + isSyllable.height();
            let cellCentreX = cellLeft + (isSyllable.width() / 2);
            let imgLeft = cellCentreX - (imgWidth / 2);

            let left, top;

            if (cellBottom < panelHeight / 2) {
                top = cellBottom + 20 + 'px';
            }
            else {
                top = cellTop - 40 - imgHeight + 'px';
            }

            if (imgLeft > 0) {
                left = imgLeft + 'px';
            }
            else {
                left = '';
            }
            tooltip.css('left', left).css('top', top);
        }
    }
};


/**
 * Hide the tooltip and remove highlight from the active image
 */
const clearSpectrogram = function () {
    tooltip.addClass('hidden');
};


/**
 * Set the focus on the grid right after page is loaded.
 * This is mainly so that user can use Page Up and Page Down right away
 */
const focusOnGridOnInit = function () {
    $($('div[hidefocus]')[0]).focus();
};


/**
 * Allow user to upload songs
 */
const initUploadSongsBtn = function () {

    uploadSongsBtn.click(function () {
        uploadSongsModal.modal('show');
    });

    uploadCsvBtn.click(function () {
        csvUploadInput.click();
    });

    csvUploadInput.change(function () {
        csvUploadSubmitBtn.click();
    });

    csvUploadForm.submit(function (e) {
        e.preventDefault();
        let formData = new FormData(this);
        uploadRequest({
            requestSlug: 'koe/import-audio-metadata',
            data: formData
        });
    });
};

/**
 * Allows user to remove songs
 */
const initDeleteSongsBtn = function () {
    deleteSongsBtn.click(function () {
        let grid_ = grid.mainGrid;
        let selectedRows = grid_.getSelectedRows();
        let numRows = selectedRows.length;
        let ids = [];
        let selectedItems = [];
        let dataView = grid_.getData();
        for (let i = 0; i < numRows; i++) {
            let item = dataView.getItem(selectedRows[i]);
            ids.push(item.id);
            selectedItems.push(item);
        }

        let databaseId = ce.databaseCombo.attr('database');

        ce.dialogModalTitle.html(`Confirm delete ${numRows} song(s)`);
        ce.dialogModalBody.html(`Are you sure you want to delete these songs and all data associated with it? 
        Audio files (all formats) are also deleted. This action is not reverseable.`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.one('click', function () {
            let postData = {
                ids: JSON.stringify(ids),
                database: databaseId
            };
            let msgGen = function (isSuccess, response) {
                return isSuccess ?
                    'Files successfully deleted.' :
                    `Something's wrong. The server says ${response}. Files might have been deleted.`;
            };
            let onSuccess = function () {
                for (let i = 0; i < numRows; i++) {
                    dataView.deleteItem(ids[i]);
                }
            };
            ce.dialogModal.modal('hide');
            postRequest({
                requestSlug: 'koe/delete-audio-files',
                data: postData,
                msgGen,
                onSuccess,
                immediate: true
            });
        })
    });
};


/**
 * Allows user to copy songs to a different database
 */
const initCopySongsBtn = function () {
    copySongsBtn.click(function () {
        let grid_ = grid.mainGrid;
        let selectedRows = grid_.getSelectedRows();
        let numRows = selectedRows.length;
        let ids = [];
        let selectedItems = [];
        let dataView = grid_.getData();
        for (let i = 0; i < numRows; i++) {
            let item = dataView.getItem(selectedRows[i]);
            ids.push(item.id);
            selectedItems.push(item);
        }

        let databaseId = ce.databaseCombo.attr('database');

        ce.dialogModalTitle.html(`Copy ${numRows} song(s) to a database`);
        ce.dialogModalBody.html(`Please provide the name of the target database for these files to be copied to. 
        Make sure you have permission to add files to this database.`);

        let inputEl = ce.inputText;
        ce.dialogModalBody.append(inputEl);

        ce.dialogModal.on('shown.bs.modal', function () {
            inputEl.focus();
        });

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.off('click').one('click', function () {
            let databaseName = inputEl.val();

            let postData = {
                ids: JSON.stringify(ids),
                'target-database-name': databaseName,
                'source-database-id': databaseId
            };

            let msgGen = function (isSuccess) {
                return isSuccess ?
                    `Success. ${numRows} file(s) copied to database ${databaseName}. 
                    You can view these files by switching to database ${databaseName}` :
                    null;
            };

            ce.dialogModal.modal('hide');
            postRequest({
                requestSlug: 'koe/copy-audio-files',
                data: postData,
                msgGen
            });
        });
    });
};


let extraArgs = {
    granularity,
    viewas,
};

let gridArgs = {
    multiSelect: true
};

/**
 * Initialise the dropzone
 */
function setupSongsUpload() {
    let maxFiles = 100;
    let maxFilesize = 50;

    let dropzoneSelector = '#songs-upload';
    let databaseId = parseInt(uploadSongsModal.attr('database'));

    let previewNode = document.querySelector('#template');
    previewNode.id = '';
    let previewTemplate = previewNode.parentNode.innerHTML;
    previewNode.parentNode.removeChild(previewNode);

    const myDropzone = new Dropzone(dropzoneSelector, {
        url: getUrl('send-request', 'koe/import-audio-files'),
        maxFilesize,
        addRemoveLinks: false,
        acceptedFiles: 'audio/wav',
        uploadMultiple: true,
        parallelUploads: 8,
        maxFiles,
        method: 'post',
        dictDefaultMessage: `Drag and drop, or click to upload songs (WAV only). You can upload up to ${maxFiles} songs.`,
        dictResponseError: 'Error uploading file!',
        createImageThumbnails: false,
        previewTemplate,
        previewsContainer: '#previews',
        autoQueue: false,
        init () {
            let self = this;

            self.on('sending', function (file, xhr, formData) {
                formData.append('database', databaseId);
            });

            self.on('maxfilesexceeded', function (file) {
                alert(`You can only upload up to ${maxFiles} photos.`);
                self.removeFile(file);
            });

            self.on('success', function(file, response) {
                let rows = JSON.parse(response).message;
                let lastRow = rows[rows.length - 1];
                grid.appendRows(rows);
                grid.mainGrid.gotoCell(lastRow.id, 0);
                grid.mainGrid.scrollCellIntoView(lastRow.id, 0);
            });
        }
    });

    uploadSongsModal.find('.start').click(function() {
        myDropzone.enqueueFiles(myDropzone.getFilesWithStatus(Dropzone.ADDED));
    });

    uploadSongsModal.find('.removel-all').click(function() {
        myDropzone.removeAllFiles(true);
    });

    uploadSongsModal.find('.cancel').click(function() {
        uploadSongsModal.modal('hide');
    });
}

export const run = function (commonElements) {
    ce = commonElements;
    let argDict = ce.argDict;

    grid.init(granularity);
    grid.initMainGridHeader(gridArgs, extraArgs, function () {
        grid.initMainGridContent(gridArgs, extraArgs, function() {
            focusOnGridOnInit();
            if (argDict.__action === 'upload') {
                uploadSongsBtn.click();
            }
        });
        subscribeSlickEvents();
        subscribeFlexibleEvents();
    });

    initSlider();
};

export const postRun = function () {
    initAudioContext();
    setupSongsUpload();
    initUploadSongsBtn();
    initDeleteSongsBtn();
    initCopySongsBtn();
};

export const handleDatabaseChange = function () {
    location.reload()
};

export const viewPortChangeHandler = function () {
    grid.mainGrid.resizeCanvas();
};
