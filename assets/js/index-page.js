import * as fg from "flexible-grid";
import * as utils from "./utils";
import {defaultGridOptions} from "./flexible-grid";
import * as ah from "./audio-handler";


const gridOptions = utils.deepCopy(defaultGridOptions);
gridOptions.rowHeight = 50;


class SegmentGrid extends fg.FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'segment-info',
            'grid-type': 'segment-info',
            gridOptions: gridOptions
        });
    };

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
}

const grid = new SegmentGrid();


const playAudio = function (e, args) {
    if (args.rowElement.hasClass('has-image')) {
        let segId = args.songId;
        $.post(utils.getUrl('fetch-data', 'koe/get-segment-audio'), {'segment-id': segId}, function (encoded) {
            ah.playRawAudio(encoded);
        })
    }
};


const initTable = function () {
    grid.init();
    grid.initMainGridHeader({rowMoveable: true, multiSelect: true}, function () {
        let dm = $('#distance-matrix-combo').attr('dm');
        grid.initMainGridContent({__extra__dm:dm});
    });
};


/**
 * Redraw the table on orientation changed
 */
export const orientationChange = function () {
    initTable();
};

export const run = function () {
    console.log("Index page is now running.");
    ah.initAudioContext();
    initTable();
    grid.on('click', playAudio);

    $('.select-dm').on('click', function (e) {
        e.preventDefault();
        let dm = this.getAttribute('dm');
        let dmName = $(this).html().trim();
        grid.initMainGridContent({__extra__dm:dm});

        /* Update the button */
        $('#distance-matrix-combo').attr('dm', dm).html(dmName + `<span class="caret"></span>`);
    });
};

export const getData = function () {
    return grid.mainGrid.getData().getItems();
};