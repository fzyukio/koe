/* eslint global-require: off */

let Urls = window.Urls;
export {
    Urls,
};

import {isNull, SlickEditors, createCsv, downloadBlob} from './utils';
import {SelectizeEditor} from './selectize-formatter';
require("no-going-back");

let page;

const dialogModal = $('#dialog-modal');
const dialogModalTitle = dialogModal.find('.modal-title');
const dialogModalBody = dialogModal.find('.modal-body');
const dialogModalOkBtn = dialogModal.find('#dialog-modal-yes-button');
const alertSuccess = $('.alert-success');
const alertFailure = $('.alert-danger');

const commonElements = {
    dialogModal,
    dialogModalTitle,
    dialogModalBody,
    dialogModalOkBtn,
    alertSuccess,
    alertFailure
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
 *
 */
const adjustFullHeightOffset = function () {
    let offsetItems = $('.vh-offset');
    let maxVh = $('#max-vh').css('max-height');
    maxVh = maxVh.substr(0, maxVh.indexOf('px'));
    let vh = Math.min(maxVh, Math.max(document.documentElement.clientHeight, window.innerHeight || 0));

    for (let i = 0; i < offsetItems.length; i++) {
        let item = $(offsetItems[i]);
        let holder = $('#' + item.attr('id') + '-offset-holder');
        let attr = holder.attr('attr');
        let subtractExpression = holder.attr('minus');
        let subtractAmount = subtractExpression ? eval(subtractExpression) : 0;

        let divideFactor = holder.attr('divide') || 1;

        let offsetValue = holder.css(attr);
        offsetValue = 100000 - offsetValue.substr(0, offsetValue.indexOf('px'));
        item.css(attr, (vh - offsetValue - subtractAmount) / divideFactor);
    }
};

/**
 * Put everything you need to run before the page has been loaded here
 * @private
 */
const _preRun = function () {

    SlickEditors.Select = SelectizeEditor;

    adjustFullHeightOffset();
    let body = $('body');

    /**
     * Trigger the loading modal to be displayed/stopped while an Ajax call is being made
     */
    $(document).on({
        ajaxStart () {
            body.addClass('loading');
        },
        ajaxStop () {
            body.removeClass('loading');
        }
    });

    restoreModalAfterClosing();
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
    $('.dropdown-menu-right .dropdown-submenu').on('mouseover', function () {
        let submenu = $(this).find('.dropdown-menu');
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
 * Put everything you need to run after the page has been loaded here
 */
const _postRun = function () {
    const viewPortChangeCallback = function () {
        viewPortChangeHandler().then(function () {
            adjustFullHeightOffset();

            if (!isNull(page) && typeof page.orientationChange == 'function') {
                page.orientationChange();
            }
        });
    };

    window.addEventListener('orientationchange', viewPortChangeCallback);

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
};

/**
 * Loading the page by URL's location, e.g localhost:8000/herd-allocation
 */
$(document).ready(function () {
    let pageName = location.pathname;
    if (pageName === '/') {
        page = require('home-page');
    }
    else if (pageName === '/label/') {
        page = require('index-page');
    }
    else if (pageName === '/version/') {
        page = require('version-page');
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

