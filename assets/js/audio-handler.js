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
 */
export const playAudio = function (beginMs = 'start', endSecond = 'end', callback = null) {
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


const playAudioDataArray = function (fullAudioDataArray, sampleRate, startSecond = 'start', endSecond = 'end') {
    audioBuffer = audioContext.createBuffer(1, fullAudioDataArray.length, sampleRate);
    audioBuffer.getChannelData(0).set(fullAudioDataArray);
    playAudio(startSecond, endSecond);
};


export const queryAndPlayAudio = function (url, postData, cacheKey) {
    let cached = cachedArrays[cacheKey];
    if (cacheKey && cached) {
        playAudioDataArray(cached[0], cached[1]);
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
                debug(`Playing at sampleRate: ${sampleRate}`);
                playAudioDataArray(fullAudioDataArray, sampleRate);
            });
        };

        const xhr = new XMLHttpRequest();
        xhr.open('POST', url, true);
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
        xhr.send(postData)
    }
};

export const playAudioFromUrl = function (url, startSecond, endSecond) {
    let cached = cachedArrays[url];
    if (url && cached) {
        playAudioDataArray(cached[0], cached[1], startSecond, endSecond);
    }
    else {
        const reader = new FileReader();
        reader.onload = function () {
            const arrayBuffer = reader.result;
            audioContext.decodeAudioData(arrayBuffer, function (_audioBuffer) {
                let fullAudioDataArray = _audioBuffer.getChannelData(0);
                let sampleRate = _audioBuffer.sampleRate;
                if (url) {
                    cachedArrays[url] = [fullAudioDataArray, sampleRate];
                }
                debug(`Playing at sampleRate: ${sampleRate}`);
                playAudioDataArray(fullAudioDataArray, sampleRate, startSecond, endSecond);
            });
        };

        const xhr = new XMLHttpRequest();
        xhr.open('GET', url, true);
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
        xhr.send();
    }
};
