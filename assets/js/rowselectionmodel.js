/* global Slick*/
/* eslint require-jsdoc: off */
(function ($) {
  // register namespace
  $.extend(true, window, {
    Slick: {
      RowSelectionModel,
    },
  });

  function RowSelectionModel(options) {
    let _grid;
    let _ranges = [];
    let self = this;
    let _handler = new Slick.EventHandler();
    let _inHandler;
    let _options;
    let _defaults = {
      selectActiveRow: true,
    };

    function init(grid) {
      _options = $.extend(true, {}, _defaults, options);
      _grid = grid;
      _handler.subscribe(
        _grid.onActiveCellChanged,
        wrapHandler(handleActiveCellChange)
      );
      _handler.subscribe(_grid.onKeyDown, wrapHandler(handleKeyDown));
      _handler.subscribe(_grid.onClick, wrapHandler(handleClick));
    }

    function destroy() {
      _handler.unsubscribeAll();
    }

    function wrapHandler(handler) {
      return function () {
        if (!_inHandler) {
          _inHandler = true;

          // eslint-disable-next-line prefer-rest-params
          handler.apply(this, arguments);
          _inHandler = false;
        }
      };
    }

    function rangesToRows(ranges) {
      let rows = [];
      for (let i = 0; i < ranges.length; i++) {
        for (let j = ranges[i].fromRow; j <= ranges[i].toRow; j++) {
          rows.push(j);
        }
      }
      return rows;
    }

    function rowsToRanges(rows) {
      let ranges = [];
      let lastCell = _grid.getColumns().length - 1;
      for (let i = 0; i < rows.length; i++) {
        ranges.push(new Slick.Range(rows[i], 0, rows[i], lastCell));
      }
      return ranges;
    }

    function getRowsRange(from, to) {
      let i,
        rows = [];
      for (i = from; i <= to; i++) {
        rows.push(i);
      }
      for (i = to; i < from; i++) {
        rows.push(i);
      }
      return rows;
    }

    function getSelectedRows() {
      return rangesToRows(_ranges);
    }

    function setSelectedRows(rows, quiet = false) {
      setSelectedRanges(rowsToRanges(rows), quiet);
    }

    function setSelectedRanges(ranges, quiet = false) {
      // simle check for: empty selection didn't change, prevent firing onSelectedRangesChanged
      if (
        (!_ranges || _ranges.length === 0) &&
        (!ranges || ranges.length === 0)
      ) {
        return;
      }
      _ranges = ranges;
      if (!quiet) {
        self.onSelectedRangesChanged.notify(_ranges);
      }
    }

    function getSelectedRanges() {
      return _ranges;
    }

    function handleActiveCellChange(e, data) {
      if (_options.selectActiveRow && data.row !== null) {
        setSelectedRanges([
          new Slick.Range(data.row, 0, data.row, _grid.getColumns().length - 1),
        ]);
      }
    }

    /**
     * Apply bulk selection when the key Ctrl or Shift is pressed
     * @param e event
     */
    function handleKeyDown(e) {
      let activeRow = _grid.getActiveCell();
      if (
        activeRow &&
        e.shiftKey &&
        !e.ctrlKey &&
        !e.altKey &&
        !e.metaKey &&
        (e.which == 38 || e.which == 40)
      ) {
        let selectedRows = getSelectedRows();
        selectedRows.sort(function (x, y) {
          return x - y;
        });

        if (!selectedRows.length) {
          selectedRows = [activeRow.row];
        }

        let top = selectedRows[0];
        let bottom = selectedRows[selectedRows.length - 1];
        let active;

        if (e.which == 40) {
          active = activeRow.row < bottom || top == bottom ? ++bottom : ++top;
        } else {
          active = activeRow.row < bottom ? --bottom : --top;
        }

        if (active >= 0 && active < _grid.getDataLength()) {
          _grid.scrollRowIntoView(active);
          let tempRanges = rowsToRanges(getRowsRange(top, bottom));
          setSelectedRanges(tempRanges);
        }

        e.preventDefault();
        e.stopPropagation();
      }
    }

    /**
     * Remove or add row index to/from the list of selected rows.
     *
     * @param e event
     * @returns {boolean} true
     */
    function handleClick(e) {
      let cell = _grid.getCellFromEvent(e);
      if (!cell || !_grid.canCellBeActive(cell.row, cell.cell)) {
        return false;
      }

      if (
        !_grid.getOptions().multiSelect ||
        (!e.ctrlKey && !e.shiftKey && !e.metaKey)
      ) {
        return false;
      }

      let selection = rangesToRows(_ranges);
      let idx = $.inArray(cell.row, selection);

      if (idx === -1 && (e.ctrlKey || e.metaKey)) {
        selection.push(cell.row);
        _grid.setActiveCell(cell.row, cell.cell);
      } else if (idx !== -1 && (e.ctrlKey || e.metaKey)) {
        selection = $.grep(selection, function (o) {
          return o !== cell.row;
        });
        _grid.setActiveCell(cell.row, cell.cell);
      } else if (selection.length && e.shiftKey) {
        let last = selection.pop();
        let from = Math.min(cell.row, last);
        let to = Math.max(cell.row, last);
        selection = [];
        for (let i = from; i <= to; i++) {
          if (i !== last) {
            selection.push(i);
          }
        }
        selection.push(last);
        _grid.setActiveCell(cell.row, cell.cell);
      }

      let tempRanges = rowsToRanges(selection);
      setSelectedRanges(tempRanges);
      e.stopImmediatePropagation();

      return true;
    }

    $.extend(this, {
      getSelectedRows,
      setSelectedRows,

      getSelectedRanges,
      setSelectedRanges,

      init,
      destroy,
      onSelectedRangesChanged: new Slick.Event(),
    });
  }
})(jQuery);
