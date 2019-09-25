"""
Convert audio file to spectrogram. Then use the trained segmentation encoder to detect syllables.
Then display the segmentation on a webpage
"""
from scipy import ndimage
from skimage import morphology
from skimage.measure import regionprops
from scipy import signal

import numpy as np

from koe.management.abstract_commands.use_segmentation import UseSegmenter, Segmenter


def get_median_clipping_mask(spectrogram):
    """
    Median clip spectrogram according to Lasseck & return the binary mask
    :param audio_file:
    :return:
    """
    spectrogram_shape = np.shape(spectrogram)

    nrow, ncol = spectrogram_shape
    mask_col = np.empty(spectrogram_shape)
    mask_row = np.empty(spectrogram_shape)

    for i in range(ncol):
        thresh = 3 * np.median(spectrogram[:, i])
        mask_col[:, i] = spectrogram[:, i] > thresh

    for i in range(nrow):
        thresh = 3 * np.median(spectrogram[i, :])
        mask_row[i, :] = spectrogram[i, :] > thresh

    mask = mask_col * mask_row
    return mask


class LasseckSegmenter(Segmenter):
    def get_segment(self, spectrogram, audio_file):
        min_freq = 500
        num_bins, nframes = spectrogram.shape
        niqst_fs = audio_file.fs / 2

        lo_bin = int(min_freq * num_bins / niqst_fs)
        spectrogram[:lo_bin, :] = spectrogram.min()

        mask = get_median_clipping_mask(spectrogram)
        # nrow, ncol = np.shape(mask)

        closed = ndimage.binary_closing(mask)
        filtered = signal.medfilt(closed, 5)

        labelled = morphology.label(filtered, background=0)
        regions = regionprops(labelled)

        # x0s = []
        # x1s = []
        # y0s = []
        # y1s = []

        for props in regions:
            bbox_area = props.area
            if bbox_area < 100:
                bbox = props.bbox
                y0 = bbox[0]
                y1 = bbox[2]
                x0 = bbox[1]
                x1 = bbox[3]
                filtered[y0:y1, x0:x1] = 0

        # labelled = morphology.label(filtered, background=0)
        # regions = regionprops(labelled)

        min_spect = spectrogram.min()
        spectrogram[np.where(filtered == 0)] = min_spect

        threshold = 1

        syllable_frames = filtered.sum(axis=0) > threshold

        syllables = []
        current_syl = None
        opening = False
        for i in range(nframes - 1):
            this_frame = syllable_frames[i]
            next_frame = syllable_frames[i + 1]
            if this_frame and next_frame:
                if opening is False:
                    opening = True
                    current_syl = [i]
            elif this_frame and opening:
                opening = False
                current_syl.append(i)
                syllables.append(current_syl)
                current_syl = None

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
        return LasseckSegmenter()

    def create_variables(self, options) -> dict:
        variables = {'format': 'spect', 'normalise': False}
        return variables
