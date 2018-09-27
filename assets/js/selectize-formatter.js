import {getCache} from './utils';
require('selectize/dist/js/selectize.js');


export const initSelectizeSimple = function ($select, options) {
    let args = {
        sortField: 'text',
        valueField: 'value',
        labelField: 'text',
        searchField: 'text',
        create: true,
        selectOnTab: true,
        dropdownDirection: 'auto',
    };
    if (options) {
        args.options = options;
    }
    $select.selectize(args);

    return $select[0].selectize;
};


export const constructSelectizeOptionsForConstants = function (selectOptions, defaultValue) {
    let options = [];
    $.each(selectOptions, function (value, label) {
        options.push({
            value,
            label
        });
    });

    return {
        valueField: 'value',
        labelField: 'label',
        searchField: 'label',
        create: false,
        selectOnTab: false,
        openOnFocus: true,
        dropdownDirection: 'auto',
        render: {
            option (item) {
                return `<div>${item.label}</div>`;
            }
        },
        sortField: [
            {
                field: 'value',
                direction: 'asc'
            },
            {
                field: '$score'
            }
        ],
        items: [defaultValue],
        options
    };
};

export const constructSelectizeOptionsForLabellings = function(field, defaultValue) {
    let selectableColumns = getCache('selectableOptions');
    let selectableOptions = selectableColumns[field];
    let options = [];

    for (let option in selectableOptions) {
        if (option && Object.prototype.hasOwnProperty.call(selectableOptions, option)) {
            let count = selectableOptions[option];
            options.push({
                option,
                count
            });
        }
    }

    return {
        valueField: 'option',
        labelField: 'option',
        searchField: 'option',
        create: true,
        selectOnTab: true,
        openOnFocus: false,
        dropdownDirection: 'auto',
        render: {
            option (item) {
                return `<div><span class="badge">${item.count}</span> ${item.option}</div>`;
            }
        },
        sortField: [
            {
                field: 'count',
                direction: 'desc'
            },
            {
                field: '$score'
            }
        ],
        items: [defaultValue],
        options
    };
};


export const initSelectize = function ($select, selectizeOptions) {
    let control = $select.selectize(selectizeOptions);

    control[0].selectize.onMouseDown = function (e) {
        e.preventDefault();
        e.stopPropagation();
    };

    control[0].selectize.onClick = function (e) {
        e.preventDefault();
        e.stopPropagation();
    };

    return control;
};

/**
 * This class helps render magic choice options as a combo box in the grid.
 * Same signature as other editors, as found in Slick.Editors
 * @param args expects one attributes `options` which is a map from one type to its aliases
 * @constructor will break the options into separate key-value pairs and create a HTML element accordingly
 */
export const SelectizeEditor = function (args) {
    let $select, defaultValue;

    this.init = function () {
        $(args.container).find('select').remove();
        $select = $('<SELECT tabIndex=\'0\' class=\'selectize\'></SELECT>');
        $select.appendTo(args.container);

        let selectizeOptions;
        defaultValue = args.item[args.column.field];

        if (args.column._formatter == 'Select') {
            selectizeOptions = constructSelectizeOptionsForConstants(args.column.options, defaultValue);
        }
        else {
            selectizeOptions = constructSelectizeOptionsForLabellings(args.column.field, defaultValue);
        }

        initSelectize($select, selectizeOptions);

        $select[0].selectize.focus();
    };

    this.destroy = function () {
        $select.remove();
        $select[0].selectize.destroy();
    };

    this.focus = function () {
        $select.focus();
    };

    this.loadValue = function (item) {
        defaultValue = item[args.column.field];
        $select.val(defaultValue);
    };

    this.serializeValue = function () {
        if (args.column._formatter == 'Checkmark') {
            return ($select.val() === 'yes');
        }
        return $select.val();
    };

    this.applyValue = function (item, state) {
        item[args.column.field] = state;
    };

    this.isValueChanged = function () {
        let val = $select.val();
        if (val || defaultValue) return (val !== defaultValue);
        return false;
    };

    this.validate = function () {
        return {
            valid: true,
            msg: null
        };
    };

    this.init();
};
