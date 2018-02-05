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
            'default-field': 'label_family',
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
        grid.initMainGridContent({__extra__dm: dm});
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
        grid.initMainGridContent({__extra__dm: dm});

        /* Update the button */
        $('#distance-matrix-combo').attr('dm', dm).html(dmName + `<span class="caret"></span>`);
    });

    grid.subscribe('onContextMenu', function (e, args) {
        let grid_ = args.grid;
        e.preventDefault();
        let cell = grid_.getCellFromEvent(e);
        let columnField = grid_.getColumns()[cell.cell].field;
        $("#contextMenu")
            .data("row", cell.row)
            .data("columnField", columnField)
            .css("top", e.pageY)
            .css("left", e.pageX)
            .show();
        $("body").one("click", function () {
            $("#contextMenu").hide();
        });
    });

    $("#contextMenu").click(function (e, args) {
        if (!$(e.target).is("li")) {
            return;
        }
        if (!grid.mainGrid.getEditorLock().commitCurrentEdit()) {
            return;
        }
        let action = e.target.getAttribute("action");
        let row = $(this).data("row");
        let columnField = $(this).data("columnField");
        let actionHandler = actionHandlers[action];
        actionHandler(row, columnField);
    });
};

const addFilter = function (row, field) {
    let filterInput = $(grid.filterSelector);
    let currentFilterValue = filterInput.val();
    let fieldValueIndex = currentFilterValue.indexOf(field);
    let fieldArgIndexEnd, fieldArgIndexBeg;

    if (fieldValueIndex == -1) {
        currentFilterValue += " " + field + ":()";
        fieldValueIndex = currentFilterValue.indexOf(field);
        filterInput.val(currentFilterValue);
        fieldArgIndexBeg = fieldValueIndex + field.length + 2;
        fieldArgIndexEnd = fieldArgIndexBeg;
    }
    else {
        fieldArgIndexEnd = currentFilterValue.substr(fieldValueIndex).indexOf(")") + fieldValueIndex;
        fieldArgIndexBeg = fieldValueIndex + field.length + 2;
    }
    filterInput[0].setSelectionRange(fieldArgIndexBeg, fieldArgIndexEnd);
    filterInput[0].focus();
};

const actionHandlers = {
    filter: addFilter
};

export const getData = function () {
    return grid.mainGrid.getData().getItems();
};

let body = $("body");

/**
 * Trigger the loading modal to be displayed/stopped while an Ajax call is being made
 */
$(document).on({
    ajaxStart: function () {
        body.addClass("loading");
    },
    ajaxStop: function () {
        body.removeClass("loading");
    }
});