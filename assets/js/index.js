/* eslint global-require: off */
/* global keyboardJS */

let Urls = window.Urls;
export {
    Urls,
};

Promise.config({
    cancellation: true
});

/**
 * Replace native Promise with BlueBird's Promise. BB's has cancellation capability and it is also much faster.
 * See https://softwareengineering.stackexchange.com/a/279003 and
 * https://github.com/petkaantonov/bluebird/tree/master/benchmark
 */
window.Promise = Promise;

import {isNull, createCsv, downloadBlob, getUrl, getGetParams,
    createTable, extractHeader, convertRawUrl, showAlert, isEmpty, getCache, logError, uuid4, toJSONLocal
} from './utils';
import {postRequest} from './ajax-handler';
import {queryAndPlayAudio} from './audio-handler';
import {initSidebar} from './sidebar';
import {findColumn} from 'grid-utils';
const Papa = require('papaparse');
require('no-going-back');

let page;

const inputText = $('<input type="text" class="form-control"/>');
const inputSelect = $('<select class="selectize" ></select>');

const dialogModal = $('#dialog-modal');
const dialogModalTitle = dialogModal.find('.modal-title');
const dialogModalBody = dialogModal.find('.modal-body');
const dialogModalOkBtn = dialogModal.find('#dialog-modal-yes-button');
const dialogModalCancelBtn = dialogModal.find('#dialog-modal-no-button');
const alertSuccess = $('.alert-success');
const alertFailure = $('.alert-danger');

let argDict = getGetParams();

const commonElements = {
    inputText,
    inputSelect,
    dialogModal,
    dialogModalTitle,
    dialogModalBody,
    dialogModalOkBtn,
    dialogModalCancelBtn,
    alertSuccess,
    alertFailure,
    argDict
};


/**
 * If user uses keyboard shortcut to open the modal, restore the element that was focused before the modal was opened
 */
const restoreModalAfterClosing = function () {

    dialogModal.on('hidden.bs.modal', function () {
        // Restore keyboard navigation to the grid
        $($('div[hidefocus]')[0]).focus();
    });

};


/**
 * Mobile viewport height after orientation change
 * See: https://stackoverflow.com/questions/12452349/mobile-viewport-height-after-orientation-change
 * Wait until innerheight changes, for max 120 frames
 */
function viewPortChangeHandler() {
    const timeout = 120;
    return new window.Promise(function (resolve) {
        const go = (i, height0) => {
            window.innerHeight != height0 || i >= timeout ?
                resolve() :
                window.requestAnimationFrame(() => go(i + 1, height0));
        };
        go(0, window.innerHeight);
    });
}


/**
 * Play the sound if the current active cell is the spectrogram
 * @param e
 */
const playAudioOnKey = function (e) {
    let gridEl = $(e.path[0]).closest('.has-grid');
    if (gridEl.length == 0) {
        return;
    }
    let grid = getCache('grids', gridEl.attr('id'));
    let grid_ = grid.mainGrid;
    let activeCell = grid_.getActiveCell();
    if (isNull(activeCell)) {
        return;
    }
    let $activeCellEl = $(grid_.getCellNode(activeCell.row, activeCell.cell));

    // This if statement will check if the click falls into the grid
    // Because the actual target is lost, the only way we know that the activeCellEl is focused
    // Is if the event's path contains the main grid
    if (gridEl.has($activeCellEl).length > 0) {
        if ($activeCellEl.hasClass('has-image')) {
            let img = $activeCellEl.find('img');
            let segId = img.attr('seg-id');
            if (segId) {
                let args_ = {
                    url: getUrl('send-request', 'koe/get-segment-audio-data'),
                    cacheKey: segId,
                    postData: {'segment-id': segId}
                };
                queryAndPlayAudio(args_);
            }
        }
    }
};


/**
 * Toogle checkbox at the row where the mouse is currently highlighting.
 */
const toggleSelectHighlightedRow = function (e) {
    let gridEl = $(e.path[0]).closest('.has-grid');
    if (gridEl.length > 0) {
        let grid = getCache('grids', gridEl.attr('id'));
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
    }
};


/**
 * Deselect all rows including rows hidden by the filter
 * @param e
 */
const deselectAll = function (e) {
    let gridEl = $(e.path[0]).closest('.has-grid');
    if (gridEl.length > 0) {
        let grid = getCache('grids', gridEl.attr('id'));
        grid.mainGrid.setSelectedRows([]);
    }
};


/**
 * Jump to the next cell (on the same column) that has different value
 */
const jumpNext = function (e, type) {
    let gridEl = $(e.path[0]).closest('.has-grid');
    if (gridEl.length > 0) {
        let grid = getCache('grids', gridEl.attr('id'));
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
                    grid_.gotoCell(i, activeCell.cell, false);
                    break;
                }
                i = incFunc(i);
            }
        }
    }
};


const initKeyboardShortcuts = function () {
    keyboardJS.bind(['space'], playAudioOnKey);
    keyboardJS.bind(['shift + space'], toggleSelectHighlightedRow);
    keyboardJS.bind(['ctrl + `'], deselectAll);
    keyboardJS.bind(['shift + mod + down', 'ctrl + down', 'mod + down', 'ctrl + shift + down'], function (e) {
        jumpNext(e, 'down');
    });
    keyboardJS.bind(['shift + mod + up', 'ctrl + up', 'mod + up', 'ctrl + shift + up'], function (e) {
        jumpNext(e, 'up');
    });
};


/**
 * Put everything you need to run before the page has been loaded here
 * @private
 */
const _preRun = function () {
    initKeyboardShortcuts();
    restoreModalAfterClosing();
    subMenuOpenRight();
    initChangeArgSelections();
    appendGetArguments();

    $('.alert .close').on('click', function () {
        let alertEl = $(this).parent();
        let timerId = alertEl.attr('timer-id');
        clearTimeout(timerId);
        alertEl.hide();
    });

    const viewPortChangeCallback = function () {
        viewPortChangeHandler().then(function () {
            if (!isNull(page) && typeof page.viewPortChangeHandler === 'function') {
                page.viewPortChangeHandler();
            }
        });
    };

    window.addEventListener('orientationchange', viewPortChangeCallback);
    window.addEventListener('resize', viewPortChangeCallback);

    return Promise.resolve();
};


/**
 * If there is a timer, count down to 0 and redirect
 */
const countDown = function () {
    const timer = document.getElementById('countdown-redirect');
    if (timer) {
        const redirect = timer.getAttribute('url');
        let count = parseInt(timer.getAttribute('count'));

        setInterval(function () {
            count--;
            timer.innerHTML = count;
            if (count === 0) {
                window.location.href = redirect;
            }
        }, 1000);
    }
};


/**
 * Submenu of a right-aligned menu should open all the way to the left.
 * However this is impossible to do with css because the value of `left` depends on the width of the submenu item
 * e.g. if the submenu is 200px wide then its css should be `left: -200px;`, but submenu's width is unknown.
 * This script will calculate the width of the submenu and set the css attribute accordingly.
 */
const subMenuOpenRight = function () {
    $('.dropdown-menu-right .dropdown-submenu').on('mouseover click', function () {
        let submenu = $(this).find('.dropdown-menu').first();
        let width = submenu.width();

        /*
         * Make it 10px overlap with the parent item, so that it looks nice & also to prevent it from disappearing when
         * the mouse reaches the border of the parent
         */
        submenu.css('display', 'block').css('left', `-${width - 10}px`);
        return false;
    }).on('mouseleave', function () {
        $(this).find('.dropdown-menu').css('display', 'none');
        return false;
    });
};


// /**
//  * When user clicks on the "create new database" button from the drop down menu, show a dialog
//  * asking for name. Send the name to the server to check for duplicate. If there exists a database with the same name,
//  * repeat this process. Only dismiss the dialog if a new database is created.
//  * @param errorMessage to be shown if not undefined
//  */
// function showCreateDatabaseDialog(errorMessage) {
//     dialogModalTitle.html('Creating a new database...');
//     dialogModalBody.html('<label>Give it a name</label>');
//     dialogModalBody.append(inputText);
//     if (errorMessage) {
//         dialogModalBody.append(`<p>${errorMessage}</p>`);
//     }
//
//     dialogModal.modal('show');
//
//     dialogModalOkBtn.one('click', function () {
//         dialogModal.modal('hide');
//         let url = getUrl('send-request', 'koe/create-database');
//         let databaseName = inputText.val();
//         inputText.val('');
//
//         $.post(url, {name: databaseName}).done(function () {
//             dialogModal.one('hidden.bs.modal', function () {
//                 location.reload();
//             });
//             dialogModal.modal('hide');
//         }).fail(function (response) {
//             dialogModal.one('hidden.bs.modal', function () {
//                 showCreateDatabaseDialog(response.responseText);
//             });
//             dialogModal.modal('hide');
//         });
//     });
// }


/**
 * For all selectable options that will change GET arguments and reload the page, e.g. viewas, database, ...
 * append existing arguments to their bare links.
 * Accept 'internal' arguments, but exclude 'external' type arguments
 * Internal arguments are meant for only a specific page. They shouldn't be appended to links to different page
 * External arguments are meant to trigger some specific functions of a page. They shouldn't be propagated even to
 * links to the same page.
 */
const initChangeArgSelections = function () {
    let locationOrigin = window.location.origin;
    let localtionPath = window.location.pathname;

    $('.change-arg').click(function (e) {
        e.preventDefault();
        argDict[this.getAttribute('key')] = this.getAttribute('value');
        let replace = this.getAttribute('replace');
        if (!isNull(replace)) {
            delete argDict[replace];
        }

        let argString = '?';
        $.each(argDict, function (k, v) {
            if (!k.startsWith('__')) {
                argString += `${k}=${v}&`;
            }
        });
        let newUrl = `${locationOrigin}${localtionPath}${argString}`;
        let quiet = $(this).hasClass('quiet');
        if (quiet) {
            window.history.pushState('', '', newUrl);
        }
        else {
            window.location.href = newUrl;
        }
    });
};


/**
 * Search for all "appendable urls" and append the GET arguments to them.
 * Except 'internal' and 'external' arguments.
 * Internal arguments are meant for only a specific page. They shouldn't be appended to links to different page
 * External arguments are meant to trigger some specific functions of a page. They shouldn't be propagated even to
 * links to the same page.
 *
 * E.g. the current url is localhost/blah?x=1&y=3
 * A clickable URL to localhost/foo will be changed to localhost/foo?x=1&y=3
 */
const appendGetArguments = function () {
    $('a.appendable').each(function (idx, a) {
        let href = a.getAttribute('href');
        let argsStart = href.indexOf('?');

        let argString = '?';
        $.each(argDict, function (k, v) {
            if (!k.startsWith('_')) {
                argString += `${k}=${v}&`;
            }
        });

        if (argsStart > -1) {
            href = href.substr(argsStart);
        }
        a.setAttribute('href', href + argString);
    });
};


/**
 * Remove enclosing quotes from string if exist
 * @param val
 * @returns {*}
 */
function sanitise(val) {
    if (val.startsWith('"')) {
        val = val.substr(1, val.length - 2);
    }
    return val.trim();
}


/**
 * Get the field value of all item
 * @param items
 * @param column
 */
function getKeyFields(items, column) {
    let importKey = column.field;
    return items.map(function (x) {
        let value = x[importKey];
        if (column._formatter === 'Url') {
            value = convertRawUrl(value).val;
        }
        return value;
    });
}


/**
 * Split the list of columns from header to two array: columns allowed to import vs disallowed.
 * @param header
 * @param permittedCols names of the columns that are allowed to import.
 * @param importKey
 * @returns {{unmatched: Array, matched: {}}}
 */
function matchColumns(header, permittedCols, importKey) {
    let unmatched = [];
    let matched = {};

    $.each(header, function (csvCol, column) {
        column = sanitise(column);

        let permittedCol = permittedCols.indexOf(column);
        if (permittedCol > -1) {
            matched[permittedCol] = csvCol;
        }
        else {
            unmatched.push(column)
        }
    });
    if (Object.keys(matched).length === 0) {
        throw new Error('Columns in your CSV don\'t match with any importable columns');
    }

    // The key column is ALWASY the first in permittedCols and it MUST have a match in matchedCols
    // Careful, matchedCols[0] is not the first element (matchedCols is not an array), but the corresponding
    // column index of the key column in the uploaded CSV.
    if (matched[0] === undefined) {
        throw new Error(`Key column "${importKey}" is missing from your CSV`);
    }
    return {unmatched, matched};
}

/**
 * From the list of grid items and csv rows, find the rows that match grid items at key field and
 * differ from the grid data at at least one other field
 * @param items
 * @param csvRows
 * @param rowKeys
 * @param matched
 * @param permittedCols
 * @param importKey
 * @returns {{rows: Array, info: string}}
 */
function getMatchedAndChangedRows(items, csvRows, rowKeys, matched, permittedCols, importKey) {
    let rows = [];
    let idMatchCount = 0;
    let totalRowCount = csvRows.length;
    $.each(csvRows, function (_i, csvRow) {
        let rowKey = csvRow[matched[0]];
        let rowIdx = rowKeys.indexOf(rowKey);
        if (rowIdx > -1) {
            idMatchCount++;
            let item = items[rowIdx];
            let itemId = item.id;
            let changed = false;

            // We skip the key column (let permittedCol = 1 instead of 0), so we add it before the loop.
            let row = [rowKey];
            for (let permittedCol = 1; permittedCol < permittedCols.length; permittedCol++) {
                let field = permittedCols[permittedCol];
                let csvCol = matched[permittedCol];
                if (undefined === csvCol) {
                    row.push(null);
                }
                else {
                    let csvCellVal = csvRow[csvCol];
                    let itemFieldVal = item[field];

                    if ((!isEmpty(itemFieldVal) || !isEmpty(csvCellVal)) && csvCellVal !== itemFieldVal) {
                        changed = true;
                    }
                    row.push(csvCellVal);
                }
            }

            // Only add rows that differ from the corresponding grid item
            if (changed) {
                // Always put the ID last so that it will not be rendered to the table which the user can see.
                row.push(itemId);
                rows.push(row);
            }
        }
    });
    let changedCount = rows.length;
    if (changedCount === 0) {
        throw new Error('Your CSV contains the exact same data as current on the table. The table will not be updated.');
    }

    let info = `You CSV contains <strong>${totalRowCount}</strong> rows. 
                <strong>${idMatchCount}</strong> rows have matching <strong>${importKey}</strong>.
                <strong>${changedCount}</strong> rows differ from table value. 
                The table will be updated based on these <strong>${changedCount}</strong> rows.`;

    return {rows, info};
}

/**
 * Read csv from text & perform other task to arrive at {rows: the rows that will update the grid, info: information
 * about the data being imported and matched: list of columns that match the grid columns.
 * @param csvText
 * @param permittedCols
 * @param importKey
 * @param columns
 * @param items
 * @returns {Promise}
 */
function processCsv(csvText, permittedCols, importKey, columns, items) {
    let importKeyColumn = findColumn(columns, importKey);
    let rowKeys = getKeyFields(items, importKeyColumn);

    return new Promise(function (resolve, reject) {
        try {
            let csvRows = [];
            Papa.parse(csvText, {
                skipEmptyLines: true,
                step(results, parser) {
                    if (results.errors.length) {
                        let errorMessage = results.errors.map((x) => x.message).join(';');
                        let e = new Error(`Error parsing CSV: ${errorMessage}`);
                        logError(e);
                        parser.abort();
                        reject(e);
                    }
                    let row = results.data[0];
                    csvRows.push(row);
                },
                complete() {
                    let header = csvRows.splice(0, 1)[0];
                    let {matched} = matchColumns(header, permittedCols, importKey);
                    let {rows, info} = getMatchedAndChangedRows(items, csvRows, rowKeys, matched, permittedCols, importKey);
                    resolve({rows, info, matched});
                }
            });
        }
        catch (e) {
            logError(e);
            reject(e);
        }
    });

}


/**
 * Upload the data to server to update grid
 * @param rows
 * @param attrs
 * @param missingAttrs
 * @param gridType
 * @returns {Promise}
 */
function uploadCsvToServer(rows, attrs, missingAttrs, gridType) {
    return new Promise(function(resolve, reject) {
        postRequest({
            requestSlug: 'change-properties-table',
            data: {
                'grid-type': gridType,
                rows: JSON.stringify(rows),
                attrs: JSON.stringify(attrs),
                'missing-attrs': JSON.stringify(missingAttrs)
            },
            onSuccess(data) {
                resolve(data);
            },
            onFailure(data) {
                reject(new Error(data));
            }
        });
    });
}


/**
 * Remove the key column because it is guaranteed to be the same between grid and csv
 * @TODO maybe this is unnecessary - saves little data transfer but makes program harder to follow
 * @param rows
 * @param permittedCols
 * @param matched
 * @returns {{missingCols: Array}}
 */
function reduceData({rows, permittedCols, matched}) {
    let missingCols = [];
    $.each(permittedCols, function(permittedColIx, permittedCol) {
        if (matched[permittedColIx] === undefined) {
            missingCols.push(permittedCol)
        }
    });

    let retval = {missingCols};

    if (missingCols.length) {
        retval.warning = 'The following columns are missing from your CSV: ' + missingCols.join(', ');
    }

    // Remove the key column because it is guaranteed to be the same between grid and csv - that's how we match them
    retval.rows = rows.map((row) => row.slice(1));
    retval.permittedCols = permittedCols.slice(1);

    return retval;
}


/**
 * Allow user to upload songs
 */
const initUploadCsv = function () {
    if (page && page.grid && page.grid.importKey) {
        let grid = page.grid.mainGrid;
        let importKey = page.grid.importKey;
        let gridType = page.grid.gridType;

        let $modal = $('#upload-csv-modal');
        let uploadCsvBtn = $modal.find('#upload-csv-btn');
        let processCsvBtn = $modal.find('#process-csv-btn');
        let uploadForm = $modal.find('#file-upload-form');
        let uploadInput = uploadForm.find('input[type=file]');
        let modalAlertFailure = $modal.find('.alert-danger');
        let modalAlertWarning = $modal.find('.alert-warning');
        let modalAlertSuccess = $modal.find('.alert-success');

        let $table = $modal.find('table');
        let columns = grid.getColumns();
        let permittedCols = extractHeader(columns, 'importable', importKey);
        let items = grid.getData().getItems();

        uploadCsvBtn.on('click', function () {
            uploadInput.click();
        });

        uploadInput.change(function (e) {
            e.preventDefault();
            let file = e.target.files[0];
            let reader = new FileReader();

            reader.onload = function () {
                uploadInput.val(null);
                processCsv(reader.result, permittedCols, importKey, columns, items).
                    then(function ({rows, info, matched}) {
                        if (info) {
                            showAlert(modalAlertSuccess, info, -1);
                        }

                        $table.children().remove();

                        createTable($table, permittedCols, rows, true);
                        processCsvBtn.prop('disabled', false);

                        let reduced = reduceData({rows, permittedCols, matched});
                        rows = reduced.rows;
                        permittedCols = reduced.permittedCols;
                        let warning = reduced.warning;
                        let missingCols = reduced.missingCols;

                        if (warning) {
                            showAlert(modalAlertWarning, warning, -1);
                        }

                        processCsvBtn.on('click', function() {
                            uploadCsvToServer(rows, permittedCols, missingCols, gridType).
                                then(function() {
                                    processCsvBtn.prop('disabled', true);
                                    uploadCsvBtn.prop('disabled', true);
                                    processCsvBtn.off('click');
                                    let msg = 'Data imported successfully. Page will reload';
                                    showAlert(modalAlertSuccess, msg, 1500).then(function() {
                                        window.location.reload();
                                    });
                                }).
                                catch(function(err) {
                                    showAlert(modalAlertFailure, err, -1);
                                });
                        });

                    }).catch(function (err) {
                        logError(err);
                        processCsvBtn.prop('disabled', true);
                        showAlert(modalAlertFailure, err, 15000);
                    });
            };
            reader.readAsText(file);
        });

        $('#open-upload-csv-modal').click(function () {
            $modal.find('.import-key').html(importKey);
            $table.children().remove();
            processCsvBtn.prop('disabled', true);
            createTable($table, permittedCols);
            $modal.modal('show');
        });
    }


};

/**
 * Put everything you need to run after the page has been loaded here
 */
const _postRun = function () {
    let pageViewportHandler;
    if (!isNull(page)) {
        pageViewportHandler = page.viewPortChangeHandler;
    }
    initSidebar(pageViewportHandler);

    $('.btn[url]').on('click', function (e) {
        e.preventDefault();
        window.location = this.getAttribute('url');
    });

    $('.download-xls').click(function () {
        let downloadType = $(this).data('download-type');
        let gridType = page.grid.gridName;
        let csvContent = createCsv(page.grid.mainGrid, downloadType);

        let d = new Date();
        let dateString = toJSONLocal(d);
        let filename = `koe-${gridType}-${dateString}.csv`;
        let blob = new Blob([csvContent], {type: 'text/csv;charset=utf-8;'});
        downloadBlob(blob, filename);
    });

    initUploadCsv();
    countDown();
};

const showErrorDialog = function (errMsg) {
    dialogModalTitle.html('Oops, something\'s not right');

    dialogModalBody.children().remove();
    dialogModalBody.append(`<div>${errMsg}</div>`);
    dialogModal.modal('show');

    dialogModalCancelBtn.html('Dismiss');
    dialogModalOkBtn.parent().hide();
    dialogModal.on('hidden.bs.modal', function () {
        dialogModalOkBtn.parent().show();
        dialogModalCancelBtn.html('No');
    });
};


const openNewWindow = window.open;

/**
 * Replace open() with a version that can detect popup blocker, and displays the message in that case
 * @param urlToOpen
 */
window.open = function (urlToOpen) {
    let popupWindow = openNewWindow(urlToOpen, uuid4(), '');
    try {
        popupWindow.focus();
    }
    catch (e) {
        let errMsg = `
            <p>Koe was prevented from opening a new window to <a href="${urlToOpen}">${urlToOpen}</a> by your browser.</p>
            <p>Please whitelist this website in <strong>Pop-ups and Redirects</strong> settings.</p>`;
        showErrorDialog(errMsg);
    }
};

/**
 * Loading the page by URL's location, e.g localhost:8000/herd-allocation
 */
$(document).ready(function () {
    let windowWith = $(window).width();
    if (windowWith < 576) {
        $('#content-wrapper').removeClass('toggled').addClass('not-toggled');
    }

    let pageName = location.pathname;
    if (pageName === '/dashboard/') {
        page = require('dashboard-page');
    }
    else if (pageName.startsWith('/song-partition/')) {
        page = require('song-partition-page');
    }
    else if (pageName.startsWith('/syllables/')) {
        page = require('syllables-page');
    }
    else if (pageName.startsWith('/segmentation/')) {
        page = require('segmentation-page');
    }
    else if (pageName.startsWith('/songs/')) {
        page = require('songs-page');
    }
    else if (pageName.startsWith('/exemplars/')) {
        page = require('exemplars-page');
    }
    else if (pageName.startsWith('/sequence-mining/')) {
        page = require('sequence-mining-page')
    }
    else if (pageName.startsWith('/extraction/feature/')) {
        page = require('feature-extraction-page')
    }
    else if (pageName.startsWith('/extraction/ordination/')) {
        page = require('ordination-extraction-page')
    }
    else if (pageName.startsWith('/extraction/similarity/')) {
        page = require('similarity-extraction-page')
    }
    else if (pageName.startsWith('/view-ordination/')) {
        page = require('view-ordination-page')
    }
    else if (pageName === '/contact-us/') {
        page = require('contact-us-page');
    }

    let runPage = function () {
        if (isNull(page)) {
            return Promise.resolve();
        }
        else {
            let preRun = page.preRun || (() => Promise.resolve());

            return preRun(commonElements).then(function () {
                return page.run(commonElements).then(function () {
                    if (typeof page.postRun == 'function') {
                        return page.postRun();
                    }
                    return Promise.resolve();
                });
            });
        }
    };

    _preRun().then(function () {
        return runPage();
    }).then(function () {
        return _postRun();
    }).catch(function (e) {
        logError(e);
        showErrorDialog(e);
    });

});

