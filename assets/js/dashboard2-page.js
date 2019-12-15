require('jqwidgets-scripts/jqwidgets/jqxcore.js');
require('jqwidgets-scripts/jqwidgets/jqxsplitter.js');

let ce;

export const run = function (commonElements) {
    ce = commonElements;
    $('#mainSplitter').jqxSplitter({
        width: 850,
        height: 850,
        orientation: 'horizontal',
        panels: [{size: 300, collapsible: false}]
    });
    // $('#firstNested').jqxSplitter({
    //     width: '100%',
    //     height: '100%',
    //     orientation: 'vertical',
    //     panels: [{size: 300, collapsible: false}]
    // });
    // $('#secondNested').jqxSplitter({width: '100%', height: '100%', orientation: 'horizontal', panels: [{size: 150}]});
    // $('#thirdNested').jqxSplitter({
    //     width: '100%',
    //     height: '100%',
    //     orientation: 'horizontal',
    //     panels: [{size: 150, collapsible: false}]
    // });
    return Promise.resolve();
};


export const postRun = function () {
    return Promise.resolve();
};

export const viewPortChangeHandler = function () {
};
