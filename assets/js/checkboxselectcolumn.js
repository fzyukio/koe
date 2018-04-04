/* global Slick*/
/* eslint require-jsdoc: off */
(function ($) {
    // register namespace
    $.extend(true, window, {
        'Slick': {
            CheckboxSelectColumn
        }
    });


    function CheckboxSelectColumn(options) {
        let _grid;
        let _handler = new Slick.EventHandler();
        let _selectedRowsLookup = {};
        let _defaults = {
            columnId: '_sel',
            cssClass: null,
            toolTip: 'Select/Deselect All',
            width: 22,
        };

        let _options = $.extend(true, {}, _defaults, options);

        function init(grid) {
            _grid = grid;
            _handler.subscribe(_grid.onSelectedRowsChanged, handleSelectedRowsChanged).subscribe(_grid.onClick, handleClick).subscribe(_grid.onHeaderClick, handleHeaderClick).subscribe(_grid.onKeyDown, handleKeyDown);
        }

        function destroy() {
            _handler.unsubscribeAll();
        }

        function handleSelectedRowsChanged() {
            let selectedRows = _grid.getSelectedRows();
            let lookup = {},
                row, i, item;
            for (i = 0; i < selectedRows.length; i++) {
                row = selectedRows[i];
                lookup[row] = true;
                if (lookup[row] !== _selectedRowsLookup[row]) {
                    item = _grid.getDataItem(row);
                    item._sel = true;
                    _grid.invalidateRow(row);
                    delete _selectedRowsLookup[row];
                }
            }

            let _selectedRowsLookupIdxs = Object.keys(_selectedRowsLookup);
            for (i = 0; i < _selectedRowsLookupIdxs.length; i++) {
                row = parseInt(_selectedRowsLookupIdxs[i]);
                if (selectedRows.indexOf(row) < 0) {
                    // Row has been toggled
                    item = _grid.getDataItem(row);

                    // Null check because the row can be out of view (filtered)
                    if (item) {
                        item._sel = false;
                    }
                }
            }

            for (i in _selectedRowsLookup) {
                if (Object.prototype.hasOwnProperty.call(_selectedRowsLookup, i)) {
                    _grid.invalidateRow(i);
                }
            }
            _selectedRowsLookup = lookup;
            _grid.render();

            if (selectedRows.length && selectedRows.length == _grid.getDataLength()) {
                _grid.updateColumnHeader(_options.columnId, '<input type=\'checkbox\' checked=\'checked\'/>', _options.toolTip);
            }
            else {
                _grid.updateColumnHeader(_options.columnId, '<input type=\'checkbox\'/>', _options.toolTip);
            }
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
            if (_grid.getColumns()[args.cell].id === _options.columnId && $(e.target).is(':checkbox')) {
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
            if (_selectedRowsLookup[row]) {
                _grid.setSelectedRows($.grep(_grid.getSelectedRows(), function (n) {
                    return n != row
                }));
            }
            else {
                _grid.setSelectedRows(_grid.getSelectedRows().concat(row));
            }
        }

        function handleHeaderClick(e, args) {
            if (args.column.id == _options.columnId && $(e.target).is(':checkbox')) {
                // if editing, try to commit
                if (_grid.getEditorLock().isActive() && !_grid.getEditorLock().commitCurrentEdit()) {
                    e.preventDefault();
                    e.stopImmediatePropagation();
                    return;
                }

                if ($(e.target).is(':checked')) {
                    let rows = [];
                    for (let i = 0; i < _grid.getDataLength(); i++) {
                        rows.push(i);
                    }
                    _grid.setSelectedRows(rows);
                }
                else {
                    _grid.setSelectedRows([]);
                }
                e.stopPropagation();
                e.stopImmediatePropagation();
            }
        }

        function getColumnDefinition() {
            return {
                id: _options.columnId,
                name: '<input type=\'checkbox\'/>',
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
                if (dataContext._isLoading) {
                    return '<div class="loader"></div>'
                }
                return _selectedRowsLookup[row] ?
                    '<input type=\'checkbox\' checked=\'checked\'/>' :
                    '<input type=\'checkbox\'/>';
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
