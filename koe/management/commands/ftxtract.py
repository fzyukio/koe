from __future__ import print_function

import numpy as np
from django.db.models import Count
from django.db.models import F
from progress.bar import Bar
from python_speech_features import xfcc, delta, xfc
from scipy import interpolate

from koe import wavfile
from koe.management.commands.chirp_generator import *
from root.utils import wav_path

window_size_relative = 0.2  # Of the largest window


def resize_arr(arr, length):
    old_len = len(arr)
    t = np.linspace(1, old_len, old_len)
    f = interpolate.interp1d(t, arr)
    t1 = np.linspace(1, old_len, length)
    return f(t1)


# with open('chirps.pkl', 'rb') as f:
#     chirps_dict = pickle.load(f)
#
# chirps_feature_dict = {}


@profile
def extract_xfcc(segments, config, is_pattern=False, method_name='mfcc'):
    nsegs = len(segments)

    lower = int(config.get('lower', 20))
    upper = int(config.get('upper', 8000))
    ndelta = int(config.get('delta', 0))
    nfilt = int(config.get('nfilt', 26))
    nmfcc = int(config.get('nmfcc', nfilt / 2))

    assert nmfcc <= nfilt
    xtrargs = {'name': method_name, 'lowfreq': lower,
               'highfreq': upper, 'numcep': nmfcc, 'nfilt': nfilt}
    if 'cepsfunc' in config:
        xtrargs['cepsfunc'] = config['cepsfunc']

    if method_name in ['mfcc', 'bfcc', 'lfcc']:
        method = xfcc
    elif method_name == 'gfcc':
        lowhear = int(config.get('lowhear', 500))
        hihear = int(config.get('hihear', 12000))
        xtrargs['lowhear'] = lowhear
        xtrargs['hihear'] = hihear
        method = xfcc
    elif method_name in ['mfc', 'bfc', 'lfc']:
        method = xfc
    elif method_name == 'gfc':
        lowhear = int(config.get('lowhear', 500))
        hihear = int(config.get('hihear', 12000))
        xtrargs['lowhear'] = lowhear
        xtrargs['hihear'] = hihear
        method = xfc
    else:
        raise Exception('No such method: {}'.format(method_name))

    lower = xtrargs['lowfreq']
    upper = xtrargs['highfreq']
    nmfcc = xtrargs['numcep']
    bar = Bar('Extracting {} Range={}~{}, nCoefs={}, delta={}'.format(method_name, lower, upper, nmfcc, ndelta),
              max=nsegs, suffix='%(index)d/%(max)d %(elapsed)ds/%(eta)ds')

    if is_pattern:
        cache = {}

        original_segment_ids = np.array(
            segments.values_list('id', flat=True), dtype=np.int32)

        # Sort by duration so that we can cache them effectively
        segments = segments.annotate(duration=F(
            'end_time_ms') - F('start_time_ms')).order_by('duration')
        duration_sorted_segment_ids = np.array(
            segments.values_list('id', flat=True), dtype=np.int32)

        # We need the index array in order to restore the original order:
        ascending_sorted_idx = np.sort(original_segment_ids)

        ascending_sorted_to_original_order = np.searchsorted(
            ascending_sorted_idx, original_segment_ids)
        duration_sorted_to_ascending_sorted_order = np.argsort(
            duration_sorted_segment_ids)
        duration_sorted_to_original_order = duration_sorted_to_ascending_sorted_order[
            ascending_sorted_to_original_order]

        sorted_mfcc = []

        segments_info = segments.values_list(
            'duration', 'segmentation__audio_file__fs')
        for duration, fs in segments_info:
            if duration not in cache:
                cache = {duration: {}}
            if fs not in cache[duration]:
                chirps = []
                for amp_profile_name in amp_profile_names:
                    for f0_profile_name in f0_profile_names:
                        chirp = generate_chirp(
                            f0_profile_name, amp_profile_name, duration, fs)
                        chirps.append(chirp)
                cache[duration][fs] = chirps

            if 'ft' not in cache[duration]:
                chirps = cache[duration][fs]
                mfcc_fts = []

                for chirp in chirps:
                    mfcc_ft = _extract_xfcc(chirp, fs, method, xtrargs, ndelta)
                    mfcc_fts.append(mfcc_ft)

                cache[duration]['ft'] = mfcc_fts

            else:
                mfcc_fts = cache[duration]['ft']

            sorted_mfcc.append(mfcc_fts)
            bar.next()
        mfccs = np.array(sorted_mfcc)[duration_sorted_to_original_order]

    else:
        mfccs = []
        segments_info = segments.values_list('segmentation__audio_file__name', 'segmentation__audio_file__length',
                                             'segmentation__audio_file__fs', 'start_time_ms', 'end_time_ms')

        for file_name, length, fs, start, end in segments_info:
            file_url = wav_path(file_name)
            sig = wavfile.read_segment(file_url, start, end, mono=True)
            mfcc_fts = _extract_xfcc(sig, fs, method, xtrargs, ndelta)

            mfccs.append(mfcc_fts)
            bar.next()
        mfccs = np.array(mfccs)

    bar.finish()
    return mfccs


def _extract_xfcc(sig, fs, method, xtrargs, ndelta):
    mfcc_raw = method(signal=sig, samplerate=fs,
                      winlen=0.002, winstep=0.001, **xtrargs)
    if ndelta == 1:
        mfcc_delta1 = delta(mfcc_raw, 1)
        mfcc_fts = np.concatenate((mfcc_raw, mfcc_delta1), axis=1)

    elif ndelta == 2:
        mfcc_delta1 = delta(mfcc_raw, 1)
        mfcc_delta2 = delta(mfcc_delta1, 1)
        mfcc_fts = np.concatenate((mfcc_raw, mfcc_delta1, mfcc_delta2), axis=1)

    else:
        mfcc_fts = mfcc_raw
    return mfcc_fts


extract_funcs = {
    'mfcc': lambda objs, cfg, ip: extract_xfcc(objs, cfg, ip, 'mfcc'),
    'bfcc': lambda objs, cfg, ip: extract_xfcc(objs, cfg, ip, 'bfcc'),
    'gfcc': lambda objs, cfg, ip: extract_xfcc(objs, cfg, ip, 'gfcc'),
    'lfcc': lambda objs, cfg, ip: extract_xfcc(objs, cfg, ip, 'lfcc'),
    'mfc': lambda objs, cfg, ip: extract_xfcc(objs, cfg, ip, 'mfc'),
    'bfc': lambda objs, cfg, ip: extract_xfcc(objs, cfg, ip, 'bfc'),
    'gfc': lambda objs, cfg, ip: extract_xfcc(objs, cfg, ip, 'gfc'),
    'lfc': lambda objs, cfg, ip: extract_xfcc(objs, cfg, ip, 'lfc')
}
