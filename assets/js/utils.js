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

import * as apa from "property-actions";

/**
 * slick.editors uses only this part of jquery-ui. Do this instead of loading the whole library
 */
if ($.ui.keyCode === undefined) {
    $.ui.keyCode = {
        "BACKSPACE": 8,
        "COMMA": 188,
        "DELETE": 46,
        "DOWN": 40,
        "END": 35,
        "ENTER": 13,
        "ESCAPE": 27,
        "HOME": 36,
        "LEFT": 37,
        "PAGE_DOWN": 34,
        "PAGE_UP": 33,
        "PERIOD": 190,
        "RIGHT": 39,
        "SPACE": 32,
        "TAB": 9,
        "UP": 38
    };
}

/*
 * Prevent datepicker to conflick with jqueryui's datepicker
 * return $.fn.datepicker to previously assigned value and give it a new name
 */
let datepicker = $.fn.datepicker.noConflict();
$.fn.bootstrapDP = datepicker;


export const editabilityAwareFormatter = function DefaultFormatter(row, cell, value, columnDef, item) {
    if (!value) {
        value = "";
    } else {
        value = (value + "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    let field = columnDef.field;

    let field_editability = '__' + field + '_editable';
    let editability = 'non-editable';
    if (!isNull(item[field_editability])) {
        editability = item[field_editability] ? 'editable' : 'non-editable';
    }
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
        let defaultDateParts = defaultDate.split("-");
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

export const setCache = function (cache, value) {
    window.appCache[cache] = value;
};

/**
 * Return django static urls by their names.
 * @param name named url
 * @param arg parameter, if required
 * @return {string}
 */
export const getUrl = function (name, arg) {
    let url = window.appCache.urls[name];
    if (arg) {
        url = url.replace('arg', arg);
    }
    return url
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
    let items = location.search.substr(1).split("&");
    for (let index = 0; index < items.length; index++) {
        tmp = items[index].split("=");
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
        try {
            value = value.toFixed(this.numDecimal);
        }
        catch (e) {
        }
    }
    return editabilityAwareFormatter(row, cell, value, columnDef, item)
}


/**
 * Convert all caps, underscore separated to title case, space separated, e.g. "HELLO_WORLD" -> "Hello World"
 * @param allCaps
 */
export const capsToTitleCase = function (allCaps) {
    return allCaps
        .replace(/_/g, ' ')
        .replace(/\w\S*/g, function (word) {
            return word.charAt(0).toUpperCase() + word.substr(1).toLowerCase();
        });
};

/**
 * Display title cased label instead of integer value of the constants
 * @return {string}
 */
function SelectionFormatter(row, cell, value, columnDef, dataContext) {
    let options = columnDef.options;
    for (let key in options) {
        if (options.hasOwnProperty(key)) {
            if (parseInt(value) === options[key]) {
                return capsToTitleCase(key);
            }
        }
    }
    return editabilityAwareFormatter(row, cell, value, columnDef, dataContext);
}

/**
 * To facilitate displaying a button inside a grid cell
 * Signature follows other Slick.Formatters
 * @param row
 * @param cell
 * @param value
 * @param columnDef
 * @param dataContext
 * @returns string HTML string of the button
 */
function ActionButtonFormatter(row, cell, value, columnDef, dataContext) {
    let formattedString = "";
    let actions = columnDef.actions;
    let actionsValues = dataContext.actions || {};
    for (let i = 0; i < actions.length; i++) {
        let action = actions[i];

        if (apa.interactionTypes[action] === 'click') {
            let actionValue = actionsValues[action] || '_default';
            let actionIcon = apa.actionIcons[action][actionValue];
            let actionTitle = apa.actionTitles[action][actionValue];
            let actionButtonStyle = apa.actionButtonStyles[action][actionValue];
            if (apa.isClickableOnRow(row, dataContext, action)) {
                formattedString += `<button type="button" class="btn btn-xs ` + actionButtonStyle + `" action="` + action + `" row="` + row + `">
                           <i class="fa ` + actionIcon + `"></i> ` + actionTitle + `
                           </button>`
            }
        }
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
const ImageFormatter = function (row, cell, imgUrl, columnDef, item) {
    return `<img src="${imgUrl}" height="100%"/>`;
};


/**
 * @return {string}
 */
const RowMoveableFormatter = function (row, cell, imgUrl, columnDef, item) {
    return `<i class="fa fa-bars" aria-hidden="true"></i>`;
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
   * Store the url on an inner variable to be reused later, e.g if the field is 'filename' then
   *  the variable is _url_filename which will takes the value of the URL, and the variable filename is set to the
   *  actual string value
   * Ideally we should keep it intact and the filter should be able to apply to the string part only
   */

  let fieldName = columnDef.field;
  let fieldUrl = '_url_' + fieldName;

  if (dataContext[fieldUrl]) {
    return `<a href="${dataContext[fieldUrl]}" target="_blank">${value}</a>`
  }

  let matches = urlRegex.exec(value);
  if (matches) {
    let url = dataContext[fieldUrl] = matches[1];
    let value = dataContext[fieldName] = matches[2];
    return `<a href="${url}" target="_blank">${matches[2]}</a>`
  }
  return value
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
SlickFormatters['DecimalPoint'] = DecimalPointFormatter.bind({numDecimal: 2});
SlickFormatters['Select'] = SelectionFormatter;
SlickFormatters['Action'] = ActionButtonFormatter;
SlickFormatters['Checkmark'] = CheckmarkFormatter;
SlickFormatters['Image'] = ImageFormatter;
SlickFormatters['Url'] = UrlFormatter;


const FloatEditor__rewritten = function (args) {
    let $input;
    let defaultValue;
    let scope = this;

    this.init = function () {
        $input = $("<INPUT type=\"number\" inputmode=\"numeric\" step=\"0.01\" class='editor-text' />");

        $input.on("keydown.nav", function (e) {
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

    function getDecimalPlaces() {
        // returns the number of fixed decimal places or null
        let rtn = args.column.editorFixedDecimalPlaces;
        if (typeof rtn == 'undefined') {
            rtn = FloatEditor__rewritten.DefaultDecimalPlaces;
        }
        return (!rtn && rtn !== 0 ? null : rtn);
    }

    this.loadValue = function (item) {
        defaultValue = item[args.column.field];

        let decPlaces = getDecimalPlaces();
        if (decPlaces !== null
            && (defaultValue || defaultValue === 0)
            && defaultValue.toFixed) {
            defaultValue = defaultValue.toFixed(decPlaces);
        }

        $input.val(defaultValue);
        $input[0].defaultValue = defaultValue;
        $input.select();
    };

    this.serializeValue = function () {
        let rtn = parseFloat($input.val());
        if (FloatEditor__rewritten.AllowEmptyValue) {
            if (!rtn && rtn !== 0) {
                rtn = '';
            }
        } else {
            rtn |= 0;
        }

        let decPlaces = getDecimalPlaces();
        if (decPlaces !== null
            && (rtn || rtn === 0)
            && rtn.toFixed) {
            rtn = parseFloat(rtn.toFixed(decPlaces));
        }

        return rtn;
    };

    this.applyValue = function (item, state) {
        item[args.column.field] = state;
    };

    this.isValueChanged = function () {
        return (!($input.val() == "" && defaultValue == null)) && ($input.val() != defaultValue);
    };

    this.validate = function () {
        if (isNaN($input.val())) {
            return {
                valid: false,
                msg: "Please enter a valid number"
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

FloatEditor__rewritten.DefaultDecimalPlaces = null;
FloatEditor__rewritten.AllowEmptyValue = false;


/**
 * Rewrite this because the default DateEditor doesn't work very well with bootstrap.
 * Essentially we're replacing Jquery UI's datepicker by bootstrap-datepicker
 * @source: http://www.eyecon.ro/bootstrap-datepicker/
 * @readthedoc: https://bootstrap-datepicker.readthedocs.io/en/stable/options.html
 *
 * @constructor
 */
const DateEditor__rewritten = function (args) {
    let inputElement;
    let defaultValue;
    let calendarOpen = false;

    this.init = function () {
        let defaultDate = args.item[args.column.field];

        inputElement = $('<input type="text" class="editor-text" value="' + defaultDate + '"/>');
        inputElement.appendTo(args.container);

        if (defaultDate) {
            let defaultDateParts = defaultDate.split("-");
            defaultDate = {
                year: parseInt(defaultDateParts[0]),
                month: parseInt(defaultDateParts[1]),
                day: parseInt(defaultDateParts[2])
            }
        }

        inputElement.bootstrapDP({
            format: "yyyy-mm-dd",
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

    this.position = function (position) {
        if (calendarOpen) {
            // Not sure what to do here. This function appears to be unbound to `this`
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
        return (!(inputElement.val() === "" && isNull(defaultValue))) && (inputElement.val() !== defaultValue);
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
const filterRegex = /([^()]+)\s*:\s*\(([^()]+)\)/;

/**
 * The overall filter can be multiple of individual filter,
 * e.g. category:(A) file_duration:(>2)
 * @type {RegExp}
 */
const filtersRegex = /(\s*[^()]+\s*:\s*\([^()]+\)\s*)+/;

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
 * Evaluate a numerical expression
 * @param number lvalue of the expression, e.g. 50
 * @returns {boolean}
 *
 * @bind ({filterValue}) rvalue of the expression, e.g. ">5", "<= 3.5", etc.
 */
const numberFilter = function (number) {
    try {
        //noinspection JSValidateTypes
        return eval(number + ' ' + this.filterValue);
    }
    catch (e) {
        // If syntax error, then ignore the filter - the user might not have finished typing
        return true;
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
    return value === this.filterValue;
};


const filterFunctions = {
    'String': stringFilter,
    'Number': numberFilter,
    'Boolean': booleanFilter,
    'Regex': regexFilter
};


/**
 * Utility to return an appropriate filter
 * @param paramName name of the param
 * @param type
 * @param filterContent
 */
const filterGenerator = function (paramName, type, filterContent) {
    filterContent = filterContent.replace("%%quoteb%%", "\\(").replace("%%quotee%%", "\\)");
    if (filterContent === '') {
        filterContent = null;
    }
    else if (type === 'String') {
        try {
            filterContent = new RegExp(filterContent, 'i');
        }
        catch (e) {
            filterContent = null;
        }
    }
    setCache('regex-filter:' + paramName, filterContent);
    return filterFunctions[type].bind({filterValue: filterContent});
};

export const regexMatchMultiple = function(regex, value) {
    let matches = filtersRegex.exec(value);
    if (! matches) {
        return null;
    }
    let retval = [matches[0]];
    while (matches) {
        let match = matches[1];
        retval.push(match);
        let matchedIndexBeg = value.indexOf(match);
        let matchedIndexEnd = matchedIndexBeg + match.length - 1;
        value = value.substr(0, matchedIndexBeg) + value.substr(matchedIndexEnd);
        matches = filtersRegex.exec(value);
    }
    return retval;
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
    let availableFilters = [], filterTypes = {};
    for (let i = 0; i < cols.length; i++) {
        availableFilters.push(cols[i].field);
        filterTypes[cols[i].field] = cols[i].filter;
    }

    $(inputSelector).on("input", function () {
        let filterContent = this.value.replace("\\(", "%%quoteb%%").replace("\\)", "%%quotee%%").trim();
        let matches = regexMatchMultiple(filtersRegex, filterContent);
        let filterArgs = {};
        let filterIsCompleted = true;

        /* The default case */
        if (isNull(matches) && !isNull(defaultField)) {
            if (availableFilters.indexOf(defaultField) >= 0) {
                filterArgs[defaultField] = filterGenerator(defaultField, 'String', filterContent);
            }
        }

        else {
            let allMatchesCombined = matches[0].trim();
            if (allMatchesCombined != filterContent) {
                filterIsCompleted = false;
            }
            else {
                for (let i = 1; i < matches.length; i++) {
                    let filter = filterRegex.exec(matches[i]);
                    let param = filter[1].trim();
                    let value = filter[2].trim();
                    let filterType = filterTypes[param];

                    /* A filter must match a slug of one of the column, e.g. filename, file_duration, ... */
                    if (availableFilters.indexOf(param) >= 0 && filterType !== undefined) {

                        /* Value of this dict is a function handle with bounded filter value */
                        filterArgs[param] = filterGenerator(param, filterType, value);
                    }
                }
            }
        }
        if (filterIsCompleted) {
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
        }
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
            if (filters.hasOwnProperty(field)) {
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
SlickEditors['Date'] = DateEditor__rewritten;
SlickEditors['Float'] = FloatEditor__rewritten;

/**
 * A validator against zero length text
 */
const NonBlankValidator = function (value) {
    if (isNull(value) || !value.length) {
        return {valid: false, msg: "This is a required field"};
    } else {
        return {valid: true, msg: null};
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
    if (!dateString.match(regEx))
        return {valid: false, msg: "The format must be like 2016-01-20 (YYYY-MM-DD)"};
    let d;
    if (!((d = new Date(dateString)) | 0))
        return {valid: false, msg: "This date is invalid"};
    if (d.toISOString().slice(0, 10) !== dateString) {
        return {valid: false, msg: "This date is invalid"};
    }
    return {valid: true, msg: null};
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
    let row, i;
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
    //dataView.endUpdate();
};


/**
 * Attach any class designated by 'rowClass1 property to the row
 * @param old_metadata
 * @returns {Function}
 */
function metadata(old_metadata) {
    return function (row) {
        let item = this.getItem(row);
        let meta = old_metadata(row) || {};
        if (item) {
            if (item.rowClass) {
                if (meta.cssClasses) {
                    meta.cssClasses += ' ' + item.rowClass;
                } else {
                    meta.cssClasses = ' ' + item.rowClass;
                }
            }
        }
        return meta;
    }
}


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

    let filter = args.filter;

    /*
     * Avoid repeat initialising the grid if only the data needs to be updated.
     * A grid is said to have initialised if it has column models
     */
    if (grid.getColumns().length > 0) {
        updateSlickGridData(grid, rows);
        return grid;
    }

    let columnActions = [];
    const gridType = args.gridType;
    /*
     * Assign appropriate input validator, input editor, output formatter, and make the cell width minimum at 50px
     */
    let swappableFields = [], swappableClasses = [], idxOfActionColumn;
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
    if (!apa.hasActionsOfType('click', columnActions)) {
        columns.splice(idxOfActionColumn, 1);
    }

    /*
     * Resize column width to fit the area.
     * If the total width of all cols is still less than the available with, we're adjust them to fit the screen
     */
    let availableWidth = $(selector).width();
    let minimumWidth = 50; // Pixels
    let columnWidth = Math.max(minimumWidth, availableWidth / columns.length);

    let undersizedCols = [];
    let totalUsedWidth = 0;

    for (let i = 0; i < columns.length; i++) {
        let column = columns[i];
        if (isNull(column.width)) {
            column.width = columnWidth;
        } else if (column.width < columnWidth) {
            undersizedCols.push(column);
        }
        totalUsedWidth += column.width;
    }

    let remainingWidth = availableWidth - totalUsedWidth;

    if (remainingWidth > 0) {
        let shareWidth = remainingWidth / undersizedCols.length;

        for (let i = 0; i < undersizedCols.length; i++) {
            undersizedCols[i].width += shareWidth;
        }
    }

    /*
     * Row selection model, if required:
     */
    let selectorPlugin = null;
    if (multiSelect) {
        selectorPlugin = new Slick.CheckboxSelectColumn({cssClass: "checkboxsel"});
    }
    if (radioSelect) {
        selectorPlugin = new Slick.RadioSelectColumn({cssClass: "checkboxsel"});
    }

    grid.setSelectionModel(new Slick.RowSelectionModel({selectActiveRow: false}));
    if (selectorPlugin) {
        // Inject the checkbox column at the beginning of the column list
        columns.unshift(selectorPlugin.getColumnDefinition());
        grid.registerPlugin(selectorPlugin);
        grid.getCheckBoxSelector = function () {
            return selectorPlugin;
        }
    }

    if (rowMoveable) {
        let moveRowsPlugin = new Slick.RowMoveManager({
            cancelEditOnDrag: true
        });

        columns.unshift({
            id: "#",
            field: "#",
            name: "",
            width: 40,
            behavior: "selectAndMove",
            selectable: false,
            resizable: false,
            cssClass: "cell-reorder dnd",
            formatter: RowMoveableFormatter
        });

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
        moveRowsPlugin.onMoveRows.subscribe(function (e, args) {
            let extractedRows = [], left, right;
            let rows = args.rows;
            let insertBefore = args.insertBefore;
            let dataView = grid.getData();
            let data = dataView.getItems();
            left = data.slice(0, insertBefore);
            right = data.slice(insertBefore, data.length);
            rows.sort(function (a, b) {
                return a - b;
            });
            for (let i = 0; i < rows.length; i++) {
                extractedRows.push(data[rows[i]]);
            }
            rows.reverse();
            for (let i = 0; i < rows.length; i++) {
                let row = rows[i];
                if (row < insertBefore) {
                    left.splice(row, 1);
                } else {
                    right.splice(row - insertBefore, 1);
                }
            }
            data = left.concat(extractedRows.concat(right));
            let selectedRows = [];
            for (let i = 0; i < rows.length; i++)
                selectedRows.push(left.length + i);
            grid.resetActiveCell();
            dataView.setItems(data);
            grid.setSelectedRows(selectedRows);
            grid.render();
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
        let fieldValue, swappableOptions, swappableField, swappableClass;
        for (let i = 0; i < swappableFields.length; i++) {
            swappableField = swappableFields[i];
            swappableClass = swappableClasses[i];
            for (let i = 0; i < rows.length; i++) {
                fieldValue = rows[i][swappableField];
                swappableOptions = getCache('aliases', swappableClass)[fieldValue];
                if (rows[i].swappables === undefined) {
                    rows[i].swappables = {};
                }
                rows[i].swappables[swappableField] = swappableOptions;
            }
        }
    }

    let dataView = new Slick.Data.DataView();
    dataView.getItemMetadata = metadata(dataView.getItemMetadata);
    grid.setData(dataView);

    grid.setColumns(columns);
    grid.init();

    // Make the grid respond to DataView change events.
    dataView.onRowCountChanged.subscribe(function (e, args) {
        grid.updateRowCount();
    });

    dataView.onRowsChanged.subscribe(function (e, args) {
        grid.invalidateRows(args.rows);
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
    grid.onSort.subscribe(function (e, args) {
        let cols = args.sortCols;
        dataView.sort(function (dataRow1, dataRow2) {
            for (let i = 0, l = cols.length; i < l; i++) {
                let field = cols[i].sortCol.field;
                let sign = cols[i].sortAsc ? 1 : -1;
                if (field === 'sel') {
                    let value1 = dataRow1._sel, value2 = dataRow2._sel;
                    return value1 ? value2 ? 0 : sign : value2 ? -sign : 0;
                }
                else {
                    let value1 = dataRow1[field], value2 = dataRow2[field];
                    let result = (value1 === value2 ? 0 : (value1 > value2 ? 1 : -1)) * sign;
                    if (result !== 0) {
                        return result;
                    }
                }
            }
            return 0;
        });
        args.grid.invalidate();
        args.grid.render();
    });

    /*
     * Destroy the current tooltip before the editor is destroyed.
     * (If there is still an error, a new tooltip will be created anyway)
     */
    grid.onBeforeCellEditorDestroy.subscribe(function (e, args) {
        let currentCell = args.grid.getActiveCell();
        let currentElement = $(args.grid.getCellNode(currentCell.row, currentCell.cell));
        currentElement.parent().find('[role=tooltip]').remove();
        currentElement.attr('data-placement', undefined).attr('data-original-title', undefined).attr('data-content', undefined);
    });

    /*
     * Show a tooltip if input error
     */
    grid.onValidationError.subscribe(function (e, args) {
        let element = $(args.grid.getCellNode(args.row, args.cell));
        let rowCount = args.grid.getDataLength();
        let currentRowIndex = args.row;
        let toolTipPlace = 'top';

        /*
         * Avoid placing the tooltip top of the first few rows
         */
        if (currentRowIndex < rowCount / 2) {
            toolTipPlace = 'bottom'
        }
        element.attr('data-placement', toolTipPlace).attr('data-original-title', 'Input error').attr('data-content', args.validationResults.msg).popover('show');
    });


    /*
     * Allow adding a new item and edit items that allow edit, except the fields that are not editable
     */
    grid.onBeforeEditCell.subscribe(function (e, args) {
        let field = args.column.field;
        let field_editability = '__' + field + '_editable';
        let editable = true;
        if (!isNull(args.item[field_editability])) {
            editable = args.item[field_editability];
        }
        let value = args.item[field];
        args.item['_old_' + field] = value;

        if (args.row === args.grid.getDataLength()) {
            return true;
        }
        else {
            let item = args.item;

            /*
             * item._isNew when it is being created, in which case any field (incl. immutable fields) can be edited.
             * args.column.editable refers to that particular field, e.g. name, slug, type, etc.
             * item refers to the whole row. The default `editable` value is permissive (implying true if undefined), hence
             *  we use `item.editable !== false` rather than `item.editable === true`
             *
             * TL;DR: user can make change to a field of a new item or of an exiting item given that both the item and the
             *   field are editable (some items have a blanket ban on editing)
             */
            if (item._isNew)
                return true;

            return (args.column.editable !== false && item.editable !== false && editable);
        }
    });

    /*
     * Add new row to the grid (but not yet submitted to the server)
     */
    grid.onAddNewRow.subscribe(function (e, args) {
        let item = args.item;
        let dataView = grid.getData();
        let rows = dataView.getItems();
        item._isNew = true;
        item.id = rows.length;
        args.grid.invalidateRow(rows.length);
        dataView.addItem(item);
        args.grid.updateRowCount();
        args.grid.render();
    });

    /*
     * Some onclick actions, currently only deletion
     */
    if (columnActions.length) {

        if (apa.hasActionsOfType('click', columnActions)) {
            grid.onClick.subscribe(function (e, args) {
                let action = $(e.target).closest('button').attr("action");
                let handler = apa.actionHandlers[action];
                let row = args.row;
                let dataView = args.grid.getData();
                let item = dataView.getItem(row);

                if (apa.isClickableOnRow(row, item, action)) {
                    handler(row, grid);
                }
            });
        }

        if (apa.hasActionsOfType('resize', columnActions)) {
            grid.onColumnsResized.subscribe(function (e, args) {
                let handlers = apa.getHandlerOfActionType('resize', columnActions);
                for (let i = 0; i < handlers.length; i++) {
                    handlers[i](e, args.grid, gridType);
                }
            });
        }

        if (apa.hasActionsOfType('reorder', columnActions)) {
            grid.onColumnsReordered.subscribe(function (e, args) {
                let handlers = apa.getHandlerOfActionType('reorder', columnActions);
                for (let i = 0; i < handlers.length; i++) {
                    handlers[i](e, args.grid, gridType);
                }
            });
        }
    }

    /*
     * Allow changing the property
     */
    grid.onCellChange.subscribe(function (e, args) {
        let item = args.item;
        let dataView = grid.getData();
        let rows = dataView.getItems();
        item._isChanged = true;
        args.grid.invalidateRow(rows.length);
        dataView.updateItem(item.id, item);
        args.grid.updateRowCount();
        args.grid.render();
    });

    return grid;
};


/**
 * Handle changes to the property settings (i.e. user clicking on the 'Save' button in the modal)
 * @param grid
 * @param servingType either PropertyOf.SONG or PropertyOf.SEGMENT (enum)
 * @param callback to handle server returned value
 */
export const propertiesSettingsChangeHandler = function (grid, servingType, callback) {
    let rows = grid.getData().getItems();
    let newOrChangedRows = [];
    let actionValueChangedRows = [];

    for (let i = 0; i < rows.length; i++) {
        let row = rows[i];
        if (row._isNew || row._isChanged) {
            newOrChangedRows.push(row);
        }
        if (row._isActionValueChanged) {
            actionValueChangedRows.push(row);
        }
    }

    if (newOrChangedRows.length) {
        $.post(
            getUrl('send-data', 'change-metadata'),
            {
                'for': servingType,
                'prototypes': JSON.stringify(newOrChangedRows)
            },
            callback
        );
    }
    if (actionValueChangedRows.length) {
        let columnIdsActionValues = {};
        for (let i = 0; i < actionValueChangedRows.length; i++) {
            let row = actionValueChangedRows[i];
            columnIdsActionValues[row.slug] = row.actions;
        }

        $.post(
            getUrl('send-data', 'change-action-values'),
            {
                'grid-type': self.gridType,
                'column-ids-action-values': JSON.stringify(columnIdsActionValues)
            },
            callback
        );
    }
    if ((newOrChangedRows.length + actionValueChangedRows.length) === 0) {
        callback('nochange');
    }

};

export const isNull = function (val) {
    return val === undefined || val === null;
};
