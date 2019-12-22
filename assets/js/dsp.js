const log = Math.log10;
const sqrt = Math.sqrt;

export const POST_PROCESS_PSD = (x) => 10 * log(x);

export const POST_PROCESS_NOOP = (x) => x;

/**
 * Calculate spectrogram from raw data
 * @param sig
 * @param segs
 * @param fft
 * @param fftComplexArray
 * @param window
 */
export const calcSpect = function (sig, segs, fft, fftComplexArray, window, windowed, postProcessFunc = POST_PROCESS_PSD) {
    const nfft = segs[0][1] - segs[0][0];
    const nframes = segs.length;
    const spect = [];
    let fbeg, fend, i, j;

    for (i = 0; i < nframes; i++) {
        fbeg = segs[i][0];
        fend = segs[i][1];
        const slice = sig.slice(fbeg, fend);
        for (j = 0; j < nfft; j++) {
            windowed[j] = slice[j] * window[j];
        }

        fft.realTransform(fftComplexArray, windowed);

        const frameFTArr = [];
        let real, imag, absValue;

        /*
         * fft.realTransform returns only half the spectrum, but the array frameFT is always 2*nfft elements,
         * so the second half is rubbish. In addition, a 'Complex Array' is basically a normal array with odd elements
         * being the real and even element being the complex part. So the array is 4 times as large as the actual one-sided
         * spectrum.
         */
        for (j = 0; j < fftComplexArray.length / 4 + 1; j++) {
            real = fftComplexArray[2 * j];
            imag = fftComplexArray[2 * j + 1];
            absValue = sqrt(real * real + imag * imag);
            frameFTArr.push(postProcessFunc(absValue));
        }
        spect.push(frameFTArr);
    }

    return spect;
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
