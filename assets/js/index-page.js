import * as fg from "flexible-grid";
import * as utils from "./utils";
import {defaultGridOptions} from "./flexible-grid";
import * as ah from "./audio-handler";
import {initSelectize} from "./selectize-formatter";
const keyboardJS = require('keyboardjs/dist/keyboard.min.js');

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
        if (cell) {
            let row = cell.row;
            let rowElement = $(e.target.parentElement);
            let songId = dataView.getItem(row).id;
            self.eventNotifier.trigger(eventType, {e: e, songId: songId, rowElement: rowElement});
        }
    }
}

const grid = new SegmentGrid();
const contextMenu = $("#context-menu");
const filterLiA = contextMenu.find('a[action=filter]');
const filterLi = filterLiA.parent();
const setLabelLiA = contextMenu.find('a[action=set-label]');
const setLabelLi = setLabelLiA.parent();

const setLabelModal = $("#set-label-modal");
const setLabelLabel = setLabelModal.find("#set-label-label");
const setLabelCount = setLabelModal.find("#set-label-count");
const setLabelBtn = setLabelModal.find("#set-label-btn");

const tooltip = $("#spectrogram-details-tooltip");
const tooltipImg = tooltip.find('img');


const playAudio = function (e, args) {
    let cellElement = $(args.e.target);
    let hasImage = cellElement.closest(".has-image");
    if (hasImage.length == 1) {
        let segId = args.songId;
        $.post(utils.getUrl('fetch-data', 'koe/get-segment-audio'), {'segment-id': segId}, function (encoded) {
            ah.playRawAudio(encoded);
        })
    }
};


const toggleCheckBox = function (e, args) {
    let cellElement = $(args.e.target);
    let hasCheckBox = cellElement.find('input[type=checkbox]').closest("input[type=checkbox]");
    if (hasCheckBox.length == 1) {
        hasCheckBox.click();
    }
};


const subscribeEvents = function () {
    grid.on('click', function () {
        playAudio.apply(null, arguments);
        toggleCheckBox.apply(null, arguments);
    });

    grid.on('mouseenter', showBigSpectrogram);
    grid.on('mouseleave', function (e, args) {
        let cellElement = $(args.e.target);
        let hasImage = cellElement.closest(".has-image");
        if (hasImage.length == 1) {
            tooltip.addClass('hidden');
            hasImage.find('img').removeClass('highlight');
        }
    });

    grid.subscribe('onContextMenu', function (e, args) {
        let grid_ = args.grid;
        e.preventDefault();
        let cell = grid_.getCellFromEvent(e);
        let colDef = grid_.getColumns()[cell.cell];
        let field = colDef.field;

        contextHandlerDecorator(colDef);

        contextMenu
            .data("field", field)
            .css("top", e.pageY)
            .css("left", e.pageX)
            .show();
        $("body").one("click", function () {
            contextMenu.hide();
        });
    });
};


/**
 * Redraw the table on orientation changed
 */
export const orientationChange = function () {
    grid.redrawMainGrid({rowMoveable: true, multiSelect: true});
    subscribeEvents();
};


const showBigSpectrogram = function (e, args) {
    let cellElement = $(args.e.target);
    let hasImage = cellElement.closest(".has-image");
    if (hasImage.length == 1) {
        const originalImage = hasImage.find('img');

        tooltipImg.attr('src', originalImage.attr('src'));
        tooltip.removeClass('hidden');

        originalImage.addClass('highlight');

        const panelHeight = $('#segment-info').height();
        const imgWidth = tooltipImg.width();
        const imgHeight = tooltipImg.height();

        const pos = hasImage.offset();
        const cellTop = pos.top;
        const cellLeft = pos.left;

        let cellBottom = cellTop + originalImage.height();
        let cellCentreX = cellLeft + originalImage.width() / 2;
        let imgLeft = cellCentreX - imgWidth / 2;

        let top, left;

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
};

export const run = function () {
    console.log("Index page is now running.");
    ah.initAudioContext();

    grid.init();
    grid.initMainGridHeader({rowMoveable: true, multiSelect: true}, function () {
        let dm = $('#distance-matrix-combo').attr('dm');
        grid.initMainGridContent({__extra__dm: dm});
    });

    subscribeEvents();

    $('.select-dm').on('click', function (e) {
        e.preventDefault();
        let dm = this.getAttribute('dm');
        let dmName = $(this).html().trim();
        grid.initMainGridContent({__extra__dm: dm});

        /* Update the button */
        $('#distance-matrix-combo').attr('dm', dm).html(dmName + `<span class="caret"></span>`);
    });

    contextMenu.click(function (e, args) {
        if (!$(e.target).is("a")) {
            return;
        }
        if (!grid.mainGrid.getEditorLock().commitCurrentEdit()) {
            return;
        }
        let action = e.target.getAttribute("action");
        let field = $(this).data("field");
        let actionHandler = actionHandlers[action];
        actionHandler(field);
    });

    keyboardJS.bind(['mod+shift+l', 'ctrl+shift+l'], function () {
        setLabel('label');
    });
    keyboardJS.bind(['mod+shift+f', 'ctrl+shift+f'], function () {
        setLabel('label_family');
    });
    keyboardJS.bind(['mod+shift+s', 'ctrl+shift+s'], function () {
        setLabel('label_subfamily');
    });
};

const addFilter = function (field) {
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

const inputText = $(`<input type="text" class="form-control" id="set-label-input">`);
const inputSelect = $(`<select class="selectize" id="set-label-input"></select>`);

const setLabel = function (field) {
    let grid_ = grid.mainGrid;
    let selectedRows = grid_.getSelectedRows();
    let numRows = selectedRows.length;
    if (numRows > 0) {
        setLabelLabel.html(field);
        setLabelCount.html(numRows);

        let ids = [];
        let items = grid_.getData().getItems();
        for (let i = 0; i < selectedRows.length; i++) {
            let item = items[selectedRows[i]];
            ids.push(item.id);
        }

        let selectableColumns = utils.getCache('selectableOptions');
        let selectableOptions = selectableColumns[field];

        const isSelectize = !!selectableOptions;
        let inputEl = isSelectize ? inputSelect : inputText;
        $('#input-wrapper').children().remove();
        $('#input-wrapper').append(inputEl);
        let defaultValue = inputEl.val();

        if (isSelectize) {
            let control = inputEl[0].selectize;
            if (control) control.destroy();

            initSelectize(inputEl, field, defaultValue);

            setLabelModal.on('shown.bs.modal', function (e) {
                inputEl[0].selectize.focus();
            });
        }
        else {
            setLabelModal.on('shown.bs.modal', function (e) {
                inputEl.focus();
            });
        }

        setLabelModal.modal('show');

        setLabelBtn.one('click', function (e) {
            let value = inputEl.val();
            if (selectableOptions) {
                selectableOptions[value] = (selectableOptions[value] || 0) + 1;
            }

            $.post(utils.getUrl('fetch-data', 'change-property-bulk'),
                {
                    ids: JSON.stringify(ids),
                    field: field,
                    value: value,
                    'grid-type': grid.gridType
                },
                function (msg) {
                    for (let i = 0; i < selectedRows.length; i++) {
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

const contextHandlerDecorator = function (colDef) {
    // if the column is not sortable, disable filter
    filterLi.removeClass('disabled');
    filterLiA.html(`Filter ${colDef.field}.`);
    if (!colDef.sortable) {
        filterLi.addClass('disabled');
        filterLiA.html('No filter applicable to this column.')
    }

    // If the column is not editable, disable set-label
    let numRows = grid.mainGrid.getSelectedRows().length;

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