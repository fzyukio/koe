/* eslint consistent-this: off, no-console: off */
let d3 = require('d3/d3.js');
require('jquery-contextmenu');

import {getUrl, getCache, calcSegments} from './utils';
import * as DSP from './dsp';
import * as ah from 'audio-handler'
import * as utils from 'utils'

const nfft = 256;
const noverlap = nfft * 3 / 4;

/**
 * Converts segment of a signal into spectrogram and displays it.
 * Keep in mind that the spectrogram's SVG contaims multiple images next to each other.
 * This function should be called multiple times to generate the full spectrogram
 * @param viz the Visualisation object
 * @param sig full audio signal
 * @param segs the segment indices to be turned into spectrogram
 * @param offset where the image starts
 */
function displaySpectrogram(viz, sig, segs, offset) {
    let subImgWidth = segs.length;
    new Promise(function (resolve) {
        let img = new Image();
        img.onload = function () {
            let spect = DSP.spectrogram(sig, segs);
            spect = DSP.transposeFlipUD(spect);
            let canvas = document.createElement('canvas');
            let context = canvas.getContext('2d');
            let imgData = context.createImageData(subImgWidth, viz.imgHeight);

            canvas.height = viz.imgHeight;
            canvas.width = subImgWidth;

            DSP.spectToCanvas(spect, imgData);
            // put data to context at (0, 0)
            context.putImageData(imgData, 0, 0);
            resolve(canvas.toDataURL('image/png'));
        };

        // This data URI is a dummy one, use it to trigger onload()
        img.src = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z/C/HgAGgwJ/lK3Q6wAAAABJRU5ErkJggg==';
    }).then(function (dataURI) {
        viz.spectrogramSpects.
            append('image').
            attr('height', viz.imgHeight).
            attr('width', subImgWidth).
            attr('x', offset).
            attr('xlink:href', dataURI).
            style('transform', `scaleY(${viz.spectHeight / viz.imgHeight})`);
    });
}


export const Visualise = function () {
    this.init = function (spectId) {
        const viz = this;
        // Handlers of the D3JS objects
        viz.spectrogramGroup = null;
        viz.spectrogramSvg = null;
        viz.spectWidth = null;
        viz.spectHeight = null;
        viz.margin = null;
        viz.height = null;
        viz.width = null;
        viz.spectXScale = null;
        viz.spectYScale = null;
        viz.scrollbarHeight = 10;
        viz.spectrogramId = '#' + spectId;
        viz.spectBrush = null;

        /**
         * All events of the file browser will be broadcast via this mock element
         * @type {*}
         */
        viz.eventNotifier = $(document.createElement('div'));

        return this;
    };

    this.drawBrush = function () {
        const viz = this;

        let resizePath = function (d) {
            // Style the brush resize handles (copied-pasted code. Don't ask what the variables mean).
            let e = Number(d === 'e'),
                x = e ? 1 : -1,
                y = viz.spectHeight / 3;
            return `M${0.5 * x},${y}A6,6 0 0 ${e} ${6.5 * x},${y + 6}V${2 * y - 6}A6,6 0 0 ${e} ${0.5 * x},${2 * y}ZM${2.5 * x},${y + 8}V${2 * y - 8}M${4.5 * x},${y + 8}V${2 * y - 8}`;
        };

        viz.spectBrush = d3.svg.brush().
            x(viz.spectXScale).
            on('brushstart', function () {
                console.log('on brushstart');
            }).
            on('brushend', function () {
                console.log('on brushend');
                if (viz.spectBrush.empty()) {

                /*
                 * Remove the brush means that no syllable is currently resizable
                 */
                    utils.setCache('resizeable-syl-id', undefined);
                    console.log('Current resizeable syllable index: ' + window.appCache['resizeable-syl-id']);
                }
                else {
                    let endpoints = viz.spectBrush.extent();
                    let duration = viz.spectXScale.domain()[1];
                    let start = endpoints[0] / duration;
                    let end = endpoints[1] / duration;

                    console.log('start= ' + start + ' end=' + end);

                    let syllables = utils.getCache('syllables') || {};
                    let sylIdx = utils.getCache('resizeable-syl-id');

                    if (sylIdx === undefined) {
                        let newId = utils.getCache('next-syl-idx') || 0;
                        let newSyllable = {id: newId,
                            x0: start,
                            x1: end,
                            y0: 0,
                            y1: 1};
                        syllables[newId] = newSyllable;

                        viz.eventNotifier.trigger('segment-changed', {type: 'segment-created',
                            target: newSyllable});

                        utils.setCache('syllables', syllables);
                        window.appCache['next-syl-idx']++;

                        // Clear the brush right away
                        viz.spectBrush.extent([0, 0]);
                        viz.spectBrush(viz.spectrogramSvg.select('.spect-brush'));
                    }
                    else {
                        syllables[sylIdx].x0 = start;
                        syllables[sylIdx].x1 = end;

                        viz.eventNotifier.trigger('segment-changed', {
                            type: 'segment-adjusted',
                            target: syllables[sylIdx]
                        });

                    // We don't clear the brush here because it's likely that the user still want to re-adjust the syllable
                    }

                    viz.displaySegs(syllables);
                }
            });

        viz.spectrogramSvg.append('g').
            attr('class', 'spect-brush').
            call(viz.spectBrush).
            selectAll('rect').
            attr('height', viz.spectHeight);

        viz.spectrogramSvg.selectAll('.resize').
            append('path').
            attr('class', 'brush-handle').
            attr('cursor', 'ew-resize').
            attr('d', resizePath);
    };

    this.visualise = function (fileId, sig) {
        const viz = this;
        viz.margin = {top: 0,
            right: 0,
            bottom: 0,
            left: 0};

        /*
         * The file can be long so we must generate the spectrogram in chunks.
         * First we need to know how many frame will be generated as the final product.
         * Then create a canvas that can accommodate the entire image.
         * And then incrementally add frames to it
         */
        let segs = calcSegments(sig.length, nfft, noverlap);
        let imgWidth = segs.length;
        let imgHeight = nfft / 2;
        let fileLength = getCache('file-length');
        let fileFs = getCache('file-fs');
        let durationMs = fileLength * 1000 / fileFs;

        let spectXExtent = [0, durationMs];
        viz.spectXScale = d3.scale.linear().range([0, imgWidth]).domain(spectXExtent);
        viz.spectYScale = d3.scale.linear().range([0, imgHeight]).domain([0, 1]);

        viz.imgHeight = imgHeight;
        viz.imgWidth = imgWidth;

        viz.spectWidth = $(viz.spectrogramId).width() - viz.margin.left - viz.margin.right;
        viz.spectHeight = $(viz.spectrogramId).height() - viz.margin.top - viz.scrollbarHeight;

        viz.spectrogramSvg = d3.select(viz.spectrogramId).append('svg');
        viz.spectrogramSvg.
            attr('height', viz.spectHeight + viz.margin.top + viz.margin.bottom).
            attr('width', viz.imgWidth + viz.margin.left + viz.margin.right);

        viz.spectrogramSpects = viz.spectrogramSvg.append('g').classed('spects', true);

        let chunks = calcSegments(segs.length, viz.spectWidth, 0);
        for (let i = 0; i < chunks.length; i++) {
            let chunk = chunks[i];
            let segBeg = chunk[0];
            let segEnd = chunk[1];
            let subSegs = segs.slice(segBeg, segEnd);
            displaySpectrogram(viz, sig, subSegs, segBeg);
        }
        viz.drawBrush();
    };

    this.clearAllSegments = function (callback) {
        let viz = this;
        if (viz.spectrogramSvg) {
            viz.spectrogramSvg.selectAll('rect.syllable').remove();
        }
        if (typeof callback === 'function') {
            callback();
        }
    };

    /**
     *
     * @param syllables an array of dict having these keys: {start_time_ms, end_time_ms, id}
     * @param eventHandler
     */
    this.displaySegs = function (syllables) {
        let viz = this;
        viz.clearAllSegments();

        for (let sylIdx in syllables) {
            if (Object.prototype.hasOwnProperty.call(syllables, sylIdx)) {
                let syl = syllables[sylIdx];
                let beginMs = syl.start_time_ms;
                let endMs = syl.end_time_ms;

                let x = viz.spectXScale(beginMs);
                let width = viz.spectXScale(endMs - beginMs);

                viz.spectrogramSvg.append('rect').
                    attr('class', 'syllable').
                    attr('syl-id', syl.id).
                    attr('begin', beginMs).
                    attr('end', endMs).
                    attr('x', x).
                    attr('y', 0).
                    attr('height', viz.spectHeight).
                    attr('width', width);
            }
        }

        /*
         * Attach (once) the following behaviours to each syllables:
         * + On click, play the enclosed owner of audio.
         * + On mouse over, draw the brush and the boundary handlers so that the syllable can be adjusted.
         * + On mouse leaving from the top or bottom of syllable rectangle, remove the brush
         *    If the mouse is leaving from either side, do nothing, because this will be handled by the boundary handlers.
         */
        $(viz.spectrogramId + ' .syllable').each(function (idx, el) {
            el = $(el);
            if (!el.hasClass('mouse-behaviour-attached')) {
                el.on('click', function (event) {
                    // Left click
                    let self = this;
                    if (event.which === 1) {
                        let begin = self.getAttribute('begin');
                        let end = self.getAttribute('end');

                        let fileId = getCache('file-id');
                        let data = new FormData();
                        data.append('file-id', fileId);

                        let args = {
                            url: getUrl('send-request', 'koe/get-segment-audio'),
                            postData: data,
                            cacheKey: fileId,
                            startSecond: begin / 1000,
                            endSecond: end / 1000
                        };
                        ah.queryAndPlayAudio(args);
                    }
                }).
                    on('mouseover', function () {
                        console.log('On mouse over');
                        let self = this;
                        let sylIdx = self.getAttribute('syl-id');
                        let syl = utils.getCache('syllables', sylIdx);
                        utils.setCache('resizeable-syl-id', sylIdx);

                        console.log('Current resizeable syllable index: ' + window.appCache['resizeable-syl-id']);

                        // $('#segment-table #' + thisId).addClass('highlight');

                        // define our brush extent to be begin and end of the syllable
                        // viz.spectBrush.extent([startSec, endSec]);
                        viz.spectBrush.extent([syl.start_time_ms, syl.end_time_ms]);

                        // now draw the brush to match our extent
                        viz.spectBrush(viz.spectrogramSvg.select('.spect-brush'));

                        // External process might be interested in this event too
                        viz.eventNotifier.trigger('segment-mouse', {type: 'segment-mouseover',
                            target: this});
                    }).
                    on('mouseleave', function (event) {
                        event.preventDefault();
                        let bbox = $(viz.spectrogramId)[0].getClientRects()[0];

                        /*
                     * Only clear the brush if the mouse if over the top or below the bottom.
                     * Right and left boundary are handled by the reside handlers.
                     */
                        let mouseY = event.originalEvent.clientY;
                        if (mouseY < bbox.top || mouseY > bbox.bottom) {
                            viz.spectBrush.extent([0, 0]);
                            viz.spectBrush(viz.spectrogramSvg.select('.spect-brush'));
                            utils.setCache('resizeable-syl-id', undefined);
                            console.log('1Current resizeable syllable index: ' + window.appCache['resizeable-syl-id']);
                        }

                        // External process might be interested in this event too
                        viz.eventNotifier.trigger('segment-mouse', {type: 'segment-mouseleave',
                            target: this});
                    });
                el.addClass('mouse-behaviour-attached');
            }
        });

        /*
         * Attached (once) the following behaviours to each boundary handlers:
         * + On mouse leave, clear the boundary, and check if the left mouse is clicked (which means the user is dragging
         *      the boundary to adjust the syllables, in which case do nothing else,
         *     otherwise this means the user is simply moving away from the current syllable, in which case the syllable's
         *      index needs to be cleared from the cache.
         */
        $('.spect-brush .resize').each(function (idx, el) {
            el = $(el);
            if (!el.hasClass('mouse-behaviour-attached')) {
                el.on('mouseleave', function (event) {
                    event.preventDefault();

                    // Clear the brush right away
                    viz.spectBrush.extent([0, 0]);
                    viz.spectBrush(viz.spectrogramSvg.select('.spect-brush'));

                    /*
                     * If the left mouse button is pressed, this is a resize, so keep the index of the resizeable syllable,
                     * otherwise erase it.
                     */
                    if (event.originalEvent.buttons === 0) {
                        utils.setCache('resizeable-syl-id', undefined);
                        console.log('2Current resizeable syllable index: ' + window.appCache['resizeable-syl-id']);
                    }
                });
                el.addClass('mouse-behaviour-attached');
            }
        });

    };
};
