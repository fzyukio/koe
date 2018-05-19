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


const body = $('body');
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
export const handleResponse = function ({response, msgGen = noop, isSuccess = true, callback = noop, immediate = false}) {
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
 * @param noSpinner if true, don't show the spinner during AJAX loads
 */
const ajaxRequest = function ({
    requestSlug, data, msgGen = noop, type = 'POST', ajaxArgs = {}, onSuccess = noop,
    onFailure = noop, immediate = false, noSpinner = false
}) {

    ajaxArgs.url = getUrl('send-request', requestSlug);
    ajaxArgs.type = type;
    ajaxArgs.data = data;
    ajaxArgs.beforeSend = function () {
        if (!noSpinner) {
            body.addClass('loading');
        }
        body.css("cursor", "progress");
    };
    ajaxArgs.success = function (response) {
        if (!noSpinner) {
            body.removeClass('loading');
        }
        body.css("cursor", "default");
        handleResponse({
            response,
            msgGen,
            isSuccess: true,
            callback: onSuccess,
            immediate
        })
    };
    ajaxArgs.error = function (response) {
        if (!noSpinner) {
            body.removeClass('loading');
        }
        body.css("cursor", "default");
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
