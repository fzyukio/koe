import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {deepCopy, getUrl, getCache, setCache, debug, randomRange} from './utils';
import {changePlaybackSpeed, queryAndPlayAudio} from './audio-handler';
import {postRequest} from './ajax-handler';
import {updateSlickGridData} from './grid-utils';
require('bootstrap-slider/dist/bootstrap-slider.js');


const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 50;

// To store the spectrogram's random indices and curent random batch's index
const spectrogramRandInds = {};
const numSpectrogramsToShow = 10;

/**
 * Shuffle all exemplars randomly and pick the next 10 exemplars (rotate at end of arrays)
 * @param rows SlickGrid rows
 * @returns {Array} array of the same rows, with 10 spectrograms each class
 */
function randomPick(rows) {
    let rndRows = [];
    $.each(rows, function(idx, row) {
        let rndRow = {
            id: row.id, cls: row.cls, count: row.count
        };
        let spectrograms = row.spectrograms;
        let nSpectrograms = spectrograms.length;
        if (nSpectrograms <= numSpectrogramsToShow) {
            rndRow.spectrograms = spectrograms;
        }
        else {
            let exists = spectrogramRandInds[row.id];
            let randomIndices, currentIdx;
            if (exists) {
                randomIndices = exists.randomIndices;
                currentIdx = exists.currentIdx;
            }
            else {
                randomIndices = randomRange(nSpectrograms);
                currentIdx = 0;
                spectrogramRandInds[row.id] = {
                    randomIndices, currentIdx
                };
            }
            let rndSpectrograms = [];
            for (let i = 0; i < numSpectrogramsToShow; i++) {
                if (currentIdx >= nSpectrograms) {
                    currentIdx = 0;
                }
                let ind = randomIndices[currentIdx];
                rndSpectrograms.push(spectrograms[ind]);
                currentIdx++;
            }
            spectrogramRandInds[row.id].currentIdx = currentIdx;
            rndRow.spectrograms = rndSpectrograms;
        }
        rndRows.push(rndRow);
    });
    return rndRows;
}


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
     * Overwrite because we want to deal with the rows differently
     * @param defaultArgs
     * @param extraArgs
     */
    initMainGridContent(defaultArgs, extraArgs) {
        let self = this;
        self.defaultArgs = defaultArgs || {};

        let args = deepCopy(self.defaultArgs);
        args['grid-type'] = self.gridType;

        if (extraArgs) {
            args.extras = JSON.stringify(extraArgs);
        }

        return new Promise(function(resolve) {
            postRequest({
                requestSlug: 'get-grid-content',
                data: args,
                onSuccess(rows) {
                    resolve(rows);
                }
            });
        });
    }
}

export const grid = new ExemplarsGrid();
let granularity = $('#exemplars-grid').attr('granularity');
let viewas = $('#exemplars-grid').attr('viewas');

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

const playAudio = function (e) {
    e.preventDefault();
    let imgSrc = this.getAttribute('src');
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
};


/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 * When mouse over a slickgrid cell, attach event handlers to all the children.
 * When mouse leaves, remove events
 *
 * We have to do this because
 *  1) In this view, the spectrogram cells contain multiple images and we want to deal with
 * then separately. So dealing with cell's mouse events is not enough
 *  2) We can't blanket bind mouse event handlers to all images because only a few rows are rendered at a time.
 * The one unrendered will not be affected by such blanket bind
 */
const subscribeFlexibleEvents = function () {
    debug('subscribeFlexibleEvents called');
    grid.on('mouseenter', attachHandlerToChildren);
    grid.on('mouseleave', removeHandlerFromChildrem);
};


/**
 * When mouse over a cell, make each image handle:
 *  - mouseover by showing big image
 *  - mouseleave by removing the big image just shown
 *  - click by play the audio segment corresponding to the segment being clicked
 * @param e
 * @param args
 */
const attachHandlerToChildren = function(e, args) {
    let rowElement = args.rowElement;
    let target = args.target;

    // If the mouse is already over one of the children, trigger it manually
    if (target.tagName === 'IMG') {
        showBigSpectrogram($(target));
    }

    let children = rowElement.find('img');
    children.
        on('mouseover', function(e_) {
            e_.preventDefault();
            showBigSpectrogram($(this));
        }).
        on('mouseleave', clearSpectrogram).
        on('click', playAudio);
};

/**
 * Remove all event handler binding from the images once the mouse leaves their parent cell
 * @param e
 * @param args
 */
const removeHandlerFromChildrem = function(e, args) {
    let rowElement = args.rowElement;
    rowElement.find('img').off('mouseover').off('mouseleave').off('click');
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
};


const showBigSpectrogram = function ($img) {
    // exemplar-view
    tooltipImg.attr('src', $img.attr('src'));
    tooltip.removeClass('hidden');

    $img.addClass('highlight');

    const panelHeight = $('#exemplars-grid').height();
    const imgWidth = tooltipImg.width();
    const imgHeight = tooltipImg.height();

    const pos = $img.offset();
    const cellTop = pos.top;
    const cellLeft = pos.left;

    let cellBottom = cellTop + $img.height();
    let cellCentreX = cellLeft + $img.width() / 2;
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

    setCache('current-highlighted-image', undefined, $img);
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
 * Set the focus on the grid right after page is loaded.
 * This is mainly so that user can use Page Up and Page Down right away
 */
const focusOnGridOnInit = function () {
    $($('div[hidefocus]')[0]).focus();
};


let extraArgs = {
    granularity,
    viewas
};


export const run = function () {
    grid.init();

    initSlider();

    // Get the next 10 random spectrogram and replace existing ones with them
    $('#next-10').click(function() {
        let rows = randomPick(grid.rows);
        updateSlickGridData(grid.mainGrid, rows);
    });

    return grid.initMainGridHeader({}, extraArgs).then(function () {
        subscribeSlickEvents();
        subscribeFlexibleEvents();

        return grid.initMainGridContent({}, extraArgs).then(function(rows) {
            grid.rows = rows;
            rows = randomPick(grid.rows);

            grid.appendRows(rows);

            focusOnGridOnInit();
        });
    });
};

export const viewPortChangeHandler = function () {
    grid.mainGrid.resizeCanvas();
};
