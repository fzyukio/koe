import numpy as np
from ced import pyed
from django.core.management.base import BaseCommand
from django.db.utils import IntegrityError
from progress.bar import Bar
from scipy.cluster.hierarchy import linkage

from koe.model_utils import natural_order
from koe.models import Coordinate, Database
from pymlfunc import normxcorr2
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


def calc_gap(feature_arrays):
    feature_array_shape = np.shape(feature_arrays[0])
    if len(feature_array_shape) == 1:
        return np.array([0])

    gap = np.zeros((feature_array_shape[1], ), dtype=np.float)
    return gap


class MockDistance:
    def __init__(self, distance):
        self.distance = distance

    def get_dist(self):
        return self.distance


def xcorrs(seg_one_f0, seg_two_f0, *args, **kwargs):
    distance = normxcorr2(seg_one_f0, seg_two_f0)[0, 0]
    return MockDistance(distance)


def euclid(seg_one_f0, seg_two_f0, *args, **kwargs):
    """
    :param seg_one_f0:
    :param seg_two_f0:
    :param args:
    :param kwargs:
    :return:
    """
    distance = np.linalg.norm(seg_one_f0 - seg_two_f0)
    return MockDistance(distance)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--features',
            action='store',
            dest='features',
            required=True,
            help='List of features you want to use to represent syllables and acoustic patterns',
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
            help='List of edit distance algorithms [dtw, edr, erp, lcss, xcorr2]',
        )

        parser.add_argument(
            '--norms',
            action='store',
            dest='norms',
            default='none',
            help='List of normalisation algorithm [none, max]',
        )

        parser.add_argument(
            '--database-name',
            action='store',
            dest='database_name',
            required=True,
            type=str,
            help='E.g Bellbird, Whale, ...',
        )

        parser.add_argument(
            '--algorithm-name',
            action='store',
            dest='algorithm_name',
            default=None,
            type=str,
            help='E.g Bellbird, Whale, ...',
        )

    def handle(self, features, dists, metrics, norms, database_name, algorithm_name, *args, **options):
        from koe.models import Segment
        # DistanceMatrix.objects.all().delete()
        database, _ = Database.objects.get_or_create(name=database_name)
        segments = Segment.objects.filter(audio_file__database=database)

        unsorted_ids = np.array(segments.values_list('id', flat=True))
        sorted_idx = np.argsort(unsorted_ids)
        segments_ids = unsorted_ids[sorted_idx]

        nsegs = len(segments_ids)

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
            bulk_extract_func = None
            segment_feature_array = None
            chirps_feature_array = None
            nchirps = 0

            for dist_name in dists.split(','):
                for metric_name in metrics.split(','):
                    for norm in norms.split(','):
                        test_name = '{}-{}{}-{}-{}'.format(
                            feature_name, config_str, dist_name, metric_name, norm)
                        if bulk_extract_func is None or segment_feature_array is None:
                            bulk_extract_func = extract_funcs[feature_name]
                            segment_feature_array = bulk_extract_func(segments, config, False)
                            chirps_feature_array = bulk_extract_func(segments, config, True)

                            chirps_feature_array = chirps_feature_array[sorted_idx]
                            segment_feature_array = segment_feature_array[sorted_idx]

                            nchirps = len(chirps_feature_array[0])

                        bar = Bar('Find coordinates of the segments ({})'.format(test_name), max=nsegs,
                                  suffix='%(index)d/%(max)d %(elapsed)ds/%(eta)ds')
                        coordinates = np.zeros(
                            (nsegs, nchirps), dtype=np.float64)

                        if metric_name == 'edr':
                            sigmas = calc_sigma(segment_feature_array)
                            metric_func = pyed.Edr
                            args = {'sigmas': sigmas}
                        elif metric_name == 'erp':
                            gap = calc_gap(segment_feature_array)
                            metric_func = pyed.Erp
                            args = {'gap': gap}
                        elif metric_name == 'lcss':
                            sigmas = calc_sigma(segment_feature_array)
                            metric_func = pyed.Lcss
                            args = {'sigmas': sigmas}
                        elif metric_name == 'dtw':
                            metric_func = pyed.Dtw
                            args = {}
                        elif metric_name == 'xcorrs':
                            metric_func = xcorrs
                            args = dict(boundary='symm', mode='same')
                        else:
                            metric_func = euclid

                        settings = pyed.Settings(dist=dist_name, norm=norm, compute_path=False)

                        for i in range(nsegs):
                            seg_one_f0 = segment_feature_array[i]
                            seg_one_chirps = chirps_feature_array[i]

                            for j in range(nchirps):
                                seg_two_f0 = seg_one_chirps[j]
                                distance = metric_func(
                                    seg_one_f0, seg_two_f0, args, settings)
                                coordinates[i, j] = distance.get_dist()
                            bar.next()
                        bar.finish()

                        tree = linkage(coordinates, method='average')
                        order = natural_order(tree)
                        sorted_order = np.argsort(order)

                        # mdict = {
                        #     'coordinates': coordinates, 'tree': tree, 'order': sorted_order,
                        #     'ids': segments_ids
                        # }
                        #
                        # with open('{}.pkl'.format(test_name), 'wb') as f:
                        #     pickle.dump(mdict, f, pickle.HIGHEST_PROTOCOL)
                        #
                        # scipy.io.savemat('{}.mat'.format(test_name), mdict=mdict)

                        # print(tree)

                        c = Coordinate()
                        c.database = database
                        if algorithm_name is None:
                            c.algorithm = test_name
                        else:
                            c.algorithm = algorithm_name
                        c.ids = segments_ids
                        c.tree = tree
                        c.order = sorted_order
                        c.coordinates = coordinates
                        i = 1
                        while True:
                            try:
                                c.save()
                                break
                            except IntegrityError:
                                i += 1
                                algorithm_name = '{} #{}'.format(test_name, i)
                                c.algorithm = algorithm_name
