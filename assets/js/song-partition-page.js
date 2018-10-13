/* global keyboardJS*/
import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {
    changePlaybackSpeed, createAudioFromDataArray, initAudioContext, loadLocalAudioFile, loadSongById
} from './audio-handler';
import {deepCopy, setCache, getCache, uuid4, isNumber, showAlert, debug} from './utils';
import {postRequest, uploadRequest} from './ajax-handler';
import {Visualiser} from './audio-visualisation'
import {initSelectizeSimple} from './selectize-formatter';

require('bootstrap-slider/dist/bootstrap-slider.js');

const gridOptions = deepCopy(defaultGridOptions);

const uploadSongsBtn = $('#upload-raw-recording-btn');
const audioUploadForm = $('#file-upload-form');
const audioUploadInput = audioUploadForm.find('input[type=file]');

const audioData = {};
const vizContainerId = '#track-visualisation';
let spectViz;
let ce;

const gridEl = $('#song-partition-grid');
const databaseId = gridEl.attr('database-id');
const speedSlider = $('#speed-slider');

const saveSongsBtn = $('#save-songs-btn');
const deleteSongsBtn = $('#delete-songs-btn');
const trackInfoForm = $('#track-info');
const saveTrackInfoBtn = trackInfoForm.find('#save-track-info');
const $songNamePattern = $('#song-name-pattern');
const $songNamePatternInput = $songNamePattern.find('input');

const renameAllBtn = $('#rename-all-btn');

let namePatternInput;
const defaultOptions = [
    {
        value: '$order',
        text: 'Order',
        explain: 'The order in which the song appears, e.g. 1, 2, 3',
        isVar: true
    }
];

const defaultSelectizeArgs = {
    render: {
        option (item) {
            let label = item.text;
            if (item.isVar) {
                label = `${item.text}: ${item.explain}`;
            }
            return `<div class="item" data-value="${item.value}">${label}</div>`;
        },
        item (item) {
            let isVar = '';
            if (item.isVar) {
                isVar = 'is-var'
            }
            return `<div class="item ${isVar}" data-value="${item.value}">${item.text}</div>`;
        }
    }
};

const patternValues = {};

/**
 * Generate and store name for an item based on the selected pattern.
 * @param item
 * @param force if true, change name even if the corresponding song has already been saved to database
 * @returns {boolean} true if the item's name has been changed
 */
function populateName(item, force = false) {
    let items = grid.mainGrid.getData().getItems();
    let needChange = false;
    if (force || (!isNumber(item.id) && item.id.startsWith('new:'))) {
        needChange = true;
    }
    if (needChange) {
        let patterns = namePatternInput.items;
        let newName;

        if (patterns.length === 0) {
            if (item.id.startsWith('new:')) {
                newName = item.id.substr(4);
            }
            else {
                newName = item.name || uuid4();
            }
        }
        else {
            newName = '';
            $.each(patterns, function (idx, pattern) {
                let patternValue;
                if (pattern == '$order') {
                    let i = 0;
                    for (; i < items.length; i++) {
                        if (items[i].id === item.id) {
                            break;
                        }
                    }
                    patternValue = i + 1;
                }
                else {
                    patternValue = patternValues[pattern];
                }
                newName += patternValue;
            });
        }
        let oldName = item.name;
        item.name = newName;
        if (oldName && oldName !== newName) {

            // eslint-disable-next-line camelcase
            item._old_name = oldName;
            return true;
        }
    }
    return false;
}

/**
 * Call populateName on all items of the grid. Collect the ones that have been updated
 * @param force see populateName
 * @returns {Array} array of updated itemns
 */
function populateNameAll(force = false) {
    let items = grid.mainGrid.getData().getItems();
    let updated = [];
    $.each(items, function (idx, item) {
        let changed = populateName(item, force);
        if (changed) {
            updated.push(item)
        }
    });
    grid.mainGrid.invalidate();
    grid.mainGrid.render();
    return updated;
}

class Grid extends FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'song-partition-grid',
            'grid-type': 'song-partition-grid',
            gridOptions
        });
    }

    /**
     * Highlight the owner's measurement in the segmentation table when the corresponding spectrogram owner is mouseover
     * @param args indexed array {event: name of the event, target: the element that is being mouseover}
     */
    segmentMouseEventHandler(e, args) {
        let resizing = getCache('resizeable-syl-id');
        if (resizing && spectViz.editMode) {
            // Currently editing another segment, ignore.
            return;
        }

        const self = this;
        let eventType = args.type;
        let target = args.target;
        let dataView = self.mainGrid.getData();
        let sylId = target.getAttribute('syl-id');
        let sylIdx = dataView.getIdxById(sylId);

        /*
         * Scroll the table to this position, this is necessary because if the cell is currently overflow, getCellNode()
         * will return undefined.
         */
        self.mainGrid.gotoCell(sylIdx, 0);
        self.mainGrid.scrollCellIntoView(sylIdx, 0);
        let cellElement = self.mainGrid.getCellNode(sylIdx, 0);
        if (cellElement) {
            let rowElement = $(cellElement.parentElement);

            if (eventType === 'segment-mouseover') {
                rowElement.addClass('highlight');
            }
            else if (eventType === 'segment-mouseleave') {
                rowElement.removeClass('highlight');
            }
        }
    }

    /**
     * Change the syllable table when a new syllable is drawn or an existing one is adjusted (incl. deletion)
     * from the spectrogram
     * @param args
     */
    segmentChangeEventHandler(e, args) {
        const self = this;
        let eventType = args.type;
        let target = args.target;
        let dataView = self.mainGrid.getData();
        let syllableDict = getCache('syllableDict');

        if (trackInfoForm.find('#id_track_id').attr('valid') === 'true') {
            saveSongsBtn.prop('disabled', false);
        }

        if (eventType === 'segment-created') {
            populateName(target);
            // This will add the item to syllableArray too
            dataView.addItem(target);

            syllableDict[target.id] = target
        }
        else if (eventType === 'segment-adjusted') {
            // This will change the item in syllableArray too
            dataView.updateItem(target.id, target);

            syllableDict[target.id] = target
        }
    }

    rowChangeHandler(e, args, onSuccess, onFailure) {
        let item = args.item;
        // Only change properties of files that already exist on the server
        if (item.progress === 'Uploaded') {
            return super.rowChangeHandler(e, args, onSuccess, onFailure);
        }
        return Promise.resolve();
    }
}

export const grid = new Grid();

export const highlightSegments = function (e, args) {
    let eventType = e.type;
    let segmentsGridRowElement = args.rowElement;

    if (eventType === 'mouseenter') {
        segmentsGridRowElement.addClass('highlight');
    }
    else {
        segmentsGridRowElement.removeClass('highlight');
    }

    spectViz.highlightSegments(e, args)
};


const saveSongsToDb = function () {
    let syllableArray = grid.mainGrid.getData().getItems();
    let syllableDict = getCache('syllableDict');
    let itemsToUpdate = [];
    for (let i = 0; i < syllableArray.length; i++) {
        let item = syllableArray[i];
        if (item.progress !== 'Uploaded') {
            itemsToUpdate.push(item);
        }
    }

    /**
     * Update complete percentage as the files are being rendered
     * @param item
     * @param percentComplete
     */
    function onProgress(item, percentComplete) {
        let oldId = item.id;
        item.progress = `${percentComplete} %`;
        grid.mainGrid.invalidateRows(oldId);
        grid.mainGrid.render();
    }

    // We need to use promise chain to ensure the sequential of the songs and of the callbacks
    let uploadPromise = itemsToUpdate.reduce(function (promiseChain, item, i) {
        let startMs = item.start;
        let endMs = item.end;
        let durationMs = audioData.durationMs;
        let nSamples = audioData.length;
        let startSample = Math.floor(startMs * nSamples / durationMs);
        let endSample = Math.min(Math.ceil(endMs * nSamples / durationMs), nSamples);

        let subSig = audioData.sig.slice(startSample, endSample);
        let blob = createAudioFromDataArray(subSig, audioData.fs);

        let formData = new FormData();
        formData.append('file', blob, item.name);
        formData.append('item', JSON.stringify(item));
        formData.append('database-id', databaseId);
        formData.append('track-id', trackInfoForm.find('#id_track_id').attr('value'));

        return promiseChain.then(function () {
            debug(`Sending audio data  #${i}`);

            // Send data to server
            return new Promise(function (resolve) {
                uploadRequest({
                    requestSlug: 'koe/import-audio-file',
                    data: formData,
                    onSuccess: resolve,
                    onProgress(e) {
                        if (e.loaded === e.total) {
                            // Do nothing to not be in conflict with onSuccess
                            return;
                        }
                        let percentComplete = Math.round(e.loaded * 100 / e.total);
                        onProgress(item, percentComplete);
                    }
                });
            });
        }).then(function ({id, name}) {
            debug(`Update song #${i}`);

            // Update item ID and refresh the grid for each row
            let oldId = item.id;

            grid.mainGrid.invalidateRows(oldId);
            item.progress = 'Uploaded';
            item.id = id;
            item.name = name;
            grid.mainGrid.render();

            if (oldId !== id) {
                syllableDict[id] = syllableDict[oldId];
                delete syllableDict[oldId];
            }
        })
    }, Promise.resolve());

    // After all songs sent and updated, throw away the old data items and append the new one.
    // They are exactly the same object, however without calling appendItem() the index list will not be updated
    // Ideally this can be avoided if DataView's updateIdxById() is public.
    uploadPromise.then(function () {
        grid.deleteAllRows();
        grid.appendRows(syllableArray);

        saveSongsBtn.attr('disabled', true);
        setCache('resizeable-syl-id', null, undefined);

        // The syllableArray reference is now detached from grid's data items, so we need to get it back
        syllableArray = grid.mainGrid.getData().getItems();
        setCache('syllableArray', undefined, syllableArray);
        spectViz.displaySegs();
    });
};

const initController = function () {
    speedSlider.slider();

    speedSlider.on('slideStop', function (slideEvt) {
        changePlaybackSpeed(slideEvt.value);
    });

    speedSlider.find('.slider').on('click', function () {
        let newValue = speedSlider.find('.tooltip-inner').text();
        changePlaybackSpeed(parseInt(newValue));
    });

    saveSongsBtn.click(function () {
        saveSongsToDb();
    })
};


/**
 * Allows user to remove songs
 */
const initDeleteSegmentsBtn = function () {
    deleteSongsBtn.click(function () {
        let grid_ = grid.mainGrid;
        let selectedRows = grid_.getSelectedRows();
        let numRows = selectedRows.length;
        let dataView = grid_.getData();
        let syllableDict = getCache('syllableDict');
        let itemsIds = [];
        for (let i = 0; i < numRows; i++) {
            let item = dataView.getItem(selectedRows[i]);
            itemsIds.push(item.id);
        }

        for (let i = 0; i < numRows; i++) {
            let itemId = itemsIds[i];
            dataView.deleteItem(itemId);
            delete syllableDict[itemId];
        }
        spectViz.displaySegs();
    });
};


/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    grid.on('mouseenter', highlightSegments);
    grid.on('mouseleave', highlightSegments);

    /**
     * When segments are selected, enable delete button
     */
    function enableDeleteSegmentsBtn() {
        deleteSongsBtn.prop('disabled', false);
    }

    /**
     * When segments are removed, if there is songs left, disable the delete button
     * @param e event
     * @param args contains 'grid' - the main SlickGrid
     */
    function disableDeleteSegmentsBtn(e, args) {
        let grid_ = args.grid;
        if (grid_.getSelectedRows().length == 0) deleteSongsBtn.prop('disabled', true);
    }

    grid.on('row-added', enableDeleteSegmentsBtn);
    grid.on('rows-added', enableDeleteSegmentsBtn);

    grid.on('row-removed', disableDeleteSegmentsBtn);
    grid.on('rows-removed', disableDeleteSegmentsBtn);

    spectViz.eventNotifier.on('segment-mouse', function (e, args) {
        grid.segmentMouseEventHandler(e, args);
    });

    spectViz.eventNotifier.on('segment-changed', function (e, args) {
        grid.segmentChangeEventHandler(e, args);
    });
};


const initKeyboardHooks = function () {
    keyboardJS.bind(
        ['shift'],
        function () {
            let highlighted = getCache('highlighted-syl-id');

            /* Edit mode on and highlighted. Show brush */
            if (highlighted) {
                spectViz.showBrush(highlighted);
            }
            spectViz.editMode = true;
        }, function () {
            spectViz.clearBrush();
            spectViz.editMode = false;
        }
    );
};


let extraArgs = {
    'track_id': trackInfoForm.find('#id_track_id').attr('valid'),
};

let gridArgs = {
    multiSelect: true
};


const uploadModal = $('#upload-modal');
const cancelDownloadBtn = uploadModal.find('#cancel-upload-btn');
const uploadProgressWrapper = uploadModal.find('.progress');
const uploadProgressBar = uploadProgressWrapper.find('.progress-bar');

/**
 * Allow user to upload songs
 */
const initUploadSongsBtn = function () {
    const reader = new FileReader();
    uploadSongsBtn.click(function () {
        audioUploadInput.click();
    });

    cancelDownloadBtn.click(function () {
        cancelDownloadBtn.attr('disabled', true);
        uploadSongsBtn.attr('disabled', false);
        reader.abort();
    });

    uploadModal.modal('show');

    return new Promise(function (resolve) {
        audioUploadInput.change(function (e) {
            e.preventDefault();
            let file = e.target.files[0];

            let onProgress = function (evt) {
                if (evt.lengthComputable) {
                    let percentLoaded = Math.round((evt.loaded / evt.total) * 100);
                    if (percentLoaded < 100) {
                        uploadProgressBar.css('width', `${percentLoaded}%`);
                        uploadProgressBar.attr('aria-valuenow', percentLoaded);
                        uploadProgressBar.html(`${percentLoaded}%`);
                    }
                }
            };

            let onLoadStart = function () {
                uploadProgressWrapper.show();
                cancelDownloadBtn.attr('disabled', false);
                uploadSongsBtn.attr('disabled', true);
            };

            let onError = function (evt) {
                switch (evt.target.error.code) {
                    case evt.target.error.NOT_FOUND_ERR:
                        uploadProgressBar.html('File Not Found!');
                        break;
                    case evt.target.error.NOT_READABLE_ERR:
                        uploadProgressBar.html('File is not readable');
                        break;
                    case evt.target.error.ABORT_ERR:
                        break;
                    default:
                        uploadProgressBar.html('An error occurred reading this file.');
                }
            };

            let onLoad = function () {
                uploadProgressBar.css('width', '100%');
                uploadProgressBar.attr('aria-valuenow', '100');
                uploadProgressBar.html('File uploads successfully. Processing...');
            };

            let onAbort = function () {
                uploadProgressBar.css('width', '100%');
                uploadProgressBar.attr('aria-valuenow', 100);
                uploadProgressBar.html('Aborted. You can upload a new file.');
            };

            loadLocalAudioFile({
                file,
                reader,
                onProgress,
                onError,
                onLoad,
                onAbort,
                onLoadStart
            }).then(function ({sig, fs}) {
                uploadModal.modal('hide');
                resolve({sig_: sig, fs_: fs});
            });
        });
    });
};


const initSaveTrackInfoBtn = function () {
    saveTrackInfoBtn.click(function () {
        trackInfoForm.submit();
    });

    trackInfoForm.submit(function (e) {
        e.preventDefault();
        let formData = new FormData(this);
        let url = this.getAttribute('url');

        postRequest({
            url,
            data: formData,
            onSuccess (res) {
                trackInfoForm.find('.replaceable').html(res);
                if (trackInfoForm.find('#id_track_id').attr('valid') === 'true') {
                    let trackNameInput = trackInfoForm.find('#id_name');
                    let trackDateInput = trackInfoForm.find('#id_date');

                    let name = trackNameInput.val();
                    let options = deepCopy(defaultOptions);

                    options.push({
                        value: '$track-name', text: 'Track name',
                        explain: `Name of the track, in this case it's "${name}"`, isVar: true
                    });
                    patternValues['$track-name'] = name;

                    let date = trackDateInput.val();
                    if (date) {
                        date = new Date(date);
                        let day = date.getDate();
                        let month = date.getMonth() + 1;
                        let year = date.getFullYear();

                        options.push({
                            value: '$track-date',
                            text: 'Date',
                            explain: `Date when this is recorded, in this case it is "${day}"`,
                            isVar: true
                        });
                        options.push({
                            value: '$track-month',
                            text: 'Month',
                            explain: `Month when this is recorded, in this case it is "${month}"`,
                            isVar: true
                        });
                        options.push({
                            value: '$track-year',
                            text: 'Year',
                            explain: `Year when this is recorded, in this case it is "${year}"`,
                            isVar: true
                        });

                        patternValues['$track-date'] = day;
                        patternValues['$track-month'] = month;
                        patternValues['$track-year'] = year;
                    }
                    namePatternInput.refreshOptions();

                    initSelectize(options);

                    let numItems = grid.mainGrid.getData().getItems().length;
                    if (numItems > 0) {
                        saveSongsBtn.prop('disabled', false);
                    }

                    // eslint-disable-next-line dot-notation
                    extraArgs['track_id'] = trackInfoForm.find('#id_track_id').attr('value');
                }
            }
        });
        return false;
    });
};

/**
 * When user adds a new option to selectize, we want to A)sanitise it to remove all special characters and B)Suffix it
 * in order to have duplicate items. Selectize doesn't allow two items with the same value, e.g. if '-' has been added
 * to the list, user cannot add another '-'. We want this to be possible such that a pattern 'foo'-'bar'-'blar' is
 * possible. To get around this problem, after '-' is added to the list of option, we remove it immediately and create
 * a suffixed one, '-$0' and store this one instead. Next time '-' is stored, it will be replaced by '-$1', and so on
 * @param value the original, insanitised value
 * @param data the option item
 */
function handleInputAdded(value, data) {

    // We must do this to avoid infinite callback because later we call addOption which trigger another 'option_add'
    if (value in patternValues) {
        return;
    }
    let sanitised = value.replace(/[^a-zA-Z0-9-_]/g, '').trim();
    let existingsOptions = namePatternInput.options;

    if (sanitised !== value) {
        let message = 'Your pattern contains special characters which I just removed. Only numbers, alphabets, underscores and dashes are allowed.';
        showAlert(ce.alertFailure, message);
    }

    if (sanitised) {
        let suffix = 0;
        let offseted = `${sanitised}$${suffix}`;
        while (offseted in existingsOptions) {
            suffix++;
            offseted = `${sanitised}$${suffix}`;
        }

        data.value = offseted;
        data.text = sanitised;

        patternValues[offseted] = sanitised;

        namePatternInput.removeOption(value);
        namePatternInput.addOption(data);
        namePatternInput.addItem(offseted);
    }
    else {
        namePatternInput.removeOption(value);
    }
    populateNameAll();
}


/**
 * Initialise a selectize attached to #song-name-pattern input with some default options
 * @param options
 */
function initSelectize(options) {
    if (namePatternInput) {
        namePatternInput.destroy();
    }
    namePatternInput = initSelectizeSimple($songNamePatternInput, options, defaultSelectizeArgs);
    namePatternInput.on('option_add', handleInputAdded);

    namePatternInput.on('item_remove', function (value) {
        if (value in patternValues) {
            namePatternInput.removeOption(value);
        }
        populateNameAll();
    });

    namePatternInput.on('item_add', function () {
        populateNameAll();
    });
}


export const run = function (commonElements) {
    ce = commonElements;
    let predefinedSongId = ce.argDict._song;
    let loadSongPromise;

    if (predefinedSongId) {
        loadSongPromise = loadSongById(predefinedSongId);
    }
    else {
        loadSongPromise = initUploadSongsBtn();
    }

    let zoom = ce.argDict._zoom || 100;
    let colourMap = ce.argDict._cm || 'Green';

    spectViz = new Visualiser(vizContainerId);
    spectViz.initScroll();
    spectViz.initController();
    spectViz.resetArgs({zoom, contrast: 0, noverlap: 0, colourMap});

    loadSongPromise.then(function ({sig_, fs_}) {
        audioData.sig = sig_;
        audioData.fs = fs_;
        audioData.length = sig_.length;
        audioData.durationMs = audioData.length * 1000 / fs_;

        spectViz.setData(audioData);
        spectViz.initCanvas();
        spectViz.visualiseSpectrogram();
        spectViz.drawBrush();
    });

    initAudioContext();
    initSaveTrackInfoBtn();

    grid.init(trackInfoForm.find('#id_track_id').attr('value'));

    grid.initMainGridHeader(gridArgs, extraArgs, function () {
        grid.initMainGridContent(gridArgs, extraArgs, function () {
            let syllableArray = grid.mainGrid.getData().getItems();
            let syllableDict = {};
            for (let i = 0; i < syllableArray.length; i++) {
                let item = syllableArray[i];
                syllableDict[item.id] = item;
            }
            setCache('syllableArray', undefined, syllableArray);
            setCache('syllableDict', undefined, syllableDict);
            spectViz.displaySegs();

        });
    });

    initController();
    initKeyboardHooks();
    initDeleteSegmentsBtn();
    initSelectize(defaultOptions);

    renameAllBtn.click(function () {
        let updated = populateNameAll(true);
        saveSongMetadata(updated);
    });
};


export const postRun = function () {
    subscribeFlexibleEvents();
};

export const viewPortChangeHandler = function () {
    grid.mainGrid.resizeCanvas();
};


const saveSongMetadata = function (items) {
    let commitPromise = items.reduce(function (promiseChain, item) {
        return promiseChain.then(function () {
            return grid.rowChangeHandler(null, {item});
        });
    }, Promise.resolve());

    commitPromise.then(function () {
        showAlert(ce.alertSuccess, 'Success', 500);
    });
};
