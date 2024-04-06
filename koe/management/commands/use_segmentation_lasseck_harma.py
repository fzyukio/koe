"""
Convert audio file to spectrogram. Then use the trained segmentation encoder to detect syllables.
Then display the segmentation on a webpage
"""

import numpy as np
from scipy import ndimage, signal
from skimage import morphology
from skimage.measure import regionprops

from koe.management.abstract_commands.use_segmentation import Segmenter, UseSegmenter
from koe.management.commands.use_segmentation_lasseck import get_median_clipping_mask


class LasseckHarmaSegmenter(Segmenter):
    def get_segment(self, spectrogram, audio_file):
        min_freq = 500
        num_bins, nframes = spectrogram.shape
        niqst_fs = audio_file.fs / 2
        min_spect = spectrogram.min()
        max_spect = spectrogram.max()

        lo_bin = int(min_freq * num_bins / niqst_fs)
        spectrogram[:lo_bin, :] = min_spect

        mask = get_median_clipping_mask(spectrogram)

        closed = ndimage.binary_closing(mask)
        filtered = signal.medfilt(closed, 5)

        labelled = morphology.label(filtered, background=0)
        regions = regionprops(labelled)

        for props in regions:
            bbox_area = props.area
            if bbox_area < 100:
                bbox = props.bbox
                y0 = bbox[0]
                y1 = bbox[2]
                x0 = bbox[1]
                x1 = bbox[3]
                filtered[y0:y1, x0:x1] = 0

        spectrogram[np.where(filtered == 0)] = min_spect

        eps = 1e-3
        log_spect = 20.0 * np.log10(spectrogram / max_spect + eps)
        spect_normed = (log_spect - log_spect.min()) / (log_spect.max() - log_spect.min())

        peak_over_time = np.max(spect_normed, 0)
        max_peak = np.max(peak_over_time)
        dropout_thresh = 0.3 * max_peak
        global_min = 0.8 * max_peak
        syllable_count = 0
        x0s = []
        x1s = []
        while True:
            max_idx = np.argmax(peak_over_time)
            max_val = peak_over_time[max_idx]
            if max_val > global_min:
                left_idx = max_idx
                while True:
                    left_idx -= 1
                    if left_idx < 0:
                        left_idx = 0
                        break
                    if peak_over_time[left_idx] <= max_val - dropout_thresh:
                        break

                right_idx = max_idx
                while True:
                    right_idx += 1
                    if right_idx >= nframes:
                        right_idx = nframes - 1
                        break
                    if peak_over_time[right_idx] <= max_val - dropout_thresh:
                        break

                peak_over_time[left_idx : min(nframes, right_idx + 1)] = -np.inf
                syllable_count += 1
                x0s.append(left_idx)
                x1s.append(right_idx)
            else:
                break
        x0s = np.asarray(x0s)
        x1s = np.asarray(x1s)

        sorted_idx = np.argsort(x0s)
        x0s = x0s[sorted_idx]
        x1s = x1s[sorted_idx]

        syllables = [[x0, x1] for x0, x1 in zip(x0s, x1s)]

        return syllables, regions

    def paint_extra(self, af_spect, regions):
        border_colour = [255, 255, 255]
        border_thickness = 1
        nrows, ncols, _ = af_spect.shape
        for props in regions:
            bbox_area = props.area
            if bbox_area >= 100:
                bbox = props.bbox
                y0 = bbox[0]
                y1 = bbox[2]
                x0 = bbox[1]
                x1 = bbox[3]

                y0_ = max(0, y0 - border_thickness)
                y1_ = min(nrows, y1 + border_thickness)
                x0_ = max(0, x0 - border_thickness)
                x1_ = min(x1 + border_thickness, ncols)

                af_spect[y0_:y1_, x0_:x0] = border_colour
                af_spect[y0_:y1_, x1:x1_] = border_colour
                af_spect[y0_:y0, x0:x1] = border_colour
                af_spect[y1:y1_, x0:x1] = border_colour


class Command(UseSegmenter):
    def close(self):
        pass

    def create_segmenter(self, variables) -> Segmenter:
        return LasseckHarmaSegmenter()

    def create_variables(self, options) -> dict:
        variables = {"format": "spect", "normalise": False}
        return variables
