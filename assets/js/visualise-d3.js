/* eslint consistent-this: off, no-console: off */
let d3 = require('d3/d3.js');
require('jquery-contextmenu');

import {getUrl, getCache, calcSegments, setCache, uuid4, debug} from './utils';
import * as DSP from './dsp';
import * as ah from 'audio-handler'

const nfft = 256;
const noverlap = nfft * 3 / 4;

// (200ms per tick)
const tickInterval = 200;

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
        viz.spectrogramSpects.append('image').attr('height', viz.imgHeight).attr('width', subImgWidth).attr('x', offset).attr('xlink:href', dataURI).style('transform', `scaleY(${viz.spectHeight / viz.imgHeight})`);
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
        viz.axisHeight = 30;
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
            // let e = Number(d === 'e'),
            //     x = e ? 1 : -1,
            //     h = viz.spectHeight;
            // return `M${0.5 * x} 1 A 6 6 0 0 ${e} ${6.5 * x}, 6 V${h - 6}A6,6 0 0 ${e} ${0.5 * x},${h}ZM${2.5 * x},${8}V${h - 8}M${4.5 * x},${8}V${h - 8}`;
        };

        viz.spectBrush = d3.svg.brush().x(viz.spectXScale).
            on('brushstart', function () {
                console.log('on brushstart');
            }).
            on('brushend', function () {
                console.log('on brushend');
                if (viz.spectBrush.empty()) {

                /*
                 * Remove the brush means that no syllable is currently resizable
                 */
                    setCache('resizeable-syl-id', undefined);
                    debug('Current resizeable syllable index: ' + window.appCache['resizeable-syl-id']);
                }
                else {
                    let endpoints = viz.spectBrush.extent();
                    let start = Math.floor(endpoints[0]);
                    let end = Math.ceil(endpoints[1]);

                    console.log('start= ' + start + ' end=' + end);

                    let syllables = getCache('syllables') || {};
                    let sylIdx = getCache('resizeable-syl-id');

                    if (sylIdx === undefined) {
                        let newId = `new:${uuid4()}`;
                        let newSyllable = {
                            id: newId,
                            start,
                            end,
                        };
                        syllables[newId] = newSyllable;

                        viz.eventNotifier.trigger('segment-changed', {
                            type: 'segment-created',
                            target: newSyllable
                        });

                        setCache('syllables', syllables);

                        // Clear the brush right away
                        viz.spectBrush.extent([0, 0]);
                        viz.spectBrush(viz.spectrogramSvg.select('.spect-brush'));
                    }
                    else {
                        syllables[sylIdx].start = start;
                        syllables[sylIdx].end = end;

                        viz.eventNotifier.trigger('segment-changed', {
                            type: 'segment-adjusted',
                            target: syllables[sylIdx]
                        });
                    }

                    viz.displaySegs(syllables);
                }
            });

        viz.spectrogramSvg.append('g').attr('class', 'spect-brush').call(viz.spectBrush).selectAll('rect').attr('height', viz.spectHeight);

        viz.spectrogramSvg.selectAll('.resize').append('path').attr('class', 'brush-handle').attr('cursor', 'ew-resize').attr('d', resizePath);
    };

    this.visualise = function (fileId, sig) {
        const viz = this;
        viz.margin = {
            top: 0,
            right: 0,
            bottom: viz.axisHeight,
            left: 0
        };

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
        viz.spectHeight = $(viz.spectrogramId).height() - viz.margin.top - viz.scrollbarHeight - viz.axisHeight;

        viz.spectrogramSvg = d3.select(viz.spectrogramId).append('svg');
        viz.spectrogramSvg.attr('height', viz.spectHeight + viz.margin.top + viz.margin.bottom);
        viz.spectrogramSvg.attr('width', viz.imgWidth + viz.margin.left + viz.margin.right);

        /*
         * Show the time axis under the spectrogram. Draw one tick per interval (default 200ms per click)
         */
        let numTicks = durationMs / tickInterval;
        let xAxis = d3.svg.axis().scale(viz.spectXScale).orient('bottom').ticks(numTicks);

        viz.spectrogramAxis = viz.spectrogramSvg.append('g');
        viz.spectrogramAxis.attr('class', 'x axis');
        viz.spectrogramAxis.attr('transform', 'translate(0,' + viz.spectHeight + ')');
        viz.spectrogramAxis.call(xAxis);

        /* Remove the first tick at time = 0 (ugly) */
        viz.spectrogramAxis.selectAll('.tick').filter((d) => d === 0).remove();

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

    /**
     * Remove all rect elements on the spectrogram
     * @param callback
     */
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
     * Play the syllable where mouse left click was registered
     * @param event the mouse click event
     */
    function playAudio(event) {
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
    }

    /**
     * Show the brush include its resize handles.
     * @param sylIdx index of the syllable where the brush should appear
     */
    this.showBrush = function (sylIdx) {
        let viz = this;
        let syl = getCache('syllables', sylIdx);
        setCache('resizeable-syl-id', sylIdx);

        // define our brush extent to be begin and end of the syllable
        viz.spectBrush.extent([syl.start, syl.end]);

        // now draw the brush to match our extent
        viz.spectBrush(viz.spectrogramSvg.select('.spect-brush'));
    };

    /**
     * Clear the brush include its resize handles.
     */
    this.clearBrush = function () {
        let viz = this;
        viz.spectBrush.extent([0, 0]);
        viz.spectBrush(viz.spectrogramSvg.select('.spect-brush'));
        setCache('resizeable-syl-id', undefined);
    };

    /**
     * When a syllable on spectrogram is on mouseover, highlight the rect element and store its ID on the cache.
     * If the Ctrl button is being pressed, display the brush to allow user to change the syllable as well
     *
     * @param element the HTML element (rect) where mouse event occurs
     * @param viz an instance of Visualise
     */
    function highlightSpectrogramSegment(element, viz) {
        let sylIdx = element.getAttribute('syl-id');
        setCache('highlighted-syl-id', sylIdx);

        if (viz.editMode) {
            viz.showBrush(sylIdx);
        }
        // External process might be interested in this event too
        viz.eventNotifier.trigger('segment-mouse', {
            type: 'segment-mouseover',
            target: element
        });
    }

    /**
     * When a syllable on spectrogram is on mouseleave, clear the highlight and erase its ID from the cache.
     * But we don't clear the brush. The brush is only cleared when the Ctrl button is unpressed.
     *
     * @param element the HTML element (rect) where mouse event occurs
     * @param viz an instance of Visualise
     */
    function clearSpectrogramHighlight(element, viz) {
        setCache('highlighted-syl-id', undefined);
        if (viz.editMode) {
            console.log('Edit mode on and not highlighted. Keep brush');
        }
        // External process might be interested in this event too
        viz.eventNotifier.trigger('segment-mouse', {
            type: 'segment-mouseleave',
            target: element
        });
    }

    /**
     *
     * @param syllables an array of dict having these keys: {start, end, id}
     */
    this.displaySegs = function (syllables) {
        let viz = this;
        viz.clearAllSegments();

        for (let sylIdx in syllables) {
            if (Object.prototype.hasOwnProperty.call(syllables, sylIdx)) {
                let syl = syllables[sylIdx];
                let beginMs = syl.start;
                let endMs = syl.end;

                let x = viz.spectXScale(beginMs);
                let width = viz.spectXScale(endMs - beginMs);

                let rect = viz.spectrogramSvg.append('rect');
                rect.attr('class', 'syllable');
                rect.attr('syl-id', syl.id);
                rect.attr('begin', beginMs);
                rect.attr('end', endMs);
                rect.attr('x', x).attr('y', 0);
                rect.attr('height', viz.spectHeight);
                rect.attr('width', width);
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
                el.on('click', playAudio);
                el.on('mouseover', function () {
                    highlightSpectrogramSegment(this, viz);
                });
                el.on('mouseleave', function () {
                    clearSpectrogramHighlight(this, viz);
                });
                el.addClass('mouse-behaviour-attached');
            }
        });
    };
};
