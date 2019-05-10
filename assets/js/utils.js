/* eslint-disable no-unused-lets */
require('jquery-ui/ui/widgets/sortable');
require('bootstrap-datepicker');
require('jquery.browser');
require('jquery-getscrollbarwidth');
require('devtools-detect');

const JSZip = require('jszip/dist/jszip.min.js');
const filesaver = require('file-saver/dist/FileSaver.min.js');

/**
 * slick.editors uses only this part of jquery-ui. Do this instead of loading the whole library
 */
if ($.ui.keyCode === undefined) {
    $.ui.keyCode = {
        'BACKSPACE': 8,
        'COMMA': 188,
        'DELETE': 46,
        'DOWN': 40,
        'END': 35,
        'ENTER': 13,
        'ESCAPE': 27,
        'HOME': 36,
        'LEFT': 37,
        'PAGE_DOWN': 34,
        'PAGE_UP': 33,
        'PERIOD': 190,
        'RIGHT': 39,
        'SPACE': 32,
        'TAB': 9,
        'UP': 38
    };
}

export const debug = function (str) {
    if (window.PRINT_DEBUG) {

        // Get the origin of the call. To print out the devtool window for make it easy to jump right to the caller
        let stack = new Error().stack;

        // Why 2? The first line is always "Error", the second line is this debug function, the third is the caller.
        let where = stack.split('\n')[2];

        // eslint-disable-next-line
        console.log(`${str}\t\t\t${where}`);
    }
};


export const logError = function(err) {
    // eslint-disable-next-line
    console.log(err);
};

export const isNumber = function (str) {
    return !isNaN(str);
};


jQuery.fn.selectText = function () {
    let doc = document;
    let element = this[0];
    let range, selection;

    if (doc.body.createTextRange) {
        range = document.body.createTextRange();
        range.moveToElementText(element);
        range.select();
    }
    else if (window.getSelection) {
        selection = window.getSelection();
        range = document.createRange();
        range.selectNodeContents(element);
        selection.removeAllRanges();
        selection.addRange(range);
    }
};

/*
 * Prevent datepicker to conflick with jqueryui's datepicker
 * return $.fn.datepicker to previously assigned value and give it a new name
 */
let datepicker = $.fn.datepicker.noConflict();
$.fn.bootstrapDP = datepicker;


export const initDatePicker = function (jEl, defaultDate) {
    let defaultDateObject;

    if (defaultDate) {
        let defaultDateParts = defaultDate.split('-');
        defaultDate = {
            year: parseInt(defaultDateParts[0]),
            month: parseInt(defaultDateParts[1]) - 1,
            day: parseInt(defaultDateParts[2])
        };
        defaultDateObject = new Date(defaultDate.year, defaultDate.month, defaultDate.day)
    }

    jEl.bootstrapDP({
        format: 'dd/mm/yy',
        autoclose: true,
        forceParse: false,
        todayHighlight: true,
        todayBtn: true,
        ignoreReadonly: true,
        focusOnShow: false,
        templates: {
            leftArrow: '<i class="fa fa-arrow-circle-left"></i>',
            rightArrow: '<i class="fa fa-arrow-circle-right"></i>'
        }
    });

    if (defaultDate) {
        jEl.bootstrapDP('setDate', defaultDateObject);
        jEl.bootstrapDP('update');
    }
};


/**
 * Shuffles array in place. ES6 version
 * @param {Array} a items The array containing the items.
 */
export const shuffle = function (a) {
    for (let i = a.length; i; i--) {
        let j = Math.floor(Math.random() * i);
        [a[i - 1], a[j]] = [a[j], a[i - 1]];
    }
};

/**
 * Cookie helper
 * @param name
 * @returns {*}
 */
export const getCookie = function (name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        let cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            let cookie = jQuery.trim(cookies[i]);
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
};

export const getCache = function (cache, key = undefined) {
    if (isNull(key)) {
        return window.appCache[cache];
    }
    else {
        if (isNull(window.appCache[cache])) {
            return undefined;
        }
        return window.appCache[cache][key];
    }
};

export const setCache = function (cache, key, value) {
    if (key) {
        let _cache = window.appCache[cache];
        if (_cache) {
            if (value) {
                _cache[key] = value;
            }
            else {
                delete _cache[key];
            }
        }
        else if (value) {
            _cache = {};
            _cache[key] = value;
            window.appCache[cache] = _cache;
        }
    }
    else if (value) {
        window.appCache[cache] = value;
    }
    else {
        delete window.appCache[cache];
    }
};

/**
 * Return django static urls by their names.
 * @param name named url
 * @param arg parameter, if required
 * @return {string}
 */
export const getUrl = function (name, arg) {
    let url = getCache('urls', name);
    if (arg) {
        url = url.replace('arg', arg);
    }
    return url;
};


/**
 * Make a deep copy of an object
 * @param object
 */
export const deepCopy = function (object) {
    if (Array.isArray(object)) {
        return $.extend(true, [], object);
    }
    return $.extend(true, {}, object);
};

/**
 * Return GET request's parameter values
 * @param parameterName
 * @returns {*}
 */
export const findGetParameter = function (parameterName) {
    let result = null,
        tmp = [];
    let items = location.search.substr(1).split('&');
    for (let index = 0; index < items.length; index++) {
        tmp = items[index].split('=');
        if (tmp[0] === parameterName) result = decodeURIComponent(tmp[1]);
    }
    return result;
};


/**
 * Convert all caps, underscore separated to title case, space separated, e.g. "HELLO_WORLD" -> "Hello World"
 * @param allCaps
 */
export const capsToTitleCase = function (allCaps) {
    return allCaps.replace(/_/g, ' ').replace(/\w\S*/g, function (word) {
        return word.charAt(0).toUpperCase() + word.substr(1).toLowerCase();
    });
};


/**
 * Break a markdown URL down to url and text
 * @param rawUrl markdown URL
 */
export const convertRawUrl = function(rawUrl) {
    let matches = urlRegex.exec(rawUrl);
    let url;
    let val = rawUrl;
    if (matches) {
        url = matches[1];
        val = matches[2];
    }
    return {
        url,
        val
    };
};


/**
 * For embedded URL we're using Markdown's pattern, e.g. [http://www.example.com](example.com)
 * e.g. file_duration:(<3.5) (meaning that filter out any file that has duration > 3.5 sec)
 * @type {RegExp}
 */
const urlRegex = /\[(.*)]\((.*)\)/;


/**
 * A more consistent way to check for being null
 * @param val
 * @returns {boolean} true if is either undefined or null
 */
export const isNull = function (val) {
    return val === undefined || val === null;
};


export const getValue = function (obj, attr, def) {
    let val = obj[attr];
    if (val === undefined) {
        return def;
    }
    return val;
};


/**
 * A more consistent way to check for a string being empty
 * @param str
 * @returns {boolean} true if is either undefined or null or empty string
 */
export const isEmpty = function (str) {
    return str === undefined || str === null || str === '';
};


export const extractHeader = function (columns, permission, importKey) {
    let columnHeadings = [];
    for (let i = 0; i < columns.length; i++) {
        let column = columns[i];
        let columnVal = column.field;
        if (importKey !== undefined && columnVal === importKey) {
            columnHeadings.unshift(columnVal);
        }
        else if (column[permission]) {
            columnHeadings.push(columnVal)
        }
    }
    return columnHeadings;
};


/**
 * Convert grid data to a CSV string
 * @param grid a SlickGrid
 * @param downloadType if `all` will download everything,
 *                     otherwise download the visible data (after pagination & filter)
 * @returns {string} a comma separated CSV body of text, each line is one row.
 */
export const createCsv = function (grid, downloadType) {
    let dataView = grid.getData();
    let pagingInfo = dataView.getPagingInfo();
    let pageSize = pagingInfo.pageSize;
    let start = pageSize * (pagingInfo.pageNum);
    let end = start + (pageSize == 0 ? pagingInfo.totalRows : pageSize);
    let itemsForDownload = downloadType == 'all' ? dataView.getItems() : dataView.getFilteredItems().slice(start, end);

    let columns = grid.getColumns();
    let columnHeadings = extractHeader(columns, 'exportable');

    let rows = [];
    for (let i = 0; i < itemsForDownload.length; i++) {
        let row = [];
        let item = itemsForDownload[i];
        for (let j = 0; j < columns.length; j++) {
            let column = columns[j];
            let columnField = column.field;
            let exportable = column.exportable;
            if (exportable) {
                let fieldValue = item[columnField];
                row.push(`${fieldValue || ''}`);
            }
        }
        rows.push(row);
    }

    // Must enclose the column headings in quotes otherwise if the first column is `ID`, Excel
    // complains that the file type doesn't match
    // Also enclose everything in quote to avoid having strings with special characters in it
    let lineArray = [columnHeadings.map((x) => `"${x.replace(/"/g, '""')}"`).join(',')];
    rows.forEach(function (rowArray) {
        let line = [rowArray.map((x) => `"${x.replace(/"/g, '""')}"`)].join(',');
        lineArray.push(line);
    });

    return lineArray.join('\n');
};


/**
 * Facilitate downloading a blob as file
 * @param blob an instance of Blob
 * @param filename name with extension
 * @param aszip boolean, if true the content will be zipped
 */
export const downloadBlob = function (blob, filename, aszip) {
    if (aszip) {
        let zip = new JSZip();
        zip.file(filename, blob);

        zip.generateAsync({type: 'blob', compression: 'DEFLATE'}).then(function (content) {
            filesaver.saveAs(content, `${filename}.zip`);
        });
    }
    else if (navigator.msSaveBlob) {
        navigator.msSaveBlob(blob, filename);
    }
    else {
        let link = document.createElement('a');
        if (link.download !== undefined) {
            // Browsers that support HTML5 download attribute
            let url = URL.createObjectURL(blob);
            link.setAttribute('href', url);
            link.setAttribute('download', filename);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    }
};

/**
 * Calculate how many segments can be extracted from a signal given the window size and overlap size
 * @param signalLength length of the signal
 * @param windowSize window size (number of samples)
 * @param noverlap overlap size (number of samples)
 * @param includeTail true to always include the last segment (might be < window), false to exclude it if it's < window
 * @returns {Array} a two dimensional arrays. Each column is a pair of segments indices
 *
 * Example:
 *  segs = calcSegments(53, 10, 5)
 *   segs =
 *     1    10
 *     6    15
 *    11    20
 *    16    25
 *    21    30
 *    26    35
 *    31    40
 *    36    45
 *    41    50
 *    51    53
 */
export const calcSegments = function (signalLength, windowSize, noverlap, includeTail = false) {
    let step = windowSize - noverlap;
    let segs = [];
    let startIdx = 0;
    let endIdx = startIdx + windowSize;

    while (endIdx <= signalLength) {
        segs.push([startIdx, endIdx]);
        startIdx += step;
        endIdx += step;
    }

    if (includeTail && endIdx > signalLength && startIdx < signalLength) {
        segs.push([startIdx, signalLength]);
    }

    return segs;
};


const CHARS = '0123456789ABCDEF'.split('');
const FORMAT = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.split('');

/* eslint-disable no-bitwise */
/**
 * Generate a uuid4
 * @returns {string}
 */
export const uuid4 = function () {
    let c = CHARS;
    let id = FORMAT;
    let r;

    id[0] = c[(r = Math.random() * 0x100000000) & 0xf];
    id[1] = c[(r >>>= 4) & 0xf];
    id[2] = c[(r >>>= 4) & 0xf];
    id[3] = c[(r >>>= 4) & 0xf];
    id[4] = c[(r >>>= 4) & 0xf];
    id[5] = c[(r >>>= 4) & 0xf];
    id[6] = c[(r >>>= 4) & 0xf];
    id[7] = c[(r >>>= 4) & 0xf];

    id[9] = c[(r = Math.random() * 0x100000000) & 0xf];
    id[10] = c[(r >>>= 4) & 0xf];
    id[11] = c[(r >>>= 4) & 0xf];
    id[12] = c[(r >>>= 4) & 0xf];
    id[15] = c[(r >>>= 4) & 0xf];
    id[16] = c[(r >>>= 4) & 0xf];
    id[17] = c[(r >>>= 4) & 0xf];

    id[19] = c[(r = Math.random() * 0x100000000) & 0x3 | 0x8];
    id[20] = c[(r >>>= 4) & 0xf];
    id[21] = c[(r >>>= 4) & 0xf];
    id[22] = c[(r >>>= 4) & 0xf];
    id[24] = c[(r >>>= 4) & 0xf];
    id[25] = c[(r >>>= 4) & 0xf];
    id[26] = c[(r >>>= 4) & 0xf];
    id[27] = c[(r >>>= 4) & 0xf];

    id[28] = c[(r = Math.random() * 0x100000000) & 0xf];
    id[29] = c[(r >>>= 4) & 0xf];
    id[30] = c[(r >>>= 4) & 0xf];
    id[31] = c[(r >>>= 4) & 0xf];
    id[32] = c[(r >>>= 4) & 0xf];
    id[33] = c[(r >>>= 4) & 0xf];
    id[34] = c[(r >>>= 4) & 0xf];
    id[35] = c[(r >>>= 4) & 0xf];

    return id.join('');
};


/**
 * A do nothing function
 */
export const noop = function () {
    return undefined;
};


/**
 Smoothly scroll element to the given target (element.scrollLeft)
 for the given duration

 Returns a promise that's fulfilled when done, or rejected if
 interrupted
 */
export const smoothScrollTo = function (element, target, duration) {
    target = Math.round(target);
    duration = Math.round(duration);
    if (duration < 0) {
        return Promise.reject(new Error('bad duration'));
    }
    if (duration === 0) {
        element.scrollLeft = target;
        return Promise.resolve();
    }

    let startTime = Date.now();
    let endTime = startTime + duration;

    let start = element.scrollLeft;
    let distance = target - start;

    return new Promise(function (resolve, reject, onCancel) {
        // This is to keep track of where the element's scrollLeft is
        // supposed to be, based on what we're doing
        let previous = element.scrollLeft;
        let timeoutId;

        // This is like a think function from a game loop
        let scrollFrame = function () {
            if (element.scrollLeft != previous) {
                reject(new Error('interrupted'));
                return;
            }

            // set the scrollLeft for this frame
            let now = Date.now();
            let frameScrollPosition = Math.round(start + (distance * (now - startTime) / (endTime - startTime)));
            element.scrollLeft = frameScrollPosition;

            // check if we're done!
            if (now >= endTime) {
                resolve();
                return;
            }

            // If we were supposed to scroll but didn't, then we
            // probably hit the limit, so consider it done; not
            // interrupted.
            if (element.scrollLeft === previous &&
                element.scrollLeft !== frameScrollPosition) {
                resolve();
                return;
            }
            previous = element.scrollLeft;

            // schedule next frame for execution
            timeoutId = setTimeout(scrollFrame, 0);
        };

        // boostrap the animation process
        timeoutId = setTimeout(scrollFrame, 0);
        onCancel(() => clearTimeout(timeoutId));
    });
};


/**
 * Find index of the element with max value
 * @param arr
 * @returns {number}
 */
export const argmax = function(arr) {
    if (arr.length === 0) {
        return -1;
    }

    let max = arr[0];
    let maxIndex = 0;

    for (let i = 1; i < arr.length; i++) {
        if (arr[i] > max) {
            maxIndex = i;
            max = arr[i];
        }
    }

    return maxIndex;
};

/**
 * Sort an array ascendingly
 * @param arr
 */
export const sort = function (arr) {
    arr.sort(function (a, b) {
        return a - b;
    });
};

/**
 * Find median of an sorted array
 * @param arr
 */
export const median = function (arr) {
    if (arr.length === 0) return 0;
    let half = Math.floor(arr.length / 2);
    if (arr.length % 2) return arr[half];
    else return (arr[half - 1] + arr[half]) / 2.0;
};


export const getGetParams = function() {
    let args = window.location.search.substr(1);
    let argDict = {};
    $.each(args.split('&'), function(idx, arg) {
        if (arg !== '') {
            let argPart = arg.split('=');
            argDict[argPart[0]] = argPart[1];
        }
    });

    return argDict;
};

export const showAlert = function (alertEl, message, delay = 5000, errorId = undefined) {
    alertEl.find('.message').html(message);
    if (errorId) {
        alertEl.find('.link').attr('error-id', errorId);
        alertEl.find('.report').show();
    }
    else {
        alertEl.find('.report').hide();
    }

    let timerId = alertEl.attr('timer-id');
    if (timerId) {
        clearTimeout(timerId);
    }

    let promise;
    if (delay >= 0) {

        promise = new Promise(function (resolve) {
            timerId = setTimeout(function () {
                alertEl.fadeOut(500, resolve);
            }, delay);
        });

        alertEl.attr('timer-id', timerId);
        alertEl.fadeIn();
    }
    else {
        alertEl.fadeIn();
        promise = Promise.resolve();
    }

    return promise
};


/**
 * Create a range array and then shuffle it randomly.
 * @returns {[*]}
 */
export const randomRange = function (limit) {
    let array = [...Array(limit).keys()];
    shuffle(array);
    return array
};


export const createTable = function($table, columns, rows, firstColBold) {
    if ($table === undefined || $table.length === 0) {
        $table = $('<table></table>');
        $table.addClass('table table-bordered table-condensed table-striped table-hover');
    }

    let $thead = $('<thead></thead>');
    let $tr = $('<tr></tr>');

    $.each(columns, function(idx, column) {
        let $th = `<th>${column}</th>`;
        $tr.append($th);
    });

    $thead.append($tr);
    $table.append($thead);

    let tdsTemplate = columns.map(() => '<td></td>');
    if (firstColBold) {
        tdsTemplate[0] = '<th scope="row"></th>';
    }

    let $tbody = $('<tbody></tbody>');
    $.each(rows, function(i, row) {
        $tr = $('<tr></tr>');
        let tds = deepCopy(tdsTemplate);
        for (let j = 0; j < columns.length; j++) {
            let $td = $(tds[j]).html(row[j]);
            $tr.append($td);
        }
        $tbody.append($tr);
    });

    $table.append($tbody);

    return $table;
};


/**
 * Pad number with leading character, e.g. 1 => '0001'
 * @param num integer number
 * @param size number of digits including the number, e.g. size of '000123' is 6
 * @param char the character to pad, default to 0
 * @returns {string}
 */
export const pad = function(num, size, char = '0') {
    let s = String(num);
    while (s.length < size) s = char + s;
    return s;
};

/**
 * Date to string format yyyy-mm-dd_hh-mm-ss
 * @param date
 * @returns {string}
 */
export function toJSONLocal (date) {
    let local = new Date(date);
    local.setMinutes(date.getMinutes() - date.getTimezoneOffset());
    let formatted = local.toJSON();
    let dateStr = formatted.slice(0, 10);
    let timeStr = formatted.slice(11, 19).replace(/:/g, '-');
    return `${dateStr}_${timeStr}`;
}

/**
 * Convenient function to ensure same event is attached once to the same event-type of the same element
 * @param element a Jquery element
 * @param eventType e.g. 'click', etc...
 * @param func the function
 * @param funcName name of the function, must given if function is anonymous. Otherwise func.name will be used
 */
export function attachEventOnce({element, eventType, func, funcName}) {
    if (isNull(funcName)) {
        funcName = func.name;
        if (isNull(funcName)) {
            throw Error('Function name must be provided for anonymous function')
        }
    }

    let key = `attached-${eventType}-${funcName}`;
    if (element.attr(key) === undefined) {
        element.on(eventType, func)
    }
}
