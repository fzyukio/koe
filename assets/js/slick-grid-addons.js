/* global Slick */
require('slickgrid/slick.core');
require('slickgrid/slick.editors');
require('slickgrid/slick.formatters');

import {isNull, convertRawUrl} from './utils';
import {SelectizeEditor} from './selectize-formatter';

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


/**
 * Plugin to Slick.Formatter: Format float values with two decimal points
 * @return {string}
 */
const DecimalPointFormatter = function(row, cell, value, columnDef, item) {
    if (!isNull(value)) {
        value = value.toFixed(this.numDecimal);
    }
    return editabilityAwareFormatter(row, cell, value, columnDef, item)
};


/**
 * Display title cased label instead of integer value of the constants
 * @return {string}
 */
const SelectionFormatter = function(row, cell, value, columnDef, dataContext) {
    let options = columnDef.options;
    let intValue = parseInt(value);
    let label = options[intValue];
    if (label) {
        value = label;
    }
    return editabilityAwareFormatter(row, cell, value, columnDef, dataContext);
};

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
const SpectsFormatter = function (row, cell, idsTids) {
    let retval = '';
    $.each(idsTids, function (idx, idsTid) {
        let id = idsTid[0];
        let tid = idsTid[1];
        retval += `<img seg-id="${id}" src="/user_data/spect/fft/syllable/${tid}.png" height="100%"/>`;
    });
    return retval;
};


/**
 * Render one or many images given the id or array of ids of the spectrograms
 * spetrogram images are located at /user_data/spect/fft/syllable/<ID>.png
 * @returns {string}
 * @constructor
 */
const SpectFormatter = function (row, cell, value, columnDef, dataContext) {
    return `<img seg-id="${dataContext.id}" src="/user_data/spect/fft/syllable/${value}.png" height="100%"/>`;
};


/**
 * @return {string}
 */
export const RowMoveableFormatter = function () {
    return '<i class="fa fa-bars" aria-hidden="true"></i>';
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
    let tids = song['sequence-tids'];

    let retval = `<div class="syllable start full-audio" start=0 end=${duration}>
                  <i class="fa fa-play" aria-hidden="true"></i>
                </div>`;

    let nLabels = segLabels ? segLabels.length : 0;
    for (let i = 0; i < nLabels; i++) {
        let start = segStarts[i];
        let end = segEnds[i];
        let segLabel = segLabels[i];
        let tid = tids[i];
        retval += `<div class="syllable" start=${start} end=${end} imgsrc="/user_data/spect/fft/syllable/${tid}.png">${segLabel}</div>`;
    }
    return retval;
};

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
 * @return {string}
 */
const SpeciesFormatter = function(row, cell, value) {
    if (value.genus && value.species) {
        return value.genus + ' ' + value.species;
    }
    return '';
};

const SpeciesEditor = function(args) {
    let $genus, $species;
    let self = this;
    let defaultValue;

    this.init = function () {
        $genus = $('<INPUT type=text style=\'width:40px\' />').
            appendTo(args.container).
            on('keydown', self.handleKeyDown);
        $(args.container).append('&nbsp;');
        $species = $('<INPUT type=text style=\'width:40px\' />').
            appendTo(args.container).
            on('keydown', self.handleKeyDown);
        self.focus();
    };
    this.handleKeyDown = function (e) {
        if (e.keyCode == $.ui.keyCode.LEFT || e.keyCode == $.ui.keyCode.RIGHT || e.keyCode == $.ui.keyCode.TAB) {
            e.stopImmediatePropagation();
        }
    };
    this.destroy = function () {
        $(args.container).empty();
    };
    this.focus = function () {
        $genus.focus();
    };
    this.serializeValue = function () {
        return {genus: $genus.val().trim(), species: $species.val().trim()};
    };
    this.applyValue = function (item, state) {
        item[args.column.field] = state;
    };
    this.loadValue = function (item) {
        defaultValue = item[args.column.field];
        $genus.val(defaultValue.genus);
        $species.val(defaultValue.species);
    };
    this.isValueChanged = function () {
        let value = args.item[args.column.field];
        return value.genus != $genus.val().trim() || value.species != $species.val().trim();
    };
    this.validate = function () {
        let genus = $genus.val().trim();
        let species = $species.val().trim();
        let regEx = /^[A-Z][a-z]+$/;
        if (!genus.match(regEx) || !species.match(regEx)) {
            return {valid: false, msg: 'Genus and Species must be alphabetic and start with an uppercase letter'};
        }
        return {valid: true, msg: null};
    };
    this.init();
};

/**
 * Validator bank
 */
export const SLickValidator = {
    'NotBlank': NonBlankValidator,
    'IsoDate': IsoDateValidator
};


/*
 * Make a copy of Slick.Editor and then add new editors
 */
export const SlickEditors = $.extend({}, Slick.Editors);
SlickEditors.Date = DateEditorRewritten;
SlickEditors.Float = FloatEditorRewritten;
SlickEditors.Select = SelectizeEditor;
SlickEditors.Species = SpeciesEditor;

/*
 * Make a copy of Slick.Formater and then add new formatter
 */
export const SlickFormatters = $.extend({}, Slick.Formatters);
SlickFormatters.DecimalPoint = DecimalPointFormatter.bind({numDecimal: 2});
SlickFormatters.Select = SelectionFormatter;
SlickFormatters.Checkmark = CheckmarkFormatter;
SlickFormatters.Image = ImageFormatter;
SlickFormatters.Spects = SpectsFormatter;
SlickFormatters.Spect = SpectFormatter;
SlickFormatters.Url = UrlFormatter;
SlickFormatters.Sequence = SequenceFormatter;
SlickFormatters.Species = SpeciesFormatter;
