import {getUrl, noop} from './utils';

const alertSuccess = $('.alert-success');
const alertFailure = $('.alert-danger');

/**
 * Generate default message given the response
 * @returns {*} the default message
 * @param isSuccess
 * @param response
 */
function defaultMsgGen(isSuccess, response) {
    return isSuccess ?
        null :
        `Something's wrong, server says <strong><i>"${response}"</i></strong>.`;
}


const delayOnSuccess = 500;
const delayOnFailure = 4000;

/**
 * Shortcut to call ajaxRequest for normal POST requests
 * @param args see ajaxRequest
 */
export const postRequest = function (args) {
    args.type = 'POST';
    ajaxRequest(args)
};


export const postPromise = function (args) {
    let onSuccess = args.onSuccess;
    let onFailure = args.onFailure;

    if (onSuccess !== undefined || onFailure !== undefined) {
        throw new Error('Success and Failure are handled by Promise, thus cannot be provided as arguments');
    }

    return new Promise(function (resolve, reject) {
        args.type = 'POST';
        args.onSuccess = function(response) {
            resolve(response);
        };
        args.onFailure = function (response) {
            reject(response);
        };
        ajaxRequest(args);
    });
};


/**
 * Make a request to download file by GET
 * @param url
 * @param ArrayClass if not null, the response is converted to the typed array of this class
 * @returns {Promise}
 */
export const downloadRequest = function (url, ArrayClass = null) {
    return new Promise(function (resolve, reject) {
        let req = new XMLHttpRequest();
        req.open('GET', url, true);
        if (ArrayClass) {
            req.responseType = 'arraybuffer';
        }

        req.onload = function () {
            if (ArrayClass) {
                let byteArray = new ArrayClass(req.response);
                resolve(byteArray);
            }
            else {
                resolve(req.response);
            }
        };

        req.onreadystatechange = function () {
            if (this.readyState === 4) {
                if (this.status !== 200) {
                    let responseJson = JSON.parse(this.response);
                    let responseMessage = responseJson.message;
                    reject(new Error(responseMessage));
                }
            }
        };

        req.send(null);
    });
};


/**
 * Shortcut to call ajaxRequest for file upload
 * @param args see ajaxRequest
 */
export const uploadRequest = function (args) {
    args.ajaxArgs = {
        // !IMPORTANT: this tells jquery to not set expectation of the content type.
        // If not set to false it will not send the file
        contentType: false,

        // !IMPORTANT: this tells jquery to not convert the form data into string.
        // If not set to false it will raise "IllegalInvocation" exception
        processData: false
    };
    args.type = 'POST';
    ajaxRequest(args);
};

/**
 * Show notification corresponding to the response, and pass it on the the callback
 * @param response response body
 * @param msgGen function to generate notification message
 * @param isSuccess true if response is success
 * @param callback
 * @param immediate whether or not to call callback right after showing the notification
 */
export const handleResponse = function ({
    response, msgGen = noop, isSuccess, callback = noop, immediate = false
}) {
    let alertEl, delay;
    let responseJson = JSON.parse(response);
    let errorId = responseJson.errid;
    let responseMessage = responseJson.message;
    let message = msgGen(isSuccess, responseMessage) || defaultMsgGen(isSuccess, responseMessage);

    if (isSuccess) {
        alertEl = alertSuccess;
        delay = delayOnSuccess;
    }
    else {
        alertEl = alertFailure;
        delay = delayOnFailure;
    }

    if (message) {
        alertEl.find('.message').html(message);
        if (errorId) {
            alertEl.find('.link').attr('error-id', errorId);
        }

        let timerId = alertEl.attr('timer-id');
        if (timerId) {
            clearTimeout(timerId);
        }

        timerId = setTimeout(function () {
            alertEl.fadeOut(500, function () {
                if (!immediate) callback(responseMessage);
            });
        }, delay);

        alertEl.attr('timer-id', timerId);
        alertEl.fadeIn();

    }
    else {
        immediate = true;
    }

    if (immediate) callback(responseMessage);
};


const body = $('body');

/**
 * Create two functions, start() to show the spinner; clear() to clear the spinner
 * @param delayStart: in millisecond. The spinner will not show if clear() is called within this amount of time.
 * @returns {{start: start, clear: clear}}
 */
export const createSpinner = function(delayStart = 300) {
    let timerId;

    let start = function () {
        timerId = setTimeout(function () {
            body.addClass('loading');
            body.css('cursor', 'progress');
        }, delayStart);
    };

    let clear = function () {
        clearTimeout(timerId);
        body.removeClass('loading');
        body.css('cursor', 'default');
    };

    return {start, clear};
};


/**
 *
 * @param url the direct URL to send request. If left empty, requestSlug will be used
 * @param requestSlug second part of a send-request/ url
 * @param data data
 * @param msgGen function to generate notification message
 * @param type POST or GET
 * @param ajaxArgs extra arguments for the AJAX call
 * @param onSuccess callback when success
 * @param onFailure callback when failure
 * @param onProgress callback when progress changes
 * @param immediate whether or not to call callback right after showing the notification
 * @param spinner
 */
const ajaxRequest = function ({
    url, requestSlug, data, msgGen = noop, type = 'POST', ajaxArgs = {}, onSuccess = noop, onFailure = noop,
    onProgress = noop, immediate = false, spinner = undefined
}) {

    if (spinner === undefined) {
        spinner = createSpinner();
    }

    if (url) {
        ajaxArgs.url = url;
    }
    else {
        ajaxArgs.url = getUrl('send-request', requestSlug);
    }
    ajaxArgs.type = type;
    ajaxArgs.data = data;

    if (data instanceof FormData) {
        ajaxArgs.processData = false;
        ajaxArgs.contentType = false;
    }

    ajaxArgs.beforeSend = function() {
        if (spinner) {
            spinner.start()
        }
    };

    ajaxArgs.success = function (response) {
        if (spinner) {
            spinner.clear();
        }

        handleResponse({
            response,
            msgGen,
            isSuccess: true,
            callback: onSuccess,
            immediate
        })
    };
    ajaxArgs.error = function (response) {
        if (spinner) {
            spinner.clear();
        }
        body.removeClass('loading');
        body.css('cursor', 'default');
        handleResponse({
            response: response.responseText,
            msgGen,
            isSuccess: false,
            callback: onFailure,
            immediate
        })
    };

    ajaxArgs.xhr = function () {
        let myXhr = $.ajaxSettings.xhr();
        if (myXhr.upload) {
            myXhr.upload.addEventListener('progress', onProgress, false);
        }
        return myXhr;
    };

    $.ajax(ajaxArgs);
};
