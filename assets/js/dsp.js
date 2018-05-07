const d3 = require('d3');
const FFT = require('fft.js');
import {defaultCm} from './colour-map';

/**
 * Calculate spectrogram from raw data
 * @param sig
 * @param segs
 */
export const spectrogram = function (sig, segs) {
    const nfft = segs[0][1] - segs[0][0];
    const fft = new FFT(nfft);
    const nframes = segs.length;
    const spect = [];
    let fbeg, fend, i, j;
    const window = new Float32Array(nfft);
    const windowed = new Float32Array(nfft);
    const cos = Math.cos;
    const PI = Math.PI;
    const log = Math.log10;

    /*
     * This is Hann window
     */
    for (i = 0; i < nfft; i++) {
        window[i] = 0.5 * (1 - cos(PI * 2 * i / (nfft - 1)));
    }

    /*
     * FFT each frame and accumulate the result
     */
    const frameFT = fft.createComplexArray();

    for (i = 0; i < nframes; i++) {
        fbeg = segs[i][0];
        fend = segs[i][1];
        const slice = sig.slice(fbeg, fend);
        for (j = 0; j < nfft; j++) {
            windowed[j] = slice[j] * window[j];
        }

        fft.realTransform(frameFT, windowed);

        const frameFTArr = [];

        /*
         * fft.realTransform returns only half the spectrum, but the array frameFT is always 2*nfft elements,
         * so the second half is rubbish. In addition, a 'Complex Array' is basically a normal array with odd elements
         * being the real and even element being the complex part. So the array is 4 times as large as the actual one-sided
         * spectrum. The power density spectra is calculated as 10*log10(real^2 + complex^2), or 10*log10(even^2 + odd^2)
         */
        for (j = 0; j < frameFT.length / 4; j++) {
            frameFTArr.push(10 * log(frameFT[2 * j] * frameFT[2 * j] + frameFT[2 * j + 1] * frameFT[2 * j + 1]));
        }
        spect.push(frameFTArr);
    }

    return spect;
};

const globalMinSpectPixel = -139;
const globalMaxSpectPixel = 43;
const interval64 = (globalMaxSpectPixel - globalMinSpectPixel) / 63;
const round = Math.round;

/**
 * Convert a given a spectrogram (power spectral density 2D array), put it on the canvas
 * @param spect a 2D FloatArray
 * @param imgData the imageData of the canvas to be written to
 */
export const spectToCanvas = function (spect, imgData) {

    /*
     * Some checking: spect and canvas must have the same size
     */
    let height = spect.length;
    let width = spect[0].length;

    if (height != imgData.height || width != imgData.width) throw new Error('Spect and canvas must have the same size');

    const spectrumFlatened = spect.reduce(function (p, c) {
        return p.concat(c);
    });

    // fill imgData with colors from array
    let i,
        k = 0,
        psd, colourMapIndex;
    for (i = 0; i < spectrumFlatened.length; i++) {
        psd = spectrumFlatened[i];
        colourMapIndex = round((psd - globalMinSpectPixel) / interval64);
        if (defaultCm[colourMapIndex] === undefined) {
            colourMapIndex = 0;
        }
        imgData.data[k++] = defaultCm[colourMapIndex][0] * 255;
        imgData.data[k++] = defaultCm[colourMapIndex][1] * 255;
        imgData.data[k++] = defaultCm[colourMapIndex][2] * 255;

        // Alpha channel
        imgData.data[k++] = 255;
    }
};

export const transposeFlipUD = function (arr) {
    let newArray = [],
        origArrayLength = arr.length,
        arrayLength = arr[0].length,
        i;
    for (i = 0; i < arrayLength; i++) {
        newArray.push([]);
    }

    for (i = 0; i < origArrayLength; i++) {
        for (let j = 0; j < arrayLength; j++) {
            newArray[j].push(arr[i][arrayLength - 1 - j]);
        }
    }
    return newArray;
};

export const maxIgnoreNaN = function (arr) {
    return d3.max(arr.filter(function (val) {
        return isFinite(val);
    }));
};

export const minIgnoreNaN = function (arr) {
    return d3.min(arr.filter(function (val) {
        return isFinite(val);
    }));
};