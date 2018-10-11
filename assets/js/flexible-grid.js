/* global Slick */
import {postRequest} from './ajax-handler';
import {
    editabilityAwareFormatter, isNull, getCache, setCache, deepCopy, appendSlickGridData, replaceSlickGridData,
    renderSlickGrid, initFilter, updateSlickGridData
} from './utils';

require('slickgrid/plugins/slick.autotooltips');


/**
 * This is the overall options. Details see SlickGrid's documentation
 * @type {{enableCellNavigation: boolean, enableColumnReorder: boolean, multiColumnSort: boolean, editable: boolean, enableAddRow: boolean, asyncEditorLoading: boolean, autoEdit: boolean}}
 */
export const defaultGridOptions = {
    enableCellNavigation: true,
    enableColumnReorder: true,
    multiColumnSort: true,
    editable: true,
    enableAddRow: false,
    asyncEditorLoading: true,
    autoEdit: true,
    enableTextSelectionOnCells: true,
    rowHeight: 25,
    defaultFormatter: editabilityAwareFormatter,
};


export class FlexibleGrid {

    /**
     * Init two grids and query for the meta table (also header)
     * @param args
     */

    init(args) {
        this.gridName = args['grid-name'];
        this.gridType = args['grid-type'];
        this.defaultFilterField = args['default-field'];
        this.currentMouseEvent = null;

        this.mainGridSelector = '#' + this.gridType;
        this.gridOptions = args.gridOptions || defaultGridOptions;
        this.mainGrid = new Slick.Grid(this.mainGridSelector, [], [], this.gridOptions);
        this.mainGrid.registerPlugin(new Slick.AutoTooltips());
        this.filterSelector = '#' + this.gridType + '-filter';

        /**
         * All events of the file browser will be broadcast via this mock element
         * @type {*}
         */
        this.eventNotifier = $(document.createElement('div'));
        this.previousRowCacheName = this.gridType + 'previousRows';
    }

    /**
     * Convenient way to register event handlers
     * @param eventType
     * @param callback
     */
    on(eventType, callback) {
        this.eventNotifier.on(eventType, callback);
        return this;
    }

    /**
     * Allow ousider to subscribe to any event on the grid.
     *
     * @param eventType must be one of those listed at https://github.com/mleibman/SlickGrid/wiki/Grid-Events
     * @param callback
     */
    subscribe(eventType, callback) {
        let event = this.mainGrid[eventType];
        if (!isNull(event)) {
            event.subscribe(callback);
        }
    }

    /**
     * Allow ousider to subscribe to any event on the dataview.
     *
     * @param eventType must be one of those listed at https://github.com/mleibman/SlickGrid/wiki/Dataview-Events
     * @param callback
     */
    subscribeDv(eventType, callback) {
        let event = this.mainGrid.getData()[eventType];
        if (!isNull(event)) {
            event.subscribe(callback);
        }
    }

    /**
     * Highlight the active row on mouse over
     * @param e
     * @param args
     */
    mouseHandler(e, args) {
        let eventType = e.type;
        let rowElement = $(e.target.parentElement);
        let cell = args.grid.getCellFromEvent(e);
        this.currentMouseEvent = cell;

        if (eventType === 'mouseenter') {
            rowElement.parent().find('.slick-row').removeClass('highlight');
            rowElement.addClass('highlight');
        }
        else {
            rowElement.removeClass('highlight');
        }
    }

    /**
     * Handling the event when a row is selected or not selected
     * (Only applies to tables with checkbox selection model)
     * @param e
     * @param args ({})
     */
    rowSelectedHandler(e, args) {
        let self = this;
        let grid = args.grid;
        let dataView = grid.getData();
        let rows = args.rows;
        let previousRows = getCache(self.previousRowCacheName) || {};
        let i, item, row, rowId;
        let removedRows = [];
        let addedItems = [];
        let addedRows = [];
        let removedItems = [];


        for (rowId in previousRows) {
            if (Object.prototype.hasOwnProperty.call(previousRows, rowId)) {
                row = dataView.getIdxById(rowId);
                item = dataView.getItemById(rowId);

                // Row has been removed
                if (item === undefined || item._sel === false) {
                    delete previousRows[rowId];
                    removedRows.push(row);
                    removedItems.push(item);
                }
            }
        }

        for (i = 0; i < rows.length; i++) {
            row = rows[i];
            item = dataView.getItem(row);
            rowId = item.id;

            // Row has been added
            if (previousRows[rowId] === undefined) {
                previousRows[rowId] = row;
                addedRows.push(row);
                addedItems.push(item);
            }
        }

        if (removedItems.length > 1) {
            self.eventNotifier.trigger('rows-removed', {
                rows: removedRows,
                items: removedItems,
                grid
            });
        }
        else if (removedItems.length > 0) {
            self.eventNotifier.trigger('row-removed', {
                row: removedRows[0],
                item: removedItems[0],
                grid
            });
        }

        if (addedItems.length > 1) {
            self.eventNotifier.trigger('rows-added', {
                rows: addedRows,
                items: addedItems,
                grid
            });
        }
        else if (addedItems.length > 0) {
            self.eventNotifier.trigger('row-added', {
                row: addedRows[0],
                item: addedItems[0],
                grid
            });
        }

        setCache(self.previousRowCacheName, null, previousRows);
    }


    rowChangeHandler(e, args, onSuccess, onFailure) {
        const self = this;
        let item = args.item;
        let selectableColumns = getCache('selectableOptions');

        /* Strip off all irrelevant information */
        let itemSimplified = {id: item.id};
        for (let attr in item) {
            if (Object.prototype.hasOwnProperty.call(item, attr)) {
                let oldAttr = '_old_' + attr;
                if (Object.prototype.hasOwnProperty.call(item, oldAttr)) {
                    let newValue = item[attr];
                    itemSimplified[attr] = newValue;
                    itemSimplified[oldAttr] = item[oldAttr] || null;

                    let selectableOptions = selectableColumns[attr];
                    if (newValue && selectableOptions) {
                        selectableOptions[newValue] = (selectableOptions[newValue] || 0) + 1;
                    }
                }
            }
        }

        let postData = {
            'grid-type': self.gridType,
            'property': JSON.stringify(itemSimplified)
        };

        return new Promise(function (resolve, reject) {
            postRequest({
                requestSlug: 'change-properties',
                data: postData,
                onSuccess(...args_) {
                    if (onSuccess) {
                        onSuccess(...args_);
                    }
                    return resolve({args: args_});
                },
                onFailure(...args_) {
                    if (onFailure) {
                        onFailure(...args_);
                    }
                    return reject(new Error(args_));
                },
                immediate: true
            });
        });
    }

    /**
     * Shortcut
     * @param rows
     */
    appendRows(rows) {
        appendSlickGridData(this.mainGrid, rows);
    }

    /**
     * Append ONE row, the scroll down to that row
     * @param row
     */
    appendRowAndHighlight(row) {
        this.mainGrid.getData().addItem(row);
        this.mainGrid.gotoCell(row.id, 0);
        this.mainGrid.scrollCellIntoView(row.id, 0);
    }

    /**
     *
     * @param rows
     */
    replaceRows(rows) {
        replaceSlickGridData(this.mainGrid, rows);
    }

    /**
     * Shortcut
     * @param rows
     */
    deleteRows(rows) {
        let dataView = this.mainGrid.getData();
        for (let i = 0; i < rows.length; i++) {
            dataView.deleteItem(rows[i]);
        }
    }

    /**
     * Delete everything
     */
    deleteAllRows() {
        let dataView = this.mainGrid.getData();
        dataView.setItems([]);
        setCache(this.previousRowCacheName, null, undefined);
    }

    postMainGridHeader() {
        let self = this;

        self.mainGrid.onCellChange.subscribe(function (e, args) {
            self.rowChangeHandler(e, args, undefined, function() {
                let column = args.grid.getColumns()[args.cell];
                let field = column.field;
                let oldValue = args.item[`_old_${field}`];
                args.item[field] = oldValue;
                args.grid.invalidateRow(args.row);
                args.grid.render();
            });
        });
        self.mainGrid.onMouseEnter.subscribe(function (e, args) {
            self.mouseHandler(e, args);
        });
        self.mainGrid.onMouseLeave.subscribe(function (e, args) {
            self.mouseHandler(e, args);
        });
        self.mainGrid.onSelectedRowsChanged.subscribe(function (e, args) {
            self.rowSelectedHandler(e, args);
        });
        self.mainGrid.onClick.subscribe(function (e, args) {
            self.mouseHandler(e, args);
        });
    }

    initMainGridHeader(defaultArgs, extraArgs, callback) {
        let self = this;
        defaultArgs['grid-type'] = self.gridType;

        let onSuccess = function (columns) {
            self.columns = columns;

            renderSlickGrid(self.mainGridSelector, self.mainGrid, [], deepCopy(self.columns), defaultArgs);

            self.postMainGridHeader();
            initFilter(self.filterSelector, self.mainGrid, self.columns, self.defaultFilterField);

            if (typeof callback == 'function') {
                callback();
            }
        };

        postRequest({
            requestSlug: 'get-grid-column-definition',
            data: {
                'grid-type': self.gridType,
                'extras': JSON.stringify(extraArgs)
            },
            onSuccess
        });
    }

    redrawMainGrid(args, callback) {
        let self = this;

        self.mainGrid = new Slick.Grid(this.mainGridSelector, [], [], this.gridOptions);
        self.mainGrid.registerPlugin(new Slick.AutoTooltips());

        renderSlickGrid(self.mainGridSelector, self.mainGrid, [], deepCopy(self.columns), args);
        self.postMainGridHeader();
        initFilter(self.filterSelector, self.mainGrid, self.columns, self.defaultFilterField);

        if (typeof callback == 'function') {
            callback();
        }

        updateSlickGridData(self.mainGrid, self.rows);
    }

    cacheSelectableOptions() {
        let self = this;
        let grid = self.mainGrid;
        let columns = grid.getColumns();
        let items = grid.getData().getItems();

        let selectableColumns = getCache('selectableOptions');
        if (isNull(selectableColumns)) {
            selectableColumns = {};
        }
        for (let i = 0; i < columns.length; i++) {
            let column = columns[i];
            if (column._editor === 'Select') {
                selectableColumns[column.field] = {};
            }
        }

        for (let i = 0; i < items.length; i++) {
            let item = items[i];
            for (let field in selectableColumns) {
                if (Object.prototype.hasOwnProperty.call(selectableColumns, field)) {
                    let count = selectableColumns[field];
                    let val = item[field];
                    val = val && val.trim();
                    if (val) count[val] = (count[val] || 0) + 1;
                }
            }
        }
        setCache('selectableOptions', undefined, selectableColumns)
    }

    initMainGridContent(defaultArgs, extraArgs, callback) {
        let self = this;
        self.defaultArgs = defaultArgs || {};
        let doCacheSelectableOptions = self.defaultArgs.doCacheSelectableOptions;
        if (doCacheSelectableOptions === undefined) {
            doCacheSelectableOptions = true;
        }

        let args = deepCopy(self.defaultArgs);
        args['grid-type'] = self.gridType;

        if (extraArgs) {
            args.extras = JSON.stringify(extraArgs);
        }

        let onSuccess = function (rows) {
            self.rows = rows;
            updateSlickGridData(self.mainGrid, rows);
            if (doCacheSelectableOptions) {
                self.cacheSelectableOptions();
            }

            if (typeof callback === 'function') {
                callback();
            }
        };

        postRequest({
            requestSlug: 'get-grid-content',
            data: args,
            onSuccess
        });
    }

    getSelectedRows() {
        const self = this;
        let dataView = self.mainGrid.getData();
        let rows = self.mainGrid.getSelectedRows();
        let items = [];
        for (let i = 0; i < rows.length; i++) {
            items.push(dataView.getItem(rows[i]));
        }
        return {
            items,
            rows,
            grid: self.mainGrid
        };
    }
}
