import * as fg from "flexible-grid";
import {defaultGridOptions} from "./flexible-grid";
import * as ah from "./audio-handler";
import {initSelectize} from "./selectize-formatter";
import {log, debug, deepCopy, getUrl, getCache, createCsv, downloadBlob} from "utils";
import {setCache} from "./utils";
const keyboardJS = require('keyboardjs/dist/keyboard.min.js');
require('bootstrap-slider/dist/bootstrap-slider.js');


const gridOptions = deepCopy(defaultGridOptions);
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
            let col = cell.cell;
            let coldef = grid.getColumns()[col];
            let rowElement = $(e.target.parentElement);
            let songId = dataView.getItem(row).id;
            self.eventNotifier.trigger(eventType, {e: e, songId: songId, rowElement: rowElement, coldef: coldef});
        }
    }

    rowChangeHandler(e, args) {
        super.rowChangeHandler(e, args, generalResponseHandler);
    }
}

const grid = new SegmentGrid();
const contextMenu = $("#context-menu");
const filterLiA = contextMenu.find('a[action=filter]');
const filterLi = filterLiA.parent();
const setLabelLiA = contextMenu.find('a[action=set-label]');
const setLabelLi = setLabelLiA.parent();

const tooltip = $("#spectrogram-details-tooltip");
const tooltipImg = tooltip.find('img');
const speedSlider = $("#speed-slider");
const gridStatus = $('#grid-status');
const gridStatusNSelceted = gridStatus.find('#nselected');
const gridStatusNTotal = gridStatus.find('#ntotal');


let ce;

/**
 * Display error in the alert box if a request failed, and vice versa
 * @param response
 */
const generalResponseHandler = function (response) {
    let message = `Success`;
    let alertEl = ce.alertSuccess;
    if (response != 'ok') {
        message = `Something's wrong. The server says "${response}".`;
        alertEl = ce.alertFailure;
    }
    alertEl.html(message);
    alertEl.fadeIn().delay(4000).fadeOut(400);
};


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
    e.preventDefault();
    let cellElement = $(args.e.target);
    let hasImage = cellElement.closest(".has-image");
    if (hasImage.length == 1) {
        let segId = args.songId;
        let data = new FormData();
        data.append('segment-id', segId);
        ah.queryAndPlayAudio(getUrl('send-request', 'koe/get-segment-audio'), data, segId)
    }
};


/**
 * Triggered on click. If the cell is of type checkbox and the click falls within the vicinity of the cell, then
 * toggle the checkbox - this helps the user to not have to click the checkbox precisely
 *
 * @param e
 * @param args
 */
const toggleCheckBox = function (e, args) {
    let cellElement = $(args.e.target);
    let hasCheckBox = cellElement.find('input[type=checkbox]').closest("input[type=checkbox]");
    if (hasCheckBox.length == 1) {
        hasCheckBox.click();
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


const resetStatus = function (e, args) {
    e.preventDefault();
    let nRowChanged = 0;
    if (e.type == "row-added") {
        nRowChanged = 1;
    } else if (e.type == "rows-added") {
        nRowChanged = args.rows.length;
    } else if (e.type == "row-removed") {
        nRowChanged = -1;
    } else if (e.type == "rows-removed") {
        nRowChanged = -args.rows.length;
    }
    let nSelectedRows = parseInt(gridStatusNSelceted.html());
    gridStatusNSelceted.html(nSelectedRows + nRowChanged);

    // Restore keyboard navigation to the grid
    $($('div[hidefocus]')[0]).focus();
};


/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    log(`subscribeFlexibleEvents called`);
    grid.on('click', function (e) {
        e.preventDefault();
        playAudio.apply(null, arguments);
        toggleCheckBox.apply(null, arguments);
        selectTextForCopy.apply(null, arguments);
    });

    grid.on('mouseenter', showBigSpectrogram);
    grid.on('mouseleave', clearSpectrogram);
    grid.on('row-added', resetStatus)
        .on('rows-added', resetStatus)
        .on('row-removed', resetStatus)
        .on('rows-removed', resetStatus);
};


/**
 * Subscribe to events on the slick grid. This must be called everytime the slick is reconstructed, e.g. when changing
 * screen orientation or size
 */
const subscribeSlickEvents = function () {
    log(`subscribeSlickEvents called`);
    grid.subscribe('onContextMenu', function (e, args) {
        e.preventDefault();
        let grid_ = args.grid;
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

    grid.subscribeDv('onRowCountChanged', function (e, args) {
        let currentRowCount = args.current;
        gridStatusNTotal.html(currentRowCount);
    });

    grid.subscribe('onActiveCellChanged', showSpectrogramOnActiveCell);
};


/**
 * Redraw the table on orientation changed
 */
export const orientationChange = function () {
    grid.redrawMainGrid({rowMoveable: true, multiSelect: true}, function () {
        subscribeSlickEvents();
    });
};


const showBigSpectrogram = function (e, args) {
    e.preventDefault();
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

        setCache('current-highlighted-image', originalImage)
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
        setCache('current-highlighted-image', undefined)
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
        let column = grid_.getColumns()[activeCell.cell];
        if (!column.editable) {
            let fakeEvent = {target: activeCellEl};
            let segId = grid_.getData().getItem(activeCell.row).id;
            let args = {e: fakeEvent, songId: segId};
            playAudio(e, args);
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
                target: activeCellEl, preventDefault: function () {}
            };
            let args = {e: fakeEvent};
            showBigSpectrogram(fakeEvent, args);
        }
    }
};


/**
 * Deselect all rows including rows hidden by the filter
 * @param e
 */
const deselectAll = function (e) {
    grid.mainGrid.setSelectedRows([]);
};


/**
 * Set the focus on the grid right after page is loaded.
 * This is mainly so that user can use Page Up and Page Down right away
 */
const focusOnGridOnInit = function () {
    $($('div[hidefocus]')[0]).focus();
};


export const run = function (commonElements) {
    console.log("Index page is now running.");
    ce = commonElements;

    ah.initAudioContext();

    grid.init();
    grid.initMainGridHeader({multiSelect: true}, function () {
        let similarity = $('#similarity-sort-combo').attr('similarity');
        grid.initMainGridContent({__extra__similarity: similarity}, focusOnGridOnInit);
        subscribeSlickEvents();
        subscribeFlexibleEvents();
    });

    $('.select-similarity').on('click', function (e) {
        e.preventDefault();
        let similarity = this.getAttribute('similarity');
        let similarityName = $(this).html().trim();
        grid.initMainGridContent({__extra__similarity: similarity}, focusOnGridOnInit);

        /* Update the button */
        $('#similarity-sort-combo').attr('similarity', similarity).html(similarityName + `<span class="caret"></span>`);
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
    keyboardJS.bind(['shift + space'], toggleSelectHighlightedRow);
    keyboardJS.bind(['space'], playAudioOnKey);
    keyboardJS.bind(['ctrl + `'], deselectAll);

    initSlider();
};

const addFilter = function (field) {
    field = ' ' + field + ':';
    let filterInput = $(grid.filterSelector);
    let currentFilterValue = filterInput.val();
    let fieldValueIndex = currentFilterValue.indexOf(field);
    let fieldArgIndexEnd, fieldArgIndexBeg;

    if (fieldValueIndex == -1) {
        currentFilterValue += field + "()";
        fieldValueIndex = currentFilterValue.indexOf(field);
        filterInput.val(currentFilterValue);
        fieldArgIndexBeg = fieldValueIndex + field.length + 1;
        fieldArgIndexEnd = fieldArgIndexBeg;
    }
    else {
        fieldArgIndexEnd = currentFilterValue.substr(fieldValueIndex).indexOf(")") + fieldValueIndex;
        fieldArgIndexBeg = fieldValueIndex + field.length + 1;
    }
    filterInput[0].setSelectionRange(fieldArgIndexBeg, fieldArgIndexEnd);
    filterInput[0].focus();
};

const inputText = $(`<input type="text" class="form-control">`);
const inputSelect = $(`<select class="selectize" ></select>`);

const setLabel = function (field) {
    let grid_ = grid.mainGrid;
    let selectedRows = grid_.getSelectedRows();
    let numRows = selectedRows.length;
    if (numRows > 0) {
        ce.dialogModalTitle.html(`Set ${field} for ${numRows} rows`);

        let ids = [];
        let selectedItems = [];
        let dataView = grid_.getData();
        for (let i = 0; i < numRows; i++) {
            let item = dataView.getItem(selectedRows[i]);
            ids.push(item.id);
            selectedItems.push(item);
        }

        let selectableColumns = getCache('selectableOptions');
        let selectableOptions = selectableColumns[field];

        const isSelectize = !!selectableOptions;
        let inputEl = isSelectize ? inputSelect : inputText;
        ce.dialogModalBody.children().remove();
        ce.dialogModalBody.append(inputEl);
        let defaultValue = inputEl.val();

        if (isSelectize) {
            let control = inputEl[0].selectize;
            if (control) control.destroy();

            initSelectize(inputEl, field, defaultValue);

            ce.dialogModal.on('shown.bs.modal', function (e) {
                inputEl[0].selectize.focus();
            });
        }
        else {
            ce.dialogModal.on('shown.bs.modal', function (e) {
                inputEl.focus();
            });
        }

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.off('click').one('click', function (e) {
            let value = inputEl.val();
            if (selectableOptions) {
                selectableOptions[value] = (selectableOptions[value] || 0) + numRows;
            }

            $.post(getUrl('send-request', 'set-property-bulk'),
                {
                    ids: JSON.stringify(ids),
                    field: field,
                    value: value,
                    'grid-type': grid.gridType
                },
                function (msg) {
                    for (let i = 0; i < numRows; i++) {
                        let row = selectedRows[i];
                        let item = selectedItems[i];
                        item[field] = value;
                        grid_.invalidateRow(row);
                    }
                    grid_.render();
                    ce.dialogModal.modal('hide');
                    generalResponseHandler(msg);
                }
            );

        })
    }
};


/**
 * Toogle checkbox at the row where the mouse is currently highlighting.
 * @param e
 * @param args
 */
const toggleSelectHighlightedRow = function (e, args) {
    let currentMouseEvent = grid.currentMouseEvent;
    let selectedRow = grid.getSelectedRows().rows;
    let row = currentMouseEvent.row;
    let index = selectedRow.indexOf(row);
    if (index == -1) {
        selectedRow.push(row);
    }
    else {
        selectedRow.splice(index, 1);
    }
    grid.mainGrid.setSelectedRows(selectedRow);
};

const actionHandlers = {
    filter: addFilter,
    "set-label": setLabel
};

const contextHandlerDecorator = function (colDef) {
    // if the column is not sortable, disable filter
    filterLi.removeClass('disabled');
    filterLiA.html(`Filter ${colDef.field}.`);
    if (!colDef.filter) {
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

export const postRun = function () {
    $('#save-data-btn').click(function (e) {
        inputText.val('');

        ce.dialogModalTitle.html("Backing up your data...");
        ce.dialogModalBody.html(`<label>Give it a comment (optionl)</label>`);
        ce.dialogModalBody.append(inputText);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.one('click', function (e) {
            let url = getUrl('send-request', 'koe/save-history');
            let value = inputText.val();
            inputText.val('');

            ce.dialogModal.modal('hide');

            $.post(url, {comment: value}, function (filename) {
                ce.dialogModal.modal('hide');
                let message = `History saved to ${filename}. You can download it from the version control page`;
                ce.alertSuccess.html(message);
                ce.alertSuccess.fadeIn().delay(4000).fadeOut(400);
            });
        });
    });

    $('.download-xls').click(function (e) {
        let downloadType = $(this).data('download-type');
        let csvContent = createCsv(grid.mainGrid, downloadType);

        let d = new Date();
        let filename = `koe-${d.getFullYear()}-${d.getMonth()}-${d.getDate()}_${d.getHours()}-${d.getMinutes()}-${d.getSeconds()}.csv`;
        let blob = new Blob([csvContent], {type: 'text/csv;charset=utf-8;'});
        downloadBlob(blob, filename);
    });
};