"""
Extract spectrograms from syllables in database
Train an auto encoder with it
Then display a pair of original - reconstructed syllable
Make it playable too
"""

import json
import os
import pickle
import zipfile
from logging import info

from django.core.management.base import BaseCommand

import numpy as np
from ml.s2senc_utils import read_variables

from koe.ml.nd_vl_s2s_mlp import NDS2MLPFactory
from koe.models import AudioFile, Segment
from koe.spect_utils import extractors
from koe.utils import split_segments, wav_path
from root.utils import mkdirp


good_audio_file_ids = [
    14437,
    14455,
    14476,
    20024,
    14006,
    14130,
    20046,
    14013,
    19401,
    14350,
    14076,
    14079,
    14444,
    13319,
    14175,
    14104,
    20053,
    14053,
    20054,
    19387,
    14060,
    14056,
    14133,
]

# good_audio_file_ids = [14437]


def extract_psd(extractor, audio_file):
    """
    Extract audio file's spectrogram given its ID
    :param audio_file:
    :param extractor:
    :return: the normalised spectrogram (spectrogram - wise, not dimension wise)
    """
    wav_file_path = wav_path(audio_file)
    database = audio_file.database
    spect = extractor(
        wav_file_path,
        audio_file.fs,
        0,
        None,
        nfft=database.nfft,
        noverlap=database.noverlap,
    )
    spect_min = np.min(spect)
    spect_max = np.max(spect)

    return (spect - spect_min) / (spect_max - spect_min)


def create_segment_profile(audio_file, duration_frames, filepath, window_len, step_size=1):
    """
    Each audio file has a number of segments. We'll slide a window through it spectrogam to create segments.
    then we create a mask for each segment with the same length corresponding to the frame number of the segment.
    For each frame of the segments that falls into the boundary of a syllable, its corresponding value in the mask
     is 1, otherwise 0.
    Each of these windowed segments is given a unique ID that is constructible from the audio file's ID and the
     timestamp
    :param step_size: how many frames is the next segment ahead of the
    :param window_len: length of the sliding window
    :param audio_file:
    :return: a dictionary of (fake) segment IDs and their corresponding audiofile, start and end indices
    """
    noverlap = window_len - step_size
    real_segments = Segment.objects.filter(audio_file=audio_file)
    real_segments_timestamps = real_segments.values_list("start_time_ms", "end_time_ms")

    # Construct a mask for the entire audiofile, then simply slicing it into fake segments
    duration_ms = int(audio_file.length / audio_file.fs * 1000)

    mask = np.zeros((duration_frames, 1), dtype=np.float32)
    for beg, end in real_segments_timestamps:
        beg_frame = int(beg / duration_ms * duration_frames)
        end_frame = int(end / duration_ms * duration_frames)
        mask[beg_frame:end_frame, :] = 1

    nwindows, windows = split_segments(duration_frames, window_len, noverlap, incltail=False)
    profiles = {}
    for beg, end in windows:
        windowed_id = "{}_{}".format(audio_file.id, beg)
        windowed_mask = mask[beg:end, :].tolist()
        profiles[windowed_id] = (filepath, beg, end, windowed_mask)

    return profiles


def prepare_samples(spect_dir, format, window_len):
    extractor = extractors[format]
    input_dims = None
    all_profiles = {}
    for afid in good_audio_file_ids:
        filepath = os.path.join(spect_dir, "{}.{}".format(afid, format))
        audio_file = AudioFile.objects.filter(id=afid).first()
        if not os.path.isfile(filepath):
            spect = extract_psd(extractor, audio_file)
            with open(filepath, "wb") as f:
                pickle.dump(spect, f)
        else:
            with open(filepath, "rb") as f:
                spect = pickle.load(f)
        dims, duration_frames = spect.shape
        if input_dims is None:
            input_dims = dims

        profiles = create_segment_profile(audio_file, duration_frames, filepath, window_len, step_size=1)
        all_profiles.update(profiles)
    return all_profiles, input_dims


def save_variables(variables, all_profiles, input_dims, save_to):
    sids = list(all_profiles.keys())
    variables["sids"] = sids
    variables["profiles"] = all_profiles
    variables["input_dims"] = input_dims
    # variables['output_dims'] = 10

    n_samples = len(sids)
    n_train = n_samples * 9 // 10
    n_test = n_samples - n_train
    np.random.shuffle(sids)

    sids_for_training = sids[:n_train]
    sids_for_testing = sids[n_train:]

    variables["sids_for_training"] = sids_for_training
    variables["sids_for_testing"] = sids_for_testing
    variables["n_train"] = n_train
    variables["n_test"] = n_test

    content = json.dumps(variables)
    with zipfile.ZipFile(save_to, "w", zipfile.ZIP_BZIP2, False) as zip_file:
        zip_file.writestr("variables", content)


def train(variables, save_to):
    sids_for_training = variables["sids_for_training"]
    sids_for_testing = variables["sids_for_testing"]
    n_train = len(sids_for_training)
    n_test = len(sids_for_testing)
    topology = variables["topology"]
    batch_size = variables["batch_size"]
    n_iterations = variables["n_iterations"]
    keep_prob = variables["keep_prob"]
    profiles = variables["profiles"]

    batch_index_limits = dict(train=n_train, test=n_test)
    sids_collections = dict(train=sids_for_training, test=sids_for_testing)

    spects = {}
    windows_masked = {}

    def get_batch(this_batch_size=10, data_type="train"):
        batch_index_limit = batch_index_limits[data_type]
        sids_collection = sids_collections[data_type]
        if this_batch_size is None:
            this_batch_size = batch_index_limit

        current_batch_index = variables["current_batch_index"][data_type]
        next_batch_index = current_batch_index + this_batch_size

        if current_batch_index == 0:
            np.random.shuffle(sids_collection)

        if next_batch_index >= batch_index_limit:
            next_batch_index = batch_index_limit
            variables["current_batch_index"][data_type] = 0
            final_batch = True
        else:
            variables["current_batch_index"][data_type] = next_batch_index
            final_batch = False

        batch_ids = sids_for_training[current_batch_index:next_batch_index]

        input_spects = []
        output_masks = []

        for sid in batch_ids:
            filepath, beg, end, window_masked = profiles[sid]
            if sid in windows_masked:
                window_masked = windows_masked[sid]
            else:
                window_masked = np.array(window_masked, dtype=np.float32)
                windows_masked[sid] = window_masked

            if filepath in spects:
                file_spect = spects[filepath]
            else:
                with open(filepath, "rb") as f:
                    file_spect = pickle.load(f).transpose(1, 0)
                spects[filepath] = file_spect

            windowed_spect = file_spect[beg:end, :]
            input_spects.append(windowed_spect)
            output_masks.append(window_masked)

        return input_spects, output_masks, final_batch

    def train_batch_gen(batch_size):
        return get_batch(batch_size, "train")

    def test_batch_gen(batch_size):
        return get_batch(batch_size, "test")

    factory = NDS2MLPFactory()
    factory.set_output(save_to)
    factory.lrtype = variables["lrtype"]
    factory.lrargs = variables["lrargs"]
    factory.input_dim = variables["input_dims"]
    factory.output_dim = variables["output_dims"]
    factory.keep_prob = keep_prob
    factory.stop_pad_length = 0
    factory.go_token = -1
    factory.layer_sizes = infer_topology(topology, variables["input_dims"])
    mlp = factory.build()
    mlp.train(
        train_batch_gen,
        test_batch_gen,
        batch_size=batch_size,
        n_iterations=n_iterations,
        display_step=100,
        save_step=100,
    )


def infer_topology(topology, dims=None):
    layer_sizes = []
    if dims is None:
        try:
            topology = list(topology.split(","))
            for number in topology:
                try:
                    number = int(number)
                except ValueError:
                    number = float(number)
                layer_sizes.append(number)
        except ValueError:
            raise Exception("Network topology must be either a single number or a list of comma separated numbers")
    else:
        layer_sizes = []
        for number in topology:
            if isinstance(number, int):
                layer_sizes.append(number)
            else:
                layer_sizes.append(int(number * dims))
    return layer_sizes


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--format", action="store", dest="format", required=True, type=str)
        parser.add_argument(
            "--spect-dir",
            action="store",
            dest="spect_dir",
            required=True,
            type=str,
            help="Path to the directory where audio segments will be saved",
        )
        parser.add_argument("--save-to", action="store", dest="save_to", required=True, type=str)
        parser.add_argument("--window-len", action="store", dest="window_len", required=True, type=int)
        parser.add_argument("--batch-size", action="store", dest="batch_size", required=True, type=int)
        parser.add_argument(
            "--n-iterations",
            action="store",
            dest="n_iterations",
            required=True,
            type=int,
        )
        parser.add_argument("--lrtype", action="store", dest="lrtype", default="constant", type=str)
        parser.add_argument("--lrargs", action="store", dest="lrargs", default='{"lr": 0.001}', type=str)
        parser.add_argument("--keep-prob", action="store", dest="keep_prob", default=None, type=float)
        parser.add_argument(
            "--topology",
            action="store",
            dest="topology",
            default="1",
            type=str,
            help="Network topology of the encoder, can be a single number or comma-separated list."
            "A float (e.g. 0.5, 1.5) corresponds to the ratio of number of neurons to input size"
            "An integer (e.g. 1, 2, 200) corresponds to the number of neurons."
            'E.g. "0.5, 100" means 2 layers, the first layer has 0.5xinput size neurons, '
            "the second layer has 100 neurons. The final encoded representation has dimension "
            "equals to the total number of neurons in all layers.",
        )

    def handle(self, *args, **options):
        save_to = options["save_to"]
        spect_dir = options["spect_dir"]
        format = options["format"]
        batch_size = options["batch_size"]
        window_len = options["window_len"]
        n_iterations = options["n_iterations"]
        lrtype = options["lrtype"]
        lrargs = json.loads(options["lrargs"])
        keep_prob = options["keep_prob"]
        topology = infer_topology(options["topology"])

        if not save_to.lower().endswith(".zip"):
            save_to += ".zip"

        all_profiles, input_dims = prepare_samples(spect_dir, format, window_len)

        input_dims = input_dims * options["window_len"]

        if os.path.isfile(save_to):
            info("===========CONTINUING===========")
            variables = read_variables(save_to)
            variables["profiles"] = all_profiles
            # assert variables['input_dims'] == input_dims, 'Saved file content is different from expected.'
            if "format" in variables:
                assert variables["format"] == format, "Saved file content is different from expected."
            else:
                variables["format"] = format
            if "topology" in variables:
                assert variables["topology"] == topology, "Saved file content is different from expected."
            else:
                variables["topology"] = topology
            if "keep_prob" in variables:
                assert variables["keep_prob"] == keep_prob, "Saved file content is different from expected."
            else:
                variables["keep_prob"] = keep_prob

        else:
            mkdirp(spect_dir)
            variables = dict(
                current_batch_index=dict(train=0, test=0),
                spect_dir=spect_dir,
                format=format,
                topology=topology,
                keep_prob=keep_prob,
                output_dims=options["window_len"],
            )
            save_variables(variables, all_profiles, input_dims, save_to)

        # These variables can be changed when resuming a saved file
        variables["batch_size"] = batch_size
        variables["n_iterations"] = n_iterations
        variables["lrtype"] = lrtype
        variables["lrargs"] = lrargs

        train(variables, save_to)
