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
const contextMenu = $("#contextMenu");
const filterLiA = contextMenu.find('a[action=filter]');
const filterLi = filterLiA.parent();
const setLabelLiA = contextMenu.find('a[action=set-label]');
const setLabelLi = setLabelLiA.parent();

const setLabelModal = $("#set-label-modal");
const setLabelLabel = setLabelModal.find("#set-label-label");
const setLabelCount = setLabelModal.find("#set-label-count");
const setLabelInput = setLabelModal.find("#set-label-input");
const setLabelBtn = setLabelModal.find("#set-label-btn");

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
        let colDef = grid_.getColumns()[cell.cell];

        contextHandlerDecorator(colDef, grid_);

        contextMenu
            .data("row", cell.row)
            .data("colDef", colDef)
            .data("grid", grid_)
            .css("top", e.pageY)
            .css("left", e.pageX)
            .show();
        $("body").one("click", function () {
            contextMenu.hide();
        });
    });

    contextMenu.click(function (e, args) {
        if (!$(e.target).is("a")) {
            return;
        }
        if (!grid.mainGrid.getEditorLock().commitCurrentEdit()) {
            return;
        }
        let action = e.target.getAttribute("action");
        let row = $(this).data("row");
        let colDef = $(this).data("colDef");
        let grid_ = $(this).data("grid");
        let actionHandler = actionHandlers[action];
        actionHandler(row, colDef, grid_);
    });
};

const addFilter = function (row, colDef, grid_) {
    let field = colDef.field;
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

const setLabel = function (row, colDef, grid_) {
    let selectedRows = grid_.getSelectedRows();
    let colName = colDef.name;
    let numRows = selectedRows.length;
    let field = colDef.field;
    if (numRows > 0) {
        setLabelLabel.html(colName);
        setLabelCount.html(numRows);
        setLabelModal.modal('show');

        let ids = [];
        let items = grid_.getData().getItems();
        for (let i=0; i<selectedRows.length; i++) {
            let item = items[selectedRows[i]];
            ids.push(item.id);
        }

        setLabelBtn.one('click', function (e) {
            let value = setLabelInput.val();
            $.post(utils.getUrl('fetch-data', 'change-property-bulk'),
                {
                    ids: JSON.stringify(ids),
                    field: field,
                    value: value,
                    'grid-type': grid.gridType
                },
                function (msg) {
                    console.log(msg);
                    for (let i=0; i<selectedRows.length; i++) {
                        let row = selectedRows[i];
                        let item = items[row];
                        item[field] = value;
                        grid_.invalidateRow(row);
                    }
                    grid_.render();
                    setLabelModal.modal("hide");
                }
            );

        })
    }
};

const actionHandlers = {
    filter: addFilter,
    "set-label": setLabel
};

const contextHandlerDecorator = function (colDef, grid_) {
    // if the column is not sortable, disable filter
    filterLi.removeClass('disabled');
    filterLiA.html(`Filter ${colDef.field}.`);
    if (!colDef.sortable) {
        filterLi.addClass('disabled');
        filterLiA.html('No filter applicable to this column.')
    }

    // If the column is not editable, disable set-label
    let numRows = grid_.getSelectedRows().length;

    setLabelLi.removeClass('disabled');
    setLabelLiA.html(`Bulk set ${colDef.name}.`);

    if (!colDef.editable) {
        setLabelLi.addClass('disabled');
        setLabelLiA.html('Bulk set: This column is not editable.')
    }
    if (numRows == 0) {
        setLabelLi.addClass('disabled');
        setLabelLiA.html('Bulk set: you need to select some rows first.')
    }
};

export const getData = function () {
    return grid.mainGrid.getData().getItems();
};