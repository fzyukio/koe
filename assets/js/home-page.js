/**
 * The screenshot in the landking page might become too small and hangs in the middle of the screen.
 * This function ensures the screenshot is always half the width and anchors at the bottom of the screen
 */
function anchorLandingPageScreenshot() {
    let section1 = $('#section-1');
    let section1a = section1.find('#section-1a');
    let section1b = section1.find('#section-1b');
    let screenshot = section1b.find('img');
    let imgHeight = screenshot.height();

    let imgOriginalWidth = screenshot[0].naturalWidth;
    let imgOriginalHeight = screenshot[0].naturalHeight;
    let newImgWidth = imgOriginalWidth * imgHeight / imgOriginalHeight;

    let section1Height = section1.height();
    let section1aNewHeight = section1Height - imgHeight;
    section1b.height(imgHeight);
    section1b.width(newImgWidth);

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
