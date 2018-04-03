"""
Run DTW on a list of command-line specified features
args:
    --features=wes-f0,yin-f0,mfcc13,mfcc39 (comma separated)
"""

import numpy as np
from ced import pyed
from django.core.management.base import BaseCommand
from progress.bar import Bar

from .ftxtract import extract_funcs


def calc_sigma(feature_arrays, ratio=0.25):
    """
    According to Chen, Otsu, Oria, "Robust and fast similarity search for moving object trajectories":
    best sigma is 1/4 of the stdev
    :param ratio: the ratio sigma/stdev (default is 1/4)
    :param feature_arrays: an array of feature arrays, the length of the first dimension must be the same
    :return: an array of n sigmas, with n being the number of first dimension of the feature arrays
    """
    concat = np.concatenate(feature_arrays)
    sigmas = np.std(concat, axis=0) * ratio
    if len(np.shape(sigmas)) == 0:
        return np.array([sigmas])
    return sigmas


class DummyDistance:
    def get_dist(self):
        return np.random.randn()


d_ = DummyDistance()


def dummy(seg_one_f0, seg_two_f0, *args, **kwargs):
    return d_


def calc_gap(feature_arrays):
    feature_array_shape = np.shape(feature_arrays[0])
    if len(feature_array_shape) == 1:
        return np.array([0])

    gap = np.zeros((feature_array_shape[1],), dtype=np.float)
    return gap


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--features',
            action='store',
            dest='features',
            required=True,
            help='List of features you want to run edit distance on',
        )

        parser.add_argument(
            '--dists',
            action='store',
            dest='dists',
            required=True,
            help='List of distance measure algorithm [euclid, euclid_square, manhattan]',
        )

        parser.add_argument(
            '--metrics',
            action='store',
            dest='metrics',
            required=True,
            help='List of edit distance algorithms [dtw, edr, erp, lcss]',
        )

        parser.add_argument(
            '--norms',
            action='store',
            dest='norms',
            default='min',
            help='List of normalisation algorithm [none, min, avg, max]',
        )

    @profile
    def handle(self, features, dists, metrics, norms, *args, **options):
        from koe.models import Segment, DistanceMatrix
        DistanceMatrix.objects.all().delete()
        segments_ids = np.array(
            list(Segment.objects.all().order_by('id').values_list('id', flat=True)))

        nsegs = len(segments_ids)
        ndistances = int(nsegs * (nsegs - 1) / 2)

        for feature in features.split(','):
            _split = feature.split(':')
            configs = _split[1] if len(_split) > 1 else []
            config = {}
            config_str = ''
            if configs:
                for c in configs.split(';'):
                    param, value = c.split('=')
                    config[param] = value
                for k, v in config.items():
                    config_str += '{}={}-'.format(k, v)
            else:
                config_str = '-'

            feature_name = _split[0]
            extract_func = None
            feature_array = None

            for dist_name in dists.split(','):
                for metric_name in metrics.split(','):
                    for norm in norms.split(','):
                        test_name = '{}-{}{}-{}-{}'.format(
                            feature_name, config_str, dist_name, metric_name, norm)
                        if extract_func is None or feature_array is None:
                            extract_func = extract_funcs[feature_name]
                            feature_array = extract_func(segments_ids, config)

                        distance_count = 0

                        bar = Bar('Calc distance ({})'.format(
                            test_name), max=nsegs)

                        if metric_name == 'dummy':
                            metric_func = dummy
                            args = {}
                        elif metric_name == 'edr':
                            sigmas = calc_sigma(feature_array)
                            metric_func = pyed.Edr
                            args = {'sigmas': sigmas}
                        elif metric_name == 'erp':
                            gap = calc_gap(feature_array)
                            metric_func = pyed.Erp
                            args = {'gap': gap}
                        elif metric_name == 'lcss':
                            sigmas = calc_sigma(feature_array)
                            metric_func = pyed.Lcss
                            args = {'sigmas': sigmas}
                        else:
                            metric_func = pyed.Dtw
                            args = {}

                        triu = np.random.rand(ndistances).astype(np.float16)

                        bar.finish()

                        triu[np.isinf(triu)] = np.nan
                        max_value = np.nanmax(triu) * 2
                        triu[np.isnan(triu)] = max_value

                        chksum = DistanceMatrix.calc_chksum(segments_ids)
                        dm = DistanceMatrix.objects.filter(chksum=chksum).first()
                        if dm is None:
                            dm = DistanceMatrix()
                            dm.chksum = chksum
                            dm.ids = segments_ids
                        dm.triu = triu
                        dm.algorithm = test_name
                        dm.save()
