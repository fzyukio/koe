let Urls = window.Urls;
export {
    Urls,
};

import {isNull, getUrl} from "./utils";

let page;

/**
 * Mobile viewport height after orientation change
 * See: https://stackoverflow.com/questions/12452349/mobile-viewport-height-after-orientation-change
 * Wait until innerheight changes, for max 120 frames
 */
function orientationChanged() {
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
    adjustFullHeightOffset();
    let body = $("body");

    /**
     * Trigger the loading modal to be displayed/stopped while an Ajax call is being made
     */
    $(document).on({
        ajaxStart: function () {
            body.addClass("loading");
        },
        ajaxStop: function () {
            body.removeClass("loading");
        }
    });
};


/**
 * If there is a timer, count down to 0 and redirect
 */
const countDown = function () {
    const timer = document.getElementById("countdown-redirect");
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
 * Put everything you need to run after the page has been loaded here
 * @private
 */
const _postRun = function () {
    window.addEventListener('orientationchange', function () {
        orientationChanged().then(function () {
            adjustFullHeightOffset();

            if (!isNull(page) && typeof page.orientationChange == 'function') {
                page.orientationChange();
            }
        });
    });

    $('.btn[url]').on('click', function (e) {
        e.preventDefault();
        window.location = this.getAttribute('url');
    });

    countDown();
};

/**
 * Loading the page by URL's location, e.g localhost:8000/herd-allocation
 */
$(document).ready(function () {
    let pageName = location.pathname;
    console.log("Loading " + pageName);

    if (pageName === '/') {
        page = require('index-page');
    }

    _preRun();

    if (!isNull(page)) {

        if (typeof page.preRun == 'function') {
            page.preRun();
        }

        page.run();

        if (typeof page.postRun == 'function') {
            page.postRun();
        }
    }

    _postRun();

});

