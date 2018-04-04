const base64 = require('base64-arraybuffer/lib/base64-arraybuffer.js');
import * as utils from './utils';

/**
 * Decode numpy's array as base64 to typed array
 * @param base64Encoded
 * @param reshape if true the array will be reshaped from 1d to 2d (if applicable)
 */
export const decodeArray = function (base64Encoded, reshape = false) {
    let separatorIdx = base64Encoded.indexOf('::');
    let shapeInfo = base64Encoded.substr(0, separatorIdx);
    let data = base64Encoded.substr(separatorIdx + 2);

    let shapeRegex = /(uint8|uint16|uint32|int8|int16|int32|float32|float64)\((\d+)\s*,\s*(\d*)\)/g;
    let matched = shapeRegex.exec(shapeInfo);
    let arrayType = matched[1];
    let nRows = matched[2];
    let nCols = 0;
    if (matched.length === 4) {
        nCols = matched[3];
    }

    let arrayTypes = {
        'int8': Int8Array,
        'int16': Int16Array,
        'int32': Int32Array,
        'uint8': Uint8Array,
        'uint16': Uint16Array,
        'uint32': Uint32Array,
        'float32': Float32Array,
        'float64': Float64Array
    };

    let array1d = new arrayTypes[arrayType](base64.decode(data));

    if (!reshape || nCols === 0) {
        return {'array': array1d,
            nRows,
            nCols};
    }

    let array2d = [];

    for (let i = 0; i < nRows; i++) {
        array2d.push(array1d.slice(i * nCols, (i + 1) * nCols));
    }

    return {'array': array2d,
        nRows,
        nCols};
};


/**
 * Extra argument to query f0 from the server (end points of the syllables as segmented)
 * @returns {*}
 */
const fetchF0Args = function () {
    let segments = utils.getCache('segments');

    if (segments !== undefined) {
        return {'x0s[]': segments.x0s,
            'x1s[]': segments.x1s,
            'y0s[]': segments.y0s,
            'y1s[]': segments.y1s};
    }
    return {'x0s[]': [0],
        'x1s[]': [1],
        'y0s[]': [0],
        'y1s[]': [1]};
};

/**
 * Extra argument to query f0 from the server
 * (currently not used but if is will return STFT arguments such as window size, noverlap, etcetera)
 * @returns {{}}
 */
const fetchFftArgs = function () {
    return {};
};


/**
 * Fetch the binary mask and draw it on the spectrogram (via callback)
 * @param retval
 * @param callback
 */
const handleBinaryMask = function (retval, callback) {
    let decoded = decodeArray(retval);
    let imgHeight = decoded.nRows;
    let imgWidth = decoded.nCols;
    let dfIndex = decoded.array;

    let canvas = document.createElement('canvas'),
        context = canvas.getContext('2d'),
        imgData = context.createImageData(imgWidth, imgHeight);

    canvas.height = imgHeight;
    canvas.width = imgWidth;

    let colourB = 0,
        colourG = 0,
        colourR = 0;

    let arrIdx = 0,
        colIdx = 0,
        imgIdx = 0,
        rowIdx = 0;

    for (let i = 0; i < dfIndex.length; i++) {

        /*
         * Python spectrogram is indexed from top left, while imgData is indexed from bottom left.
         * This part will convert top index to bottom index
         */
        arrIdx = dfIndex[i];
        rowIdx = Math.floor(arrIdx / imgWidth);
        colIdx = arrIdx % imgWidth;
        imgIdx = ((imgHeight - rowIdx - 1) * imgWidth + colIdx) * 4;

        imgData.data[imgIdx] = colourR;
        imgData.data[imgIdx + 1] = colourG;
        imgData.data[imgIdx + 2] = colourB;
        imgData.data[imgIdx + 3] = 255;
    }

    // put data to context at (0, 0)
    context.putImageData(imgData, 0, 0);

    // Display the points
    callback(canvas.toDataURL('image/png'));

};


/**
 * Fetch the binary mask and draw it on the spectrogram (via callback)
 * @param retval
 * @param callback
 */
const handlePolylines = function (retval, callback) {
    let polynomials = JSON.parse(retval);
    for (let i = 0; i < polynomials.length; i++) {
        let polynomial = polynomials[i];
        let data = [];

        let freqBeg = polynomial[0];
        let timeBeg = polynomial[1];
        let timeEnd = polynomial[2];

        let p0 = polynomial[4];
        let p1 = polynomial[5];
        let p2 = polynomial[6];
        let p3 = polynomial[7];

        let nSamples = 20;
        let xStep = (timeEnd - timeBeg) / nSamples;

        for (let j = 0; j < nSamples; j++) {
            data.push({
                x: timeBeg + j * xStep,
                y: (p0 * Math.pow(j, 3) + p1 * Math.pow(j, 2) + p2 * Math.pow(j, 1) + p3 + (1 - freqBeg))
            })
        }

        callback(data);
    }
};


/**
 * Draw the spectrogram
 * @param retval
 */
const fetchFft = function (retval) {
    let separatorIdx = retval.indexOf('::');
    let shapeInfo = retval.substr(0, separatorIdx);
    let data = retval.substr(separatorIdx + 2);

    let shapeRegex = /\((\d+)\s*,\s*(\d+)\)/g;
    let matched = shapeRegex.exec(shapeInfo);
    let nRows = matched[1];
    let nCols = matched[2];

    let array1d = new Float64Array(base64.decode(data));
    let array2d = [];

    for (let i = 0; i < nRows; i++) {
        array2d.push(array1d.slice(i * nCols, (i + 1) * nCols));
    }
};

/**
 *
 */
export const fetchSegments = function (fileId, segType, idPrefix, callback) {
    $.post(
        utils.getUrl('send-request', 'get-segments'),
        {'file-id': fileId,
            'seg-type': segType,
            'id-prefix': idPrefix},
        function (data) {
            if (data) {
                const segments = JSON.parse(data);

                let x0s = segments.x0s,
                    x1s = segments.x1s,
                    y0s = segments.y0s,
                    y1s = segments.y1s,
                    ids = segments.ids;
                let numSyls = x0s.length;
                let syllables = {};
                let rows = segments.rows;
                let segmentationId = segments['segmentation-id'];
                let scores = segments.scores;

                for (let i = 0; i < numSyls; i++) {
                    syllables[ids[i]] = {id: ids[i],
                        x0: x0s[i],
                        x1: x1s[i],
                        y0: y0s[i],
                        y1: y1s[i]};
                }
                callback({syllables,
                    rows,
                    segmentationId,
                    scores});
            }
        }
    );
};

/**
 * Lookup dictionary for the get-arguments functions
 * @type {*}
 */
export const fetchDataGetArgs = {
    'get-raw-f0': fetchF0Args,
    'get-cleaned-f0': fetchF0Args,
    'get-fft': fetchFftArgs
};

/**
 * Lookup dictionary for the send-request functions
 * @type {*}
 */
export const handleSpectralDataFunctions = {
    'get-raw-f0': handleBinaryMask,
    'get-cleaned-f0': handleBinaryMask,
    'get-dominant-frequency': handleBinaryMask,
    'get-binary-clipping-mask': handleBinaryMask,
    'get-polyfited-lines': handlePolylines,
    'get-fft': fetchFft
};
