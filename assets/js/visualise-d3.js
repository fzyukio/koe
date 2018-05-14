/* eslint consistent-this: off, no-console: off */
const FFT = require('fft.js');
import d3 from './d3-importer';
import {stopAudio, queryAndPlayAudio} from './audio-handler';
import {defaultCm} from './colour-map';

import {getUrl, getCache, calcSegments, setCache, uuid4, debug, noop} from './utils';
import {transposeFlipUD, calcSpect} from './dsp';

const nfft = 256;
const noverlap = nfft * 3 / 4;

// (200ms per tick)
const tickInterval = 200;
const globalMinSpectPixel = -139;
const globalMaxSpectPixel = 43;
const {rPixelValues, gPixelValues, bPixelValues} = defaultCm;
const standardLength = 0.3 * 48000;


/**
 * Converts segment of a signal into spectrogram and displays it.
 * Keep in mind that the spectrogram's SVG contaims multiple images next to each other.
 * This function should be called multiple times to generate the full spectrogram
 * @param imgHeight
 * @param sig full audio signal
 * @param segs the segment indices to be turned into spectrogram
 * @param fft
 * @param contrast
 */
function displaySpectrogram(imgHeight, sig, segs, fft, contrast) {
    let subImgWidth = segs.length;
    return new Promise(function (resolve) {
        let img = new Image();
        let cacheKey = `${segs[0][0]} -- ${segs[segs.length - 1][1]}`;
        img.onload = function () {
            let spect = getCache('spect', cacheKey);
            if (spect === undefined) {
                spect = transposeFlipUD(calcSpect(sig, segs, fft));
                setCache('spect', cacheKey, spect);
            }
            let canvas = document.createElement('canvas');
            let context = canvas.getContext('2d');
            let imgData = context.createImageData(subImgWidth, imgHeight);

            canvas.height = imgHeight;
            canvas.width = subImgWidth;

            spectToCanvas(spect, imgData, globalMinSpectPixel, globalMaxSpectPixel, contrast);
            context.putImageData(imgData, 0, 0);
            resolve(canvas.toDataURL('image/webp', 1));
        };

        // This data URI is a dummy one, use it to trigger onload()
        img.src = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z/C/HgAGgwJ/lK3Q6wAAAABJRU5ErkJggg==';
    });
}


/**
 * Convert a given a spectrogram (power spectral density 2D array), put it on the canvas
 * @param spect a 2D FloatArray
 * @param imgData the imageData of the canvas to be written to
 * @param dspMin
 * @param dspMax
 * @param contrast
 */
const spectToCanvas = function (spect, imgData, dspMin, dspMax, contrast = 0) {

    /*
     * Some checking: spect and canvas must have the same size
     */
    let height = spect.length;
    let width = spect[0].length;

    if (height != imgData.height || width != imgData.width) throw new Error('Spect and canvas must have the same size');

    const colouredInterval = 64;
    const nIntervals = colouredInterval + contrast - 1;

    const dspBinValue = (dspMax - dspMin) / (nIntervals - 1);
    const round = Math.round;

    const spectrumFlatened = spect.reduce(function (p, c) {
        return p.concat(c);
    });

    // fill imgData with colors from array
    let i,
        k = 0,
        psd, colourMapIndex;
    for (i = 0; i < spectrumFlatened.length; i++) {
        psd = spectrumFlatened[i];
        if (isNaN(psd)) {
            colourMapIndex = 0;
        }
        else {
            colourMapIndex = round(Math.max(0, psd - dspMin) / dspBinValue) - contrast;
            if (colourMapIndex < 0) colourMapIndex = 0;
        }
        imgData.data[k++] = rPixelValues[colourMapIndex];
        imgData.data[k++] = gPixelValues[colourMapIndex];
        imgData.data[k++] = bPixelValues[colourMapIndex];

        // Alpha channel
        imgData.data[k++] = 255;
    }
};


export const visualiseSpectrogram = function (spectrogramSpects, spectHeight, spectWidth, imgHeight, imgWidth, sig, contrast, _noverlap = noverlap) {
    let segs = calcSegments(sig.length, nfft, _noverlap);
    let chunks = calcSegments(segs.length, spectWidth, 0, true);
    let fft = new FFT(nfft);

    chunks.forEach(function (chunk) {
        if (spectrogramSpects.select(`image.offset${chunk[0]}`).empty()) {
            spectrogramSpects.append('image').attr('class', `offset${chunk[0]}`);
        }
    });

    chunks.reduce(function (promiseChain, chunk) {
        let nextPromise = promiseChain.then(function () {
            let segBeg = chunk[0];
            let segEnd = chunk[1];
            let subSegs = segs.slice(segBeg, segEnd);
            let subImgWidth = subSegs.length;
            let promise = displaySpectrogram(imgHeight, sig, subSegs, fft, contrast);
            promise.then(function (dataURI) {
                let img = spectrogramSpects.select(`image.offset${segBeg}`);
                img.attr('height', imgHeight);
                img.attr('width', subImgWidth);
                img.attr('x', segBeg);
                img.attr('xlink:href', dataURI);
                img.style('transform', `scaleY(${spectHeight / imgHeight})`);
            });
        });
        return (nextPromise);
    }, Promise.resolve());
};


export const Visualise = function () {
    this.init = function (oscillogramId, spectrogramId) {
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
        viz.scrollbarHeight = 0;
        viz.axisHeight = 20;
        viz.spectrogramId = spectrogramId;
        viz.oscillogramId = oscillogramId;
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

        let resizePath = function (args) {
            // Style the brush resize handles (copied-pasted code. Don't ask what the letiables mean).
            let e = Number(args.type === 'e'),
                x = e ? 1 : -1,
                y = viz.spectHeight / 3;
            return `M${0.5 * x},${y}A6,6 0 0 ${e} ${6.5 * x},${y + 6}V${2 * y - 6}A6,6 0 0 ${e} ${0.5 * x},${2 * y}ZM${2.5 * x},${y + 8}V${2 * y - 8}M${4.5 * x},${y + 8}V${2 * y - 8}`;
        };

        viz.spectBrush = d3.brushX();
        viz.spectBrush.extent([[viz.spectXScale.domain()[0], 0], [viz.spectXScale.domain()[1], viz.spectHeight]]);

        viz.spectBrush.on('start', function () {
            viz.spectHandle.attr('display', 'unset');
            if (!d3.event.sourceEvent) return;
            console.log('on brushstart');
        }).on('brush', function () {
            let endpoints = d3.event.selection;
            if (endpoints === null) return;

            viz.spectHandle.attr('transform', function (d, i) {
                return `translate(${endpoints[i]}, 0)`;
            });
        }).on('end', function () {
            if (!d3.event.sourceEvent) return;
            console.log('on brushend');
            if (d3.event.selection === null) {

                /*
                 * Remove the brush means that no syllable is currently resizable
                 */
                setCache('resizeable-syl-id', undefined, undefined);
                debug('Current resizeable syllable index: ' + window.appCache['resizeable-syl-id']);
            }
            else {
                let endpoints = d3.event.selection.map(viz.spectXScale.invert);
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

                    setCache('syllables', undefined, syllables);

                    // Clear the brush right away
                    viz.clearBrush();
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

        viz.spectBrushEl = viz.spectrogramSvg.append('g').attr('class', 'spect-brush');
        viz.spectBrushEl.call(viz.spectBrush);

        viz.spectHandle = viz.spectBrushEl.selectAll('.brush-handle').data([{type: 'w'}, {type: 'e'}]).enter().append('path').attr('class', 'brush-handle').attr('d', resizePath).attr('cursor', 'ew-resize').attr('cursor', 'ew-resize').attr('display', 'none');

    };

    this.zoomInSyllable = function (item, sig, contrast) {
        const viz = this;

        let fileLength = getCache('file-length');
        let fileFs = getCache('file-fs');
        let durationMs = fileLength * 1000 / fileFs;
        let itemStartMs = item.start;
        let itemEndMs = item.end;
        let itemDurationMs = itemEndMs - itemStartMs;


        let sigStart = Math.ceil(itemStartMs / durationMs * sig.length);
        let sigEnd = Math.floor(itemEndMs / durationMs * sig.length);
        let subSig = sig.subarray(sigStart, sigEnd);

        viz.showZoomedOscillogram(subSig, fileFs);

        let _nfft = nfft;
        let _noverlap = _nfft * 7 / 8;
        let fft = new FFT(nfft);

        let segs = calcSegments(subSig.length, _nfft, _noverlap);
        let imgWidth = segs.length;
        let imgHeight = _nfft / 2;

        let spectZoomSvg = d3.select('#spectrogram-zoomed');
        spectZoomSvg.selectAll('g').remove();

        let spectWidth = $('#spectrogram-zoomed').width() - viz.margin.left - viz.margin.right;
        let spectHeight = $('#spectrogram-zoomed').height() - viz.margin.top - viz.scrollbarHeight - viz.axisHeight;

        spectZoomSvg.attr('height', spectHeight + viz.margin.top + viz.margin.bottom);
        spectZoomSvg.attr('width', spectWidth + viz.margin.left + viz.margin.right);

        /*
         * Show the time axis under the spectrogram. Draw one tick per interval (default 200ms per click)
         */
        let spectXExtent = [itemStartMs, itemEndMs];
        let spectXScale = d3.scaleLinear().range([0, spectWidth]).domain(spectXExtent);
        let numTicks = itemDurationMs / tickInterval * 3;
        let xAxis = d3.axisBottom().scale(spectXScale).ticks(numTicks);

        let spectrogramSpects = spectZoomSvg.append('g').classed('spects', true);

        let spectrogramAxis = spectZoomSvg.append('g');
        spectrogramAxis.attr('class', 'x axis');
        spectrogramAxis.attr('transform', 'translate(0,' + spectHeight + ')');
        spectrogramAxis.call(xAxis);

        let promise = displaySpectrogram(imgHeight, subSig, segs, fft, contrast);
        let subImgWidth = segs.length;
        promise.then(function (dataURI) {
            let img = spectrogramSpects.append('image');
            img.attr('height', imgHeight);
            img.attr('width', subImgWidth);
            img.attr('x', 0);
            img.attr('xlink:href', dataURI);
            img.style('transform', `scale(${spectWidth / imgWidth}, ${spectHeight / imgHeight})`);
        });
    };

    this.showZoomedOscillogram = function (sig, fs) {
        let viz = this;
        let length = sig.length;
        let data = [];
        let minY = 99999;
        let maxY = -99999;
        let y;
        for (let i = 0; i < length; i++) {
            y = sig[i];
            data.push({
                x: i / fs,
                y
            });
            if (minY > y) minY = y;
            if (maxY < y) maxY = y;
        }

        let elId = viz.oscillogramId + '-zoomed';

        let oscilloWidth = $(elId).width() - viz.margin.left - viz.margin.right;
        let oscilloHeight = $(elId).height() - viz.margin.top;

        let oscillogramSvg = d3.select(elId);
        oscillogramSvg.attr('width', oscilloWidth);
        oscillogramSvg.attr('height', oscilloHeight);

        let xScale = d3.scaleLinear().range([0, oscilloWidth]).domain([0, length / fs]);
        let yScale = d3.scaleLinear().domain([minY, maxY]).nice().range([oscilloHeight, 0]);

        let plotLine = d3.line().x(function (d) {
            return xScale(d.x);
        }).y(function (d) {
            return yScale(d.y);
        });
        oscillogramSvg.selectAll('path').remove();
        oscillogramSvg.append('path').attr('class', 'line').attr('d', plotLine(data));
    };

    this.showOscillogram = function (sig, fs) {
        let viz = this;
        let length = sig.length;
        let data = [];
        let resampleFactor = Math.max(1, Math.min(80, Math.round(length / standardLength)));
        console.log(`resampleFactor = ${resampleFactor}`);
        let minY = 99999;
        let maxY = -99999;
        let y;
        for (let i = 0; i < length; i += resampleFactor) {
            y = sig[i];
            data.push({
                x: i / fs,
                y
            });
            if (minY > y) minY = y;
            if (maxY < y) maxY = y;
        }

        viz.oscilloWidth = $(viz.oscillogramId).width() - viz.margin.left - viz.margin.right;
        viz.oscilloHeight = $(viz.oscillogramId).height() - viz.margin.top;

        viz.oscillogramSvg = d3.select(viz.oscillogramId);
        viz.oscillogramSvg.attr('width', viz.imgWidth);
        viz.oscillogramSvg.attr('height', viz.oscilloHeight);

        let xScale = d3.scaleLinear().range([0, viz.imgWidth]).domain([0, length / fs]);
        let yScale = d3.scaleLinear().domain([minY, maxY]).nice().range([viz.oscilloHeight, 0]);

        let plotLine = d3.line().x(function (d) {
            return xScale(d.x);
        }).y(function (d) {
            return yScale(d.y);
        });

        viz.oscillogramSvg.append('path').attr('class', 'line').attr('d', plotLine(data));
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
        viz.spectXScale = d3.scaleLinear().range([0, imgWidth]).domain(spectXExtent);

        viz.imgHeight = imgHeight;
        viz.imgWidth = imgWidth;

        viz.spectWidth = $(viz.spectrogramId).width() - viz.margin.left - viz.margin.right;
        viz.spectHeight = $(viz.spectrogramId).height() - viz.margin.top - viz.scrollbarHeight - viz.axisHeight;

        viz.showOscillogram(sig, fileFs);

        viz.spectrogramSvg = d3.select(viz.spectrogramId);
        viz.spectrogramSvg.attr('height', viz.spectHeight + viz.margin.top + viz.margin.bottom);
        viz.spectrogramSvg.attr('width', viz.imgWidth + viz.margin.left + viz.margin.right);

        /*
         * Show the time axis under the spectrogram. Draw one tick per interval (default 200ms per click)
         */
        let numTicks = durationMs / tickInterval;
        let xAxis = d3.axisBottom().scale(viz.spectXScale).ticks(numTicks);

        viz.spectrogramAxis = viz.spectrogramSvg.append('g');
        viz.spectrogramAxis.attr('class', 'x axis');
        viz.spectrogramAxis.attr('transform', 'translate(0,' + viz.spectHeight + ')');
        viz.spectrogramAxis.call(xAxis);

        /* Remove the first tick at time = 0 (ugly) */
        viz.spectrogramAxis.selectAll('.tick').filter((d) => d === 0).remove();

        viz.spectrogramSpects = viz.spectrogramSvg.append('g').classed('spects', true);


        viz.spectrogramSvg.append('line').attr('class', 'playback-indicator').
            attr('x1', 0).attr('y1', 0).
            attr('x2', 1).
            attr('y2', viz.spectHeight).
            style('stroke-width', 2).
            style('stroke', 'black').
            style('fill', 'none').
            style('display', 'none');

        viz.oscillogramSvg.append('line').attr('class', 'playback-indicator').
            attr('x1', 0).attr('y1', 0).
            attr('x2', 1).
            attr('y2', viz.oscilloHeight).
            style('stroke-width', 2).
            style('stroke', 'black').
            style('fill', 'none').
            style('display', 'none');

        viz.playbackIndicator = d3.selectAll('.playback-indicator');

        visualiseSpectrogram(viz.spectrogramSpects, viz.spectHeight, viz.spectWidth, viz.imgHeight, viz.imgWidth, sig);

        viz.drawBrush()
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
     * @param begin
     * @param end
     * @param onStartCallback
     * @param stopScrolling
     */
    this.playAudio = function (begin = 0, end = 'end', onStartCallback = noop, stopScrolling = noop) {
        let viz = this;
        let fileId = getCache('file-id');

        let startX = viz.spectXScale(begin);
        if (end === 'end') {
            end = viz.spectXScale.domain()[1];
        }

        let endX = viz.spectXScale(end);
        let endSec = end / 1000;
        let durationMs = end - begin;

        let args = {
            url: getUrl('send-request', 'koe/get-file-audio-data'),
            postData: {'file-id': fileId},
            cacheKey: fileId,
            playAudioArgs: {
                beginSec: begin / 1000,
                endSec,
                onStartCallback (playbackSpeed) {
                    let durationAtSpeed = durationMs * 100 / playbackSpeed;

                    viz.playbackIndicator.interrupt();
                    viz.playbackIndicator.style('display', 'unset').attr('transform', `translate(${startX}, 0)`);

                    let transition = viz.playbackIndicator.transition();
                    transition.attr('transform', `translate(${endX}, 0)`);
                    transition.duration(durationAtSpeed);
                    transition.ease(d3.easeLinear);

                    onStartCallback(startX, endX, durationAtSpeed);
                },
                onEndedCallback () {
                    viz.playbackIndicator.interrupt();
                    viz.playbackIndicator.style('display', 'none');
                    stopScrolling();
                }
            }
        };
        queryAndPlayAudio(args);
    };

    /**
     * Play the syllable where mouse left click was registered
     * @param begin
     * @param end
     */
    this.stopAudio = function () {
        let viz = this;
        viz.playbackIndicator.interrupt();
        stopAudio();
    };

    /**
     * Show the brush include its resize handles.
     * @param sylIdx index of the syllable where the brush should appear
     */
    this.showBrush = function (sylIdx) {
        let viz = this;
        let resizing = getCache('resizeable-syl-id');
        if (resizing && viz.editMode) {
            console.log(`Currently editing another segment, ignore. resizing = ${resizing}`);
            return;
        }

        let syl = getCache('syllables', sylIdx);
        setCache('resizeable-syl-id', undefined, sylIdx);

        // define our brush extent to be begin and end of the syllable
        // viz.spectBrush.extent([syl.start, syl.end]);
        viz.spectBrush.move(viz.spectrogramSvg.select('.spect-brush'), [syl.start, syl.end].map(viz.spectXScale));

        // now draw the brush to match our extent
        // viz.spectBrush(viz.spectrogramSvg.select('.spect-brush'));
    };

    /**
     * Clear the brush include its resize handles.
     */
    this.clearBrush = function () {
        let viz = this;
        viz.spectBrush.move(viz.spectrogramSvg.select('.spect-brush'), null);
        viz.spectHandle.attr('display', 'none');
        setCache('resizeable-syl-id', undefined, undefined);
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
        setCache('highlighted-syl-id', undefined, sylIdx);

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
        let resizing = getCache('resizeable-syl-id');
        if (resizing && viz.editMode) {
            console.log('Currently editing another segment, ignore');
            return;
        }

        setCache('highlighted-syl-id', undefined, undefined);
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
                el.on(
                    'click',
                    function (e) {
                        let self = this;
                        // Left click
                        if (e.which === 1) {
                            let begin = self.getAttribute('begin');
                            let end = self.getAttribute('end');
                            viz.playAudio(begin, end);
                        }
                    }
                );
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
