/* global d3*/
/* eslint consistent-this: off, no-console: off */
import {spectToUri} from './visual-utils';

const FFT = require('fft.js');

import {stopAudio, playAudioDataArray} from './audio-handler';

import {getCache, calcSegments, setCache, uuid4, debug, noop} from './utils';
import {transposeFlipUD, calcSpect} from './dsp';

const nfft = 256;
const noverlap = 0;

// (400ms per tick)
const tickInterval = 400;
const standardLength = 0.3 * 48000;


// Grab the head of the promise chain for cancellation purpose
let visualisationPromiseChainHead;
const visualisationContainer = $('#track-visualisation');
let imagesAreInitialised = false;
let currentImageIndex = 0;
const spectRenderingStatus = {};

const stateEmpty = 0;
const stateScheduled = 1;
const stateBeforeCalculation = 2;
const stateCalculated = 3;
const stateBeforeDisplaying = 4;
const stateDisplayed = 5;

export const Visualise = function () {
    this.visualiseSpectrogram = function (sig, _noverlap = noverlap) {
        const viz = this;
        const segs = calcSegments(sig.length, nfft, _noverlap);
        const chunks = calcSegments(segs.length, viz.spectWidth, 0, true);
        const lastChunkIdx = chunks.length - 1;
        const fft = new FFT(nfft);
        const visibleWidth = visualisationContainer.width();
        const numberOfImages = Math.floor(visibleWidth / viz.spectWidth) * 10;

        const displayAsPromises = function (centerIdx) {
            let start = Math.max(0, centerIdx - numberOfImages);
            let end = Math.min(lastChunkIdx, centerIdx + numberOfImages);

            let sliced = [];
            for (let i = start; i <= end; i++) {
                let segBeg = chunks[i][0];
                let renderStatus = spectRenderingStatus[segBeg];

                if (renderStatus.state !== stateDisplayed || renderStatus.contrast !== viz.contrast) {
                    renderStatus.contrast = viz.contrast;
                    renderStatus.state = stateScheduled;
                    sliced.push(chunks[i]);
                }
            }

            let toDelete = [];
            let needCancelled = false;
            for (let i = 0; i <= lastChunkIdx; i++) {
                if (i < start || i > end) {
                    let segBeg = chunks[i][0];
                    let renderStatus = spectRenderingStatus[segBeg];

                    if (renderStatus.state !== stateEmpty) {
                        renderStatus.spect = null;
                        toDelete.push(chunks[i]);
                        let state = renderStatus.state;
                        if (state === stateScheduled ||
                            state === stateBeforeCalculation ||
                            state === stateBeforeDisplaying) {
                            needCancelled = true;
                        }
                        renderStatus.state = stateEmpty;
                    }
                }
            }

            if (needCancelled && visualisationPromiseChainHead !== undefined) {
                visualisationPromiseChainHead.cancel();
                visualisationPromiseChainHead = undefined;
            }

            // If there are spects to be deleted, but they have not been rendered because the promise chain
            // is still running - then we must cancel the promise chain
            let deletePromises = toDelete.reduce(function (promiseChain, chunk) {
                let segBeg = chunk[0];
                let renderStatus = spectRenderingStatus[segBeg];
                return promiseChain.
                    then(function () {
                        renderStatus.state = stateEmpty;
                        debug(`Delete chunk: ${segBeg}`);
                        let img = viz.spectrogramSpects.select(`image[x="${segBeg}"]`);
                        img.attr('xlink:href', undefined);
                    });
            }, Promise.resolve());


            return sliced.reduce(function (promiseChain, chunk) {
                let segBeg = chunk[0];
                let segEnd = chunk[1];
                let subSegs = segs.slice(segBeg, segEnd);
                let renderStatus = spectRenderingStatus[segBeg];

                if (renderStatus.state === stateCalculated) {
                    return promiseChain;
                }

                return promiseChain.
                    then(function () {
                        let spect = renderStatus.spect;
                        if (spect === null) {
                            debug(`Calculate chunk: ${segBeg}`);
                            renderStatus.state = stateBeforeCalculation;
                            spect = transposeFlipUD(calcSpect(sig, subSegs, fft));
                            renderStatus.spect = spect;
                            renderStatus.state = stateCalculated;
                            return spect;
                        }
                        else if (renderStatus.state !== stateDisplayed) {
                            return spect;
                        }
                        return undefined;
                    }).
                    then(function (spect) {
                        if (spect) {
                            renderStatus.state = stateBeforeDisplaying;
                            return spectToUri(spect, viz.imgHeight, subSegs.length, viz.contrast);
                        }
                        return undefined;
                    }).
                    then(function (dataURI) {
                        if (dataURI) {
                            renderStatus.state = stateDisplayed;
                            let img = viz.spectrogramSpects.select(`image[x="${segBeg}"]`);
                            img.attr('xlink:href', dataURI);
                        }
                    });
            }, deletePromises);
        };

        if (!imagesAreInitialised) {
            chunks.forEach(function (chunk) {
                let segBeg = chunk[0];
                let segEnd = chunk[1];
                let subImgWidth = segEnd - segBeg;

                viz.spectrogramSpects.append('image').
                    attr('id', `spect-${segBeg}`).
                    attr('height', viz.imgHeight).
                    attr('width', subImgWidth).
                    attr('x', segBeg).
                    style('transform', `scaleY(${viz.spectHeight / viz.imgHeight})`);

                spectRenderingStatus[segBeg] = {
                    state: stateEmpty,
                    contrast: null,
                    spect: null
                }
            });

            setCache('spectRenderingStatus', undefined, spectRenderingStatus);

            visualisationContainer.scroll(function () {
                let cursorPosition = visualisationContainer.scrollLeft();
                let imageStartIndex = Math.floor(cursorPosition / viz.spectWidth);

                if (imageStartIndex !== currentImageIndex) {
                    currentImageIndex = imageStartIndex;
                    if (visualisationPromiseChainHead) {
                        visualisationPromiseChainHead.then(displayAsPromises(currentImageIndex));
                    }
                    else {
                        visualisationPromiseChainHead = displayAsPromises(currentImageIndex);
                    }
                }
            });

            imagesAreInitialised = true;
        }

        if (visualisationPromiseChainHead) {
            visualisationPromiseChainHead.then(displayAsPromises(currentImageIndex));
        }
        else {
            visualisationPromiseChainHead = displayAsPromises(currentImageIndex);
        }
    };


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
        viz.contrast = 0;

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
            debug('on brushstart');
        }).on('brush', function () {
            let endpoints = d3.event.selection;
            if (endpoints === null) return;

            viz.spectHandle.attr('transform', function (d, i) {
                return `translate(${endpoints[i]}, 0)`;
            });
        }).on('end', function () {
            if (!d3.event.sourceEvent) return;
            debug('on brushend');
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

                debug('start= ' + start + ' end=' + end);

                let syllables = getCache('syllables') || {};
                let sylIdx = getCache('resizeable-syl-id');

                if (sylIdx === undefined) {
                    let newId = `new:${uuid4()}`;
                    let newSyllable = {
                        id: newId,
                        start,
                        end,
                        duration: end - start,
                        name: uuid4()
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
                    syllables[sylIdx].duration = end - start;
                    syllables[sylIdx].progress = 'Changed';

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

    this.showOscillogram = function (sig, fs) {
        let viz = this;
        let length = sig.length;
        let data = [];
        let resampleFactor = Math.max(1, Math.min(1000, Math.round(length / standardLength)));
        debug(`resampleFactor = ${resampleFactor}`);
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

    this.visualise = function (sig, fs) {
        const viz = this;
        viz.originalSig = sig;
        viz.originalFs = fs;

        // let sigLength = sig.length;
        // let dsFactor = 2;
        // let dsLength = sigLength / dsFactor;
        // let dsFs = fs / dsFactor;
        // let dsSig = new sig.constructor(dsLength);

        // let i = 0,
        //     j = 0;
        // for (; i < dsLength;) {
        //     dsSig[i++] = sig[j += dsFactor];
        // }

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
        let fileLength = sig.length;
        let durationMs = fileLength * 1000 / fs;

        let spectXExtent = [0, durationMs];
        viz.spectXScale = d3.scaleLinear().range([0, imgWidth]).domain(spectXExtent);

        viz.imgHeight = imgHeight;
        viz.imgWidth = imgWidth;

        viz.spectWidth = $(viz.spectrogramId).height() - viz.margin.left - viz.margin.right;
        viz.spectHeight = $(viz.spectrogramId).height() - viz.margin.top - viz.scrollbarHeight - viz.axisHeight;

        viz.spectWidth = Math.round(viz.spectWidth);
        viz.spectWidth = Math.round(viz.spectWidth);

        viz.showOscillogram(sig, fs);

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


        viz.spectrogramSvg.append('line').attr('class', 'playback-indicator').attr('x1', 0).attr('y1', 0).attr('x2', 1).attr('y2', viz.spectHeight).style('stroke-width', 2).style('stroke', 'black').style('fill', 'none').style('display', 'none');

        viz.oscillogramSvg.append('line').attr('class', 'playback-indicator').attr('x1', 0).attr('y1', 0).attr('x2', 1).attr('y2', viz.oscilloHeight).style('stroke-width', 2).style('stroke', 'black').style('fill', 'none').style('display', 'none');

        viz.playbackIndicator = d3.selectAll('.playback-indicator');

        viz.visualiseSpectrogram(sig);

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
        let startX = viz.spectXScale(begin);
        if (end === 'end') {
            end = viz.spectXScale.domain()[1];
        }

        let endX = viz.spectXScale(end);
        let endSec = end / 1000;
        let durationMs = end - begin;

        let playAudioArgs = {
            beginSec: begin / 1000,
            endSec,
            onStartCallback(playbackSpeed) {
                let durationAtSpeed = durationMs * 100 / playbackSpeed;

                viz.playbackIndicator.interrupt();
                viz.playbackIndicator.style('display', 'unset').attr('transform', `translate(${startX}, 0)`);

                let transition = viz.playbackIndicator.transition();
                transition.attr('transform', `translate(${endX}, 0)`);
                transition.duration(durationAtSpeed);
                transition.ease(d3.easeLinear);

                onStartCallback(startX, endX, durationAtSpeed);
            },
            onEndedCallback() {
                viz.playbackIndicator.interrupt();
                viz.playbackIndicator.style('display', 'none');
                stopScrolling();
            }
        };
        playAudioDataArray(viz.originalSig, viz.originalFs, playAudioArgs);
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
            debug(`Currently editing another segment, ignore. resizing = ${resizing}`);
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
            debug('Currently editing another segment, ignore');
            return;
        }

        setCache('highlighted-syl-id', undefined, undefined);
        if (viz.editMode) {
            debug('Edit mode on and not highlighted. Keep brush');
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
