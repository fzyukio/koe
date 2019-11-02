/* global Dropzone */

import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {changePlaybackSpeed, queryAndPlayAudio, createAudioFromDataArray, queryAndHandleAudioGetOrPost, MAX_SAMPLE_RATE} from './audio-handler';
import {debug, deepCopy, getUrl, isNull} from './utils';
import {postRequest} from './ajax-handler';
require('bootstrap-slider/dist/bootstrap-slider.js');
const JSZip = require('jszip/dist/jszip.min.js');
const filesaver = require('file-saver/dist/FileSaver.min.js');

const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 30;


class Grid extends FlexibleGrid {
    init(granularity) {

        super.init({
            'grid-name': 'sequences',
            'grid-type': 'songs-grid',
            'default-field': 'filename',
            'import-key': 'filename',
            gridOptions
        });

        this.granularity = granularity;
    }
}

export const grid = new Grid();
const $segmentGrid = $('#songs-grid');
const granularity = $segmentGrid.attr('granularity');
const viewas = $segmentGrid.attr('viewas');
const database = $segmentGrid.attr('database');
const tmpdb = $segmentGrid.attr('tmpdb');

const tooltip = $('#spectrogram-details-tooltip');
const tooltipImg = tooltip.find('img');
const speedSlider = $('#speed-slider');
const gridStatus = $('#grid-status');
const gridStatusNSelected = gridStatus.find('#nselected');
const gridStatusNTotal = gridStatus.find('#ntotal');

const uploadSongsBtn = $('#upload-songs-btn');
const downloadSongsBtn = $('#download-songs-btn');
const deleteSongsBtn = $('#delete-songs-btn');
const copySongsBtn = $('#copy-songs-btn');

const uploadSongsModal = $('#upload-songs-modal');
let clashedList = uploadSongsModal.find('#clashed-list');
let clashAlert = uploadSongsModal.find('.alert');

const downloadSongsModal = $('#download-songs-modal');
const downloadProgressBar = downloadSongsModal.find('.progress-bar');

const totalFilesCount = $('#total-files-count');
const currentFileNumber = $('#current-file-no');
const currentFileName = $('#current-file-name');

const databaseId = uploadSongsModal.attr('database');
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
 * BLAH123
 */
const subscribeFlexibleEvents = function () {
    debug('subscribeFlexibleEvents called from songs-pages');
    grid.on('click', function (...args) {
        let e = args[0];
        e.preventDefault();
        playAudio(...args);
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

            // Remove the old image first to avoid showing the previous spectrogram
            tooltipImg.attr('src', '');
            // Then insert the new spectrogram
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
        setupSongsUpload();
        uploadSongsModal.modal('show');
    });

    uploadSongsModal.on('hidden.bs.modal', function () {
        dropzone.removeAllFiles(true);
    });
};

/**
 * Allow users to download songs
 */
const initDownloadSongsBtn = function () {
    downloadSongsBtn.click(function () {
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
        postRequest({
            requestSlug: 'koe/get-audio-files-urls',
            data: {'file-ids': JSON.stringify(ids), format: 'wav'},
            onSuccess(urls) {
                let zip = new JSZip();
                downloadSongsModal.modal('show');
                let numAddedFiles = 0;
                totalFilesCount.html(urls.length);

                /**
                 * Put audio data into the zip container
                 * @param filename
                 * @param byteArray
                 * @param fs
                 */
                function handleDownloadedAudio(filename, byteArray, fs) {
                    let blob = createAudioFromDataArray(byteArray, fs);
                    zip.file(filename, blob);
                    numAddedFiles++;
                    let percentLoaded = numAddedFiles / numRows * 100;
                    percentLoaded = percentLoaded.toFixed(2);

                    downloadProgressBar.css('width', `${percentLoaded}%`);
                    downloadProgressBar.attr('aria-valuenow', percentLoaded);
                    downloadProgressBar.html(`${percentLoaded}%`);
                    currentFileName.html(filename);
                    currentFileNumber.html(numAddedFiles);

                    if (numAddedFiles == urls.length) {
                        zip.generateAsync({type: 'blob'}).then(function (content) {
                            filesaver.saveAs(content, 'audiofiles.zip');
                            downloadSongsModal.modal('hide');
                            downloadSongsModal.on('hidden.bs.modal', function() {
                                downloadProgressBar.css('width', '0%');
                                downloadProgressBar.attr('aria-valuenow', 0);
                                downloadProgressBar.html('0%');
                                currentFileName.html('');
                                currentFileNumber.html('');
                                totalFilesCount.html('');
                            });
                        });
                    }
                }

                for (let i = 0; i < urls.length; i++) {
                    let url = urls[i];
                    let urlParts = url.split('/');
                    let filename = urlParts[urlParts.length - 1];

                    queryAndHandleAudioGetOrPost({
                        url,
                        cacheKey: url,
                        callback(byteArray, fs) {
                            handleDownloadedAudio(filename, byteArray, fs);
                        }
                    });
                }
            },
            immediate: true,
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
                grid.deleteRows(ids);
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
    database,
    tmpdb
};

let gridArgs = {
    multiSelect: true
};

let existingFiles;
let dropzone;

/**
 * Initialise the dropzone
 */
function setupDropZone() {
    let maxFiles = 100;
    let maxFilesize = 50;

    let dropzoneSelector = '#songs-upload';

    let previewNode = document.querySelector('#template');
    previewNode.id = '';
    let previewTemplate = previewNode.parentNode.innerHTML;
    previewNode.parentNode.removeChild(previewNode);

    dropzone = new Dropzone(dropzoneSelector, {
        url: getUrl('send-request', 'koe/import-audio-files'),
        maxFilesize,
        addRemoveLinks: false,
        acceptedFiles: 'audio/wav',
        uploadMultiple: true,
        parallelUploads: 8,
        maxFiles,
        method: 'post',
        dictDefaultMessage: `Drag & drop or click to upload songs (WAV only, up to ${maxFiles} at once)`,
        dictResponseError: 'Error uploading file!',
        createImageThumbnails: false,
        previewTemplate,
        previewsContainer: '#previews',
        autoQueue: false,
        duplicateMessageGenerator(file) {
            return `File ${file.name} already exists in the upload list`;
        },
        preventDuplicates: true,
        init () {
            let self = this;

            self.on('sending', function (file, xhr, formData) {
                formData.append('database', databaseId);
                formData.append('max-fs', MAX_SAMPLE_RATE);
            });

            self.on('maxfilesexceeded', function (file) {
                alert(`You can only upload up to ${maxFiles} photos.`);
                self.removeFile(file);
            });

            self.on('addedfile', function (file) {
                let filename = file.name;

                // Remove the ".wav" part from file name
                filename = filename.substr(0, filename.length - 4).toLowerCase();
                if (existingFiles.includes(filename)) {
                    self.removeFile(file);
                    clashedList.append(`<li>${file.name}</li>`);
                    clashAlert.show();
                }
            });

            self.on('successmultiple', function(file, response) {
                let rows = JSON.parse(response).message;
                let lastRow = rows[rows.length - 1];
                grid.appendRows(rows);
                grid.mainGrid.gotoCell(lastRow.id, 0);
                grid.mainGrid.scrollCellIntoView(lastRow.id, 0);
                self.removeAllFiles(true);
            });
        }
    });

    uploadSongsModal.find('.start').click(function() {
        dropzone.enqueueFiles(dropzone.getFilesWithStatus(Dropzone.ADDED));
    });

    uploadSongsModal.find('.removel-all').click(function() {
        dropzone.removeAllFiles(true);
    });

    uploadSongsModal.find('.cancel').click(function() {
        uploadSongsModal.modal('hide');
    });
}


/**
 * Clean up the dropzone
 */
function setupSongsUpload() {
    let items = grid.mainGrid.getData().getItems();
    existingFiles = $.map(items, (item) => item.filename.toLowerCase());
    clashedList.children().remove();
    clashAlert.hide();
    $('#previews').children().remove();
}


export const preRun = function() {
    initSlider();

    if (isNull(database) && isNull(tmpdb)) {
        return Promise.reject(new Error('Please choose a database.'))
    }
    return Promise.resolve();
};

export const run = function (commonElements) {
    ce = commonElements;
    let argDict = ce.argDict;

    grid.init(granularity);

    return new Promise(function(resolve) {
        grid.initMainGridHeader(gridArgs, extraArgs).then(function () {
            subscribeSlickEvents();
            subscribeFlexibleEvents();

            grid.initMainGridContent(gridArgs, extraArgs).then(function() {
                focusOnGridOnInit();
                if (argDict.__action === 'upload') {
                    uploadSongsBtn.click();
                }

                setupDropZone();
                initUploadSongsBtn();
                initDownloadSongsBtn();

                resolve();
            });
        });
    });
};

export const postRun = function () {
    initDeleteSongsBtn();
    initCopySongsBtn();
    return Promise.resolve();
};

export const viewPortChangeHandler = function () {
    grid.mainGrid.resizeCanvas();
};
