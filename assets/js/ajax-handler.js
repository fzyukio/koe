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
 * @param requestSlug second part of a send-request/ url
 * @param data data
 * @param msgGen function to generate notification message
 * @param onSuccess callback when success
 * @param onFailure callback when failure
 * @param immediate whether or not to call callback right after showing the notification
 */
export const postRequest = function ({
    requestSlug, data, msgGen, onSuccess = noop, onFailure = noop, immediate = false
}) {
    let type = 'POST';
    let ajaxArgs = {};
    ajaxRequest({
        requestSlug,
        data,
        msgGen,
        type,
        ajaxArgs,
        onSuccess,
        onFailure,
        immediate
    })
};

/**
 * Shortcut to call ajaxRequest for file upload
 * @param requestSlug second part of a send-request/ url
 * @param data data
 * @param msgGen function to generate notification message
 * @param onSuccess callback when success
 * @param onFailure callback when failure
 * @param immediate whether or not to call callback right after showing the notification
 */
export const uploadRequest = function ({
    requestSlug, data, msgGen, onSuccess = noop, onFailure = noop, immediate = false
}) {
    let ajaxArgs = {
        // !IMPORTANT: this tells jquery to not set expectation of the content type.
        // If not set to false it will not send the file
        contentType: false,

        // !IMPORTANT: this tells jquery to not convert the form data into string.
        // If not set to false it will raise "IllegalInvocation" exception
        processData: false
    };
    let type = 'POST';
    ajaxRequest({
        requestSlug,
        data,
        msgGen,
        type,
        ajaxArgs,
        onSuccess,
        onFailure,
        immediate
    })
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
    response, msgGen = noop, isSuccess = true, callback = noop, immediate = false
}) {
    let alertEl, delay;
    let message = msgGen(isSuccess, response) || defaultMsgGen(isSuccess, response);

    if (isSuccess) {
        alertEl = alertSuccess;
        delay = delayOnSuccess;
    }
    else {
        alertEl = alertFailure;
        delay = delayOnFailure;
    }

    if (message) {
        alertEl.html(message);
        alertEl.fadeIn().delay(delay).fadeOut(delay, function () {
            if (!immediate) callback(response);
        });
    }
    else {
        immediate = true;
    }
    if (immediate) callback(response);
};

/**
 *
 * @param requestSlug second part of a send-request/ url
 * @param data data
 * @param msgGen function to generate notification message
 * @param type POST or GET
 * @param ajaxArgs extra arguments for the AJAX call
 * @param onSuccess callback when success
 * @param onFailure callback when failure
 * @param immediate whether or not to call callback right after showing the notification
 */
const ajaxRequest = function ({
    requestSlug, data, msgGen = noop, type = 'POST', ajaxArgs = {}, onSuccess = noop,
    onFailure = noop, immediate = false
}) {
    ajaxArgs.url = getUrl('send-request', requestSlug);
    ajaxArgs.type = type;
    ajaxArgs.data = data;
    ajaxArgs.success = function (response) {
        handleResponse({
            response,
            msgGen,
            isSuccess: true,
            callback: onSuccess,
            immediate
        })
    };
    ajaxArgs.error = function (response) {
        handleResponse({
            response: response.responseText,
            msgGen,
            isSuccess: false,
            callback: onFailure,
            immediate
        })
    };

    $.ajax(ajaxArgs);
};
