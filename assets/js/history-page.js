import * as fg from "flexible-grid";
import * as utils from "./utils";
import {defaultGridOptions} from "./flexible-grid";

const gridOptions = utils.deepCopy(defaultGridOptions);
gridOptions.rowHeight = 50;


class SegmentGrid extends fg.FlexibleGrid {
    init() {
        super.init({
            'grid-name': 'history-grid',
            'grid-type': 'history-grid',
            'default-field': 'label_family',
            gridOptions: gridOptions
        });
    };
}

const grid = new SegmentGrid();


/**
 * Redraw the table on orientation changed
 */
export const orientationChange = function () {
    grid.redrawMainGrid({rowMoveable: true, multiSelect: true});
};


export const run = function () {
    console.log("History page is now running.");

    grid.init();
    grid.initMainGridHeader({rowMoveable: false, multiSelect: true}, function () {
        grid.initMainGridContent();
    });
};