/* global keyboardJS*/
import {defaultGridOptions, FlexibleGrid} from './flexible-grid';
import {deepCopy, getUrl, getCache, setCache, debug, isNull} from './utils';
import {postRequest} from './ajax-handler';
import {changePlaybackSpeed} from './audio-handler';
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
}

export const grid = new SegmentGrid();
const $segmentGrid = $('#segment-info');
const viewas = $segmentGrid.attr('viewas');
const database = $segmentGrid.attr('database');
const tmpdb = $segmentGrid.attr('tmpdb');
const similarity = $segmentGrid.attr('similarity');

const tooltip = $('#spectrogram-details-tooltip');
const tooltipImg = tooltip.find('img');
const speedSlider = $('#speed-slider');
const gridStatus = $('#grid-status');
const gridStatusNSelected = gridStatus.find('#nselected');
const gridStatusNTotal = gridStatus.find('#ntotal');

const deleteSegmentsBtn = $('#delete-segments-btn');
const makeTemporaryDatabaseBtn = $('#make-temp-db-btn');

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
    let nSelectedRows = parseInt(gridStatusNSelected.html());
    gridStatusNSelected.html(nSelectedRows + nRowChanged);

    // Restore keyboard navigation to the grid
    $($('div[hidefocus]')[0]).focus();
};


/**
 * When segments are selected, enable delete button
 */
function onRowsAdded(e, args) {
    resetStatus(e, args);
    deleteSegmentsBtn.prop('disabled', false);
    makeTemporaryDatabaseBtn.prop('disabled', false);
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
        makeTemporaryDatabaseBtn.prop('disabled', true);
    }
}


/**
 * Subscribe to this instance of Flexible Grid. This must be called only once when the page loads
 */
const subscribeFlexibleEvents = function () {
    debug('subscribeFlexibleEvents called');

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

        // Remove the old image first to avoid showing the previous spectrogram
        tooltipImg.attr('src', '');
        // Then insert the new spectrogram
        tooltipImg.attr('src', originalImage.attr('src'));
        tooltip.removeClass('hidden');

        originalImage.addClass('highlight');

        const panelHeight = $segmentGrid.height();
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
 * Set the focus on the grid right after page is loaded.
 * This is mainly so that user can use Page Up and Page Down right away
 */
const focusOnGridOnInit = function () {
    $($('div[hidefocus]')[0]).focus();
};


let extraArgs = {
    viewas,
    database,
    tmpdb,
    similarity,
};

let gridArgs = {
    multiSelect: true
};


export const preRun = function() {
    initSlider();

    if (isNull(database) && isNull(tmpdb)) {
        return Promise.reject(new Error('Please choose a database.'))
    }
    return Promise.resolve();
};


export const run = function (commonElements) {
    ce = commonElements;
    if (ce.argDict._holdout) {
        extraArgs._holdout = ce.argDict._holdout;
    }

    grid.init();

    keyboardJS.bind(['mod+shift+l', 'ctrl+shift+l'], function () {
        grid.bulkSetValue('label');
    });
    keyboardJS.bind(['mod+shift+f', 'ctrl+shift+f'], function () {
        grid.bulkSetValue('label_family');
    });
    keyboardJS.bind(['mod+shift+s', 'ctrl+shift+s'], function () {
        grid.bulkSetValue('label_subfamily');
    });

    return grid.initMainGridHeader(gridArgs, extraArgs).then(function () {
        subscribeSlickEvents();
        subscribeFlexibleEvents();
        return grid.initMainGridContent(gridArgs, extraArgs).then(function() {
            focusOnGridOnInit();
        });
    });
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

        ce.dialogModalTitle.html(`Deleting ${numRows} syllable(s)`);
        ce.dialogModalBody.html(`Are you sure you want to delete these syllables and all data associated with it? 
        This action is not reverseable.`);

        ce.dialogModal.modal('show');

        ce.dialogModalOkBtn.off('click').one('click', function () {
            let postData = {
                ids: JSON.stringify(itemsIds),
                'database-id': database
            };
            let onSuccess = function () {
                let items = dataView.getFilteredItems();
                let newItems = [];
                for (let i = 0; i < numRows; i++) {
                    let row = selectedRows[i];
                    delete items[row];
                }
                for (let i = 0; i < numRows; i++) {
                    let item = items[i];
                    if (item) {
                        newItems.push(item);
                    }
                }
                dataView.setItems(newItems);
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


const inputText = $('<input type="text" class="form-control"/>');

const dialogModal = $('#dialog-modal');
const dialogModalTitle = dialogModal.find('.modal-title');
const dialogModalBody = dialogModal.find('.modal-body');
const dialogModalOkBtn = dialogModal.find('#dialog-modal-yes-button');


const initCreateTemporaryDatabaseBtn = function() {
    let generatedName;

    /**
     * Repeat showing the dialog until the database name is valid
     * param error to be shown in the modal if not undefined
     */
    function showDialog(error) {
        dialogModalTitle.html('Collection created successfully...');
        dialogModalBody.html(`<label>We gave it the temporary name of ${generatedName}. Do you want to give it a different name?</label>`);
        dialogModalBody.append(inputText);

        if (error) {
            dialogModalBody.append(`<p>${error.message}</p>`);
        }

        dialogModal.modal('show');

        dialogModalOkBtn.one('click', function () {
            dialogModal.modal('hide');
            let url = getUrl('send-request', 'koe/change-tmpdb-name');
            let databaseName = inputText.val();
            inputText.val('');
            let postData = {
                'old-name': generatedName,
                'new-name': databaseName
            };

            $.post(url, postData).done(function () {
                dialogModal.modal('hide');
            }).fail(function (response) {
                dialogModal.one('hidden.bs.modal', function () {
                    let errorMessage = JSON.parse(response.responseText);
                    showDialog(errorMessage);
                });
                dialogModal.modal('hide');
            });
        });
    }

    makeTemporaryDatabaseBtn.click(function(e) {
        e.preventDefault();
        let grid_ = grid.mainGrid;
        let selectedRows = grid_.getSelectedRows();
        let numRows = selectedRows.length;
        let dataView = grid_.getData();
        let itemsIds = [];
        for (let i = 0; i < numRows; i++) {
            let item = dataView.getItem(selectedRows[i]);
            itemsIds.push(item.id);
        }

        let postData = {
            ids: itemsIds.join(),
            database,
        };

        postRequest({
            requestSlug: 'koe/make-tmpdb',
            data: postData,
            immediate: true,
            onSuccess({name, created}) {
                generatedName = name;
                showDialog(created);
            },
            onFailure(message) {
                dialogModalTitle.html('Collection with these IDs already exists...');
                dialogModalBody.html(`<p>You've already created a Collection with name <strong>${message}</strong>. Please choose a unique name.</p>`);

                dialogModal.modal('show');
                dialogModalOkBtn.one('click', function () {
                    dialogModal.modal('hide');
                });
            }
        });
    });
};


export const postRun = function () {
    initDeleteSegmentsBtn();
    initCreateTemporaryDatabaseBtn();
    return Promise.resolve();
};

export const viewPortChangeHandler = function () {
    grid.mainGrid.resizeCanvas();
};
