/* eslint global-require: off */

let Urls = window.Urls;
export {
    Urls,
};

const Promise = require('bluebird');

Promise.config({
    cancellation: true
});

/**
 * Replace native Promise with BlueBird's Promise. BB's has cancellation capability and it is also much faster.
 * See https://softwareengineering.stackexchange.com/a/279003 and
 * https://github.com/petkaantonov/bluebird/tree/master/benchmark
 */
window.Promise = Promise;

import {isNull, SlickEditors, createCsv, downloadBlob, getUrl} from './utils';
import {postRequest} from './ajax-handler';
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
const currentDatabaseAttr = databaseCombo.attr('current-attr');
const databaseClass = databaseCombo.attr('cls');

const commonElements = {
    inputText,
    inputSelect,
    dialogModal,
    dialogModalTitle,
    dialogModalBody,
    dialogModalOkBtn,
    alertSuccess,
    alertFailure,
    databaseCombo
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


const initDatabaseButtons = function () {
    $('.select-database').on('click', function (e) {
        e.preventDefault();

        let parent = $(this).parent();
        if (parent.hasClass('not-active')) {
            let databaseId = this.getAttribute('database');
            let postData = {
                attr: currentDatabaseAttr,
                klass: databaseClass,
                value: databaseId
            };
            let onSuccess = function () {
                page.handleDatabaseChange();
            };

            postRequest({
                requestSlug: 'change-extra-attr-value',
                data: postData,
                onSuccess
            });

            /* Update the button */
            databaseCombo.attr('database', databaseId);
            $('.database-value').val(databaseId);
            parent.parent().find('li.active').removeClass('active').addClass('not-active');
            parent.removeClass('not-active').addClass('active');
        }
    });

    $('#create-database-btn').on('click', function (e) {
        e.preventDefault();
        showCreateDatabaseDialog();
    });

    $('.request-database').on('click', function (e) {
        e.preventDefault();
        let databaseId = this.getAttribute('database');

        let msgGen = function (isSuccess) {
            return isSuccess ?
                'Requested has been posted. A database admin will response to your request.' :
                null;
        };

        postRequest({
            requestSlug: 'koe/request-database-access',
            data: {'database-id': databaseId},
            msgGen,
            immediate: false
        });
    });

    $('.approve-request').on('click', function (e) {
        e.preventDefault();
        let requestId = this.getAttribute('request');

        let msgGen = function (isSuccess) {
            return isSuccess ? 'Success' : null;
        };

        postRequest({
            requestSlug: 'koe/approve-database-access',
            data: {'request-id': requestId},
            immediate: false,
            msgGen
        });
    });
};


/**
 * Put everything you need to run after the page has been loaded here
 */
const _postRun = function () {
    const viewPortChangeCallback = function () {
        viewPortChangeHandler().then(function () {

            if (!isNull(page) && page.grid) {
                page.grid.mainGrid.resizeCanvas();
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
    initDatabaseButtons();
};

/**
 * Loading the page by URL's location, e.g localhost:8000/herd-allocation
 */
$(document).ready(function () {
    let pageName = location.pathname;
    if (pageName === '/') {
        page = require('home-page');
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
    else if (pageName.startsWith('/feature-extraction/')) {
        page = require('feature-extraction-page')
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

