import copy
from abc import ABC, abstractmethod

import numpy as np

from ced import pyed
from koe.features.feature_extract import feature_extractors
from koe.management.commands.chirp_generator import generate_chirp
from pymlfunc import normxcorr2

from koe.models import Aggregation
from koe.utils import divide_conquer


# @memoize(timeout=300)
def _cached_get_chirp(chirp_type, nsamples):
    return generate_chirp(chirp_type, 'constant', nsamples)


# @memoize(timeout=300)
def _cached_get_chirp_feature(feature_name, args):
    args = copy.deepcopy(args)
    nsamples = args['nsamples']
    chirp_type = args['chirp_type']

    chirp = _cached_get_chirp(chirp_type, nsamples)

    args['sig'] = chirp
    extractor = feature_extractors[feature_name]
    feature_value = extractor(args)
    return feature_value


def dtw_chirp(feature, seg_feature_value, args):
    if seg_feature_value.ndim == 2:
        dim0 = seg_feature_value.shape[0]
    else:
        dim0 = 1

    chirp_feature_value = _cached_get_chirp_feature(feature.name, args)

    if feature.is_one_dimensional:
        if chirp_feature_value.ndim == 1:
            chirp_feature_value = chirp_feature_value.reshape(1, (max(chirp_feature_value.shape)))

        if seg_feature_value.ndim == 1:
            seg_feature_value = seg_feature_value.reshape(1, (max(seg_feature_value.shape)))

    settings = pyed.Settings(dist='euclid_squared', norm='max', compute_path=False)

    # if chirp_feature_value.shape != seg_feature_value.shape:
    #     chirp_feature_value = _cached_get_chirp_feature(feature.name, args)
    #     raise Exception('Feature = {}. Shape{} is not the same as {}'.format(feature.name, chirp_feature_value.shape,
    #                                                                          seg_feature_value.shape))
    retval = np.empty((dim0,), dtype=np.float64)

    for d in range(dim0):
        chirp_feature_array = chirp_feature_value[d]
        seg_feature_array = seg_feature_value[d]
        distance = pyed.Dtw(chirp_feature_array, seg_feature_array, settings=settings, args={})
        retval[d] = distance.get_dist()

    return retval


def xcorr_chirp(feature, seg_feature_value, args):
    chirp_feature_value = _cached_get_chirp_feature(feature.name, args)
    if feature.is_one_dimensional:
        chirp_feature_value = chirp_feature_value.reshape(1, (max(chirp_feature_value.shape)))
        seg_feature_value = seg_feature_value.reshape(1, (max(seg_feature_value.shape)))

    # if chirp_feature_value.shape != seg_feature_value.shape:
    #     chirp_feature_value = _cached_get_chirp_feature(feature.name, args)
    #     raise Exception('Feature = {}. Shape{} is not the same as {}'.format(feature.name, chirp_feature_value.shape,
    #                                                                          seg_feature_value.shape))

    if chirp_feature_value.shape[1] <= seg_feature_value.shape[1]:
        retval = np.max(normxcorr2(chirp_feature_value, seg_feature_value))
    else:
        retval = np.max(normxcorr2(seg_feature_value, chirp_feature_value))

    return retval


class Aggregator(ABC):
    @abstractmethod
    def process(self, input, **kwargs):
        pass

    @abstractmethod
    def get_name(self):
        pass

    @abstractmethod
    def is_chirpy(self):
        pass


class StatsAggregator(Aggregator):
    def __init__(self, method):
        self.method = method
        self.name = method.__name__

    def get_name(self):
        return self.name

    def process(self, input, **kwargs):
        return self.method(input, axis=-1)

    def is_chirpy(self):
        return False


class ChirpDtw(Aggregator):
    def __init__(self, chirp_type):
        self.chirp_type = chirp_type
        self.name = 'chirp_{}'.format(chirp_type)

    def get_name(self):
        return self.name

    def process(self, input, **kwargs):
        feature = kwargs['feature']
        args = kwargs['args']
        args['chirp_type'] = self.chirp_type
        return dtw_chirp(feature, input, args)

    def is_chirpy(self):
        return True


class ChirpXcorr(Aggregator):
    def __init__(self, chirp_type):
        self.chirp_type = chirp_type
        self.name = 'xcorr_{}'.format(chirp_type)

    def get_name(self):
        return self.name

    def process(self, input, **kwargs):
        feature = kwargs['feature']
        args = kwargs['args']
        args['chirp_type'] = self.chirp_type
        return xcorr_chirp(feature, input, args)

    def is_chirpy(self):
        return True


class DivideConquer(Aggregator):
    def __init__(self, method, ndivs):
        self.method = method
        self.ndivs = ndivs
        self.name = 'divcon_{}_{}'.format(ndivs, method.__name__)

    def get_name(self):
        return self.name

    def process(self, input, **kwargs):
        divs = divide_conquer(input, self.ndivs)
        return np.array([self.method(div, axis=-1) for div in divs]).ravel()

    def is_chirpy(self):
        return False


enabled_aggregators = {
    'stats': [
        StatsAggregator(np.mean),
        StatsAggregator(np.median),
        StatsAggregator(np.std),
    ],
    'divcon-3': [
        DivideConquer(np.mean, 3)
    ],
    'divcon-5': [
        DivideConquer(np.mean, 5)
    ],
    'divcon-7': [
        DivideConquer(np.mean, 7)
    ]
}

_disabled_aggregators = {
    'dtw': [
        ChirpDtw('pipe'),
        ChirpDtw('squeak-up'),
        ChirpDtw('squeak-down'),
        ChirpDtw('squeak-convex'),
        ChirpDtw('squeak-concave'),
    ],
    'xcorr': [
        ChirpXcorr('pipe'),
        ChirpXcorr('squeak-up'),
        ChirpXcorr('squeak-down'),
        ChirpXcorr('squeak-convex'),
        ChirpXcorr('squeak-concave'),
    ],
}

aggregators = []
aggregator_map = {}


def init():
    for aggregators_by_type, enabled in [(enabled_aggregators, True), (_disabled_aggregators, False)]:
        for group in aggregators_by_type.values():
            for aggregator in group:
                aggregator_name = aggregator.get_name()
                aggregation = Aggregation.objects.filter(name=aggregator_name).first()
                if aggregation is None:
                    aggregation = Aggregation(name=aggregator_name)
                aggregation.enabled = enabled
                aggregation.save()

                aggregators.append(aggregator)
                aggregator_map[aggregator_name] = aggregator
