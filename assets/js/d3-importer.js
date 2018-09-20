import {line} from 'd3-shape';
import {scaleLinear, scaleSequential} from 'd3-scale';
import {interpolateYlOrRd, interpolateGreys, interpolateRainbow} from 'd3-scale-chromatic';
import {axisBottom} from 'd3-axis';
import {select, selectAll, event} from 'd3-selection';
import {extent} from 'd3-array';
import {brushX} from 'd3-brush';
import {easeLinear} from 'd3-ease';
import {forceSimulation, forceLink, forceManyBody, forceCenter, forceCollide, forceRadial} from 'd3-force';
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
    forceRadial,
    interpolateYlOrRd,
    interpolateGreys,
    interpolateRainbow,
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
