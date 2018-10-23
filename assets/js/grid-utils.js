/* global Slick */
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
import {hasActionsOfType, actionHandlers, isClickableOnRow, getHandlerOfActionType} from './property-actions';
import {getCache, isNumber, setCache, isNull, deepCopy} from './utils';
import {SlickFormatters, SLickValidator, SlickEditors, RowMoveableFormatter} from './slick-grid-addons';

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
 * @param columns
 * @param defaultField
 */
export const initFilter = function (inputSelector, grid, defaultField) {
    let columns = grid.getColumns();
    let dataView = grid.getData();
    let availableFilters = [],
        filterTypes = {};
    for (let i = 0; i < columns.length; i++) {
        availableFilters.push(columns[i].field);
        filterTypes[columns[i].field] = columns[i].filter;
    }

    let $filterInput = $(inputSelector);

    $filterInput.on('input', function () {
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
const gridFilter = function (item, filters) {
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

/**
 * Update the grid data - the current row arrangement is kept.
 * @param grid
 * @param rows
 */
export const updateSlickGridData = function (grid, rows) {
    if (rows) {
        let dataView = grid.getData();

        // Generate IDs for the rows if necessary
        if (rows.length > 0 && !rows[0].id) {
            for (let i = 0; i < rows.length; i++) {
                rows[i].id = i;
            }
            dataView.setItems(rows);
        }
        else {
            let toAdd = [];
            let items = dataView.getItems();
            let toDelete = deepCopy(items);
            dataView.beginUpdate();
            $.each(rows, function (i, row) {
                let id = row.id;
                let idx = dataView.getIdxById(id);
                if (isNull(idx)) {
                    toAdd.push(row);
                }
                else {
                    dataView.updateItem(id, row);
                    toDelete[idx] = null;
                    grid.invalidateRow(idx);
                }
            });

            // Anything that is not null in toDelete (meaning they exist in previous item list
            // but not in the updated rows) needs to be removed
            $.each(toDelete, function (i, row) {
                if (row) {
                    dataView.deleteItem(row.id);
                }
            });

            $.each(toAdd, function (i, row) {
                dataView.addItem(row)
            });
            dataView.endUpdate();
            grid.render();
        }
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
    dataView.beginUpdate();
    for (i = 0; i < rows.length; i++) {
        row = rows[i];
        if (row) {
            dataView.addItem(rows[i]);
        }
    }
    dataView.endUpdate();
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
 * Attach any class designated by rowClass property to the row
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
        args_.item['_old_' + field] = args_.item[field];

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

            let fieldEditability = '__' + field + '_editable';
            return args_.item[fieldEditability];
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
 * Find the column object (Slickgrid column) from the array of columns and the name of the column being searched for
 * @param columns
 * @param field
 * @returns {*}
 */
export const findColumn = function(columns, field) {
    let retval;
    $.each(columns, function (idx, column) {
        if (column.field == field) {
            retval = column;
            return false;
        }
        return true;
    });
    return retval;
};
