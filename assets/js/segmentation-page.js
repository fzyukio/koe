/* global keyboardJS*/
import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {changePlaybackSpeed, loadSongById} from './audio-handler';
import {createSpinner, postRequest} from './ajax-handler';
import {Visualiser} from './audio-visualisation';

import {deepCopy, setCache, getCache, isNumber, isNull, calcSegments, extractLogSpect, uuid4} from './utils';
import {calcSpect, POST_PROCESS_NOOP} from './dsp';
import {replaceSlickGridData} from './grid-utils';

require('bootstrap-slider/dist/bootstrap-slider.js');
const tf = require('@tensorflow/tfjs');

const FFT = require('fft.js');

const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 50;

let ce;
const vizContainerId = '#visualisation';
const gridEl = $('#segments-grid');
const fileId = gridEl.attr('file-id');
const fileLength = gridEl.attr('length');
const fileFs = gridEl.attr('fs');
const database = gridEl.attr('database');
const speedSlider = $('#speed-slider');
let spectViz;
const saveSegmentationBtn = $('#save-segmentations-btn');
const deleteSegmentsBtn = $('#delete-segments-btn');
const segSongBtn = $('#seg-song-btn');
const segmentorLoadPath = segSongBtn.attr('load-path');
const segmentorWindowLen = parseInt(segSongBtn.attr('window-len'));
const segmentorNfft = parseInt(segSongBtn.attr('nfft'));
const segmentorNoverlap = parseInt(segSongBtn.attr('noverlap'));
// const segmentorInputDim = parseInt(segSongBtn.attr('input-dim'));
// const segmentorFormat = segSongBtn.attr('format');
const segmentorStepSize = 1;

const fft = new FFT(segmentorNfft);
const fftComplexArray = fft.createComplexArray();

const window = new Float32Array(segmentorNfft);
const cos = Math.cos;
const PI = Math.PI;

/*
 * This is Hann window
 */
for (let i = 0; i < segmentorNfft; i++) {
    window[i] = 0.5 * (1 - cos(PI * 2 * i / (segmentorNfft - 1)));
}


const audioData = {};

class Grid extends FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'segments-grid',
            'grid-type': 'segments-grid',
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

        saveSegmentationBtn.prop('disabled', false);

        if (eventType === 'segment-created') {
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
        if (isNumber(item.id)) {
            super.rowChangeHandler(e, args, onSuccess, onFailure);
        }
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


const initController = function () {
    speedSlider.slider();

    speedSlider.on('slideStop', function (slideEvt) {
        changePlaybackSpeed(slideEvt.value);
    });

    speedSlider.find('.slider').on('click', function () {
        let newValue = speedSlider.find('.tooltip-inner').text();
        changePlaybackSpeed(parseInt(newValue));
    });

    saveSegmentationBtn.click(function () {
        let items = grid.mainGrid.getData().getItems();
        let postData = {
            items: JSON.stringify(items),
            'file-id': fileId
        };
        let onSuccess = function (syllableArray) {
            grid.deleteAllRows();
            grid.appendRows(syllableArray);

            let syllableDict = {};
            for (let i = 0; i < syllableArray.length; i++) {
                let item = syllableArray[i];
                syllableDict[item.id] = item;
            }
            setCache('syllableArray', undefined, syllableArray);
            setCache('syllableDict', undefined, syllableDict);

            spectViz.displaySegs();
            saveSegmentationBtn.prop('disabled', true);
        };
        ce.dialogModal.modal('hide');
        let msgGen = function (isSuccess) {
            return isSuccess ? 'Success' : null;
        };
        postRequest({
            requestSlug: 'koe/save-segmentation',
            data: postData,
            onSuccess,
            msgGen,
            immediate: true
        });
    })
};


/**
 * Allows user to remove songs
 */
const initDeleteSegmentsBtn = function () {
    deleteSegmentsBtn.click(function () {
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
        let syllableArray = grid.mainGrid.getData().getItems();
        setCache('syllableArray', undefined, syllableArray);

        saveSegmentationBtn.prop('disabled', false);
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
        deleteSegmentsBtn.prop('disabled', false);
    }

    /**
     * When segments are removed, if there is songs left, disable the delete button
     * @param e event
     * @param args contains 'grid' - the main SlickGrid
     */
    function disableDeleteSegmentsBtn(e, args) {
        let grid_ = args.grid;
        if (grid_.getSelectedRows().length == 0) deleteSegmentsBtn.prop('disabled', true);
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
    'file_id': fileId,
    database
};

let gridArgs = {
    multiSelect: true,
    doCacheSelectableOptions: false
};

const convertJsonToTable = function() {
    let tableBody = $('#song-info tbody');
    let jsonData = tableBody.attr('json-data');
    let data = JSON.parse(jsonData);
    tableBody.attr('json-data', undefined);
    $.each(data, function (attr, value) {
        if (typeof value === 'string' && value.startsWith('__')) {
            let rowId = value.substr(2);
            value = getCache(rowId);
        }
        tableBody.append(`<tr><td>${attr}</td><td>${value}</td></tr>`);
    })
}

export const preRun = function (commonElements) {
    ce = commonElements;
    let zoom = ce.argDict._zoom || 100;
    let colourMap = ce.argDict._cm || 'Green';

    initController();
    convertJsonToTable();
    spectViz = new Visualiser(vizContainerId);
    spectViz.resetArgs({zoom, contrast: 0, noverlap: 0, colourMap});
    spectViz.initScroll();

    return new Promise(function (resolve, reject) {
        postRequest({
            requestSlug: 'koe/get-label-options',
            data: {'file-id': fileId},
            onSuccess(selectableOptions) {
                setCache('selectableOptions', undefined, selectableOptions);
                resolve();
            },
            onFailure(responseMessage) {
                reject(new Error(responseMessage));
            },
            immediate: true
        });
    });
};

export const run = function () {

    /*
     * Clear all temporary variables
     */
    setCache('resizeable-syl-id', undefined, undefined);
    setCache('file-id', undefined, fileId);
    setCache('file-length', undefined, fileLength);
    setCache('file-fs', undefined, fileFs);
    grid.init(fileId);

    let loadSongPromise = loadSongById.bind({predefinedSongId: fileId});
    let loadPreferencePromise = () => new Promise(function (resolve, reject) {
        postRequest({
            requestSlug: 'koe/get-database-spectrogram-preference',
            data: {'file-id': fileId},
            immediate: true,
            onSuccess: resolve
        });
    });

    return loadPreferencePromise().then(function ({cm, zoom}) {
        return loadSongPromise().then(function ({dataArrays, realFs, realLength, browserFs}) {
            audioData.fileId = fileId;
            audioData.dataArrays = dataArrays;
            audioData.realFs = realFs;
            audioData.browserFs = browserFs;
            audioData.realLength = realLength;
            audioData.browserLength = dataArrays[0].length;
            audioData.durationMs = realLength * 1000 / realFs;

            audioData.durationRatio = (realLength / realFs) / (audioData.browserLength / audioData.browserFs);
            if (!isNull(zoom)) {
                spectViz.resetArgs({zoom: zoom});
            }
            if (!isNull(cm)) {
                spectViz.resetArgs({colourMap: cm});
            }
            spectViz.setData(audioData);
            spectViz.initCanvas();
            spectViz.initController();
            spectViz.visualiseSpectrogram();
            spectViz.drawBrush();

            return grid.initMainGridHeader(gridArgs, extraArgs).then(function () {
                return grid.initMainGridContent(gridArgs, extraArgs).then(function () {
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
        });
    });
};


const initSegmentationButton = function() {
    const spectXScaleInvert = spectViz.spectXScale.invert;
    let spinner = createSpinner();

    segSongBtn.one('click', function () {
        spinner.start();
        const MODEL_URL = `${segmentorLoadPath}/model.json`;
        const loadGraphPromise = tf.loadGraphModel(MODEL_URL);

        const outputDim = 1;
        const goToken = -1;


        const extractLogPromise = new Promise(function (resolve) {
            const sig = audioData.dataArrays[0];
            const segs = calcSegments(sig.length, segmentorNfft, segmentorNoverlap);

            const spectrogram = calcSpect(sig, segs, fft, fftComplexArray, window, POST_PROCESS_NOOP);
            const logSpect = extractLogSpect(spectrogram);
            resolve(logSpect);
        });

        let runSegmentationPrimise = Promise.all([loadGraphPromise, extractLogPromise]).then(function (values) {
            const [model, logSpect] = [...values];

            const windows = calcSegments(logSpect.length, segmentorWindowLen, segmentorWindowLen - segmentorStepSize);
            const windoweds = [];
            for (const window_ of windows) {
                let [start, end] = [...window_];
                const windowed = logSpect.slice(start, end);
                windoweds.push(windowed);
            }
            const inputBatch = tf.tensor(windoweds);
            const batchSize = windoweds.length;

            const actualStartToken = tf.fill([batchSize, outputDim], goToken);
            const targetSequenceLength = tf.fill([batchSize], segmentorWindowLen).toInt();
            const sourceSequenceLength = tf.fill([batchSize], segmentorWindowLen).toInt();

            const mask = new Array(logSpect.length).fill(0);

            const executionPromise = model.executeAsync([targetSequenceLength, sourceSequenceLength, actualStartToken, inputBatch]);
            return executionPromise.then((value) => value.array()).then(function (predicteds) {
                for (let i = 0; i < windows.length; i++) {
                    let predicted = predicteds[i];
                    let frameBegin = windows[i][0];
                    $.each(predicted, function (j, frameOutput) {
                        if (frameOutput > 0.5) {
                            mask[frameBegin + j]++;
                        }
                    });
                }

                const threshold = segmentorWindowLen * 0.3;
                const syllableFrames = [];
                for (const maskFrame of mask) {
                    syllableFrames.push(maskFrame > threshold);
                }

                const syllables = [];
                let currentSyllable = null;
                let opening = false;

                for (let i = 0; i < logSpect.length - 1; i++) {
                    let thisFrame = syllableFrames[i];
                    let nextFrame = syllableFrames[i + 1];
                    if (thisFrame && nextFrame) {
                        if (!opening) {
                            opening = true;
                            currentSyllable = [i];
                        }
                    }
                    else if (thisFrame && opening) {
                        opening = false;
                        currentSyllable.push(i);
                        syllables.push(currentSyllable);
                        currentSyllable = null;
                    }
                }

                return syllables;
            });
        });

        runSegmentationPrimise.then(function (syllables) {
            const syllablesMs = [];
            const syllableDict = {};
            for (const syllable of syllables) {
                const startMs = Math.round(spectXScaleInvert(syllable[0]));
                const endMs = Math.round(spectXScaleInvert(syllable[1]));

                let uuid = uuid4();
                let newId = `new:${uuid}`;

                let syllableMs = {
                    duration: endMs - startMs,
                    end: endMs,
                    id: newId,
                    start: startMs
                };
                syllablesMs.push(syllableMs);
                syllableDict[newId] = syllableMs
            }
            replaceSlickGridData(grid.mainGrid, syllablesMs);
            setCache('syllableArray', undefined, syllablesMs);
            setCache('syllableDict', undefined, syllableDict);

            spectViz.clearAllSegments();
            spectViz.displaySegs();

            spinner.clear();
        });
    });
}

export const postRun = function () {
    initKeyboardHooks();
    initDeleteSegmentsBtn();
    initSegmentationButton();
    subscribeFlexibleEvents();
    return Promise.resolve();
};

export const viewPortChangeHandler = function () {
    grid.mainGrid.resizeCanvas();
};
