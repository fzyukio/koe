import {colourMaps} from './colour-map';

export const globalMinSpectPixel = -139;
export const globalMaxSpectPixel = 43;

/**
 * Convert a given a spectrogram (power spectral density 2D array), put it on the canvas
 * @param spect a 2D FloatArray
 * @param imgData the imageData of the canvas to be written to
 * @param dspMin
 * @param dspMax
 * @param contrast
 * @param colourMap
 */
const spectToCanvas = function (spect, imgData, dspMin, dspMax, contrast = 0, colourMap = 'Green') {
    const {rPixelValues, gPixelValues, bPixelValues} = colourMaps[colourMap];

    /*
     * Some checking: spect and canvas must have the same size
     */
    let height = spect.length;
    let width = spect[0].length;

    if (height != imgData.height || width != imgData.width) throw new Error('Spect and canvas must have the same size');

    const colouredInterval = 64;
    const nIntervals = colouredInterval + contrast - 1;

    const dspBinValue = (dspMax - dspMin) / (nIntervals - 1);
    const round = Math.round;

    const spectrumFlatened = spect.reduce(function (p, c) {
        return p.concat(c);
    });

    // fill imgData with colors from array
    let i,
        k = 0,
        psd, colourMapIndex;
    for (i = 0; i < spectrumFlatened.length; i++) {
        psd = spectrumFlatened[i];
        if (isNaN(psd)) {
            colourMapIndex = 0;
        }
        else {
            colourMapIndex = round(Math.max(0, psd - dspMin) / dspBinValue) - contrast;
            if (colourMapIndex < 0) colourMapIndex = 0;
        }
        imgData.data[k++] = rPixelValues[colourMapIndex];
        imgData.data[k++] = gPixelValues[colourMapIndex];
        imgData.data[k++] = bPixelValues[colourMapIndex];

        // Alpha channel
        imgData.data[k++] = 255;
    }
};


/**
 * Converts segment of a signal into spectrogram and displays it.
 * Keep in mind that the spectrogram's SVG contaims multiple images next to each other.
 * This function should be called multiple times to generate the full spectrogram
 * @param spect
 * @param imgHeight
 * @param subImgWidth
 * @param contrast
 * @param colourMap
 * @param dspMin
 * @param dspMax
 */
export const spectToUri = function(spect, imgHeight, subImgWidth, contrast, colourMap, dspMin, dspMax) {
    return new Promise(function (resolve) {
        let img = new Image();
        img.onload = function () {
            let canvas = document.createElement('canvas');
            let context = canvas.getContext('2d');
            let imgData = context.createImageData(subImgWidth, imgHeight);

            canvas.height = imgHeight;
            canvas.width = subImgWidth;

            spectToCanvas(spect, imgData, dspMin, dspMax, contrast, colourMap);
            context.putImageData(imgData, 0, 0);
            resolve(canvas.toDataURL('image/webp', 1));
        };

        // This data URI is a dummy one, use it to trigger onload()
        img.src = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z/C/HgAGgwJ/lK3Q6wAAAABJRU5ErkJggg==';
    });
};
