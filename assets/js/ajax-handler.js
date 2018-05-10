import {getUrl, noop} from './utils';
const alertSuccess = $('.alert-success');
const alertFailure = $('.alert-danger');

/**
 * Generate default message given the response
 * @param res server response
 * @returns {*} the default message
 */
function defaultMsgGen(res) {
    return res.success ?
        null :
        `Something's wrong, server says ${res.error}.`;
}

const delayOnSuccess = 500;
const delayOnFailure = 4000;

/**
 * Shortcut to call ajaxRequest for normal POST requests
 * @param requestSlug
 * @param data
 * @param msgGen
 * @param onSuccess
 * @param onFailure
 * @param immediate
 */
export const postRequest = function ({
    requestSlug, data, msgGen, onSuccess = null, onFailure = null, immediate = false
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
 * @param requestSlug
 * @param data
 * @param msgGen
 * @param onSuccess
 * @param onFailure
 * @param immediate
 */
export const uploadRequest = function ({
    requestSlug, data, msgGen, onSuccess = null, onFailure = null, immediate = false
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
 *
 * @param requestSlug
 * @param data
 * @param msgGen
 * @param type
 * @param ajaxArgs
 * @param onSuccess
 * @param onFailure
 * @param immediate
 */
const ajaxRequest = function ({
    requestSlug, data, msgGen, type = 'POST', ajaxArgs = {}, onSuccess = null,
    onFailure = null, immediate = false
}) {
    let url = getUrl('send-request', requestSlug);
    msgGen = msgGen || defaultMsgGen;

    let responseHandler = function (res) {
        res = JSON.parse(res);
        let alertEl, callback, delay, callbackArg;
        let message = msgGen(res);

        if (res.success) {
            alertEl = alertSuccess;
            callback = onSuccess || noop;
            delay = delayOnSuccess;
            callbackArg = res.response;
        }
        else {
            alertEl = alertFailure;
            callback = onFailure || noop;
            delay = delayOnFailure;
            callbackArg = undefined;
        }

        if (message) {
            alertEl.html(message);
            alertEl.fadeIn().delay(delay).fadeOut(100, function () {
                if (!immediate) callback(callbackArg);
            });
        }
        else {
            immediate = true;
        }
        if (immediate) callback(callbackArg);
    };

    ajaxArgs.url = url;
    ajaxArgs.type = type;
    ajaxArgs.data = data;
    ajaxArgs.success = responseHandler;

    $.ajax(ajaxArgs);
};
