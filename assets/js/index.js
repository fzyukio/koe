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

import {isNull, createCsv, downloadBlob, getUrl, getGetParams, getCache, logError, uuid4, toJSONLocal} from './utils';
import {queryAndPlayAudio} from './audio-handler';
import {initSidebar} from './sidebar';
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

    initButtonBehaviour();
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


/**
 * Make <button>s function like <a>s
 */
function initButtonBehaviour() {
    $('button[href]').click(function (e) {
        e.preventDefault();
        let url = this.getAttribute('href');
        if (url) {
            window.location = url;
        }
    });
}


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

    $('[data-toggle="tooltip"]').tooltip();

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
    else if (pageName.startsWith('/syntax/')) {
        page = require('syntax-page')
    }
    else if (pageName === '/contact-us/') {
        page = require('contact-us-page');
    }
    else if (pageName === '/') {
        page = require('home-page');
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

