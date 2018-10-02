/* eslint global-require: off */

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

import {isNull, SlickEditors, createCsv, downloadBlob, getUrl, getGetParams} from './utils';
import {SelectizeEditor} from './selectize-formatter';
require('no-going-back');

let page;

const inputText = $('<input type="text" class="form-control"/>');
const inputSelect = $('<select class="selectize" ></select>');

const dialogModal = $('#dialog-modal');
const dialogModalTitle = dialogModal.find('.modal-title');
const dialogModalBody = dialogModal.find('.modal-body');
const dialogModalOkBtn = dialogModal.find('#dialog-modal-yes-button');
const alertSuccess = $('.alert-success');
const alertFailure = $('.alert-danger');

const databaseCombo = $('#database-select-combo');
let argDict = getGetParams();

const commonElements = {
    inputText,
    inputSelect,
    dialogModal,
    dialogModalTitle,
    dialogModalBody,
    dialogModalOkBtn,
    alertSuccess,
    alertFailure,
    databaseCombo,
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
 * Put everything you need to run before the page has been loaded here
 * @private
 */
const _preRun = function () {

    SlickEditors.Select = SelectizeEditor;

    restoreModalAfterClosing();

    $('.alert .close').on('click', function () {
        let alertEl = $(this).parent();
        let timerId = alertEl.attr('timer-id');
        clearTimeout(timerId);
        alertEl.hide();
    });
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
 * When user clicks on the "create new database" button from the drop down menu, show a dialog
 * asking for name. Send the name to the server to check for duplicate. If there exists a database with the same name,
 * repeat this process. Only dismiss the dialog if a new database is created.
 * @param errorMessage to be shown if not undefined
 */
const showCreateDatabaseDialog = function (errorMessage) {
    dialogModalTitle.html('Creating a new database...');
    dialogModalBody.html('<label>Give it a name</label>');
    dialogModalBody.append(inputText);
    if (errorMessage) {
        dialogModalBody.append(`<p>${errorMessage}</p>`);
    }

    dialogModal.modal('show');

    dialogModalOkBtn.one('click', function () {
        dialogModal.modal('hide');
        let url = getUrl('send-request', 'koe/create-database');
        let databaseName = inputText.val();
        inputText.val('');

        $.post(url, {name: databaseName}).done(function () {
            dialogModal.one('hidden.bs.modal', function () {
                location.reload();
            });
            dialogModal.modal('hide');
        }).fail(function (response) {
            dialogModal.one('hidden.bs.modal', function () {
                showCreateDatabaseDialog(response.responseText);
            });
            dialogModal.modal('hide');
        });
    });
};


const initSidebar = function() {
    $('.menu-item-expandable > a').click(function () {
        $('.menu-submenu').slideUp(200);
        if ($(this).parent().hasClass('active')) {
            $('.menu-item-expandable').removeClass('active');
            $(this).parent().removeClass('active');
        }
        else {
            $('.menu-item-expandable').removeClass('active');
            $(this).next('.menu-submenu').slideDown(200);
            $(this).parent().addClass('active');
        }
    });

    $('.siderbar-toggler').click(function () {
        $('#content-wrapper').toggleClass('toggled').toggleClass('not-toggled');
        if (!isNull(page) && typeof page.viewPortChangeHandler === 'function') {
            setTimeout(page.viewPortChangeHandler, 250);
        }

    });

    let currentPage = $('#sidebar-menu').attr('page');
    $('.menu-item').each(function(idx, menuItemEL) {
        if (menuItemEL.getAttribute('page') === currentPage) {
            $(menuItemEL).addClass('active');
        }
    });

    $('.menu-submenu li').each(function(idx, menuItemEL) {
        if (menuItemEL.getAttribute('page') === currentPage) {
            $(menuItemEL).addClass('active');
            $(menuItemEL).parents('.menu-item-expandable').children('a').click();
        }
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
const initChangeArgSelections = function() {
    let locationOrigin = window.location.origin;
    let localtionPath = window.location.pathname;

    $('.change-arg').click(function(e) {
        e.preventDefault();
        argDict[this.getAttribute('key')] = this.getAttribute('value');
        let replace = this.getAttribute('replace');
        if (!isNull(replace)) {
            delete argDict[replace];
        }

        let argString = '?';
        $.each(argDict, function(k, v) {
            if (!k.startsWith('__')) {
                argString += `${k}=${v}&`;
            }
        });
        window.location.href = `${locationOrigin}${localtionPath}${argString}`;
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
        $.each(argDict, function(k, v) {
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
    const viewPortChangeCallback = function () {
        viewPortChangeHandler().then(function () {
            if (!isNull(page) && typeof page.viewPortChangeHandler === 'function') {
                page.viewPortChangeHandler();
            }
        });
    };

    window.addEventListener('orientationchange', viewPortChangeCallback);
    window.addEventListener('resize', viewPortChangeCallback);

    $('.btn[url]').on('click', function (e) {
        e.preventDefault();
        window.location = this.getAttribute('url');
    });

    $('.download-xls').click(function () {
        let downloadType = $(this).data('download-type');
        let gridType = page.grid.gridName;
        let csvContent = createCsv(page.grid.mainGrid, downloadType);

        let d = new Date();
        let filename = `koe-${gridType}-${d.getFullYear()}-${d.getMonth()}-${d.getDate()}_${d.getHours()}-${d.getMinutes()}-${d.getSeconds()}.csv`;
        let blob = new Blob([csvContent], {type: 'text/csv;charset=utf-8;'});
        downloadBlob(blob, filename);
    });

    countDown();
    subMenuOpenRight();
    initChangeArgSelections();
    initSidebar();
    appendGetArguments();
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
    else if (pageName === '/version/') {
        page = require('version-page');
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
    else if (pageName.startsWith('/ordination/')) {
        page = require('view-ordination-page')
    }
    else if (pageName === '/contact-us/') {
        page = require('contact-us-page');
    }

    _preRun();

    if (!isNull(page)) {

        if (typeof page.preRun == 'function') {
            page.preRun();
        }

        page.run(commonElements);

        if (typeof page.postRun == 'function') {
            page.postRun();
        }
    }

    _postRun();

});

