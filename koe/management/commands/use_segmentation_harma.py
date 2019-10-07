"""
Convert audio file to spectrogram. Then use the trained segmentation encoder to detect syllables.
Then display the segmentation on a webpage
"""
import numpy as np

from koe.management.abstract_commands.use_segmentation import UseSegmenter, Segmenter


class HarmaSegmenter(Segmenter):
    def get_segment(self, spectrogram, audio_file):
        min_freq = 500
        num_bins, nframes = spectrogram.shape
        niqst_fs = audio_file.fs / 2

        lo_bin = int(min_freq * num_bins / niqst_fs)

        peak_over_time = np.max(spectrogram[lo_bin:, :], 0)
        max_peak = np.max(peak_over_time)
        dropout_thresh = 0.2 * max_peak
        global_min = 0.7 * max_peak
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

                peak_over_time[left_idx:min(nframes, right_idx + 1)] = - np.inf
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
        return syllables, None


class Command(UseSegmenter):
    def close(self):
        pass

    def create_segmenter(self, variables) -> Segmenter:
        return HarmaSegmenter()

    def create_variables(self, options) -> dict:
        variables = {'format': 'log_spect', 'normalise': True}
        return variables
