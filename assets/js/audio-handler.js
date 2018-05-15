import {isNull} from './utils';
import {handleResponse, postRequest} from './ajax-handler';

/**
 * the global instance of AudioContext (we maintain only one instance at all time)
 * this instance must always be closed when not playing audio
 * @type {*}
 */
let audioContext = null;

/**
 * the global instance of AudioBuffer (we maintain only one instance at all time)
 * @type {null}
 */
let audioBuffer = null;
let cachedArrays = {};

/**
 * Playback speed, global
 */
let playbackSpeed = 100;

/**
 * Self-explanatory
 * @param newSpeed
 */
export const changePlaybackSpeed = function (newSpeed) {
    playbackSpeed = newSpeed;
};

/**
 * Make sure we have a suitable AudioContext class
 */
export const initAudioContext = function () {

    if (!window.AudioContext) {
        if (!window.webkitAudioContext) {
            alert('Your browser does not support any AudioContext and cannot play back this audio.');
            return;
        }
        window.AudioContext = window.webkitAudioContext;
    }

    audioContext = new AudioContext();
    audioContext.close();
};

/**
 * Plays a owner of the audio from begin point to end point
 * @param beginSec see below
 * @param endSec and beginMs : in seconds
 * @param onStartCallback callback to be called when the audio starts
 * @param onEndedCallback callback to be called when the audio finishes
 */
const playAudio = function ({beginSec = 'start', endSec = 'end', onStartCallback = null, onEndedCallback = null}) {
    if (isNull(audioContext) || audioContext.state === 'closed') {
        audioContext = new AudioContext();
    }

    /*
     * Prevent multiple audio playing at the same time: stop any instance if audioContext that is currently running
     */
    else if (!isNull(audioContext) && audioContext.state === 'running') {
        audioContext.close();
        audioContext = new AudioContext();
    }
    let source = audioContext.createBufferSource();
    source.buffer = audioBuffer;

    source.playbackRate.setValueAtTime(playbackSpeed / 100.0, 0);
    source.connect(audioContext.destination);

    if (beginSec === 'start') {
        beginSec = 0
    }

    if (endSec === 'end') {
        endSec = audioBuffer.duration;
    }

    // For more information, read up AudioBufferSourceNode.start([when][, offset][, duration])
    if (typeof onStartCallback === 'function') {
        onStartCallback(playbackSpeed);
    }

    source.start(0, beginSec, endSec - beginSec);
    source.onended = function () {
        audioContext.close();
        if (typeof onEndedCallback === 'function') {
            onEndedCallback();
        }
    };
};


/**
 * Stop the audio if it is playing
 */
export const stopAudio = function () {
    if (!isNull(audioContext) && audioContext.state === 'running') {
        audioContext.close();
        audioContext = new AudioContext();
    }
};


/**
 * Convert audio data to audio bugger and then play
 * @param fullAudioDataArray a Float32Array object
 * @param sampleRate sampling rate
 * @param playAudioArgs arguments to provide for playAudio
 */
const playAudioDataArray = function (fullAudioDataArray, sampleRate, playAudioArgs) {
    audioBuffer = audioContext.createBuffer(1, fullAudioDataArray.length, sampleRate);
    audioBuffer.getChannelData(0).set(fullAudioDataArray);
    playAudio(playAudioArgs);
};


/**
 * Convert a dict to a FormData object, with the same key-value pairs
 * @param data
 * @returns {FormData}
 */
const convertToFormData = function (data) {
    let formData;
    if (data instanceof FormData) {
        formData = data;
    }
    else {
        formData = new FormData();
        for (let key in data) {
            if (Object.prototype.hasOwnProperty.call(data, key)) {
                formData.append(key, data[key]);
            }
        }
    }
    return formData;
};


/**
 * Query, cache a piece of audio, then provide the signal and fs as arguments to the callback function
 * @param url POST or GET url, depending on the existence of postData
 * @param formData if querying for segment, formData must contain segment-id
 * @param cacheKey key to persist this song/segment in the cache
 * @param callback
 */
const queryAndHandleAudioGetOrPost = function ({url, cacheKey, formData, callback}) {
    const reader = new FileReader();
    reader.onload = function () {
        const arrayBuffer = reader.result;
        audioContext.decodeAudioData(arrayBuffer, function (_audioBuffer) {
            let fullAudioDataArray = _audioBuffer.getChannelData(0);
            let sampleRate = _audioBuffer.sampleRate;
            if (cacheKey && !window.noCache) {
                cachedArrays[cacheKey] = [fullAudioDataArray, sampleRate];
            }
            callback(fullAudioDataArray, sampleRate);
        });
    };
    let method = isNull(formData) ? 'GET' : 'POST';

    const xhr = new XMLHttpRequest();
    xhr.open(method, url, true);
    xhr.onloadend = function () {
        $.event.trigger('ajaxStop');
    };

    // We expect the response to be audio/mp4 when success, and text when failure.
    // So we need this to change the response type accordingly
    xhr.onreadystatechange = function () {
        // When request finishes, handle success/failure according to the status
        if (this.readyState == 4) {
            if (this.status == 200) {
                reader.readAsArrayBuffer(this.response);
            }
            else {
                handleResponse({
                    response: this.responseText,
                    isSuccess: false,
                })

            }
        }
        // When request is received, check if it is successful/failed and set the response type
        else if (this.readyState == 2) {
            if (this.status == 200) {
                this.responseType = 'blob';
            }
            else {
                this.responseType = 'text';
            }
        }
    };

    $.event.trigger('ajaxStart');
    xhr.send(formData);
};


/**
 * Query, cache a piece of audio, then provide the signal and fs as arguments to the callback function
 * @param url POST or GET url, depending on the existence of postData
 * @param postData POST data that contains the id of the song/segment to be downloaded. null to use GET
 * @param cacheKey key to persist this song/segment in the cache
 * @param callback
 */
export const queryAndHandleAudio = function ({url, cacheKey, postData}, callback) {
    let cached = cachedArrays[cacheKey];
    if (cacheKey && cached) {
        callback(cached[0], cached[1]);
    }
    else {
        let fileId = postData['file-id'];
        let formData = convertToFormData(postData);

        if (fileId) {
            let msgGen = function (isSuccess) {
                return isSuccess ? 'Success' : null;
            };
            let onSuccess = function (fileUrl) {
                queryAndHandleAudioGetOrPost({url: fileUrl,
                    cacheKey,
                    callback});
            };
            postRequest({
                requestSlug: 'koe/get-audio-file-url',
                data: postData,
                onSuccess,
                msgGen,
                immediate: true
            });
        }
        else {
            queryAndHandleAudioGetOrPost({url,
                cacheKey,
                formData,
                callback});
        }
    }
};

/**
 * Shortcut to download, cache a song/segment and them play for the specified segment
 * @param url POST url
 * @param postData POST data that contains the id of the song/segment to be downloaded
 * @param cacheKey key to persist this song/segment in the cache
 * @param playAudioArgs arguments to provide for playAudio
 */
export const queryAndPlayAudio = function ({url, postData, cacheKey, playAudioArgs = {}}) {
    let args = {
        url,
        cacheKey,
        postData
    };
    queryAndHandleAudio(args, function (sig, fs) {
        playAudioDataArray(sig, fs, playAudioArgs);
    });
};
