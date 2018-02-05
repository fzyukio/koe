import * as utils from './utils';

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
    asyncEditorLoading: false,
    autoEdit: true,
    enableTextSelectionOnCells: true,
    rowHeight: 25,
    defaultFormatter: utils.editabilityAwareFormatter,
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

        this.mainGridSelector = '#' + this.gridName;
        this.gridOptions = args['gridOptions'] || defaultGridOptions;
        this.mainGrid = new Slick.Grid(this.mainGridSelector, [], [], this.gridOptions);
        this.mainGrid.registerPlugin(new Slick.AutoTooltips());
        this.filterSelector = '#' + this.gridName + '-filter';

        /**
         * All events of the file browser will be broadcast via this mock element
         * @type {*}
         */
        this.eventNotifier = $(document.createElement('div'));
        this.previousRowCacheName = this.gridName + 'previousRows';
    }

    /**
     * Convenient way to register event handlers
     * @param eventType
     * @param callback
     */
    on(eventType, callback) {
        this.eventNotifier.on(eventType, callback);
    }

    /**
     *
     * @param eventType
     * @param callback
     */
    subscribe(eventType, callback) {
        let event = this.mainGrid[eventType];
        if (!utils.isNull(event)) {
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

        if (eventType === 'mouseenter') {
            rowElement.parent().find('.slick-row').removeClass('highlight');
            rowElement.addClass('highlight');
        }
        else {
            rowElement.removeClass('highlight');
        }
    };

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
        let previousRows = utils.getCache(self.previousRowCacheName) || {};
        let i, row, rowId, fileId, item;
        let removedRows = [], addedRows = [], removedItems = [], addedItems = [];

        for (rowId in previousRows) {
            if (previousRows.hasOwnProperty(rowId)) {
                row = dataView.getIdxById(rowId);
                item = dataView.getItemById(rowId);

                // Row has been removed
                if (item._sel === false) {
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
            self.eventNotifier.trigger('rows-removed', {rows: removedRows, items: removedItems, grid: grid});
        }
        else if (removedItems.length > 0) {
            self.eventNotifier.trigger('row-removed', {row: removedRows[0], item: removedItems[0], grid: grid});
        }

        if (addedItems.length > 1) {
            self.eventNotifier.trigger('rows-added', {rows: addedRows, items: addedItems, grid: grid});
        }
        else if (addedItems.length > 0) {
            self.eventNotifier.trigger('row-added', {row: addedRows[0], item: addedItems[0], grid: grid});
        }

        utils.setCache(self.previousRowCacheName, previousRows);
    };

    /**
     * Submitting property settings to the server
     */
    saveMeta(e) {
        let self = this;
        let rows = self.metaGrid.getData().getItems();

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
                utils.getUrl('send-data', 'change-metadata'),
                {
                    'grid-type': self.gridType,
                    'prototypes': JSON.stringify(newOrChangedRows)
                },
                function (retval) {
                    if (retval === 'ok') {
                        location.reload();
                    }
                }
            );
        }
        if (actionValueChangedRows.length) {
            let columnIdsActionValues = {};
            for (let i = 0; i < actionValueChangedRows.length; i++) {
                let row = actionValueChangedRows[i];
                columnIdsActionValues[row.slug] = row.actions;
            }

            $.post(
                utils.getUrl('send-data', 'change-action-values'),
                {
                    'grid-type': self.gridType,
                    'column-ids-action-values': JSON.stringify(columnIdsActionValues)
                },
                function (retval) {
                    if (retval === 'ok') {
                        location.reload();
                    }
                }
            );
        }
        if ((newOrChangedRows.length + actionValueChangedRows.length) === 0) {
            console.log('nochange')
        }
    }

    rowChangeHandler(e, args, callback) {
        const self = this;
        let dataView = args.grid.getData();
        let item = dataView.getItem(args.row);

        /* Strip off all irrelevant information */
        let itemSimplified = {id: item.id};
        for (let attr in item) {
            if (item.hasOwnProperty(attr)) {
                let oldAttr = '_old_' + attr;
                if (item.hasOwnProperty(oldAttr)) {
                    itemSimplified[attr] = item[attr];
                    itemSimplified[oldAttr] = item[oldAttr] || null;
                }
            }
        }

        let postArgs = utils.deepCopy(self.defaultArgs);
        postArgs['grid-type'] = self.gridType;
        postArgs['property'] = JSON.stringify(itemSimplified);

        $.post(
            utils.getUrl('send-data', 'change-properties'),
            {
                'grid-type': self.gridType,
                'property': JSON.stringify(itemSimplified)
            }
        );
    }

    /**
     * Shortcut
     * @param rows
     */
    appendRows(rows) {
        utils.appendSlickGridData(this.mainGrid, rows);
    };

    /**
     *
     * @param rows
     */
    replaceRows(rows) {
        utils.replaceSlickGridData(this.mainGrid, rows);
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
    };

    /**
     * Delete everything
     */
    deleteAllRows() {
        let dataView = this.mainGrid.getData();
        dataView.setItems([]);
        utils.setCache(this.previousRowCacheName, undefined);
    }

    initMainGridHeader(args, callback) {
        let self = this;
        let data = args.data || {};
        data['grid-type'] = self.gridType;

        $.post(utils.getUrl('fetch-data', 'get-grid-column-definition'), data, function (columns) {
            columns = JSON.parse(columns);
            //let rows = data.rows;

            utils.renderSlickGrid(self.mainGridSelector, self.mainGrid, [], columns, {
                multiSelect: args.multiSelect, radioSelect: args.radioSelect,
                rowMoveable: args.rowMoveable, gridType: self.gridType,
                filter: args.filter || utils.gridFilter
            });

            self.mainGrid.onCellChange.subscribe(function (e, args) {
                self.rowChangeHandler(e, args);
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

            utils.initFilter(self.filterSelector, self.mainGrid, columns, self.defaultFilterField);
            if (typeof callback == 'function') {
                callback();
            }
        });
    }

    initMainGridContent(defaultArgs) {
        let self = this;
        self.defaultArgs = defaultArgs || {};
        let args = utils.deepCopy(self.defaultArgs);
        args['grid-type'] = self.gridType;
        $.post(utils.getUrl('fetch-data', 'get-grid-content'), args, function (rows) {
            rows = JSON.parse(rows);
            utils.updateSlickGridData(self.mainGrid, rows);
        });
    }

    initGridMeta(args) {
        let self = this;
        $(self.metaModalSelector).on('shown.bs.modal', function (e) {
            if (self.metaGrid.getColumns().length === 0) {
                $.post(utils.getUrl('fetch-data', 'get-grid-meta'), {'grid-type': self.gridType},
                    function (retval) {
                        let data = JSON.parse(retval);
                        let rows = data.rows;
                        let columns = data.columns;
                        utils.renderSlickGrid(self.metaGridSelector, self.metaGrid, rows, columns);
                    }
                );
            }
        });


        $(self.saveMetaBtnSelector).on("click", function () {
            self.saveMeta();
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
        return {items: items, rows: rows, grid: self.mainGrid};
    }
}
