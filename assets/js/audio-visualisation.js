/* global d3*/
/* eslint no-console: off */
const FFT = require('fft.js');
import {spectToUri, globalMinSpectPixel, globalMaxSpectPixel} from './visual-utils';
import {stopAudio, playAudioDataArray} from './audio-handler';
import {getCache, calcSegments, setCache, uuid4, debug, smoothScrollTo, deepCopy} from './utils';
import {transposeFlipUD, calcSpect} from './dsp';

const stateEmpty = 0;
const stateScheduled = 1;
const stateBeforeCalculation = 2;
const stateCalculated = 3;
const stateBeforeDisplaying = 4;
const stateDisplayed = 5;

const defaultNfft = 256;

const contrastSlider = $('#contrast-slider');
const playSongBtn = $('#play-song');
const pauseSongBtn = $('#pause-song');
const stopSongBtn = $('#stop-song');
const resumeSongBtn = $('#resume-song');
const zoomOptions = $('.select-zoom');
const zoomBtnText = $('#zoom-btn-text');
const cmOptions = $('.select-cm');
const cmBtnText = $('#cm-btn-text');

let startPlaybackAt;
let playbackSpeed;
let playedDuration;

/**
 * Style the brush resize handles (copied-pasted code. Don't ask what the variables mean).
 * @param args
 * @returns {string}
 */
function resizePath(args) {
    let e = Number(args.type === 'e'),
        x = e ? 1 : -1,
        y = args.spectHeight / 3;
    return `M${0.5 * x},${y}A6,6 0 0 ${e} ${6.5 * x},${y + 6}V${2 * y - 6}A6,6 0 0 ${e} ${0.5 * x},${2 * y}ZM${2.5 * x},${y + 8}V${2 * y - 8}M${4.5 * x},${y + 8}V${2 * y - 8}`;
}

export class Visualiser {
    static get defaultArgs() {
        return {
            noverlap: 0,
            contrast: 0,
            colourMap: 'Green',
            zoom: 100
        }
    }

    constructor(vizContainerId) {
        this.spectrogramSvg = null;
        this.spectWidth = null;
        this.spectHeight = null;
        this.margin = null;
        this.height = null;
        this.width = null;
        this.spectXScale = null;
        this.scrollbarHeight = 0;
        this.axisHeight = 20;
        this.vizContainerId = vizContainerId;
        this.$vizContainer = $(vizContainerId);
        this.spectrogramId = `${vizContainerId} #spectrogram`;
        this.oscillogramId = `${vizContainerId} #oscillogram`;
        this.$spectrogram = $(this.spectrogramId);
        this.scrollingPromise = null;
        this.visualisationEl = this.$vizContainer[0];

        this.spectBrush = null;
        this.visibleWidth = this.$spectrogram.width();

        this.segs = null;
        this.chunks = null;
        this.lastChunkIdx = null;
        this.fft = null;
        this.numberOfImages = null;
        this.currentImageIndex = 0;
        this.sig = null;
        this.fs = null;

        this.minSpect = globalMinSpectPixel;
        this.maxSpect = globalMaxSpectPixel;

        this.scrollingTimer = null;

        // Grab the head of the promise chain for cancellation purpose
        this.visualisationPromiseChainHead = null;
        this.imagesAreInitialised = false;
        this.spectRenderingStatus = {};


        this.margin = {
            top: 0,
            right: 0,
            bottom: this.axisHeight,
            left: 0
        };

        this.spectWidth = this.$spectrogram.height() - this.margin.left - this.margin.right;
        this.spectHeight = this.$spectrogram.height() - this.margin.top - this.scrollbarHeight - this.axisHeight;

        this.spectWidth = Math.round(this.spectWidth);
        this.spectWidth = Math.round(this.spectWidth);

        this.oscilloHeight = $(this.oscillogramId).height() - this.margin.top;

        /**
         * All events of the file browser will be broadcast via this mock element
         * @type {*}
         */
        this.eventNotifier = $(document.createElement('div'));
    }

    /**
     * {zoom = this.zoom, contrast = this.contrast, noverlap = this.noverlap, colourMap = this.colourMap}
     */
    resetArgs(args) {
        let self = this;
        let changed = {};

        $.each(Visualiser.defaultArgs, function (arg, defVal) {
            let curVal = self[arg];
            let newVal = args[arg];

            if (newVal === undefined) {
                if (curVal === undefined) {
                    self[arg] = defVal;
                    changed.push(arg);
                }
            }
            else if (newVal !== curVal) {
                self[arg] = newVal;
                changed[arg] = true;
            }
        });
        if (changed.zoom) {
            if (self.zoom <= 100) {
                self.nfft = defaultNfft / (self.zoom / 100);
                self.frameSize = self.nfft;
                self.fft = new FFT(self.nfft);
            }
            else {
                if (self.nfft !== defaultNfft) {
                    self.nfft = defaultNfft;
                    self.fft = new FFT(self.nfft);
                }
                self.frameSize = Math.floor(defaultNfft / (self.zoom / 100));
            }
            self.noverlap = self.nfft - self.frameSize;
            self.tickInterval = Math.floor(self.frameSize / 10) * 20;
        }
    }

    displayAsPromises() {
        let self = this;
        let start = Math.max(0, self.currentImageIndex - self.numberOfImages);
        let end = Math.min(self.lastChunkIdx, self.currentImageIndex + self.numberOfImages);

        let sliced = [];
        for (let i = start; i <= end; i++) {
            let segBeg = self.chunks[i][0];
            let renderStatus = self.spectRenderingStatus[segBeg];

            if (renderStatus.state !== stateDisplayed || renderStatus.contrast !== self.contrast) {
                renderStatus.contrast = self.contrast;
                renderStatus.state = stateScheduled;
                sliced.push(self.chunks[i]);
            }
        }

        let toDelete = [];
        let needCancelled = false;
        for (let i = 0; i <= self.lastChunkIdx; i++) {
            if (i < start || i > end) {
                let segBeg = self.chunks[i][0];
                let renderStatus = self.spectRenderingStatus[segBeg];

                if (renderStatus.state !== stateEmpty) {
                    renderStatus.spect = null;
                    toDelete.push(self.chunks[i]);
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

        if (needCancelled && self.visualisationPromiseChainHead !== undefined) {
            self.visualisationPromiseChainHead.cancel();
            self.visualisationPromiseChainHead = undefined;
        }

        // If there are spects to be deleted, but they have not been rendered because the promise chain
        // is still running - then we must cancel the promise chain
        let deletePromises = toDelete.reduce(function (promiseChain, chunk) {
            let segBeg = chunk[0];
            let renderStatus = self.spectRenderingStatus[segBeg];
            return promiseChain.then(function () {
                renderStatus.state = stateEmpty;
                debug(`Delete chunk: ${segBeg}`);
                let img = self.spectrogramSpects.select(`image[x="${segBeg}"]`);
                img.attr('xlink:href', undefined);
                self.oscillogramPaths.select(`#oscil-${segBeg}`).select('path').remove();

            });
        }, Promise.resolve());


        return sliced.reduce(function (promiseChain, chunk) {
            let segBeg = chunk[0];
            let segEnd = chunk[1];
            let subImgWidth = segEnd - segBeg;

            let subSegs = self.segs.slice(segBeg, segEnd);
            let subSig = self.sig.subarray(subSegs[0][0], subSegs[subSegs.length - 1][1]);
            let renderStatus = self.spectRenderingStatus[segBeg];

            if (renderStatus.state === stateCalculated) {
                return promiseChain;
            }

            let data = [];

            for (let i = 0; i < subSig.length; i += 10) {
                data.push({
                    x: i,
                    y: subSig[i]
                });
            }

            let oscilXScale = d3.scaleLinear().range([0, subImgWidth]).domain([0, subSig.length]);
            let oscilYScale = d3.scaleLinear().domain([self.minY, self.maxY]).nice().range([self.oscilloHeight, 0]);

            let plotLine = d3.line().x(function (d) {
                return oscilXScale(d.x);
            }).y(function (d) {
                return oscilYScale(d.y);
            });

            return promiseChain.then(function () {
                let spect = renderStatus.spect;
                if (spect === null) {
                    debug(`Calculate chunk: ${segBeg}`);
                    renderStatus.state = stateBeforeCalculation;
                    spect = transposeFlipUD(calcSpect(self.sig, subSegs, self.fft));
                    renderStatus.spect = spect;
                    renderStatus.state = stateCalculated;
                    return spect;
                }
                else if (renderStatus.state !== stateDisplayed) {
                    return spect;
                }
                return undefined;
            }).then(function (spect) {
                if (spect) {
                    renderStatus.state = stateBeforeDisplaying;
                    $.each(spect, function (_i, row) {
                        $.each(row, function (_j, px) {
                            if (isFinite(px)) {
                                self.minSpect = Math.min(self.minSpect, px);
                                self.maxSpect = Math.max(self.maxSpect, px);
                            }
                        });
                    });
                    return spectToUri(spect, self.imgHeight, subSegs.length, self.contrast, self.colourMap, self.minSpect, self.maxSpect);
                }
                return undefined;
            }).then(function (dataURI) {
                if (dataURI) {
                    renderStatus.state = stateDisplayed;
                    let img = self.spectrogramSpects.select(`#spect-${segBeg}`);
                    img.attr('xlink:href', dataURI);
                    let osc = self.oscillogramPaths.select(`#oscil-${segBeg}`);
                    osc.append('path').attr('class', 'line').attr('d', plotLine(data));
                }
            });
        }, deletePromises);
    }

    visualiseSpectrogram() {
        const self = this;
        self.segs = calcSegments(self.sig.length, self.nfft, self.noverlap);
        self.chunks = calcSegments(self.segs.length, self.spectWidth, 0, true);
        self.lastChunkIdx = self.chunks.length - 1;
        self.numberOfImages = Math.floor(self.visibleWidth / self.spectWidth) * 10;

        if (!self.imagesAreInitialised) {
            self.chunks.forEach(function (chunk) {
                let segBeg = chunk[0];
                let segEnd = chunk[1];
                let subImgWidth = segEnd - segBeg;

                self.spectrogramSpects.append('image').attr('id', `spect-${segBeg}`).attr('height', self.imgHeight).attr('width', subImgWidth).attr('x', segBeg).style('transform', `scaleY(${self.spectHeight / self.imgHeight})`);
                self.oscillogramPaths.append('g').attr('id', `oscil-${segBeg}`).style('transform', `translateX(${segBeg}px)`);

                self.spectRenderingStatus[segBeg] = {
                    state: stateEmpty,
                    contrast: null,
                    spect: null
                }
            });

            self.imagesAreInitialised = true;
        }

        if (self.visualisationPromiseChainHead) {
            self.visualisationPromiseChainHead.then(function () {
                return self.displayAsPromises();
            });
        }
        else {
            self.visualisationPromiseChainHead = self.displayAsPromises();
        }
    }

    scroll(cursorPosition) {
        let self = this;
        let imageStartIndex = Math.floor(cursorPosition / self.spectWidth);

        if (imageStartIndex !== self.currentImageIndex) {
            self.currentImageIndex = imageStartIndex;
            if (self.visualisationPromiseChainHead) {
                self.visualisationPromiseChainHead.then(function () {
                    return self.displayAsPromises();
                });
            }
            else {
                self.visualisationPromiseChainHead = self.displayAsPromises();
            }
        }
    }

    drawBrush() {
        let self = this;
        self.spectBrush = d3.brushX();
        self.spectBrush.extent([[self.spectXScale.domain()[0], 0], [self.spectXScale.domain()[1], self.spectHeight]]);

        self.spectBrush.on('start', function () {
            self.spectHandle.attr('display', 'unset');
            if (!d3.event.sourceEvent) return;
            debug('on brushstart');

            if (d3.event.selection) {
                let startPixel = d3.event.selection[0];
                self.playbackIndicator.style('display', 'unset').attr('transform', `translate(${startPixel}, 0)`);
                let startPoint = self.spectXScale.invert(startPixel);
                console.log(startPoint);
                playSongBtn.attr('start-point', startPoint)
            }
        }).on('brush', function () {
            let endpoints = d3.event.selection;
            if (endpoints === null) return;

            self.spectHandle.attr('transform', function (d, i) {
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
                let endpoints = d3.event.selection.map(self.spectXScale.invert);
                let start = Math.floor(endpoints[0]);
                let end = Math.ceil(endpoints[1]);

                debug('start= ' + start + ' end=' + end);

                let sylIdx = getCache('resizeable-syl-id');

                if (sylIdx === undefined) {
                    let uuid = uuid4();
                    let newId = `new:${uuid}`;
                    let newSyllable = {
                        id: newId,
                        start,
                        end,
                        duration: end - start,
                    };
                    self.eventNotifier.trigger('segment-changed', {
                        type: 'segment-created',
                        target: newSyllable
                    });

                    // Clear the brush right away
                    self.clearBrush();
                }
                else {

                    // We don't have to make a deep copy - just change the syllable and both syllableDict and
                    // syllableArray will get changed immediately - but to make it clear what's going on, I decided to
                    // make a hard copy and persist it in the array as a new syllable.
                    let updatedSyllable = deepCopy(getCache('syllableDict', sylIdx));

                    updatedSyllable.start = start;
                    updatedSyllable.end = end;
                    updatedSyllable.duration = end - start;
                    updatedSyllable.progress = 'Changed';

                    self.eventNotifier.trigger('segment-changed', {
                        type: 'segment-adjusted',
                        target: updatedSyllable
                    });
                }

                self.displaySegs();
            }
        });

        this.spectBrushEl = this.spectrogramSvg.append('g').attr('class', 'spect-brush');
        this.spectBrushEl.call(this.spectBrush);

        self.spectHandle = this.spectBrushEl.selectAll('.brush-handle').
            data([{type: 'w', spectHeight: self.spectHeight}, {type: 'e', spectHeight: self.spectHeight}]).enter().
            append('path').
            attr('class', 'brush-handle').
            attr('d', resizePath).
            attr('cursor', 'ew-resize').
            attr('cursor', 'ew-resize').
            attr('display', 'none');
    }

    setData({sig, fs, length, durationMs}) {
        const self = this;
        self.sig = sig;
        self.fs = fs;
        self.durationMs = durationMs;
        self.length = length;

        let minY = 99999;
        let maxY = -99999;
        let y;
        for (let i = 0; i < length; i++) {
            y = sig[i];
            if (minY > y) minY = y;
            if (maxY < y) maxY = y;
        }

        self.minY = minY;
        self.maxY = maxY;
    }

    initCanvas() {
        const self = this;

        /*
         * The file can be long so we must generate the spectrogram in chunks.
         * First we need to know how many frame will be generated as the final product.
         * Then create a canvas that can accommodate the entire image.
         * And then incrementally add frames to it
         */
        self.imgWidth = Math.floor((self.length - self.nfft) / self.frameSize) + 1;
        self.imgHeight = self.nfft / 2;

        self.spectrogramSvg = d3.select(self.spectrogramId);
        self.spectrogramSvg.selectAll('*').remove();
        self.spectrogramSvg.attr('height', self.spectHeight + self.margin.top + self.margin.bottom);
        self.spectrogramSvg.attr('width', self.imgWidth + self.margin.left + self.margin.right);

        self.oscillogramSvg = d3.select(self.oscillogramId);
        self.oscillogramSvg.selectAll('*').remove();
        self.oscillogramSvg.attr('width', self.imgWidth);
        self.oscillogramSvg.attr('height', self.oscilloHeight);

        let spectXExtent = [0, self.durationMs];
        self.spectXScale = d3.scaleLinear().range([0, self.imgWidth]).domain(spectXExtent);

        /*
         * Show the time axis under the spectrogram. Draw one tick per interval (default 200ms per click)
         */
        let numTicks = self.durationMs / self.tickInterval;
        let xAxis = d3.axisBottom().scale(self.spectXScale).ticks(numTicks);

        self.spectrogramAxis = self.spectrogramSvg.append('g');
        self.spectrogramAxis.attr('class', 'x axis');
        self.spectrogramAxis.attr('transform', 'translate(0,' + self.spectHeight + ')');
        self.spectrogramAxis.call(xAxis);

        /* Remove the first tick at time = 0 (ugly) */
        self.spectrogramAxis.selectAll('.tick').filter((d) => d === 0).remove();

        self.spectrogramSpects = self.spectrogramSvg.append('g').classed('spects', true);
        self.oscillogramPaths = self.oscillogramSvg.append('g').classed('oscils', true);

        self.spectrogramSvg.append('line').attr('class', 'playback-indicator').attr('x1', 0).attr('y1', 0).attr('x2', 1).attr('y2', self.spectHeight).style('stroke-width', 2).style('stroke', 'black').style('fill', 'none').style('display', 'none');
        self.oscillogramSvg.append('line').attr('class', 'playback-indicator').attr('x1', 0).attr('y1', 0).attr('x2', 1).attr('y2', self.oscilloHeight).style('stroke-width', 2).style('stroke', 'black').style('fill', 'none').style('display', 'none');

        self.playbackIndicator = d3.selectAll('.playback-indicator');
    }

    /**
     * Remove all rect elements on the spectrogram
     */
    clearAllSegments() {
        let self = this;
        if (self.spectrogramSvg) {
            self.spectrogramSvg.selectAll('rect.syllable').remove();
        }
    }

    /**
     * Play the syllable where mouse left click was registered
     * @param begin
     * @param end
     * @param scroll
     */
    startPlayback(begin = 0, end = 'end', scroll = false) {
        let self = this;
        let startX = self.spectXScale(begin);
        if (end === 'end') {
            end = self.spectXScale.domain()[1];
        }

        let endX = self.spectXScale(end);
        let endSec = end / 1000;
        let durationMs = end - begin;

        let playAudioArgs = {
            beginSec: begin / 1000,
            endSec,
        };

        playAudioArgs.onStartCallback = function (_playbackSpeed) {
            startPlaybackAt = Date.now();
            playbackSpeed = _playbackSpeed;
            let durationAtSpeed = durationMs * 100 / playbackSpeed;

            self.playbackIndicator.interrupt();
            self.playbackIndicator.style('display', 'unset').attr('transform', `translate(${startX}, 0)`);

            let transition = self.playbackIndicator.transition();
            transition.attr('transform', `translate(${endX}, 0)`);
            transition.duration(durationAtSpeed);
            transition.ease(d3.easeLinear);

            if (scroll) {
                self.startScrolling(startX, endX, durationAtSpeed);
            }
        };

        playAudioArgs.onEndedCallback = function () {
            self.stopPlaybackIndicator();
            playSongBtn.show();
            pauseSongBtn.hide();
            resumeSongBtn.attr('start-point', 0);
            playSongBtn.attr('start-point', 0);
            if (scroll) {
                self.stopScrolling();
                self.visualisationEl.scrollLeft = 0;
            }
        };

        playAudioDataArray(self.sig, self.fs, playAudioArgs);
    }

    pausePlayback() {
        let self = this;
        let playedMs = Date.now() - startPlaybackAt;
        playedDuration = playedMs * playbackSpeed / 100;
        stopAudio();
        self.playbackIndicator.interrupt();
        return playedDuration;
    }

    /**
     * Play the syllable where mouse left click was registered
     */
    stopPlaybackIndicator() {
        let self = this;
        playedDuration = null;
        self.playbackIndicator.interrupt();
        self.playbackIndicator.style('display', 'none');
    }

    /**
     * Show the brush include its resize handles.
     * @param sylIdx index of the syllable where the brush should appear
     */
    showBrush(sylIdx) {
        let self = this;
        let resizing = getCache('resizeable-syl-id');
        if (resizing && self.editMode) {
            debug(`Currently editing another segment, ignore. resizing = ${resizing}`);
            return;
        }

        let syl = getCache('syllableDict', sylIdx);
        setCache('resizeable-syl-id', undefined, sylIdx);

        // define our brush extent to be begin and end of the syllable
        self.spectBrush.move(self.spectrogramSvg.select('.spect-brush'), [syl.start, syl.end].map(self.spectXScale));
    }

    /**
     * Clear the brush include its resize handles.
     */
    clearBrush() {
        let self = this;
        self.spectBrush.move(self.spectrogramSvg.select('.spect-brush'), null);
        self.spectHandle.attr('display', 'none');
        setCache('resizeable-syl-id', undefined, undefined);
    }

    /**
     * When a syllable on spectrogram is on mouseover, highlight the rect element and store its ID on the cache.
     * If the Ctrl button is being pressed, display the brush to allow user to change the syllable as well
     *
     * @param element the HTML element (rect) where mouse event occurs
     * @param self an instance of Visualise
     */
    highlightSpectrogramSegment(element) {
        let self = this;
        let sylIdx = element.getAttribute('syl-id');
        setCache('highlighted-syl-id', undefined, sylIdx);

        if (self.editMode) {
            self.showBrush(sylIdx);
        }
        // External process might be interested in this event too
        self.eventNotifier.trigger('segment-mouse', {
            type: 'segment-mouseover',
            target: element
        });
    }

    /**
     * When a syllable on spectrogram is on mouseleave, clear the highlight and erase its ID from the cache.
     * But we don't clear the brush. The brush is only cleared when the Ctrl button is unpressed.
     *
     * @param element the HTML element (rect) where mouse event occurs
     * @param self an instance of Visualise
     */
    clearSpectrogramHighlight(element) {
        let self = this;
        let resizing = getCache('resizeable-syl-id');
        if (resizing && self.editMode) {
            debug('Currently editing another segment, ignore');
            return;
        }

        setCache('highlighted-syl-id', undefined, undefined);
        if (self.editMode) {
            debug('Edit mode on and not highlighted. Keep brush');
        }
        // External process might be interested in this event too
        self.eventNotifier.trigger('segment-mouse', {
            type: 'segment-mouseleave',
            target: element
        });
    }

    /**
     *
     * @param syllables an array of dict having these keys: {start, end, id}
     */
    displaySegs() {
        let self = this;
        let syllableArray = getCache('syllableArray');
        self.clearAllSegments();

        $.each(syllableArray, function (sylIdx, syl) {
            let beginMs = syl.start;
            let endMs = syl.end;

            let x = self.spectXScale(beginMs);
            let width = self.spectXScale(endMs - beginMs);

            let rect = self.spectrogramSvg.append('rect');
            rect.attr('class', 'syllable');
            rect.attr('syl-id', syl.id);
            rect.attr('begin', beginMs);
            rect.attr('end', endMs);
            rect.attr('x', x).attr('y', 0);
            rect.attr('height', self.spectHeight);
            rect.attr('width', width);
        });

        /*
         * Attach (once) the following behaviours to each syllables:
         * + On click, play the enclosed owner of audio.
         * + On mouse over, draw the brush and the boundary handlers so that the syllable can be adjusted.
         * + On mouse leaving from the top or bottom of syllable rectangle, remove the brush
         *    If the mouse is leaving from either side, do nothing, because this will be handled by the boundary handlers.
         */
        self.$spectrogram.find('.syllable').each(function (idx, el) {
            el = $(el);
            if (!el.hasClass('mouse-behaviour-attached')) {
                el.on(
                    'click',
                    function (e) {
                        // Left click
                        if (e.which === 1) {
                            let begin = this.getAttribute('begin');
                            let end = this.getAttribute('end');
                            self.startPlayback(begin, end);
                        }
                    }
                );
                el.on('mouseover', function () {
                    self.highlightSpectrogramSegment(this);
                });
                el.on('mouseleave', function () {
                    self.clearSpectrogramHighlight(this);
                });
                el.addClass('mouse-behaviour-attached');
            }
        });
    }


    initScroll() {
        let self = this;
        self.$vizContainer.scroll(function () {
            let cursorPosition = self.$vizContainer.scrollLeft();
            self.scroll(cursorPosition);
        });
    }


    startScrolling(startX, endX, duration) {
        let self = this;
        let speed = duration / (endX - startX);

        let visualisationWidth = self.$vizContainer.width();
        let delayStart = visualisationWidth / 2 - (startX - self.visualisationEl.scrollLeft);
        let prematureEnd = visualisationWidth / 2;
        let distance = endX - startX - prematureEnd;

        let scrollDuration = distance * speed;

        if (delayStart < 0) {
            self.visualisationEl.scrollLeft += Math.abs(delayStart);
            delayStart = 0;
        }

        let delayStartDuration = delayStart * speed;
        let scrolltarget = self.visualisationEl.scrollLeft + distance;

        self.scrollingTimer = setTimeout(function () {
            self.scrollingPromise = smoothScrollTo(self.visualisationEl, scrolltarget, scrollDuration);
        }, delayStartDuration)

    }


    stopScrolling() {
        let self = this;
        if (self.scrollingTimer) {
            clearTimeout(self.scrollingTimer);
        }
        if (self.scrollingPromise) {
            self.scrollingPromise.cancel();
        }
    }


    highlightSegments(e, args) {
        let self = this;
        let eventType = e.type;
        let songId = args.songId;

        let spectrogramSegment = self.$spectrogram.find(`rect.syllable[syl-id="${songId}"]`);

        if (eventType === 'mouseenter') {
            spectrogramSegment.addClass('highlight');
        }
        else {
            spectrogramSegment.removeClass('highlight');
        }
    }

    initController() {
        let self = this;
        contrastSlider.slider();

        contrastSlider.on('slideStop', function (slideEvt) {
            let contrast = slideEvt.value;
            self.resetArgs({contrast});
            self.visualiseSpectrogram();
        });

        contrastSlider.find('.slider').on('click', function () {
            let newValue = contrastSlider.find('.tooltip-inner').text();
            let contrast = parseInt(newValue);
            self.resetArgs({contrast});
            self.visualiseSpectrogram();
        });

        playSongBtn.click(function () {
            pauseSongBtn.show();
            playSongBtn.hide();
            let startPoint = playSongBtn.attr('start-point');
            if (startPoint) {
                startPoint = parseInt(startPoint);
            }
            else {
                startPoint = 0;
            }
            resumeSongBtn.attr('start-point', startPoint).attr('end-point', 'end').attr('scroll', true);
            self.startPlayback(startPoint, 'end', true);
        });

        pauseSongBtn.click(function () {
            resumeSongBtn.show();
            pauseSongBtn.hide();
            playSongBtn.hide();
            self.pausePlayback();
            self.stopScrolling();
            let newStartPoint = parseInt(resumeSongBtn.attr('start-point')) + playedDuration;
            resumeSongBtn.attr('start-point', newStartPoint);
        });

        resumeSongBtn.click(function () {
            pauseSongBtn.show();
            playSongBtn.hide();
            resumeSongBtn.hide();
            let startPoint = parseInt(resumeSongBtn.attr('start-point'));
            if (startPoint) {
                let endPoint = resumeSongBtn.attr('end-point');
                if (endPoint !== 'end') {
                    endPoint = parseInt(endPoint);
                }
                let scroll = resumeSongBtn.attr('scroll');
                self.startPlayback(startPoint, endPoint, scroll);
            }
        });

        stopSongBtn.click(function () {
            playSongBtn.show();
            pauseSongBtn.hide();
            self.stopPlaybackIndicator();
            stopAudio();
            self.stopScrolling();
            self.visualisationEl.scrollLeft = 0;
            resumeSongBtn.attr('start-point', 0);
            playSongBtn.attr('start-point', 0);
        });

        zoomOptions.click(function () {
            let $this = $(this);
            let zoom = parseInt($this.attr('value'));
            zoomOptions.parent().removeClass('active');
            $this.parent().addClass('active');

            zoomBtnText.html($this.html());

            self.resetArgs({zoom});
            self.initCanvas();
            self.visualisationPromiseChainHead.cancel();
            self.visualisationPromiseChainHead = undefined;
            self.imagesAreInitialised = false;
            self.visualiseSpectrogram();
            self.drawBrush();
            self.displaySegs();
        });

        cmOptions.click(function () {
            let $this = $(this);
            let colourMap = $this.attr('value');
            cmOptions.parent().removeClass('active');
            $this.parent().addClass('active');

            cmBtnText.html($this.html());

            self.resetArgs({colourMap});
            self.initCanvas();
            self.visualisationPromiseChainHead.cancel();
            self.visualisationPromiseChainHead = undefined;
            self.imagesAreInitialised = false;
            self.visualiseSpectrogram();
            self.drawBrush();
            self.displaySegs();
        });
    }
}
