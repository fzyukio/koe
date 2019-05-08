/* global YT */
require('slick-carousel');
require('../vendor/iframe_api');

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

/**
 * Make the features section display slide
 */
function initCarousel() {
    $('.carousel').slick({
        autoplay: true,
        autoplaySpeed: 2000,
        dots: true,
        arrows: false,
    });
}

/**
 * Necessary functions to control Youtube's clip
 */
function initYoutube() {
    let player, iframe;
    let videoWrapper = $('#home-intro-video');

    window.onYouTubeIframeAPIReady = function () {
        player = new YT.Player('player', {
            videoId: '0RaLAJim_PA',
            host: 'https://www.youtube.com',
            events: {
                'onReady': onPlayerReady
            }
        });
    };

    /**
     * Bind buttons to click events
     * @param event
     */
    function onPlayerReady(event) {
        player = event.target;
        iframe = $('#player');

        $('.intro-video-toggle').click(function (e) {
            e.preventDefault();
            videoWrapper.show();
            player.playVideo();
            resizeToFitScreen();
        }).show();

        $('.popup-close button').click(function (e) {
            e.preventDefault();
            player.stopVideo();
            videoWrapper.hide();
        });
    }

    /**
     * Change size so that the video doesn't exceed screen width or 1280 px wide
     */
    function resizeToFitScreen() {
        let h = iframe.height();
        let w = iframe.width();

        let maxWidth = Math.min(document.body.clientWidth, 1024);
        let maxHeight = maxWidth * h / w;

        player.setSize(maxWidth, maxHeight);
    }
}

export const run = function () {
    initYoutube();
    return Promise.resolve();
};

export const postRun = function () {
    initCarousel();
    return Promise.resolve();
};
