import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {initSelectize} from './selectize-formatter';
import {deepCopy, getUrl, getCache, setCache, debug} from './utils';
import {postRequest} from './ajax-handler';
import {changePlaybackSpeed, initAudioContext, queryAndPlayAudio} from './audio-handler';
const keyboardJS = require('keyboardjs/dist/keyboard.min.js');
require('bootstrap-slider/dist/bootstrap-slider.js');


const gridOptions = deepCopy(defaultGridOptions);
gridOptions.rowHeight = 50;


class SegmentGrid extends FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'labelling',
            'grid-type': 'segment-info',
            'default-field': 'label_family',
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

export const grid = new SegmentGrid();
let fromUser = $('#segment-info').attr('from_user');
const contextMenu = $('#context-menu');
const filterLiA = contextMenu.find('a[action=filter]');
const filterLi = filterLiA.parent();
const setLabelLiA = contextMenu.find('a[action=set-label]');
const setLabelLi = setLabelLiA.parent();

const tooltip = $('#spectrogram-details-tooltip');
const tooltipImg = tooltip.find('img');
const speedSlider = $('#speed-slider');
const gridStatus = $('#grid-status');
const gridStatusNSelceted = gridStatus.find('#nselected');
const gridStatusNTotal = gridStatus.find('#ntotal');

const similarityCombo = $('#similarity-sort-combo');

const currentSimilarityAttr = similarityCombo.attr('current-attr');
const similarityClass = similarityCombo.attr('cls');
const deleteSegmentsBtn = $('#delete-segments-btn');

let ce;


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

const playAudio = function (e, args) {
    let cellElement = $(args.e.target);
    let hasImage = cellElement.closest('.has-image');
    if (hasImage.length == 1) {
        let segId = args.songId;
        let data = {'segment-id': segId};

        let args_ = {
            url: getUrl('send-request', 'koe/get-segment-audio-data'),
            cacheKey: segId,
            postData: data
        };

        queryAndPlayAudio(args_);
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
    let hasCheckBox = cellElement.find('input[type=checkbox]').closest('input[type=checkbox]');
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
    if (e.type == 'row-added') {
        nRowChanged = 1;
    }
    else if (e.type == 'rows-added') {
        nRowChanged = args.rows.length;
    }
    else if (e.type == 'row-removed') {
        nRowChanged = -1;
    }
    else if (e.type == 'rows-removed') {
        nRowChanged = -args.rows.length;
    }
    let nSelectedRows = parseInt(gridStatusNSelceted.html());
    gridStatusNSelceted.html(nSelectedRows + nRowChanged);

    // Restore keyboard navigation to the grid
    $($('div[hidefocus]')[0]).focus();
};


/**
 * When segments are selected, enable delete button
 */
function onRowsAdded(e, args) {
    resetStatus(e, args);
    deleteSegmentsBtn.prop('disabled', false);
}

/**
 * When segments are removed, if there is songs left, disable the delete button
 * @param e event
 * @param args contains 'grid' - the main SlickGrid
 */
function onRowsRemoved(e, args) {
    resetStatus(e, args);
    let grid_ = args.grid;
    if (grid_.getSelectedRows().length == 0) {
        deleteSegmentsBtn.prop('disabled', true);
    }
}


/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    debug('subscribeFlexibleEvents called');
    grid.on('click', function (...args) {
        let e = args[0];
        e.preventDefault();
        playAudio(...args);
        toggleCheckBox(...args);
        selectTextForCopy(...args);
    });

    grid.on('mouseenter', showBigSpectrogram);
    grid.on('mouseleave', clearSpectrogram);
    grid.on('row-added', onRowsAdded);
    grid.on('rows-added', onRowsAdded);
    grid.on('row-removed', onRowsRemoved);
    grid.on('rows-removed', onRowsRemoved);
};


/**
 * Subscribe to events on the slick grid. This must be called everytime the slick is reconstructed, e.g. when changing
 * screen orientation or size
 */
const subscribeSlickEvents = function () {
    debug('subscribeSlickEvents called');
    grid.subscribe('onContextMenu', function (e, args) {
        e.preventDefault();
        let grid_ = args.grid;
        let cell = grid_.getCellFromEvent(e);
        let colDef = grid_.getColumns()[cell.cell];
        let field = colDef.field;

        contextHandlerDecorator(colDef);

        contextMenu.data('field', field).css('top', e.pageY).css('left', e.pageX).show();
        $('body').one('click', function () {
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
    let hasImage = cellElement.closest('.has-image');
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
        let cellCentreX = cellLeft + (originalImage.width() / 2);
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
                let segId = grid_.getData().getItem(activeCell.row).id;
                let args = {
                    e: fakeEvent,
                    songId: segId
                };
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

            let preventDefault = function () {

                /* do nothing */
            };

            let fakeEvent = {
                target: activeCellEl,
                preventDefault
            };
            let args_ = {e: fakeEvent};
            showBigSpectrogram(fakeEvent, args_);
        }
    }
};


/**
 * Deselect all rows including rows hidden by the filter
 * @param e
 */
const deselectAll = function () {
    grid.mainGrid.setSelectedRows([]);
};


/**
 * Jump to the next cell (on the same column) that has different value
 */
const jumpNext = function (type) {
    let grid_ = grid.mainGrid;
    let activeCell = grid_.getActiveCell();
    if (activeCell) {
        let field = grid_.getColumns()[activeCell.cell].field;
        let items = grid_.getData().getFilteredItems();
        let value = grid_.getDataItem(activeCell.row)[field];
        let itemCount = items.length;
        let begin, conditionFunc, incFunc;

        if (type === 'down') {
            begin = activeCell.row + 1;
            incFunc = function (x) {
                return x + 1;
            };
            conditionFunc = function (x) {
                return x < itemCount;
            }
        }
        else {
            begin = activeCell.row - 1;
            incFunc = function (x) {
                return x - 1;
            };
            conditionFunc = function (x) {
                return x > 0;
            }
        }

        let i = begin;
        while (conditionFunc(i)) {
            if (items[i][field] != value) {
                grid_.gotoCell(i, activeCell.cell, true);
                break;
            }
            i = incFunc(i);
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


let gridExtraArgs = {
    '__extra__from_user': fromUser,
    multiSelect: true
};


export const run = function (commonElements) {
    ce = commonElements;

    initAudioContext();

    grid.init();
    grid.initMainGridHeader(gridExtraArgs, function () {
        grid.initMainGridContent(gridExtraArgs, focusOnGridOnInit);
        subscribeSlickEvents();
        subscribeFlexibleEvents();
    });

    $('.select-similarity').on('click', function (e) {
        e.preventDefault();

        let parent = $(this).parent();
        if (parent.hasClass('not-active')) {

            let similarityId = this.getAttribute('similarity');
            let postData = {
                attr: currentSimilarityAttr,
                klass: similarityClass,
                value: similarityId,
                owner: similarityCombo.attr('owner-id')
            };
            let onSuccess = function () {
                grid.initMainGridContent({}, focusOnGridOnInit);
            };

            postRequest({
                requestSlug: 'change-extra-attr-value',
                data: postData,
                onSuccess
            });

            /* Update the button */
            similarityCombo.attr('similarity', similarityId);
            parent.parent().find('li.active').removeClass('active').addClass('not-active');
            parent.removeClass('not-active').addClass('active');
        }
    });

    contextMenu.click(function (e) {
        if (!$(e.target).is('a')) {
            return;
        }
        if (!grid.mainGrid.getEditorLock().commitCurrentEdit()) {
            return;
        }
        let action = e.target.getAttribute('action');
        let field = $(this).data('field');
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
    keyboardJS.bind(['shift + mod + down', 'ctrl + down', 'mod + down', 'ctrl + shift + down'], function () {
        jumpNext('down');
    });
    keyboardJS.bind(['shift + mod + up', 'ctrl + up', 'mod + up', 'ctrl + shift + up'], function () {
        jumpNext('up');
    });

    initSlider();
};

const addFilter = function (field) {
    field = ' ' + field + ':';
    let filterInput = $(grid.filterSelector);
    let currentFilterValue = filterInput.val();
    let fieldValueIndex = currentFilterValue.indexOf(field);
    let fieldArgIndexBeg, fieldArgIndexEnd;

    if (fieldValueIndex == -1) {
        currentFilterValue += field + '()';
        fieldValueIndex = currentFilterValue.indexOf(field);
        filterInput.val(currentFilterValue);
        fieldArgIndexBeg = fieldValueIndex + field.length + 1;
        fieldArgIndexEnd = fieldArgIndexBeg;
    }
    else {
        fieldArgIndexEnd = currentFilterValue.substr(fieldValueIndex).indexOf(')') + fieldValueIndex;
        fieldArgIndexBeg = fieldValueIndex + field.length + 1;
    }
    filterInput[0].setSelectionRange(fieldArgIndexBeg, fieldArgIndexEnd);
    filterInput[0].focus();
};

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

        const isSelectize = Boolean(selectableOptions);
        let inputEl = isSelectize ? ce.inputSelect : ce.inputText;
        ce.dialogModalBody.children().remove();
        ce.dialogModalBody.append(inputEl);
        let defaultValue = inputEl.val();

        if (isSelectize) {
            let control = inputEl[0].selectize;
            if (control) control.destroy();

            initSelectize(inputEl, field, defaultValue);

            ce.dialogModal.on('shown.bs.modal', function () {
                inputEl[0].selectize.focus();
            });
        }
        else {
            ce.dialogModal.on('shown.bs.modal', function () {
                inputEl.focus();
            });
        }

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.off('click').one('click', function () {
            let value = inputEl.val();
            if (selectableOptions) {
                selectableOptions[value] = (selectableOptions[value] || 0) + numRows;
            }

            let postData = {
                ids: JSON.stringify(ids),
                field,
                value,
                'grid-type': grid.gridType
            };

            let onSuccess = function () {
                for (let i = 0; i < numRows; i++) {
                    let row = selectedRows[i];
                    let item = selectedItems[i];
                    item[field] = value;
                    grid_.invalidateRow(row);
                }
                grid_.render();
            };
            ce.dialogModal.modal('hide');
            postRequest({
                requestSlug: 'set-property-bulk',
                data: postData,
                onSuccess
            });
        })
    }
};


/**
 * Toogle checkbox at the row where the mouse is currently highlighting.
 * @param e
 * @param args
 */
const toggleSelectHighlightedRow = function () {
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
    'set-label': setLabel
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

/**
 * Allows user to remove songs
 */
const initDeleteSegmentsBtn = function () {
    deleteSegmentsBtn.click(function () {
        let grid_ = grid.mainGrid;
        let selectedRows = grid_.getSelectedRows();
        let numRows = selectedRows.length;
        let dataView = grid_.getData();
        let itemsIds = [];
        for (let i = 0; i < numRows; i++) {
            let item = dataView.getItem(selectedRows[i]);
            itemsIds.push(item.id);
        }

        let databaseId = ce.databaseCombo.attr('database');

        ce.dialogModalTitle.html(`Deleting ${numRows} syllable(s)`);
        ce.dialogModalBody.html(`Are you sure you want to delete these syllables and all data associated with it? 
        This action is not reverseable.`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.off('click').one('click', function () {
            let postData = {
                ids: JSON.stringify(itemsIds),
                'database-id': databaseId
            };

            let onSuccess = function () {
                for (let i = 0; i < numRows; i++) {
                    let itemId = itemsIds[i];
                    dataView.deleteItem(itemId);
                }
            };
            ce.dialogModal.modal('hide');
            postRequest({
                requestSlug: 'koe/delete-segments',
                data: postData,
                onSuccess,
                immediate: true
            });
        });
    });
};


export const postRun = function () {
    $('#save-data-btn').click(function () {
        ce.inputText.val('');

        ce.dialogModalTitle.html('Backing up your data...');
        ce.dialogModalBody.html('<label>Give it a comment (optional)</label>');
        ce.dialogModalBody.append(ce.inputText);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.one('click', function () {
            let value = ce.inputText.val();
            let databaseId = ce.databaseCombo.attr('database');
            ce.inputText.val('');

            ce.dialogModal.modal('hide');
            let postData = {
                comment: value,
                database: databaseId
            };
            let msgGen = function (isSuccess, response) {
                return isSuccess ?
                    `History saved to ${response}. You can download it from the version control page` :
                    `Something's wrong, server says ${response}. Version not saved.`;
            };
            postRequest({
                requestSlug: 'koe/save-history',
                data: postData,
                msgGen
            });
        });
    });

    initDeleteSegmentsBtn();
};

export const handleDatabaseChange = function () {
    location.reload()
};
