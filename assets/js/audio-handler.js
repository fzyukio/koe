const base64 = require('base64-arraybuffer/lib/base64-arraybuffer.js');
import * as utils from "utils";
import * as fd from "./fetch-data";

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
let bufferedUrl = null;
let fullAudioDataArray = null;

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
      alert("Your browser does not support any AudioContext and cannot play back this audio.");
      return;
    }
    window.AudioContext = window.webkitAudioContext;
  }

  audioContext = new AudioContext();
  audioContext.close();
};

/**
 * AJAX request an audio file
 *
 * @param fileId
 * @param callback
 */
export const getAudioAsArray = function (fileId, callback) {
  $.post(
    utils.getUrl('fetch-data', 'get-audio-signal'), {'file-id': fileId,},
    function (base64Encoded) {
      let separator_idx = base64Encoded.indexOf('::');
      let fs = parseInt(base64Encoded.substr(0, separator_idx));
      let base64_sig = base64Encoded.substr(separator_idx + 2);
      let sig = new Float32Array(base64.decode(base64_sig));

      audioBuffer = audioContext.createBuffer(1, sig.length, fs);
      audioBuffer.getChannelData(0).set(sig);

      callback(fileId, sig, fs);
    }
  );

};

/**
 * Plays a owner of the audio from begin point to end point
 * @param begin see below
 * @param end and begin : both normalised to the duration of the audio, to be in range [0-1]
 */
export const playAudio = function (begin, end, callback) {
  if (utils.isNull(audioContext) || audioContext.state === 'closed') {
    audioContext = new AudioContext();
  }
  /*
   * Prevent multiple audio playing at the same time: stop any instance if audioContext that is currently running
   */
  else if (!utils.isNull(audioContext) && audioContext.state === 'running') {
    audioContext.close();
    audioContext = new AudioContext();
  }
  let source = audioContext.createBufferSource();
  source.buffer = audioBuffer;

  source.playbackRate.value = playbackSpeed / 100.0;
  source.connect(audioContext.destination);

  // Convert to seconds then play
  let duration = audioBuffer.duration;
  let beginMs = begin * duration;
  let endMs = end * duration;
  // For more information, read up AudioBufferSourceNode.start([when][, offset][, duration])
  source.start(0, beginMs, endMs - beginMs);
  source.onended = function () {
    audioContext.close();
    if (typeof callback === 'function') {
      callback();
    }
  };
};


export const playRawAudio = function (encoded) {
  encoded = JSON.parse(encoded);
  let fs = encoded.fs;
  let sig = fd.decodeArray(encoded.data).array;

  audioBuffer = audioContext.createBuffer(1, sig.length, fs);
  audioBuffer.getChannelData(0).set(sig);

  playAudio(0, 1);
};

export const playAudioFromUrl = function (url, start, end, callback) {
  if (bufferedUrl === url) {
    playAudio(start, end, callback);
  }
  else {
    const reader = new FileReader();
    reader.onload = function () {
      const arrayBuffer = reader.result;
      audioContext.decodeAudioData(arrayBuffer, function (_audioBuffer) {
        bufferedUrl = url;
        fullAudioDataArray = _audioBuffer.getChannelData(0);
        audioBuffer = audioContext.createBuffer(1, fullAudioDataArray.length, _audioBuffer.sampleRate);
        audioBuffer.getChannelData(0).set(fullAudioDataArray);
        playAudio(start, end, callback);
      });
    };

    const xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.responseType = 'blob';

    xhr.onload = function (e) {
      if (this.status == 200) {
        reader.readAsArrayBuffer(new Blob([this.response]));
      }
    };

    xhr.send();
  }
};