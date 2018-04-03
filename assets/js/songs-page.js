import * as fg from "flexible-grid";
import {defaultGridOptions} from "./flexible-grid";
import * as ah from "./audio-handler";
import {log, deepCopy, getUrl} from "utils";
require('bootstrap-slider/dist/bootstrap-slider.js');


const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 50;


class Grid extends fg.FlexibleGrid {
    init(cls) {

        super.init({
            'grid-name': 'songs-grid',
            'grid-type': 'songs-grid',
            'default-field': 'filename',
            gridOptions
        });

        this.cls = cls;
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
let cls = $('#songs-grid').attr('cls');

const tooltip = $("#spectrogram-details-tooltip");
const tooltipImg = tooltip.find('img');
const speedSlider = $("#speed-slider");
const gridStatus = $('#grid-status');
const gridStatusNTotal = gridStatus.find('#ntotal');

const databaseCombo = $('#database-select-combo');
const currentDatabaseAttr = databaseCombo.attr('current-attr');
const databaseClass = databaseCombo.attr('cls');


const initSlider = function () {
    speedSlider.slider();

    speedSlider.on("slide", function (slideEvt) {
        ah.changePlaybackSpeed(slideEvt.value);
    });

    $('.slider').on("click", function () {
        let newvalue = $('.tooltip-inner').text();
        ah.changePlaybackSpeed(parseInt(newvalue));
    });
};

const playAudio = function (e, args) {
    let cellElement = $(args.e.target);
    let hasSyllable = cellElement.closest(".syllable");
    if (hasSyllable.length == 1) {
        let audioUrl = hasSyllable.parent().find('.full-audio').
            attr('song-url');
        let start = parseInt(hasSyllable.attr('start')) / 1000.0;
        let end = parseInt(hasSyllable.attr('end')) / 1000.0;
        ah.playAudioFromUrl(audioUrl, start, end);
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
    log(`subscribeFlexibleEvents called from songs-pages`);
    grid.on('click', function (...args) {
        let e = args[0];
        e.preventDefault();
        playAudio(...args);
        selectTextForCopy(...args);
        clearSpectrogram(...args);
        showBigSpectrogram(...args);
    });
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


/**
 * Redraw the table on orientation changed
 */
export const orientationChange = function () {
    grid.redrawMainGrid({
        rowMoveable: true,
        multiSelect: true
    }, function () {
        subscribeSlickEvents();
    });
};


const showBigSpectrogram = function (e, args) {
    e.preventDefault();
    let cellElement = $(args.e.target);
    let isSyllable = cellElement.closest(".syllable");
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


export const run = function () {
    ah.initAudioContext();

    grid.init(cls);
    grid.initMainGridHeader({}, function () {
        grid.initMainGridContent({'__extra__cls': cls}, focusOnGridOnInit);
        subscribeSlickEvents();
        subscribeFlexibleEvents();
    });

    $('.select-database').on('click', function (e) {
        e.preventDefault();

        let parent = $(this).parent();
        if (parent.hasClass('not-active')) {
            let databaseId = this.getAttribute('database');

            $.post(
                getUrl('send-request', 'change-extra-attr-value'),
                {
                    'attr': currentDatabaseAttr,
                    'klass': databaseClass,
                    'value': databaseId
                },
                function () {
                    grid.initMainGridContent({'__extra__cls': cls}, focusOnGridOnInit);
                }
            );

            /* Update the button */
            databaseCombo.attr('database', databaseId);
            parent.parent().find('li.active').
                removeClass('active').
                addClass('not-active');
            parent.removeClass('not-active').addClass('active');
        }
    });

    initSlider();
};
