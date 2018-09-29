/* global keyboardJS*/
import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {
    changePlaybackSpeed,
    createAudioFromDataArray,
    initAudioContext,
    loadLocalAudioFile
} from './audio-handler';
import {deepCopy, setCache, getCache, smotthScrollTo} from './utils';
import {postRequest, uploadRequest} from './ajax-handler';
import {Visualise} from './visualise-raw';

require('bootstrap-slider/dist/bootstrap-slider.js');

const gridOptions = deepCopy(defaultGridOptions);

let scrollingPromise;
const uploadSongsBtn = $('#upload-raw-recording-btn');
const audioUploadForm = $('#file-upload-form');
const audioUploadInput = audioUploadForm.find('input[type=file]');

const audioData = {};
let sig;
let fs;

class Grid extends FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'song-partition-grid',
            'grid-type': 'song-partition-grid',
            gridOptions
        });
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
        let row = cell.row;
        let rowElement = $(e.target.parentElement);
        let songId = dataView.getItem(row).id;
        self.eventNotifier.trigger(eventType, {
            songId,
            rowElement
        });
    }

    /**
     * Highlight the owner's measurement in the segmentation table when the corresponding spectrogram owner is mouseover
     * @param args indexed array {event: name of the event, target: the element that is being mouseover}
     */
    segmentMouseEventHandler(e, args) {
        let resizing = getCache('resizeable-syl-id');
        if (resizing && viz.editMode) {
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

        if (trackInfoForm.find('#id_track_id').attr('valid') === 'true') {
            saveSongsBtn.prop('disabled', false);
        }

        if (eventType === 'segment-created') {
            dataView.addItem(target);
        }
        else if (eventType === 'segment-adjusted') {
            dataView.updateItem(target.id, target);
        }
    }

    rowChangeHandler(e, args, onSuccess, onFailure) {
        let item = args.item;

        // Only change properties of files that already exist on the server
        if (item.progress === 'Uploaded') {
            super.rowChangeHandler(e, args, onSuccess, onFailure);
        }
    }
}

export const grid = new Grid();
const gridEl = $('#song-partition-grid');
const databaseId = gridEl.attr('database-id');
const speedSlider = $('#speed-slider');
const contrastSlider = $('#contrast-slider');
const visualisationContainer = $('#track-visualisation');
const spectrogramId = '#spectrogram';
const oscillogramId = '#oscillogram';
const viz = new Visualise();
const saveSongsBtn = $('#save-songs-btn');
const deleteSongsBtn = $('#delete-songs-btn');
const trackInfoForm = $('#track-info');
const saveTrackInfoBtn = trackInfoForm.find('#save-track-info');

export const highlightSegments = function (e, args) {
    let eventType = e.type;
    let songId = args.songId;
    let segmentsGridRowElement = args.rowElement;

    let spectrogramSegment = $(`${spectrogramId} rect.syllable[syl-id="${songId}"]`);

    if (eventType === 'mouseenter') {
        segmentsGridRowElement.addClass('highlight');
        spectrogramSegment.addClass('highlight');
    }
    else {
        segmentsGridRowElement.removeClass('highlight');
        spectrogramSegment.removeClass('highlight');
    }
};


const redrawSpectrogram = function () {
    viz.visualiseSpectrogram(sig);
};


const startScrolling = function (startX, endX, duration) {
    let visualisationEl = visualisationContainer[0];
    visualisationEl.scrollLeft = 0;
    let visualisationWidth = visualisationContainer.width();
    let distance = endX - startX - visualisationWidth;
    let speed = duration / (endX - startX);
    let delayStart = visualisationWidth / 2;
    let prematureEnd = visualisationWidth / 2;

    let delayStartDuration = delayStart * speed;
    let prematureEndDuration = prematureEnd * speed;
    let remainDuration = duration - delayStartDuration - prematureEndDuration;


    setTimeout(function () {
        scrollingPromise = smotthScrollTo(visualisationEl, visualisationEl.scrollLeft + distance, remainDuration);
    }, delayStartDuration)

};


const stopScrolling = function () {
    if (scrollingPromise) {
        scrollingPromise.cancel();
    }
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

    contrastSlider.slider();

    contrastSlider.on('slideStop', function (slideEvt) {
        viz.contrast = slideEvt.value;
        redrawSpectrogram();
    });

    contrastSlider.find('.slider').on('click', function () {
        let newValue = speedSlider.find('.tooltip-inner').text();
        viz.contrast = parseInt(newValue);
        redrawSpectrogram();
    });

    $('#play-song').click(function () {
        viz.playAudio(0, 'end', startScrolling, stopScrolling);
    });

    $('#stop-song').click(function () {
        viz.stopAudio();
        stopScrolling();
    });

    saveSongsBtn.click(function () {
        let items = grid.mainGrid.getData().getItems();
        let syllables = getCache('syllables');
        let itemsToUpdate = [];
        for (let i = 0; i < items.length; i++) {
            let item = items[i];
            if (item.progress !== 'Uploaded') {
                itemsToUpdate.push(item);
            }
        }

        for (let i = 0; i < itemsToUpdate.length; i++) {
            let item = itemsToUpdate[i];
            let startMs = item.start;
            let endMs = item.end;
            let durationMs = audioData.durationMs;
            let nSamples = audioData.length;
            let startSample = Math.floor(startMs * nSamples / durationMs);
            let endSample = Math.min(Math.ceil(endMs * nSamples / durationMs), nSamples);

            let subSig = sig.slice(startSample, endSample);
            let blob = createAudioFromDataArray(subSig, fs);

            let formData = new FormData();
            formData.append('file', blob, item.name);
            formData.append('item', JSON.stringify(item));
            formData.append('database-id', databaseId);
            formData.append('track-id', trackInfoForm.find('#id_track_id').attr('value'));


            let onSuccess = function ({id, name}) {
                let oldId = item.id;

                grid.mainGrid.invalidateRows(oldId);
                item.progress = 'Uploaded';
                item.id = id;
                item.name = name;
                grid.mainGrid.render();

                if (oldId !== id) {
                    syllables[id] = syllables[oldId];
                    delete syllables[oldId];
                }
                if (i === itemsToUpdate.length - 1) {
                    grid.deleteAllRows();
                    grid.appendRows(items);
                    saveSongsBtn.attr('disabled', true);
                    setCache('resizeable-syl-id', null, undefined);
                    viz.displaySegs(items);
                }
            };

            let onProgress = function (e) {
                if (e.loaded === e.total) {
                    // Do nothing to not be in conflict with onSuccess
                    return;
                }
                let percentComplete = Math.round(e.loaded * 100 / e.total);
                let oldId = item.id;
                item.progress = `${percentComplete} %`;
                grid.mainGrid.invalidateRows(oldId);
                grid.mainGrid.render();
            };

            uploadRequest({
                requestSlug: 'koe/import-audio-file',
                data: formData,
                onSuccess,
                onProgress
            });
        }
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
        let syllables = getCache('syllables');
        let itemsIds = [];
        for (let i = 0; i < numRows; i++) {
            let item = dataView.getItem(selectedRows[i]);
            itemsIds.push(item.id);
        }

        for (let i = 0; i < numRows; i++) {
            let itemId = itemsIds[i];
            dataView.deleteItem(itemId);
            delete syllables[itemId];
        }
        viz.displaySegs(syllables);
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

    viz.eventNotifier.on('segment-mouse', function (e, args) {
        grid.segmentMouseEventHandler(e, args);
    });

    viz.eventNotifier.on('segment-changed', function (e, args) {
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
                viz.showBrush(highlighted);
            }
            viz.editMode = true;
        }, function () {
            viz.clearBrush();
            viz.editMode = false;
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

        loadLocalAudioFile({file,
            reader,
            onProgress,
            onError,
            onLoad,
            onAbort,
            onLoadStart}).then(function (args) {
            sig = args.sig;
            fs = args.fs;
            audioData.sig = sig;
            audioData.fs = fs;
            audioData.length = sig.length;
            audioData.durationMs = audioData.length * 1000 / fs;

            uploadModal.modal('hide');
            viz.visualise(sig, fs);
        });
    });

    cancelDownloadBtn.click(function () {
        cancelDownloadBtn.attr('disabled', true);
        uploadSongsBtn.attr('disabled', false);
        reader.abort();
    });

    uploadModal.modal('show');
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


export const run = function () {
    initUploadSongsBtn();
    initAudioContext();
    initSaveTrackInfoBtn();

    // let data = {'file-id': '571283'};
    // let args = {
    //     url: getUrl('send-request', 'koe/get-file-audio-data'),
    //     postData: data,
    //     cacheKey: '571283',
    // };
    // queryAndHandleAudio(args,
    //     function (sig_, fs_) {
    //         sig = sig_;
    //         fs = fs_;
    //         audioData.sig = sig;
    //         audioData.fs = fs;
    //         audioData.length = sig.length;
    //         audioData.durationMs = audioData.length * 1000 / fs;
    //
    //         viz.visualise(sig, fs);
    //     }
    // );

    grid.init(trackInfoForm.find('#id_track_id').attr('value'));
    viz.init(oscillogramId, spectrogramId);

    grid.initMainGridHeader(gridArgs, extraArgs, function () {
        grid.initMainGridContent(gridArgs, extraArgs, function () {
            let items = grid.mainGrid.getData().getItems();
            let syllables = {};
            for (let i = 0; i < items.length; i++) {
                let item = items[i];
                syllables[item.id] = item;
            }
            setCache('syllables', undefined, syllables);
            viz.displaySegs(items);
        });
    });

    initController();
    initKeyboardHooks();
    initDeleteSegmentsBtn();
};


export const postRun = function () {
    subscribeFlexibleEvents();
};

export const viewPortChangeHandler = function () {
    grid.mainGrid.resizeCanvas();
};
