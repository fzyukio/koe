/*
 * Some colormap
 */
const colourMap = {
    custom: [
        [255, 255, 255],
        [255, 255, 255],
        [255, 255, 255],
        [255, 255, 255],
        [255, 255, 255],
        [255, 255, 255],
        [255, 255, 255],
        [232, 246, 231],
        [232, 246, 231],
        [232, 246, 231],
        [232, 246, 231],
        [232, 246, 231],
        [232, 246, 231],
        [232, 246, 231],
        [209, 236, 206],
        [209, 236, 206],
        [209, 236, 206],
        [209, 236, 206],
        [209, 236, 206],
        [209, 236, 206],
        [209, 236, 206],
        [186, 227, 182],
        [186, 227, 182],
        [186, 227, 182],
        [186, 227, 182],
        [186, 227, 182],
        [186, 227, 182],
        [186, 227, 182],
        [149, 211, 148],
        [149, 211, 148],
        [149, 211, 148],
        [149, 211, 148],
        [149, 211, 148],
        [149, 211, 148],
        [149, 211, 148],
        [113, 196, 114],
        [113, 196, 114],
        [113, 196, 114],
        [113, 196, 114],
        [113, 196, 114],
        [113, 196, 114],
        [113, 196, 114],
        [43, 166, 85],
        [43, 166, 85],
        [43, 166, 85],
        [43, 166, 85],
        [43, 166, 85],
        [43, 166, 85],
        [43, 166, 85],
        [0, 110, 39],
        [0, 110, 39],
        [0, 110, 39],
        [0, 110, 39],
        [0, 110, 39],
        [0, 110, 39],
        [0, 110, 39],
        [0, 55, 20],
        [0, 55, 20],
        [0, 55, 20],
        [0, 55, 20],
        [0, 55, 20],
        [0, 55, 20],
        [0, 55, 20],
        [0, 55, 20],
    ]
};

/**
 * Convert a colour map array into 3 channels R,G,B for faster assignment
 * @param cm the colour map
 * @returns {{rPixelValues: Uint8ClampedArray, gPixelValues: Uint8ClampedArray, bPixelValues: Uint8ClampedArray}}
 */
const convertColourMap = function(cm) {
    let nLevels = cm.length;
    let rPixelValues = new Uint8ClampedArray(nLevels);
    let gPixelValues = new Uint8ClampedArray(nLevels);
    let bPixelValues = new Uint8ClampedArray(nLevels);
    let p;
    for (let i = 0; i < nLevels; i++) {
        p = cm[i];
        rPixelValues[i] = p[0];
        gPixelValues[i] = p[1];
        bPixelValues[i] = p[2];
    }
    return {rPixelValues,
        gPixelValues,
        bPixelValues};
};

export const defaultCm = convertColourMap(colourMap.custom);
