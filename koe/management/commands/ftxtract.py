from __future__ import print_function

import numpy as np
from django.db.models import Case
from django.db.models import When
from progress.bar import Bar
from python_speech_features import xfcc, delta, xfc
from scipy import interpolate
import pickle

from koe.management.commands.chirp_generator import generate_all_chirps
from root.utils import wav_path
from koe.models import Segment
from koe import wavfile

window_size_relative = 0.2  # Of the largest window


def resize_arr(arr, length):
    old_len = len(arr)
    t = np.linspace(1, old_len, old_len)
    f = interpolate.interp1d(t, arr)
    t1 = np.linspace(1, old_len, length)
    return f(t1)


with open('chirps.pkl', 'rb') as f:
    chirps_dict = pickle.load(f)

chirps_feature_dict = {}


@profile
def extract_xfcc(segments_ids, config, is_pattern=False, method_name='mfcc'):
    preserved = Case(*[When(id=id, then=pos) for pos, id in enumerate(segments_ids)])
    segments = Segment.objects.filter(id__in=segments_ids).order_by(preserved)

    nsegs = len(segments_ids)
    assert len(segments) == nsegs

    mfccs = []

    lower = int(config.get('lower', 20))
    upper = int(config.get('upper', 8000))
    ndelta = int(config.get('delta', 0))
    nfilt = int(config.get('nfilt', 26))
    nmfcc = int(config.get('nmfcc', nfilt / 2))

    assert nmfcc <= nfilt
    xtrargs = {'name': method_name, 'lowfreq': lower, 'highfreq': upper, 'numcep': nmfcc, 'nfilt': nfilt}
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

    segments_info = segments.values_list('segmentation__audio_file__name',
                                         'segmentation__audio_file__length',
                                         'segmentation__audio_file__fs',
                                         'start_time_ms',
                                         'end_time_ms')
    for file_name, length, fs, start, end in segments_info:
        segment_duration = end-start

        file_url = wav_path(file_name)
        if is_pattern:
            chirps = chirps_dict[segment_duration]['constant'].values()
            # chirps = generate_all_chirps(segment_duration_ms/1000, fs, None)
            mfcc_fts = []
            if segment_duration not in chirps_feature_dict:
                for chirp in chirps:
                    mfcc_ft = _extract_xfcc(chirp, fs, method, xtrargs, ndelta)
                    mfcc_fts.append(mfcc_ft)
                chirps_feature_dict[segment_duration] = mfcc_fts
            else:
                mfcc_fts = chirps_feature_dict[segment_duration]

        else:
            sig = wavfile.read_segment(file_url, start, end, mono=True)
            mfcc_fts = _extract_xfcc(sig, fs, method, xtrargs, ndelta)

        mfccs.append(mfcc_fts)
        bar.next()
    bar.finish()

    return mfccs


def _extract_xfcc(sig, fs, method, xtrargs, ndelta):
    mfcc_raw = method(signal=sig, samplerate=fs, winlen=0.002, winstep=0.001, **xtrargs)
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


def dummy(segments_ids, configs):
    nsegs = len(segments_ids)
    return np.ndarray((nsegs, 1), dtype=np.float32)


extract_funcs = {
    'mfcc': lambda ids, cfg, ip: extract_xfcc(ids, cfg, ip, 'mfcc'),
    'bfcc': lambda ids, cfg, ip: extract_xfcc(ids, cfg, ip, 'bfcc'),
    'gfcc': lambda ids, cfg, ip: extract_xfcc(ids, cfg, ip, 'gfcc'),
    'lfcc': lambda ids, cfg, ip: extract_xfcc(ids, cfg, ip, 'lfcc'),
    'mfc': lambda ids, cfg, ip: extract_xfcc(ids, cfg, ip, 'mfc'),
    'bfc': lambda ids, cfg, ip: extract_xfcc(ids, cfg, ip, 'bfc'),
    'gfc': lambda ids, cfg, ip: extract_xfcc(ids, cfg, ip, 'gfc'),
    'lfc': lambda ids, cfg, ip: extract_xfcc(ids, cfg, ip, 'lfc'),
    'dummy': dummy
}