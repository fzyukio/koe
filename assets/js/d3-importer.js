import {line} from 'd3-shape';
import {scaleLinear, scaleSequential} from 'd3-scale';
import {interpolateReds, interpolateGreys} from 'd3-scale-chromatic';
import {axisBottom} from 'd3-axis';
import {select, selectAll, event} from 'd3-selection';
import {extent} from 'd3-array';
import {brushX} from 'd3-brush';
import {easeLinear} from 'd3-ease';
import {forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide} from 'd3-force';
import {drag} from 'd3-drag';

export default {
    line,
    scaleLinear,
    scaleSequential,
    forceSimulation,
    forceLink,
    forceManyBody,
    forceCenter,
    forceCollide,
    interpolateReds,
    interpolateGreys,
    drag,
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
