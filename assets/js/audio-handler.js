require('../vendor/AudioContextMonkeyPatch');
const bufferToWav = require('audiobuffer-to-wav');
import {isNull, noop, logError} from './utils';
import {handleResponse, postRequest, createSpinner} from './ajax-handler';
import {WAVDecoder} from '../vendor/audiofile';

/**
 * the global instance of AudioContext (we maintain only one instance at all time)
 * this instance must always be closed when not playing audio
 * @type {*}
 */
let audioContext = new AudioContext();
export const MAX_SAMPLE_RATE = audioContext.sampleRate;


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
 * Safari (since 2017?) and Chrome (from November 2018) and maybe other browsers in the future prohibit audiocontext
 * from playing before user has interacted with the page. This function MUST be called before any AJAX call is made.
 * So the procedure is: onclick -> call resumeAudioContext --> make AJAX call if necessary -> playAudioDataArray()
 *
 * DO NOT CALL THIS unless playAudioDataArray is next in line. Other functions in this library already do that
 */
export const resumeAudioContext = function () {

    /*
     * Prevent multiple audio playing at the same time: stop any instance if audioContext that is currently running
     */
    if (audioContext.state === 'running') {
        return audioContext.close().then(function () {
            audioContext = new AudioContext();
        }).then(function () {
            audioContext.resume();
        });
    }
    else if (audioContext.state === 'closed') {
        audioContext = new AudioContext();
        return audioContext.resume();
    }
    else {
        return audioContext.resume();
    }
};


/**
 * Plays a owner of the audio from begin point to end point
 * @param beginSec see below
 * @param endSec and beginMs : in seconds
 * @param onStartCallback callback to be called when the audio starts
 * @param onEndedCallback callback to be called when the audio finishes
 */
const playAudio = function ({beginSec = 'start', endSec = 'end', onStartCallback = null, onEndedCallback = null}) {
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
        audioContext.close().then(function () {
            if (typeof onEndedCallback === 'function') {
                onEndedCallback();
            }
        }).catch(function (err) {
            logError(err);
            if (typeof onEndedCallback === 'function') {
                onEndedCallback();
            }
        });
    };
};


/**
 * Stop the audio if it is playing
 */
export const stopAudio = function () {
    if (!isNull(audioContext) && audioContext.state === 'running') {
        audioContext.close();
    }
};


/**
 * Convert audio data to audio buffer and then play
 * @param sig a Float32Array object
 * @param fs sampling rate
 * @param playAudioArgs arguments to provide for playAudio
 */
export const playAudioDataArray = function (sig, fs, playAudioArgs) {
    audioBuffer = audioContext.createBuffer(1, sig.length, fs);
    audioBuffer.getChannelData(0).set(sig);
    playAudio(playAudioArgs);
};


/**
 * Convert Float32Array into audio object
 * @param sig a Float32Array object
 * @param fs sampling rate
 * @return Blob audio blob
 */
export const createAudioFromDataArray = function (sig, fs) {
    audioBuffer = audioContext.createBuffer(1, sig.length, fs);
    audioBuffer.getChannelData(0).set(sig);
    let wav = bufferToWav(audioBuffer);
    return new window.Blob([new DataView(wav)], {type: 'audio/wav'});
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
export const queryAndHandleAudioGetOrPost = function ({url, cacheKey, formData, callback}) {
    const reader = new FileReader();
    let decodingFunction;
    if (url.endsWith('.wav')) {
        decodingFunction = function () {
            let data = reader.result;
            let decoder = new WAVDecoder();
            let decoded = decoder.decode(data);

            let sampleRate = decoded.sampleRate;
            let dataArrays = decoded.channels;

            if (cacheKey && !window.noCache) {
                cachedArrays[cacheKey] = [dataArrays, sampleRate];
            }
            callback(dataArrays, sampleRate);
        };
    }
    else {
        decodingFunction = function () {
            const arrayBuffer = reader.result;
            audioContext.decodeAudioData(arrayBuffer, function (_audioBuffer) {
                let fullAudioDataArray = _audioBuffer.getChannelData(0);
                let sampleRate = _audioBuffer.sampleRate;
                if (cacheKey && !window.noCache) {
                    cachedArrays[cacheKey] = [fullAudioDataArray, sampleRate];
                }
                callback([fullAudioDataArray], sampleRate);
            });
        };
    }

    reader.onload = decodingFunction;
    let method = isNull(formData) ? 'GET' : 'POST';

    const xhr = new XMLHttpRequest();
    xhr.open(method, url, true);

    let spinner = createSpinner();

    xhr.onloadstart = spinner.start;
    xhr.onloadend = spinner.clear;

    // We expect the response to be audio/mp4 when success, and text when failure.
    // So we need this to change the response type accordingly
    xhr.onreadystatechange = function () {
        // When request finishes, handle success/failure according to the status
        if (this.readyState == 4) {
            if (this.status == 200) {
                if (url.endsWith('.wav')) {
                    reader.readAsBinaryString(this.response);
                }
                else {
                    reader.readAsArrayBuffer(this.response);
                }

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
const queryAndHandleAudio = function ({url, cacheKey, postData}, callback) {
    let cached = cachedArrays[cacheKey];
    if (cacheKey && cached) {
        callback(cached[0], cached[1]);
    }
    else {
        let formData, fileId;
        if (!isNull(postData)) {
            fileId = postData['file-id'];
            formData = convertToFormData(postData);
        }
        if (fileId) {
            let onSuccess = function (fileUrl) {
                queryAndHandleAudioGetOrPost({
                    url: fileUrl,
                    cacheKey,
                    callback
                });
            };
            postRequest({
                requestSlug: 'koe/get-audio-file-url',
                data: postData,
                onSuccess,
                immediate: true,
            });
        }
        else {
            queryAndHandleAudioGetOrPost({
                url,
                cacheKey,
                callback,
                formData
            });
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
    resumeAudioContext().then(function () {
        queryAndHandleAudio(args, function (sig, fs) {
            playAudioDataArray(sig, fs, playAudioArgs);
        });
    })

};

/**
 * Upload an audio file and extract its data for in-browser processing.
 * The audio might be too high frequency to be processed natively by the browser.
 * In such case, we'll fake the sample rate to be exactly the maximum supported
 * But we will also send the real sample rate back once the audio is sent to the server
 *
 * @param file a file Blob
 * @param reader A FileReader instance
 * @param onProgress callback onprogress
 * @param onAbort callback onabort
 * @param onError callback onerror
 * @param onLoadStart callback onloadstart
 * @param onLoad callback onload
 * @return Promise that resolves to {sig, fs}
 */
export const loadLocalAudioFile = function ({
    file, reader = new FileReader(), onProgress = noop, onAbort = noop, onError = noop, onLoadStart = noop,
    onLoad = noop
}) {
    return new Promise(function (resolve) {
        reader.onload = function (e) {
            onLoad(e);
            let data = reader.result;

            // We cannot use WebAudioAPI here because it will downsample high frequency audio
            // We must first find out if the sample rate is acceptable. If not, we fake it to be MAX_SAMPLE_RATE
            // And will send the real sample rate back to the server later
            let decoder = new WAVDecoder();
            let decoded = decoder.decode(data);

            let sampleRate = decoded.sampleRate;
            let dataArrays = decoded.channels;
            let realSampleRate = sampleRate;

            if (sampleRate > MAX_SAMPLE_RATE) {
                sampleRate = MAX_SAMPLE_RATE
            }
            resolve({
                dataArrays,
                sampleRate,
                realSampleRate
            });
        };
        reader.onprogress = onProgress;
        reader.onerror = onError;
        reader.onabort = onAbort;
        reader.onloadstart = onLoadStart;

        reader.readAsBinaryString(file);
    });
};


/**
 * Load an existing song into view by ID & pretend it is a raw audio
 * @param songId
 * @returns {Promise}
 */
export const loadSongById = function () {
    let songId = this.predefinedSongId;
    let data = {'file-id': songId};

    return new Promise(function (resolve) {
        postRequest({
            requestSlug: 'koe/get-audio-file-url',
            data,
            immediate: true,
            onSuccess(songData) {
                let fileUrl = songData.url;
                let realFs = songData['real-fs'];

                let urlParts = fileUrl.split('/');
                let filename = urlParts[urlParts.length - 1];
                queryAndHandleAudioGetOrPost({
                    url: fileUrl,
                    cacheKey: songId,
                    callback(sig, sampleRate) {
                        // The sampleRate the browser reads from this file might be faked.
                        // So we must provide the real fs
                        resolve({dataArrays: sig, realFs, sampleRate, filename});
                    }
                });
            }
        });
    });
};
