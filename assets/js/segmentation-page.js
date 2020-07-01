/* global keyboardJS*/
import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {changePlaybackSpeed, loadSongById} from './audio-handler';
import {deepCopy, setCache, getCache, isNumber, isNull, getUrl} from './utils';
import {postRequest} from './ajax-handler';
import {Visualiser} from './audio-visualisation';

require('bootstrap-slider/dist/bootstrap-slider.js');

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

export const preRun = function (commonElements) {
    ce = commonElements;
    let zoom = ce.argDict._zoom || 100;
    let colourMap = ce.argDict._cm || 'Green';

    initController();
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
    return new Promise(function (resolve, reject) {
        postRequest({
            requestSlug: 'koe/get-database-spectrogram-preference',
            data: {'file-id': fileId},
            immediate: true,
            onSuccess({cm, zoom}) {
                return loadSongPromise().then(function({dataArrays, realFs, realLength, browserFs}) {
                    audioData.fileId = fileId;
                    audioData.dataArrays = dataArrays;
                    audioData.realFs = realFs;
                    audioData.browserFs = browserFs;
                    audioData.realLength = realLength;
                    audioData.browserLength = dataArrays[0].length;
                    audioData.durationMs = realLength * 1000 / realFs;

                    audioData.durationRatio = (realLength / realFs) / (audioData.browserLength / audioData.browserFs);
                    if (!isNull(zoom)){
                        spectViz.resetArgs({zoom: zoom});
                    }
                    if (!isNull(cm)){
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
            }
        });
    });
};


export const postRun = function () {
    initKeyboardHooks();
    initDeleteSegmentsBtn();
    subscribeFlexibleEvents();
    return Promise.resolve();
};

export const viewPortChangeHandler = function () {
    grid.mainGrid.resizeCanvas();
};
