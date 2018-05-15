(function () {

    let devtools = {
        open: false,
        orientation: null
    };
    let threshold = 160;
    let emitEvent = function (state, orientation) {
        window.dispatchEvent(new CustomEvent('devtoolschange', {
            detail: {
                open: state,
                orientation
            }
        }));
    };

    setInterval(function () {
        let widthThreshold = window.outerWidth - window.innerWidth > threshold;
        let heightThreshold = window.outerHeight - window.innerHeight > threshold;
        let orientation = widthThreshold ? 'vertical' : 'horizontal';

        if (!(heightThreshold && widthThreshold) &&
            ((window.Firebug && window.Firebug.chrome && window.Firebug.chrome.isInitialized) || widthThreshold || heightThreshold)) {
            if (!devtools.open || devtools.orientation !== orientation) {
                emitEvent(true, orientation);
                window.PRINT_DEBUG = window.USER_IS_SUPERUSER;
            }

            devtools.open = true;
            devtools.orientation = orientation;
        }
        else {
            if (devtools.open) {
                emitEvent(false, null);
                window.PRINT_DEBUG = false;
            }

            devtools.open = false;
            devtools.orientation = null;
        }
    }, 500);

    window.devtools = devtools;
}());
