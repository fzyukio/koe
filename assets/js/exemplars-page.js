import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {deepCopy, getUrl, getCache, setCache, debug} from './utils';
import {changePlaybackSpeed, initAudioContext, queryAndPlayAudio} from './audio-handler';
const keyboardJS = require('keyboardjs/dist/keyboard.min.js');
require('bootstrap-slider/dist/bootstrap-slider.js');


const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 50;


class ExemplarsGrid extends FlexibleGrid {
    init() {

        super.init({
            'grid-name': 'exemplars',
            'grid-type': 'exemplars-grid',
            'default-field': 'cls',
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

export const grid = new ExemplarsGrid();
let cls = $('#exemplars-grid').attr('cls');
let fromUser = $('#exemplars-grid').attr('from_user');

const tooltip = $('#spectrogram-details-tooltip');
const tooltipImg = tooltip.find('img');
const speedSlider = $('#speed-slider');
const gridStatus = $('#grid-status');
const gridStatusNTotal = gridStatus.find('#ntotal');


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

const imgRegex = /.*?\/(\d+)\.png/;

const playAudio = function (e, args) {
    let cellElement = $(args.e.target);
    let hasImage = cellElement.closest('.has-image');
    if (hasImage.length == 1) {
        let imgSrc = hasImage.find('img').attr('src');
        let match = imgRegex.exec(imgSrc);
        if (match) {
            let segId = match[1];
            let args_ = {
                url: getUrl('send-request', 'koe/get-segment-audio-data'),
                cacheKey: segId,
                postData: {'segment-id': segId}
            };
            queryAndPlayAudio(args_);
        }
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

/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    debug('subscribeFlexibleEvents called');
    grid.on('click', function (...args) {
        let e = args[0];
        e.preventDefault();
        playAudio(...args);
        selectTextForCopy(...args);
    });

    grid.on('mouseenter', showBigSpectrogram);
    grid.on('mouseleave', clearSpectrogram);
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

    grid.subscribe('onActiveCellChanged', showSpectrogramOnActiveCell);
};


const showBigSpectrogram = function (e, args) {
    e.preventDefault();
    let cellElement = $(args.e.target);
    let hasImage = cellElement.closest('.has-image');
    if (hasImage.length == 1) {
        const originalImage = hasImage.find('img');

        tooltipImg.attr('src', originalImage.attr('src'));
        tooltip.removeClass('hidden');

        originalImage.addClass('highlight');

        const panelHeight = $('#exemplars-grid').height();
        const imgWidth = tooltipImg.width();
        const imgHeight = tooltipImg.height();

        const pos = hasImage.offset();
        const cellTop = pos.top;
        const cellLeft = pos.left;

        let cellBottom = cellTop + originalImage.height();
        let cellCentreX = cellLeft + originalImage.width() / 2;
        let imgLeft = cellCentreX - imgWidth / 2;

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

        setCache('current-highlighted-image', undefined, originalImage)
    }
};


/**
 * Hide the tooltip and remove highlight from the active image
 */
const clearSpectrogram = function () {
    tooltip.addClass('hidden');
    let originalImage = getCache('current-highlighted-image');
    if (originalImage) {
        originalImage.removeClass('highlight');
        setCache('current-highlighted-image', undefined, undefined)
    }
};


/**
 * Play the sound if the current active cell is the spectrogram
 * @param e
 */
const playAudioOnKey = function (e) {
    let grid_ = grid.mainGrid;
    let activeCell = grid_.getActiveCell();
    if (activeCell) {
        let activeCellEl = grid_.getCellNode(activeCell.row, activeCell.cell);

        // This if statement will check if the click falls into the grid
        // Because the actual target is lost, the only way we know that the activeCellEl is focused
        // Is if the event's path contains the main grid
        if ($(e.path[1]).has($(activeCellEl)).length) {
            let column = grid_.getColumns()[activeCell.cell];
            if (!column.editable) {
                let fakeEvent = {target: activeCellEl};
                let args = {e: fakeEvent};
                playAudio(e, args);
            }
        }
    }
};


/**
 * Highlight and show the big spectrogram when the active cell is a spectrogram
 * @param e
 * @param args
 */
const showSpectrogramOnActiveCell = function (e, args) {
    clearSpectrogram();
    let grid_ = grid.mainGrid;
    let activeCell = grid_.getActiveCell();
    if (activeCell) {
        let activeCellEl = grid_.getCellNode(args.row, args.cell);
        let column = grid_.getColumns()[activeCell.cell];
        if (!column.editable) {
            let fakeEvent = {
                target: activeCellEl,
                preventDefault () {

                    /* do nothing */
                }
            };
            let args_ = {e: fakeEvent};
            showBigSpectrogram(fakeEvent, args_);
        }
    }
};


/**
 * Set the focus on the grid right after page is loaded.
 * This is mainly so that user can use Page Up and Page Down right away
 */
const focusOnGridOnInit = function () {
    $($('div[hidefocus]')[0]).focus();
};


let extraArgs = {
    cls,
    'from_user': fromUser
};


export const run = function () {

    initAudioContext();

    grid.init();
    grid.initMainGridHeader({}, extraArgs, function () {
        grid.initMainGridContent({}, extraArgs, focusOnGridOnInit);
        subscribeSlickEvents();
        subscribeFlexibleEvents();
    });

    keyboardJS.bind(['space'], playAudioOnKey);

    initSlider();
};

export const handleDatabaseChange = function() {
    location.reload()
};

