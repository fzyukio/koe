import {isNull, debug} from './utils';

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
 * @param beginMs see below
 * @param endSecond and beginMs : in millisecond
 * @param callback
 */
const playAudio = function (beginMs = 'start', endSecond = 'end', callback = null) {
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

    if (beginMs === 'start') {
        beginMs = 0
    }

    if (endSecond === 'end') {
        endSecond = audioBuffer.duration;
    }

    // For more information, read up AudioBufferSourceNode.start([when][, offset][, duration])
    source.start(0, beginMs, endSecond - beginMs);
    source.onended = function () {
        audioContext.close();
        if (typeof callback === 'function') {
            callback();
        }
    };
};

/**
 * Convert audio data to audio bugger and then play
 * @param fullAudioDataArray a Float32Array object
 * @param sampleRate sampling rate
 * @param startSecond playback starts at
 * @param endSecond playback ends at
 */
const playAudioDataArray = function (fullAudioDataArray, sampleRate, startSecond = 'start', endSecond = 'end') {
    audioBuffer = audioContext.createBuffer(1, fullAudioDataArray.length, sampleRate);
    audioBuffer.getChannelData(0).set(fullAudioDataArray);
    playAudio(startSecond, endSecond);
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
        const reader = new FileReader();
        reader.onload = function () {
            const arrayBuffer = reader.result;
            audioContext.decodeAudioData(arrayBuffer, function (_audioBuffer) {
                let fullAudioDataArray = _audioBuffer.getChannelData(0);
                let sampleRate = _audioBuffer.sampleRate;
                if (cacheKey) {
                    cachedArrays[cacheKey] = [fullAudioDataArray, sampleRate];
                }
                callback(fullAudioDataArray, sampleRate);
            });
        };

        const xhr = new XMLHttpRequest();
        let method = isNull(postData) ? 'GET' : 'POST';

        xhr.open(method, url, true);
        xhr.responseType = 'blob';

        xhr.onload = function () {
            if (this.status == 200) {
                reader.readAsArrayBuffer(new Blob([this.response]));
            }
        };
        xhr.onloadend = function () {
            $.event.trigger('ajaxStop');
        };
        $.event.trigger('ajaxStart');
        xhr.send(postData);
    }
};

/**
 * Shortcut to download, cache a song/segment and them play for the specified segment
 * @param url POST url
 * @param postData POST data that contains the id of the song/segment to be downloaded
 * @param cacheKey key to persist this song/segment in the cache
 * @param startSecond playback starts at
 * @param endSecond playback ends at
 */
export const queryAndPlayAudio = function ({url, postData, cacheKey, startSecond, endSecond}) {
    let args = {
        url: url, cacheKey:cacheKey, postData:postData
    };
    queryAndHandleAudio(args, function(sig, fs) {
        playAudioDataArray(sig, fs, startSecond, endSecond);
    });
};

/**
 * Shortcut to download, cache a song from URL, and them play for the specified segment
 * @param url downloadable URL
 * @param startSecond playback starts at
 * @param endSecond playback ends at
 */
export const playAudioFromUrl = function ({url, startSecond, endSecond}) {
    let args = {
        url: url,
        cacheKey:url,
        postData:null
    };
    queryAndHandleAudio(args, function(sig, fs) {
        playAudioDataArray(sig, fs, startSecond, endSecond);
    });
};
