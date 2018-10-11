/* eslint-disable no-unused-lets */
/* global Slick */
require('jquery-ui/ui/widgets/sortable');
require('slickgrid/lib/jquery.event.drag-2.3.0');
require('slickgrid/slick.core');
require('slickgrid/slick.grid');
require('slickgrid/slick.editors');
require('slickgrid/slick.formatters');
require('slickgrid/slick.dataview');
require('slickgrid/plugins/slick.rowmovemanager');
require('checkboxselectcolumn');
require('radioselectcolumn');
require('rowselectionmodel');
require('bootstrap-datepicker');
require('jquery.browser');
require('jquery-getscrollbarwidth');
require('devtools-detect');
import {hasActionsOfType, actionHandlers, isClickableOnRow, getHandlerOfActionType} from './property-actions';

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


export const editabilityAwareFormatter = function (row, cell, value, columnDef, item) {
    if (isNull(value)) {
        value = '';
    }
    else {
        value = (String(value)).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    let field = columnDef.field;

    let fieldEditability = '__' + field + '_editable';
    let columnEditable = columnDef.editable;
    let cellEditable = item[fieldEditability];
    if (isNull(cellEditable)) {
        cellEditable = columnEditable;
    }
    else {
        cellEditable = cellEditable && columnEditable;
    }

    let editability = cellEditable ? 'editable' : 'non-editable';

    if (!isNull(value)) {
        try {
            return `<div class='slick-inner-cell ${editability}'>${value}</div>`;
        }
        catch (e) {
            return value;
        }
    }
    return `<div class='slick-inner-cell ${editability}'></div>`;
};


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
    if (key) {
        if (isNull(window.appCache[cache])) {
            return undefined;
        }
        return window.appCache[cache][key];
    }
    else {
        return window.appCache[cache];
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
 * Plugin to Slick.Formatter: Format float values with two decimal points
 * @return {string}
 */
function DecimalPointFormatter(row, cell, value, columnDef, item) {
    if (!isNull(value)) {
        value = value.toFixed(this.numDecimal);
    }
    return editabilityAwareFormatter(row, cell, value, columnDef, item)
}


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
 * Display title cased label instead of integer value of the constants
 * @return {string}
 */
function SelectionFormatter(row, cell, value, columnDef, dataContext) {
    let options = columnDef.options;
    let intValue = parseInt(value);
    let label = options[intValue];
    if (label) {
        value = label;
    }
    return editabilityAwareFormatter(row, cell, value, columnDef, dataContext);
}

/**
 * Reimplement CheckmarkFormatter to use font icon instead of image for the check mark
 * @param row
 * @param cell
 * @param value
 * @param columnDef
 * @param dataContext
 * @returns {string}
 * @constructor
 */
const CheckmarkFormatter = function (row, cell, value, columnDef, dataContext) {
    value = value ? '<i class="fa fa-check"></i>' : '';
    return editabilityAwareFormatter(row, cell, value, columnDef, dataContext);
};


/**
 * @return {string}
 */
const ImageFormatter = function (row, cell, imgUrl) {
    return `<img src="${imgUrl}" height="100%"/>`;
};


/**
 * Render one or many images given the id or array of ids of the spectrograms
 * spetrogram images are located at /user_data/spect/fft/syllable/<ID>.png
 * @returns {string}
 * @constructor
 */
const SpectsFormatter = function (row, cell, value) {
    if (Array.isArray(value)) {
        let retval = '';
        $.each(value, function (idx, sid) {
            retval += `<img src="/user_data/spect/fft/syllable/${sid}.png" height="100%"/>`;
        });
        return retval;
    }
    return `<img src="/user_data/spect/fft/syllable/${value}.png" height="100%"/>`;
};


/**
 * @return {string}
 */
const RowMoveableFormatter = function () {
    return '<i class="fa fa-bars" aria-hidden="true"></i>';
};


/**
 * Break a markdown URL down to url and text
 * @param rawUrl markdown URL
 */
const convertRawUrl = function(rawUrl) {
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
 * Display text as clickable URL. The url is embedded in the cell value
 * @param row
 * @param cell
 * @param value
 * @param columnDef
 * @param dataContext
 * @returns {string}
 * @constructor
 */
const UrlFormatter = function (row, cell, value, columnDef, dataContext) {

    /*
     * Render the URL and reset the value field for searching purpose.
     * Store the url on an inner letiable to be reused later, e.g if the field is 'filename' then
     *  the letiable is _url_filename which will takes the value of the URL, and the letiable filename is set to the
     *  actual string value
     * Ideally we should keep it intact and the filter should be able to apply to the string part only
     */

    let fieldName = columnDef.field;
    let fieldUrl = '_url_' + fieldName;

    if (dataContext[fieldUrl]) {
        return `<a href="${dataContext[fieldUrl]}" target="_blank">${value}</a>`
    }

    let {url, val} = convertRawUrl(value);
    if (url) {
        dataContext[fieldUrl] = url;
        dataContext[fieldName] = val;
        return `<a href="${url}" target="_blank">${val}</a>`
    }
    return val;
};


/**
 * Show sequence of syllable nicely
 * @param row
 * @param cell
 * @param value
 * @param columnDef
 * @param song
 * @returns {string}
 * @constructor
 */
const SequenceFormatter = function (row, cell, value, columnDef, song) {
    let duration = song.duration;
    let segLabels = song['sequence-labels'];
    let segStarts = song['sequence-starts'];
    let segEnds = song['sequence-ends'];
    let sids = song['sequence-ids'];

    let retval = `<div class="syllable start full-audio" start=0 end=${duration}>
                  <i class="fa fa-play" aria-hidden="true"></i>
                </div>`;

    let nLabels = segLabels ? segLabels.length : 0;
    for (let i = 0; i < nLabels; i++) {
        let start = segStarts[i];
        let end = segEnds[i];
        let segLabel = segLabels[i];
        let sid = sids[i];
        retval += `<div class="syllable" start=${start} end=${end} imgsrc="/user_data/spect/fft/syllable/${sid}.png">${segLabel}</div>`;
    }

    retval += '<div class="syllable end"><i class="fa fa-stop"></i></div>';
    return retval;
};


/**
 * For embedded URL we're using Markdown's pattern, e.g. [http://www.example.com](example.com)
 * e.g. file_duration:(<3.5) (meaning that filter out any file that has duration > 3.5 sec)
 * @type {RegExp}
 */
const urlRegex = /\[(.*)]\((.*)\)/;

/*
 * Make a copy of Slick.Formater and then add new formatter
 */
const SlickFormatters = $.extend({}, Slick.Formatters);
SlickFormatters.DecimalPoint = DecimalPointFormatter.bind({numDecimal: 2});
SlickFormatters.Select = SelectionFormatter;
SlickFormatters.Checkmark = CheckmarkFormatter;
SlickFormatters.Image = ImageFormatter;
SlickFormatters.Spects = SpectsFormatter;
SlickFormatters.Url = UrlFormatter;
SlickFormatters.Sequence = SequenceFormatter;


const FloatEditorRewritten = function (args) {
    let $input;
    let defaultValue;

    this.init = function () {
        $input = $('<INPUT type="number" inputmode="numeric" step="0.01" class=\'editor-text\' />');

        $input.on('keydown.nav', function (e) {
            if (e.keyCode === $.ui.keyCode.LEFT || e.keyCode === $.ui.keyCode.RIGHT) {
                e.stopImmediatePropagation();
            }
        });

        $input.appendTo(args.container);
        $input.focus().select();
    };

    this.destroy = function () {
        $input.remove();
    };

    this.focus = function () {
        $input.focus();
    };

    /**
     * returns the number of fixed decimal places or null
     */
    function getDecimalPlaces() {
        let rtn = args.column.editorFixedDecimalPlaces;
        if (typeof rtn == 'undefined') {
            rtn = FloatEditorRewritten.DefaultDecimalPlaces;
        }
        return (!rtn && rtn !== 0 ? null : rtn);
    }

    this.loadValue = function (item) {
        defaultValue = item[args.column.field];

        let decPlaces = getDecimalPlaces();
        if (decPlaces !== null &&
            (defaultValue || defaultValue === 0) &&
            defaultValue.toFixed) {
            defaultValue = defaultValue.toFixed(decPlaces);
        }

        $input.val(defaultValue);
        $input[0].defaultValue = defaultValue;
        $input.select();
    };

    this.serializeValue = function () {
        let rtn = parseFloat($input.val());
        if (FloatEditorRewritten.AllowEmptyValue) {
            if (!rtn && rtn !== 0) {
                rtn = '';
            }
        }
        else if (isNull(rtn)) {
            rtn = 0;
        }

        let decPlaces = getDecimalPlaces();
        if (decPlaces !== null &&
            (rtn || rtn === 0) &&
            rtn.toFixed) {
            rtn = parseFloat(rtn.toFixed(decPlaces));
        }

        return rtn;
    };

    this.applyValue = function (item, state) {
        item[args.column.field] = state;
    };

    this.isValueChanged = function () {
        return (!($input.val() === '' && defaultValue === null)) && ($input.val() !== defaultValue);
    };

    this.validate = function () {
        if (isNaN($input.val())) {
            return {
                valid: false,
                msg: 'Please enter a valid number'
            };
        }

        if (args.column.validator) {
            let validationResults = args.column.validator($input.val());
            if (!validationResults.valid) {
                return validationResults;
            }
        }

        return {
            valid: true,
            msg: null
        };
    };

    this.init();
}

FloatEditorRewritten.DefaultDecimalPlaces = null;
FloatEditorRewritten.AllowEmptyValue = false;


/**
 * Rewrite this because the default DateEditor doesn't work very well with bootstrap.
 * Essentially we're replacing Jquery UI's datepicker by bootstrap-datepicker
 * @source: http://www.eyecon.ro/bootstrap-datepicker/
 * @readthedoc: https://bootstrap-datepicker.readthedocs.io/en/stable/options.html
 *
 * @constructor
 */
const DateEditorRewritten = function (args) {
    let inputElement;
    let defaultValue;
    let calendarOpen = false;

    this.init = function () {
        let defaultDate = args.item[args.column.field];

        inputElement = $('<input type="text" class="editor-text" value="' + defaultDate + '"/>');
        inputElement.appendTo(args.container);

        if (defaultDate) {
            let defaultDateParts = defaultDate.split('-');
            defaultDate = {
                year: parseInt(defaultDateParts[0]),
                month: parseInt(defaultDateParts[1]),
                day: parseInt(defaultDateParts[2])
            }
        }

        inputElement.bootstrapDP({
            format: 'yyyy-mm-dd',
            autoclose: true,
            todayHighlight: true,
            todayBtn: true,
            defaultViewDate: defaultDate,
            templates: {
                leftArrow: '<i class="fa fa-arrow-circle-left"></i>',
                rightArrow: '<i class="fa fa-arrow-circle-right"></i>'
            }
        });
        calendarOpen = true;
    };

    this.destroy = function () {
        inputElement.bootstrapDP('destroy');
        inputElement.remove();
        calendarOpen = false;
    };

    this.show = function () {
        if (!calendarOpen) {
            inputElement.bootstrapDP('show');
            calendarOpen = true;
        }
    };

    this.hide = function () {
        if (calendarOpen) {
            inputElement.bootstrapDP('hide');
            calendarOpen = false;
        }
    };

    this.focus = function () {
        inputElement.focus();
    };

    this.loadValue = function (item) {
        defaultValue = item[args.column.field];
        inputElement.val(defaultValue);
        inputElement[0].defaultValue = defaultValue;
        inputElement.select();
    };

    this.serializeValue = function () {
        return inputElement.val();
    };

    this.applyValue = function (item, state) {
        item[args.column.field] = state;
    };

    this.isValueChanged = function () {
        return (!(inputElement.val() === '' && isNull(defaultValue))) && (inputElement.val() !== defaultValue);
    };

    this.validate = function () {
        if (args.column.validator) {
            let validationResults = args.column.validator(inputElement.val());
            if (!validationResults.valid) {
                return validationResults;
            }
        }

        return {
            valid: true,
            msg: null
        };
    };

    this.init();
};

/**
 * Each filter has this pattern : param:(value),
 * e.g. file_duration:(<3.5) (meaning that filter out any file that has duration > 3.5 sec)
 * @type {RegExp}
 */
const filterRegex = /(.*?):(.*)+/;

/**
 * Accept anything that contain the substring
 * @param {string} string the whole string
 * @returns {boolean}
 *
 * @bind ({filterValue}) the substring to be contained
 */
const stringFilter = function (string) {
    if (this.filterValue === null) {
        return true;
    }
    return this.filterValue.exec(string);
};

/**
 * Match against a predefined regex pattern
 * @param {string} string the whole string
 * @returns {boolean}
 *
 * @bind ({filterValue}) the regex pattern to be match against
 */
const regexFilter = function (string) {
    try {
        return string.match(this.filterValue);
    }
    catch (e) {
        return false;
    }
};

/**
 * Check if value is the same as the bounded value
 * @param {boolean} value
 * @returns {boolean}
 *
 * @bind ({filterValue}) boolean
 */
const booleanFilter = function (value) {
    value = value == true;
    return value === this.filterValue;
};


const filterFunctions = {
    'String': stringFilter,
    'Boolean': booleanFilter,
    'Regex': regexFilter
};


const arithmeticOperator = {
    '<'(x) {
        return x < this.filterValue;
    },
    '<='(x) {
        return x <= this.filterValue;
    },
    '='(x) {
        return x == this.filterValue;
    },
    '=='(x) {
        return x == this.filterValue;
    },
    '>'(x) {
        return x > this.filterValue;
    },
    '>='(x) {
        return x >= this.filterValue;
    },
    '..'(x) {
        return x > this.lower && x < this.upper;
    },
    '++'(x) {
        return x >= this.lower && x <= this.upper;
    },
    'in'(x) {
        return this.array.indexOf(x) != -1
    },
};


/**
 * Utility to return an appropriate filter
 * @param paramName name of the param
 * @param type
 * @param filterContent
 */
const filterGenerator = function (paramName, type, filterContent) {
    let filterFunction = filterFunctions[type];
    let binding = null;
    if (filterContent === '') {
        filterContent = null;
        binding = {filterValue: filterContent};
    }
    else if (type === 'String') {
        try {
            filterContent = new RegExp(filterContent, 'i');
        }
        catch (e) {
            filterContent = null;
        }
        binding = {filterValue: filterContent};
    }
    else if (type === 'Boolean') {
        filterContent = (filterContent == 'true');
        binding = {filterValue: filterContent};
    }
    else if (type === 'Number') {

        let char0 = filterContent.substring(0, 1);
        let char1 = filterContent.substring(1, 2);
        let char01 = filterContent.substring(0, 2);

        if (char1 === '=') {
            let remaining = filterContent.substring(2);
            let filterValue = parseFloat(remaining);

            filterFunction = arithmeticOperator[char01];
            binding = {filterValue};
        }
        else if (char0 === '<' || char0 === '>' || char0 === '=') {
            let remaining = filterContent.substring(1);
            let filterValue = parseFloat(remaining);

            filterFunction = arithmeticOperator[char0];
            binding = {filterValue};

        }
        else if (char0 === '[') {
            let remaining = filterContent.substring(1, filterContent.length - 1);
            let array = remaining.split(',').map(function (item) {
                return parseFloat(item);
            });
            filterFunction = arithmeticOperator.in;
            binding = {array};
        }
        else if (isNumber(filterContent)) {
            filterFunction = arithmeticOperator['='];
            binding = {filterValue: parseFloat(filterContent)};
        }
        else {
            let rangeOperators = ['..', '++'];
            for (let i = 0; i < rangeOperators.length; i++) {
                let rangeOperator = rangeOperators[i];
                let rangeStart = filterContent.indexOf(rangeOperator);
                if (rangeStart > -1) {
                    let lower = filterContent.substring(0, rangeStart);
                    let upper = filterContent.substring(rangeStart + rangeOperator.length);
                    filterFunction = arithmeticOperator[rangeOperator];
                    binding = {
                        lower,
                        upper
                    };

                    break;
                }
            }
        }
    }
    else {
        binding = {filterValue: filterContent};
    }
    setCache('regex-filter:' + paramName, null, filterContent);

    if (isNull(filterFunction)) {
        return () => {
            true
        };
    }
    return filterFunction.bind(binding);
};

/**
 * Filter the file browser table when user types anything in the filter field.
 * Break down user's input into individual filters.
 * If the input doesn't match the pattern then default to a filename filter
 *
 * @param grid
 * @param inputSelector
 * @param cols
 * @param defaultField
 */
export const initFilter = function (inputSelector, grid, cols, defaultField) {
    let dataView = grid.getData();
    let availableFilters = [],
        filterTypes = {};
    for (let i = 0; i < cols.length; i++) {
        availableFilters.push(cols[i].field);
        filterTypes[cols[i].field] = cols[i].filter;
    }

    $(inputSelector).on('input', function () {
        let filterContents = this.value.split(';');

        /*
         * If there is only one filter, it can be the default filter
         */
        if (filterContents.length == 1) {
            let filterContent = filterContents[0];
            if (filterContent.indexOf(':') == -1) {
                filterContents[0] = defaultField + ':' + filterContent;
            }
        }

        let matches = [];
        for (let i = 0; i < filterContents.length; i++) {
            let filterContent = filterContents[i];
            let match = filterRegex.exec(filterContent);
            if (match) {
                matches.push(match);
            }
            else {
                $(inputSelector).addClass('has-error');
                return;
            }
        }

        let filterArgs = {};
        for (let i = 0; i < matches.length; i++) {
            let match = matches[i];
            let param = match[1].trim();
            let value = match[2].trim();
            let filterType = filterTypes[param];

            /* A filter must match a slug of one of the column, e.g. filename, file_duration, ... */
            if (availableFilters.indexOf(param) >= 0 && filterType !== undefined) {

                /* Value of this dict is a function handle with bounded filter value */
                filterArgs[param] = filterGenerator(param, filterType, value);
            }
        }
        setCache('filterArgs', undefined, filterArgs);


        dataView.setFilterArgs(filterArgs);

        /*
         * Call this to remove the rows that are filtered out
         */
        dataView.refresh();

        /*
         * Call this to force rerendering the rows. Helpful if the row is rendered differently after applying the filter
         */
        grid.invalidate();
        grid.render();
    });
};


/**
 * Apply the filters
 *
 * @param item the underlying row's item
 * @param filters ({})
 * @returns {boolean}
 */
export const gridFilter = function (item, filters) {
    if (filters) {
        for (let field in filters) {
            if (Object.prototype.hasOwnProperty.call(filters, field)) {
                let filter = filters[field];
                let val = item[field] || '';
                if (!filter(val)) {
                    return false;
                }
            }
        }
    }
    return true;
};


/*
 * Make a copy of Slick.Editor and then add new editors
 */
export const SlickEditors = $.extend({}, Slick.Editors);
SlickEditors.Date = DateEditorRewritten;
SlickEditors.Float = FloatEditorRewritten;

/**
 * A validator against zero length text
 */
const NonBlankValidator = function (value) {
    if (isNull(value) || !value.length) {
        return {
            valid: false,
            msg: 'This is a required field'
        };
    }
    else {
        return {
            valid: true,
            msg: null
        };
    }
};

/**
 * Validate date against yyyy-mm-dd
 * @constructor
 *
 * @source: https://stackoverflow.com/a/35413963/1302520
 * @param dateString
 */
const IsoDateValidator = function (dateString) {
    let regEx = /^\d{4}-\d{2}-\d{2}$/;
    if (!dateString.match(regEx)) return {
        valid: false,
        msg: 'The format must be like 2016-01-20 (YYYY-MM-DD)'
    };
    let d;
    if (!((d = new Date(dateString)) || 0)) return {
        valid: false,
        msg: 'This date is invalid'
    };
    if (d.toISOString().slice(0, 10) !== dateString) {
        return {
            valid: false,
            msg: 'This date is invalid'
        };
    }
    return {
        valid: true,
        msg: null
    };
};

/**
 * Validator bank
 */
const SLickValidator = {
    'NotBlank': NonBlankValidator,
    'IsoDate': IsoDateValidator
};

/**
 * Simply update the grid data
 * @param grid
 * @param rows
 */
export const updateSlickGridData = function (grid, rows) {
    if (rows) {
        let dataView = grid.getData();
        if (rows.length > 0 && !rows[0].id) {
            for (let i = 0; i < rows.length; i++) {
                rows[i].id = i;
            }
        }
        dataView.setItems(rows);
    }
};

/**
 * Add new rows to existing tables
 * @param grid
 * @param rows
 */
export const appendSlickGridData = function (grid, rows) {
    let dataView = grid.getData();
    let i, row;
    for (i = 0; i < rows.length; i++) {
        row = rows[i];
        if (row) {
            dataView.addItem(rows[i]);
        }
    }
};

/**
 * Add new rows to existing tables
 * @param grid
 * @param rows
 */
export const replaceSlickGridData = function (grid, rows) {
    let dataView = grid.getData();
    dataView.setItems(rows);
};

/**
 *
 * @param grid
 * @param sylsToDelete
 */
export const deleteSyllableGridData = function (grid, sylsToDelete) {
    let dataView = grid.getData();
    for (let i = 0; i < sylsToDelete.length; i++) {
        dataView.deleteItem(sylsToDelete[i]);
    }
    // dataView.endUpdate();
};


/**
 * Attach any class designated by 'rowClass1 property to the row
 * @param oldMetadata
 * @returns {Function}
 */
function metadata(oldMetadata) {
    return function (row) {
        let item = this.getItem(row);
        let meta = oldMetadata(row) || {};
        if (item) {
            if (item.rowClass) {
                if (meta.cssClasses) {
                    meta.cssClasses += ' ' + item.rowClass;
                }
                else {
                    meta.cssClasses = ' ' + item.rowClass;
                }
            }
        }
        return meta;
    }
}


/**
 * If there is already a column in the array with the same ID, replace that with a new column
 * Otherwise insert the new column at the beginning
 * @param columns An array of columns. It will be modified.
 * @param newcol A new column
 */
const insertOrReplaceColumn = function (columns, newcol) {
    let index = -1;
    for (let i = 0; i < columns.length; i++) {
        let column = columns[i];
        if (column.id == newcol.id) {
            index = i;
            break;
        }
    }

    if (index == -1) {
        columns.unshift(newcol);
    }
    else {
        let oldColumn = columns[index];
        columns[index] = newcol;
        for (let attr in oldColumn) {
            if (Object.prototype.hasOwnProperty.call(oldColumn, attr) && !Object.prototype.hasOwnProperty.call(newcol, attr)) {
                newcol[attr] = oldColumn[attr];
            }
        }
    }
};


/**
 * Display a slickgrid & allow sorting
 * @param selector id of the bounding div
 * @param grid
 * @param rows matrix of n rows x m column
 * @param columns an array of descriptors of m columns
 * @param args: can contain the following optional arguments:
 * @letarg multiselect whether selecting multi rows is desirable
 * @letarg filter
 * @letarg eventHandlers
 */
export const renderSlickGrid = function (selector, grid, rows, columns, args = {}) {
    let multiSelect = args.multiSelect || false;
    let radioSelect = args.radioSelect || false;
    let rowMoveable = args.rowMoveable || false;

    if (multiSelect && radioSelect) {
        throw new Error('Arguments multiSelect and radioSelect can\'t both be true')
    }

    let filter = args.filter || gridFilter;

    /*
     * Avoid repeat initialising the grid if only the data needs to be updated.
     * A grid is said to have initialised if it has column models
     */
    if (grid.getColumns().length > 0) {
        updateSlickGridData(grid, rows);
        return grid;
    }

    let columnActions = [];
    const gridType = args['grid-type'];

    /*
     * Assign appropriate input validator, input editor, output formatter, and make the cell width minimum at 50px
     */
    let swappableFields = [];
    let swappableClasses = [];
    let idxOfActionColumn;

    for (let i = 0; i < columns.length; i++) {
        let c = columns[i];

        if (c.editor === 'Date') {
            c.validator = 'IsoDate';
        }

        if (c.field === 'actions') {
            columnActions = c.actions;
            idxOfActionColumn = i;
        }

        /*
         * Depending on the column's type, it may have compatible types which can be converted to, e.g. from int to float
         * We determine this ability based on the existence of the type's class in the cache's ALIASES list.
         */
        if (c.typeClass && getCache('aliases', c.typeClass)) {
            swappableFields.push(c.field);
            swappableClasses.push(c.typeClass);
        }

        /*
         * Some column might have fixed list of values from which to choose, if so, get this list of value from the cache's
         * LITERAL list and put it on the column description
         */
        if (c.typeClass && getCache('literals', c.typeClass)) {
            c.options = getCache('literals', c.typeClass);
        }
        c._validator = c.validator;
        c._editor = c.editor;
        c._formatter = c.formatter;

        c.validator = SLickValidator[c.validator];
        c.editor = SlickEditors[c.editor];
        if (c.editor) {
            c.editor.AllowEmptyValue = true;
        }
        c.formatter = SlickFormatters[c.formatter];
    }

    /*
     * Remove the column if there is no visible action (which should be action on click)
     */
    if (!hasActionsOfType('click', columnActions)) {
        columns.splice(idxOfActionColumn, 1);
    }

    /*
     * Row selection model, if required:
     */
    let selectorPlugin = null;
    if (multiSelect) {
        selectorPlugin = new Slick.CheckboxSelectColumn({cssClass: 'checkboxsel'});
    }
    if (radioSelect) {
        selectorPlugin = new Slick.RadioSelectColumn({cssClass: 'checkboxsel'});
    }

    grid.setSelectionModel(new Slick.RowSelectionModel({selectActiveRow: false}));
    if (selectorPlugin) {
        // Inject the checkbox column at the beginning of the column list or replace it with an existing column
        insertOrReplaceColumn(columns, selectorPlugin.getColumnDefinition());

        grid.registerPlugin(selectorPlugin);
        grid.getCheckBoxSelector = function () {
            return selectorPlugin;
        }
    }

    if (rowMoveable) {
        let moveRowsPlugin = new Slick.RowMoveManager({
            cancelEditOnDrag: true
        });

        let moveableHandlerCol = {
            id: '#',
            field: '#',
            name: '',
            width: 40,
            behavior: 'selectAndMove',
            selectable: false,
            resizable: false,
            cssClass: 'cell-reorder dnd',
            formatter: RowMoveableFormatter
        };

        insertOrReplaceColumn(columns, moveableHandlerCol);

        moveRowsPlugin.onBeforeMoveRows.subscribe(function (e, data) {
            for (let i = 0; i < data.rows.length; i++) {
                // no point in moving before or after itself
                if (data.rows[i] == data.insertBefore || data.rows[i] == data.insertBefore - 1) {
                    e.stopPropagation();
                    return false;
                }
            }
            return true;
        });
        moveRowsPlugin.onMoveRows.subscribe(function (e, args_) {
            let extractedRows = [],
                left, right;
            let rows_ = args_.rows;
            let insertBefore = args_.insertBefore;
            let dataView = grid.getData();
            let data = dataView.getItems();
            left = data.slice(0, insertBefore);
            right = data.slice(insertBefore, data.length);
            rows_.sort(function (a, b) {
                return a - b;
            });
            for (let i = 0; i < rows_.length; i++) {
                extractedRows.push(data[rows_[i]]);
            }
            rows_.reverse();
            for (let i = 0; i < rows_.length; i++) {
                let row = rows_[i];
                if (row < insertBefore) {
                    left.splice(row, 1);
                }
                else {
                    right.splice(row - insertBefore, 1);
                }
            }
            data = left.concat(extractedRows.concat(right));
            let selectedRows = [];
            for (let i = 0; i < rows_.length; i++) selectedRows.push(left.length + i);
            grid.resetActiveCell();
            // let filterArgs = getCache('filterArgs');
            // dataView.setFilterArgs(null);
            dataView.setItems(data);
            grid.setSelectedRows(selectedRows);
            grid.render();
            // dataView.setFilterArgs(filterArgs);
        });
        grid.registerPlugin(moveRowsPlugin);
    }

    /*
     * Give each rows a unique ID if not given
     */
    if (rows.length > 0 && !rows[0].id) {
        for (let i = 0; i < rows.length; i++) {
            rows[i].id = i;
        }
    }

    /*
     * If there are columns with convertible types, determine which options each row can be converted to and put these
     * options on the row items.
     */
    if (swappableFields.length) {
        let fieldValue, swappableClass, swappableField, swappableOptions;
        for (let i = 0; i < swappableFields.length; i++) {
            swappableField = swappableFields[i];
            swappableClass = swappableClasses[i];
            for (let j = 0; j < rows.length; j++) {
                fieldValue = rows[j][swappableField];
                swappableOptions = getCache('aliases', swappableClass)[fieldValue];
                if (rows[j].swappables === undefined) {
                    rows[j].swappables = {};
                }
                rows[j].swappables[swappableField] = swappableOptions;
            }
        }
    }

    let dataView = new Slick.Data.DataView();
    dataView.getItemMetadata = metadata(dataView.getItemMetadata);
    grid.setData(dataView);

    grid.setColumns(columns);
    grid.init();

    // Make the grid respond to DataView change events.
    dataView.onRowCountChanged.subscribe(function () {
        grid.updateRowCount();
    });

    dataView.onRowsChanged.subscribe(function (e, args_) {
        grid.invalidateRows(args_.rows);
        grid.render();
    });

    if (multiSelect || radioSelect) {
        dataView.syncGridSelection(grid, true, true);
    }

    dataView.beginUpdate();
    dataView.setItems(rows);
    if (filter) {
        dataView.setFilter(filter);
    }
    dataView.endUpdate();

    /*
     * A standard sort function
     */
    grid.onSort.subscribe(function (e, args_) {
        let cols = args_.sortCols;
        dataView.sort(function (dataRow1, dataRow2) {
            for (let i = 0, l = cols.length; i < l; i++) {
                let field = cols[i].sortCol.field;
                let sign = cols[i].sortAsc ? 1 : -1;
                if (field === 'sel') {
                    let value1 = dataRow1._sel,
                        value2 = dataRow2._sel;
                    return value1 ? value2 ? 0 : sign : value2 ? -sign : 0;
                }
                else {
                    let value1 = dataRow1[field],
                        value2 = dataRow2[field];
                    let result = (value1 === value2 ? 0 : (value1 > value2 ? 1 : -1)) * sign;
                    if (result !== 0) {
                        return result;
                    }
                }
            }
            return 0;
        });
        args_.grid.invalidate();
        args_.grid.render();
    });

    /*
     * Destroy the current tooltip before the editor is destroyed.
     * (If there is still an error, a new tooltip will be created anyway)
     */
    grid.onBeforeCellEditorDestroy.subscribe(function (e, args_) {
        let currentCell = args_.grid.getActiveCell();
        let currentElement = $(args_.grid.getCellNode(currentCell.row, currentCell.cell));
        currentElement.parent().find('[role=tooltip]').remove();
        currentElement.attr('data-placement', undefined).attr('data-original-title', undefined).attr('data-content', undefined);
    });

    /*
     * Show a tooltip if input error
     */
    grid.onValidationError.subscribe(function (e, args_) {
        let element = $(args_.grid.getCellNode(args_.row, args_.cell));
        let rowCount = args_.grid.getDataLength();
        let currentRowIndex = args_.row;
        let toolTipPlace = 'top';

        /*
         * Avoid placing the tooltip top of the first few rows
         */
        if (currentRowIndex < rowCount / 2) {
            toolTipPlace = 'bottom'
        }
        element.attr('data-placement', toolTipPlace).attr('data-original-title', 'Input error').attr('data-content', args_.validationResults.msg).popover('show');
    });


    /*
     * Allow adding a new item and edit items that allow edit, except the fields that are not editable
     */
    grid.onBeforeEditCell.subscribe(function (e, args_) {
        let field = args_.column.field;
        let fieldEditability = '__' + field + '_editable';
        let editable = true;
        if (!isNull(args_.item[fieldEditability])) {
            editable = args_.item[fieldEditability];
        }
        let value = args_.item[field];
        args_.item['_old_' + field] = value;

        if (args_.row === args_.grid.getDataLength()) {
            return true;
        }
        else {
            let item = args_.item;

            /*
             * item._isNew when it is being created, in which case any field (incl. immutable fields) can be edited.
             * args.column.editable refers to that particular field, e.g. name, slug, type, etc.
             * item refers to the whole row. The default `editable` value is permissive (implying true if undefined), hence
             *  we use `item.editable !== false` rather than `item.editable === true`
             *
             * TL;DR: user can make change to a field of a new item or of an exiting item given that both the item and the
             *   field are editable (some items have a blanket ban on editing)
             */
            if (item._isNew) return true;

            return (args_.column.editable !== false && item.editable !== false && editable);
        }
    });

    /*
     * Add new row to the grid (but not yet submitted to the server)
     */
    grid.onAddNewRow.subscribe(function (e, args_) {
        let item = args_.item;
        let dataView_ = grid.getData();
        let items = dataView_.getItems();
        item._isNew = true;
        item.id = items.length;
        args_.grid.invalidateRow(items.length);
        dataView_.addItem(item);
        args_.grid.updateRowCount();
        args_.grid.render();
    });

    /*
     * Some onclick actions, currently only deletion
     */
    if (columnActions.length) {

        if (hasActionsOfType('click', columnActions)) {
            grid.onClick.subscribe(function (e, args_) {
                let action = $(e.target).closest('button').attr('action');
                let handler = actionHandlers[action];
                let row = args_.row;
                let dataView_ = args_.grid.getData();
                let item = dataView_.getItem(row);

                if (isClickableOnRow(row, item, action)) {
                    handler(row, grid);
                }
            });
        }

        if (hasActionsOfType('resize', columnActions)) {
            grid.onColumnsResized.subscribe(function (e, args_) {
                let handlers = getHandlerOfActionType('resize', columnActions);
                for (let i = 0; i < handlers.length; i++) {
                    handlers[i](e, args_.grid, gridType);
                }
            });
        }

        if (hasActionsOfType('reorder', columnActions)) {
            grid.onColumnsReordered.subscribe(function (e, args_) {
                let handlers = getHandlerOfActionType('reorder', columnActions);
                for (let i = 0; i < handlers.length; i++) {
                    handlers[i](e, args_.grid, gridType);
                }
            });
        }
    }

    /*
     * Allow changing the property
     */
    grid.onCellChange.subscribe(function (e, args_) {
        let item = args_.item;
        let dataView_ = grid.getData();
        let items = dataView_.getItems();
        item._isChanged = true;
        args_.grid.invalidateRow(items.length);
        dataView_.updateItem(item.id, item);
        args_.grid.updateRowCount();
        args_.grid.render();
    });

    return grid;
};


/**
 * A more consistent way to check for being null
 * @param val
 * @returns {boolean} true if is either undefined or null
 */
export const isNull = function (val) {
    return val === undefined || val === null;
};


/**
 * A more consistent way to check for a string being empty
 * @param str
 * @returns {boolean} true if is either undefined or null or empty string
 */
export const isEmpty = function (str) {
    return str === undefined || str === null || str === '';
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
    let columnHeadings = [];
    for (let i = 0; i < columns.length; i++) {
        let column = columns[i];
        let exportable = column.exportable;
        if (exportable) {
            columnHeadings.push(column.name)
        }
    }

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
                if (column._formatter === 'Url') {
                    fieldValue = convertRawUrl(fieldValue).val;
                }
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
 */
export const downloadBlob = function (blob, filename) {
    if (navigator.msSaveBlob) {
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

    let promise = new Promise(function (resolve) {
        timerId = setTimeout(function () {
            alertEl.fadeOut(500, resolve);
        }, delay);
    });

    alertEl.attr('timer-id', timerId);
    alertEl.fadeIn();

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
