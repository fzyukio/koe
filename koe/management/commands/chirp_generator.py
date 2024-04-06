import pickle
from collections import OrderedDict

from django.core.management.base import BaseCommand
from django.db.models import F

import numpy as np
import scipy.signal
from progress.bar import Bar
from scipy.io import savemat

from koe.models import Database, Segment


GLOBAL_F0_MIN = 475.57
GLOBAL_F0_MAX = 5456.10
GLOBAL_F0_MEAN = (GLOBAL_F0_MIN + GLOBAL_F0_MAX) / 2


def gererate_f0_profile(time_arr, t1f, t2, t2f, method, centre=0.5):
    if method == "quadratic":
        middle_idx = int(len(time_arr) * centre)
        time_arr -= time_arr[middle_idx]
    return time_arr, t1f, t2, t2f, method


def generate_amp_profile(length, fadein=False, fadeout=False):
    original = np.ones((length,), dtype=np.float32)
    if fadein:
        onset_idx = int(length * 0.3)
        fading_factor = np.linspace(0.1, 1, onset_idx)
        original[:onset_idx] *= fading_factor
    if fadeout:
        onset_idx = int(length * 0.7)
        fading_factor = np.linspace(1, 0.1, length - onset_idx)
        original[onset_idx:] *= fading_factor

    return original


f0_profiles = {
    "pipe": lambda t: gererate_f0_profile(t, GLOBAL_F0_MEAN, t[-1], GLOBAL_F0_MEAN, "linear"),
    # 'pipe-down': lambda t: gererate_f0_profile(t, GLOBAL_F0_MAX, t[-1], GLOBAL_F0_MIN, 'linear'),
    # 'pipe-up': lambda t: gererate_f0_profile(t, GLOBAL_F0_MIN, t[-1], GLOBAL_F0_MAX, 'linear'),
    "squeak-up": lambda t: gererate_f0_profile(t, GLOBAL_F0_MIN, t[-1], GLOBAL_F0_MAX, "logarithmic"),
    "squeak-down": lambda t: gererate_f0_profile(t, GLOBAL_F0_MAX, t[-1], GLOBAL_F0_MIN, "logarithmic"),
    "squeak-convex": lambda t: gererate_f0_profile(t, GLOBAL_F0_MAX, t[-1], GLOBAL_F0_MIN, "quadratic"),
    "squeak-convex-left": lambda t: gererate_f0_profile(
        t, GLOBAL_F0_MAX, t[-1], GLOBAL_F0_MIN, "quadratic", centre=1 / 3
    ),
    "squeak-convex-right": lambda t: gererate_f0_profile(
        t, GLOBAL_F0_MAX, t[-1], GLOBAL_F0_MIN, "quadratic", centre=2 / 3
    ),
    "squeak-concave": lambda t: gererate_f0_profile(t, GLOBAL_F0_MIN, t[-1], GLOBAL_F0_MAX, "quadratic"),
    "squeak-concave-left": lambda t: gererate_f0_profile(
        t, GLOBAL_F0_MIN, t[-1], GLOBAL_F0_MAX, "quadratic", centre=1 / 3
    ),
    "squeak-concave-right": lambda t: gererate_f0_profile(
        t, GLOBAL_F0_MIN, t[-1], GLOBAL_F0_MAX, "quadratic", centre=2 / 3
    ),
}

amp_profiles = {
    "constant": lambda length: generate_amp_profile(length, fadein=False, fadeout=False),
    # 'fade-in': lambda length: generate_amp_profile(length, fadein=True, fadeout=False),
    # 'fade-out': lambda length: generate_amp_profile(length, fadein=False, fadeout=True),
    # 'fade-in-out': lambda length: generate_amp_profile(length, fadein=True, fadeout=True),
}

f0_profile_names = f0_profiles.keys()
amp_profile_names = amp_profiles.keys()


def generate_chirp(f0_profile, amp_profile, nsamples):
    """
    Create a frequency sweep signal given the shape and two frequency value in time

    :param f0_profile: the pattern that F0 follows:
                       'pipe': the F0 line is a straight line with the same frequency
                       'pipe-down': the F0 line is a straight line going downward
                       'pipe-up': the F0 line is a straight line going upward
                       'squeak-up': the F0 line is a curve going upward
                       'squeak-down': the F0 line is a curve going downward
                       'squeak-convex': the F0 line is a curve going down, bottom, and up, symmetric at the middle
                       'squeak-convex-left': the F0 line is a curve going down, bottom, and up, bottom is 1/3 from left
                       'squeak-convex-right': the F0 line is a curve going down, bottom, and up, bottom is 2/3 from left
                       'squeak-concave': the F0 line is a curve going up, top, and down, symmetric at the middle
                       'squeak-concave-left': the F0 line is a curve going up, top, and down, the top is 1/3 from left
                       'squeak-concave-right': the F0 line is a curve going up, top, and down, the top is 2/3 from left
    :param amp_profile: the pattern of amplitude:
                       'constant': same amplitude
                       'fade-in': starts low (0.1) and goes louder (1) at the end
                       'fade-out': starts loud (1) and goes low (0.1) at the end
                       'fade-in-out': starts low (0.1), goes louder in the middle, and low (0.1) at the end
    :param duration: in milliseconds
    :param fs:
    :return:
    """
    # if nsamples is None:
    #     nsamples = duration * fs // 1000
    time_arr = np.arange(0, nsamples, dtype=np.uint32)
    time_arr, t1f, t2, t2f, method = f0_profiles[f0_profile](time_arr)
    amp = amp_profiles[amp_profile](len(time_arr))

    signal = scipy.signal.chirp(time_arr, t1f, t2, t2f, method=method).astype(np.float32)
    signal *= amp

    return signal


def generate_all_chirps(duration, fs, matfile="/tmp/chirps.mat"):
    mat = {}
    chirps = []

    for f0_idx, name in enumerate(f0_profile_names):
        matlab_f0_idx = f0_idx + 1
        for amp_idx, amp_profile_name in enumerate(amp_profile_names):
            matlab_amp_idx = amp_idx + 1

            chirp = generate_chirp(name, amp_profile_name, duration, fs)

            if matfile:
                mat["chirp_{}_{}".format(matlab_f0_idx, matlab_amp_idx)] = chirp
                mat["fs_{}_{}".format(matlab_f0_idx, matlab_amp_idx)] = fs

            chirps.append(chirp)

            # p = pyaudio.PyAudio()
            # stream = p.open(format=pyaudio.paFloat32, channels=1, rate=fs, output=True)
            # stream.write(chirp)
            # stream.stop_stream()
            # stream.close()
            # p.terminate()
    mat["f0_profiles_count"] = len(f0_profile_names)
    mat["amp_profiles_count"] = len(amp_profile_names)

    if matfile:
        savemat(matfile, mdict=mat)

    return chirps


def generate_chirp_dictionary(pklfile, database):
    """
    Create all chirps with any possible duration
    :param pklfile: path to the pickle file to be saved
    :return: None
    """
    durations = list(
        set(
            Segment.objects.filter(audio_file__database=database)
            .annotate(duration=F("end_time_ms") - F("start_time_ms"))
            .values_list("duration", flat=True)
        )
    )

    fss = list(set(Segment.objects.filter(audio_file__database=database).values_list("audio_file__fs", flat=True)))

    chirp_dict = OrderedDict()
    fs = fss[0]

    bar = Bar(
        "Creating chirps",
        max=len(durations) * len(f0_profile_names) * len(amp_profile_names),
    )
    for duration in durations:
        _amp = {}
        for amp_profile_name in amp_profile_names:
            _f0 = {}
            for f0_profile_name in f0_profile_names:
                chirp = generate_chirp(f0_profile_name, amp_profile_name, duration, fs)
                _f0[f0_profile_name] = chirp
                bar.next()
            _amp[amp_profile_name] = _f0
        chirp_dict[duration] = _amp
    bar.finish()

    with open(pklfile, "wb") as f:
        pickle.dump(chirp_dict, f, protocol=pickle.HIGHEST_PROTOCOL)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--database-name",
            action="store",
            dest="database_name",
            required=True,
            type=str,
            help="E.g Bellbird, Whale, ...",
        )

    def handle(self, database_name, *args, **options):
        database, _ = Database.objects.get_or_create(name=database_name)

        generate_chirp_dictionary("chirps-{}.pkl".format(database_name), database)

        # chirp = generate_chirp('pipe', 'constant', 182 / 1000, 48000)
        #
        # p = pyaudio.PyAudio()
        # stream = p.open(format=pyaudio.paFloat32, channels=1, rate=48000, output=True)
        # stream.write(chirp)
        # stream.stop_stream()
        # stream.close()
        # p.terminate()

        # segment = Segment.objects.first()
        # duration = (segment.end_time_ms - segment.start_time_ms) / 1000
        # fs = segment.audio_file.fs
        # generate_all_chirps(duration, fs, matfile='/tmp/chirps.mat')

        # X = np.array([[0.81472, 0.15761, 0.65574], [0.90579, 0.97059, 0.035712], [0.12699, 0.95717, 0.84913],
        #               [0.91338, 0.48538, 0.93399], [0.63236, 0.80028, 0.67874], [0.09754, 0.14189, 0.75774],
        #               [0.2785, 0.42176, 0.74313], [0.54688, 0.91574, 0.39223], [0.95751, 0.79221, 0.65548],
        #               [0.96489, 0.95949, 0.17119]], dtype=np.float32)
        # tree = linkage(X, method='average')
        # order = np.array(natural_order(tree), dtype=np.int32)
        # # print(order)
        #
        # ids = np.arange(0, len(X))
        # print(ids)
        #
        # sorted_order = np.argsort(order)
        # print(sorted_order)
        #
        # ids_ = np.copy(ids)
        #
        # np.random.shuffle(ids_)
        # print(ids_)
        # order_ = sorted_order[np.searchsorted(ids, ids_)]
        # print(order_)

        # with open('mfcc-nmfcc=13-delta=2-euclid_squared-dtw-max.pkl', 'rb') as f:
        #     data = pickle.load(f)

        # Coordinate.objects.all().delete()
        # c = Coordinate()
        # c.algorithm = 'mfcc-nmfcc=13-delta=2-euclid_squared-dtw-max'
        # c.ids = data['ids']
        # c.tree = data['tree']
        # c.order = data['order']
        # c.coordinates = data['coordinates']
        # c.save()

        # coordinates = DistanceMatrix()
        # coordinates.ids = np.array([1,2,3,4,5])
        # coordinates.triu = np.array([9,8,7,6,5,4,3,2,1])
        # coordinates.algorithm = 'blah'
        #
        # coordinates.save()
        #
        # coordinates = DistanceMatrix.objects.all()[0]
        # print(coordinates)
