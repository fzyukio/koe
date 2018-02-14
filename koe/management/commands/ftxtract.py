from __future__ import print_function

import numpy as np
from django.db.models import Case
from django.db.models import When
from progress.bar import Bar
from python_speech_features import xfcc, delta, xfc
from scipy import interpolate

from root.utils import wav_path

window_size_relative = 0.2  # Of the largest window


def resize_arr(arr, length):
    old_len = len(arr)
    t = np.linspace(1, old_len, old_len)
    f = interpolate.interp1d(t, arr)
    t1 = np.linspace(1, old_len, length)
    return f(t1)


def extract_xfcc(segments_ids, config, method_name='mfcc'):
    from koe.models import Segment
    from koe import wavfile

    lower = int(config.get('lower', 20))
    upper = int(config.get('upper', 8000))
    ndelta = int(config.get('delta', 0))
    nfilt = int(config.get('nfilt', 26))
    nmfcc = int(config.get('nmfcc', nfilt / 2))

    assert nmfcc <= nfilt

    preserved = Case(*[When(id=id, then=pos) for pos, id in enumerate(segments_ids)])
    segments = Segment.objects.filter(id__in=segments_ids).order_by(preserved)

    nsegs = len(segments_ids)
    assert len(segments) == nsegs

    mfccs = []
    bar = Bar('Extracting {} Range={}~{}, nCoefs={}, delta={}'.format(method_name, lower, upper, nmfcc, ndelta),
              max=nsegs)

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

    segments_info = segments.values_list('segmentation__audio_file__name',
                                         'segmentation__audio_file__length',
                                         'segmentation__audio_file__fs',
                                         'start_time_ms',
                                         'end_time_ms')

    for file_name, length, fs, start, end in segments_info:
        duration_ms = length * 1000 / fs
        start /= duration_ms
        end /= duration_ms

        file_url = wav_path(file_name)

        sig = wavfile.read_segment(file_url, start, end, mono=True)

        mfcc_raw = method(signal=sig, samplerate=fs, winlen=0.002, winstep=0.001, **xtrargs)
        if ndelta == 1:
            mfcc_delta1 = delta(mfcc_raw, 1)
            mfcc_fts = np.concatenate((mfcc_raw, mfcc_delta1), axis=1)
            mfccs.append(mfcc_fts)
        elif ndelta == 2:
            mfcc_delta1 = delta(mfcc_raw, 1)
            mfcc_delta2 = delta(mfcc_delta1, 1)
            mfcc_fts = np.concatenate((mfcc_raw, mfcc_delta1, mfcc_delta2), axis=1)
            mfccs.append(mfcc_fts)
        else:
            mfccs.append(mfcc_raw)
        bar.next()
    bar.finish()

    return mfccs


def dummy(segments_ids, configs):
    nsegs = len(segments_ids)
    return np.ndarray((nsegs, 1), dtype=np.float32)


extract_funcs = {
    'mfcc': lambda x, y: extract_xfcc(x, y, 'mfcc'),
    'bfcc': lambda x, y: extract_xfcc(x, y, 'bfcc'),
    'gfcc': lambda x, y: extract_xfcc(x, y, 'gfcc'),
    'lfcc': lambda x, y: extract_xfcc(x, y, 'lfcc'),
    'mfc': lambda x, y: extract_xfcc(x, y, 'mfc'),
    'bfc': lambda x, y: extract_xfcc(x, y, 'bfc'),
    'gfc': lambda x, y: extract_xfcc(x, y, 'gfc'),
    'lfc': lambda x, y: extract_xfcc(x, y, 'lfc'),
    'dummy': dummy
}
