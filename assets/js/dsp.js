/**
 * Calculate spectrogram from raw data
 * @param sig
 * @param segs
 * @param fft
 * @param fftComplexArray
 * @param window
 */
export const calcSpect = function (sig, segs, fft, fftComplexArray, window, windowed) {
    const nfft = segs[0][1] - segs[0][0];
    const nframes = segs.length;
    const spect = [];
    let fbeg, fend, i, j;

    const log = Math.log10;

    for (i = 0; i < nframes; i++) {
        fbeg = segs[i][0];
        fend = segs[i][1];
        const slice = sig.slice(fbeg, fend);
        for (j = 0; j < nfft; j++) {
            windowed[j] = slice[j] * window[j];
        }

        fft.realTransform(fftComplexArray, windowed);

        const frameFTArr = [];

        /*
         * fft.realTransform returns only half the spectrum, but the array frameFT is always 2*nfft elements,
         * so the second half is rubbish. In addition, a 'Complex Array' is basically a normal array with odd elements
         * being the real and even element being the complex part. So the array is 4 times as large as the actual one-sided
         * spectrum. The power density spectra is calculated as 10*log10(real^2 + complex^2), or 10*log10(even^2 + odd^2)
         */
        for (j = 0; j < fftComplexArray.length / 4; j++) {
            frameFTArr.push(10 * log(fftComplexArray[2 * j] * fftComplexArray[2 * j] + fftComplexArray[2 * j + 1] * fftComplexArray[2 * j + 1]));
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
