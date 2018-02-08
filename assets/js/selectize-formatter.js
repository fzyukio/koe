import {getCache} from "./utils";
require('selectize/dist/js/standalone/selectize.js');


export const initSelectize = function ($select, field, defaultValue) {
    let selectableColumns = getCache('selectableOptions');
    let selectableOptions = selectableColumns[field];
    let options = [];

    for (let option in selectableOptions) {
        if (option && selectableOptions.hasOwnProperty(option)) {
            let count = selectableOptions[option];
            options.push({option: option, count: count});
        }
    }

    let control = $select.selectize({
        valueField: 'option',
        labelField: 'option',
        searchField: 'option',
        create: true,
        selectOnTab: true,
        options: options,
        render: {
            option: function (item, escape) {
                return `<div><span class="badge">${item.count}</span> ${item.option}</div>`
            }
        },
        sortField: [{field: 'count', direction: 'desc'}, {field: '$score'}],
        items: [defaultValue]
    });

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
        $select = $("<SELECT tabIndex='0' class='selectize'></SELECT>");
        $select.appendTo(args.container);

        initSelectize($select, args.column.field, args.item[args.column.field]);

        $select[0].selectize.focus()
    };

    this.destroy = function () {
        $select.remove();
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
            return ($select.val() === "yes");
        }
        return $select.val();
    };

    this.applyValue = function (item, state) {
        item[args.column.field] = state;
    };

    this.isValueChanged = function () {
        let val = $select.val();
        if (val || defaultValue)
            return (val !== defaultValue);
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
