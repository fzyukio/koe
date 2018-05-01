import * as ah from './audio-handler';
import * as fg from 'flexible-grid';
import * as vs from 'visualise-d3';
import {defaultGridOptions} from './flexible-grid';
import {deepCopy, getUrl, setCache} from "./utils";
require('bootstrap-slider/dist/bootstrap-slider.js');


const gridOptions = deepCopy(defaultGridOptions);

class Grid extends fg.FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'segments-grid',
            'grid-type': 'segments-grid',
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
        self.eventNotifier.trigger(eventType, {songId: songId, rowElement: rowElement});
    }

    /**
     * Highlight the owner's measurement in the segmentation table when the corresponding spectrogram owner is mouseover
     * @param args indexed array {event: name of the event, target: the element that is being mouseover}
     */
    segmentMouseEventHandler(e, args) {
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
    };
}

const grid = new Grid();
const gridEl = $('#segments-grid');
const fileId = gridEl.attr('file-id');
const fileLength = gridEl.attr('length');
const fileFs = gridEl.attr('fs');
const speedSlider = $('#speed-slider');
const spectrogramId = 'spectrogram';
const viz = new vs.Visualise();


export const visualiseSong = function (fileId, callback) {
    /*
     * Clear all temporary variables
     */
    setCache('resizeable-syl-id', undefined);
    setCache('syllables', {});
    setCache('next-syl-idx', 0);

    let data = new FormData();
    data.append('file-id', fileId);
    let args = {
        url: getUrl('send-request', 'koe/get-segment-audio'),
        postData: data,
        cacheKey: fileId,
        startSecond: null,
        endSecond: null
    };
    ah.queryAndHandleAudio(args, function (sig, fs) {
        viz.visualise(fileId, sig, fs);
        callback();
    });
};

export const highlightSegments = function (e, args) {
    let eventType = e.type;
    let songId = args.songId;
    let segmentsGridRowElement = args.rowElement;

    let spectrogramSegment = $('#' + spectrogramId + ' rect.syllable[syl-id="' + songId + '"]');

    if (eventType === 'mouseenter') {
        segmentsGridRowElement.addClass('highlight');
        spectrogramSegment.addClass('highlight');
    }
    else {
        segmentsGridRowElement.removeClass('highlight');
        spectrogramSegment.removeClass('highlight');
    }
};


const initSlider = function () {
    speedSlider.slider();

    speedSlider.on('slide', function (slideEvt) {
        ah.changePlaybackSpeed(slideEvt.value);
    });

    $('.slider').on('click', function () {
        let newValue = $('.tooltip-inner').text();
        ah.changePlaybackSpeed(parseInt(newValue));
    });
};


/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    grid.on('mouseenter', highlightSegments);
    grid.on('mouseleave', highlightSegments);
};


export const run = function () {
    setCache('file-id', fileId);
    setCache('file-length', fileLength);
    setCache('file-fs', fileFs);

    ah.initAudioContext();
    grid.init(fileId);
    viz.init(spectrogramId);
    viz.eventNotifier.on("segment-mouse", function (e, args) {
        grid.segmentMouseEventHandler(e, args);
    });

    visualiseSong(fileId, function () {
        grid.initMainGridHeader({'__extra__file_id': fileId}, function () {
            grid.initMainGridContent({'__extra__file_id': fileId}, function () {
                let items = grid.mainGrid.getData().getItems();
                let syllables = {};
                for (let i = 0; i < items.length; i++) {
                    let item = items[i];
                    syllables[item.id] = item;
                }
                setCache('syllables', syllables);
                viz.displaySegs(items);
            });
            subscribeFlexibleEvents();
        });
    });
    initSlider();
};
