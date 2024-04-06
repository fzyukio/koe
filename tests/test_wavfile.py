import contextlib
import os
import wave
from logging import warning

from django.test import TestCase

from koe import wavfile


class WavfileTest(TestCase):
    def _test_single_file(self, filepath):
        fs, length = wavfile.get_wav_info(filepath)
        try:
            with contextlib.closing(wave.open(filepath, "r")) as f:
                correct_length = f.getnframes()
                correct_fs = f.getframerate()
            self.assertEqual(fs, correct_fs)
            self.assertEqual(length, correct_length)
        except wave.Error as e:
            warning("Library wave is unable to read file {}. Error is: {}".format(filepath, e))

    def test_get_wav_info(self):
        # filepath = 'user_data/audio/wav/172/AV2779_Parus+nuchalis_IN_3_70-169_S.wav'
        # self._test_single_file(filepath)

        files_to_test = []

        wav_dir = "user_data/audio/wav"
        af_subdirs = os.listdir(wav_dir)
        for af_subdir in af_subdirs:
            af_subdir_path = os.path.join(wav_dir, af_subdir)
            if os.path.isdir(af_subdir_path):
                af_files = os.listdir(af_subdir_path)
                for af_file in af_files:
                    if af_file.lower().endswith(".wav"):
                        af_file_path = os.path.join(af_subdir_path, af_file)
                        files_to_test.append(af_file_path)

        n_files_to_test = len(files_to_test)
        for idx, af_file_path in enumerate(files_to_test):
            print("Testing {}/{}: {}".format(idx + 1, n_files_to_test, af_file_path))
            self._test_single_file(af_file_path)
