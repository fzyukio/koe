/* global Slick */
import {getCache, setCache} from './utils';
/* eslint require-jsdoc: off */
(function ($) {
    // register namespace
    $.extend(true, window, {
        'Slick': {
            RadioSelectColumn
        }
    });


    function RadioSelectColumn(options) {
        let _grid;
        let _idPrefix;
        let _handler = new Slick.EventHandler();
        let _selectedRowsLookup = {};
        let _defaults = {
            columnId: '_sel',
            cssClass: null,
            toolTip: 'Select/Deselect All',
            width: 30
        };

        let _options = $.extend(true, {}, _defaults, options);

        function generatePrefix() {
            if (_idPrefix === undefined) {
                let colNo = (getCache('RadioSelectColumn-#') || 0) + 1;
                setCache('RadioSelectColumn-#', undefined, colNo);
                _idPrefix = `radio-${colNo}`;
            }
        }

        function init(grid) {
            generatePrefix();
            _grid = grid;
            _handler.subscribe(_grid.onSelectedRowsChanged, handleSelectedRowsChanged).subscribe(_grid.onClick, handleClick).
                subscribe(_grid.onKeyDown, handleKeyDown);
        }

        function destroy() {
            _handler.unsubscribeAll();
        }

        function handleSelectedRowsChanged() {
            let selectedRows = _grid.getSelectedRows();
            let lookup = {};
            for (let i = 0; i < selectedRows.length; i++) {
                let row = selectedRows[i];
                lookup[row] = true;
                if (lookup[row] !== _selectedRowsLookup[row]) {
                    let item = _grid.getDataItem(row);
                    item._sel = true;
                    _grid.invalidateRow(row);
                    delete _selectedRowsLookup[row];
                }
            }
            for (let i in _selectedRowsLookup) {
                if (Object.prototype.hasOwnProperty.call(_selectedRowsLookup, i)) {
                    let item = _grid.getDataItem(i);
                    // Null check because the row can be out of view (filtered)
                    if (item) {
                        item._sel = false;
                    }
                    _grid.invalidateRow(i);
                }
            }
            _selectedRowsLookup = lookup;
            _grid.render();
        }

        function handleKeyDown(e, args) {
            if (e.which == 32) {
                if (_grid.getColumns()[args.cell].id === _options.columnId) {
                    // if editing, try to commit
                    if (!_grid.getEditorLock().isActive() || _grid.getEditorLock().commitCurrentEdit()) {
                        toggleRowSelection(args.row);
                    }
                    e.preventDefault();
                    e.stopImmediatePropagation();
                }
            }
        }

        function handleClick(e, args) {
            // clicking on a row select checkbox
            if (_grid.getColumns()[args.cell].id === _options.columnId && $(e.target).is(':radio')) {
                // if editing, try to commit
                if (_grid.getEditorLock().isActive() && !_grid.getEditorLock().commitCurrentEdit()) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    return;
                }

                toggleRowSelection(args.row);
                e.stopPropagation();
                e.stopImmediatePropagation();
            }
        }

        function toggleRowSelection(row) {
            _grid.setSelectedRows([row]);
            return true;
        }

        function getColumnDefinition() {
            return {
                id: _options.columnId,
                name: '',
                toolTip: _options.toolTip,
                field: '_sel',
                width: _options.width,
                resizable: false,
                sortable: false,
                cssClass: _options.cssClass,
                formatter: checkboxSelectionFormatter
            };
        }

        function checkboxSelectionFormatter(row, cell, value, columnDef, dataContext) {
            if (dataContext) {
                let radioId = `${_idPrefix}:${row}`;
                let checked = _selectedRowsLookup[row] ? 'checked=\'checked\'' : '';
                return `<input id='${radioId}' name='${_idPrefix}' type='radio' ${checked}/><label for='${radioId}'></label>`;
            }
            return null;
        }

        $.extend(this, {
            init,
            destroy,

            getColumnDefinition
        });
    }
}(jQuery));
