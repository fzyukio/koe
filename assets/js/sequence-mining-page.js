import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {initAudioContext} from './audio-handler';
import {debug, deepCopy} from './utils';
require('bootstrap-slider/dist/bootstrap-slider.js');


const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 25;


class Grid extends FlexibleGrid {
    init(cls) {

        super.init({
            'grid-name': 'sequences',
            'grid-type': 'sequence-mining-grid',
            'default-field': 'assocrule',
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
let cls = $('#sequence-mining-grid').attr('cls');
let fromUser = $('#sequence-mining-grid').attr('from_user');
const gridStatus = $('#grid-status');
const gridStatusNTotal = gridStatus.find('#ntotal');

const initSlider = function (name) {
    const slider = $(`#${name}-slider`);

    slider.slider({
        scale: 'logarithmic',
    });

    $('#slider-enabled').click(function () {
        if (this.checked) {
            slider.slider('enable');
            extraArgs.usegap = true;
            extraArgs[name] = parseInt(slider.val());
        }
        else {
            slider.slider('disable');
            extraArgs.usegap = false;
            extraArgs[name] = undefined;
        }
        loadGrid();
    });

    slider.on('slide', function (slideEvt) {
        document.getElementById(`${name}-slider-value`).textContent = slideEvt.value;
    });

    slider.on('slideStop', function(slideEvt) {
        document.getElementById(`${name}-slider-value`).textContent = slideEvt.value;
        extraArgs[name] = slideEvt.value;
        loadGrid();
    });
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
    debug('subscribeFlexibleEvents called from songs-pages');
    grid.on('click', function (...args) {
        let e = args[0];
        e.preventDefault();
        selectTextForCopy(...args);
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
    'from_user': fromUser,
    'usegap': false,
    'maxgap': null,
    'mingap': null,
};

const loadGrid = function () {
    grid.initMainGridContent({}, extraArgs, focusOnGridOnInit);
    subscribeSlickEvents();
    subscribeFlexibleEvents();
};

export const run = function () {
    initAudioContext();

    grid.init(cls);
    grid.initMainGridHeader({}, extraArgs, function () {
        loadGrid();
    });

    initSlider('mingap');
    initSlider('maxgap');
};


export const handleDatabaseChange = function () {
    location.reload()
};
