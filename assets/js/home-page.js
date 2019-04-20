/**
 * The videoclip in the landking page might become too small and hangs in the middle of the screen.
 * This function ensures the clip is always half the width and anchors at the bottom of the screen
 */
function anchorLandingPageScreenshot() {
    let section1 = $('#section-1');
    let section1a = section1.find('#section-1a');
    let section1b = section1.find('#section-1b');
    let youtubeClip = section1b.find('#youtube-clip');
    let clipH = youtubeClip.height();
    let clipW = youtubeClip.width();

    let section1bW = section1b.width();
    let section1bH = section1b.height();

    let clipNewW = section1bW;
    let clipNewH = section1bW * clipH / clipW;
    if (clipNewH > section1bH) {
        clipNewW = clipW * section1bH / clipH;
        clipNewH = section1bH;
    }
    else {
        section1bH = clipNewH;
    }
    let section1aNewHeight = section1a.height() + section1b.height() - section1bH;

    youtubeClip.width(clipNewW);
    youtubeClip.height(clipNewH);
    section1b.height(section1bH);
    section1a.height(section1aNewHeight);
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
}

export const viewPortChangeHandler = function () {
    anchorLandingPageScreenshot();
};

export const run = function () {
    anchorLandingPageScreenshot();
    initButtonBehaviour();
    return Promise.resolve();
};
