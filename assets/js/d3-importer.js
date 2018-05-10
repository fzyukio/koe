import {line} from 'd3-shape';
import {scaleLinear} from 'd3-scale';
import {axisBottom} from 'd3-axis';
import {select, selectAll, event} from 'd3-selection';
import {extent} from 'd3-array';
import {brushX} from 'd3-brush';
import {easeLinear} from 'd3-ease';

export default {
    line,
    scaleLinear,
    axisBottom,
    select,
    selectAll,
    extent,
    brushX,
    easeLinear,
    get event() {
        return event;
    },
};
