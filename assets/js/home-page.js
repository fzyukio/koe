require('slick-carousel');

/**
 * Show and play youtube clip on button clicked
 * @param state
 */
function toggleVideo(state) {
    // if state == 'hide', hide. Else: show video
    let div = document.getElementById('home-intro-video');
    let clip = $('#youtube-clip');
    let iframe = clip[0].contentWindow;
    div.style.display = state == 'hide' ? 'none' : '';
    let func = state == 'hide' ? 'pauseVideo' : 'playVideo';
    iframe.postMessage('{"event":"command","func":"' + func + '","args":""}', '*');
}

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

    $('.intro-video-toggle').click(function (e) {
        e.preventDefault();
        toggleVideo();
    });

    $('.popup-close button').click(function (e) {
        e.preventDefault();
        toggleVideo('hide');
    })
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

export const run = function () {
    initButtonBehaviour();
    return Promise.resolve();
};

export const postRun = function () {
    initCarousel();
    return Promise.resolve();
};
