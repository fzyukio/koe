import copy
from abc import ABC, abstractmethod

import numpy as np

from ced import pyed
from koe.features.feature_extract import feature_extractors
from koe.management.commands.chirp_generator import generate_chirp
from pymlfunc import normxcorr2
from memoize import memoize


@memoize(timeout=300)
def _cached_get_chirp(chirp_type, nsamples):
    return generate_chirp(chirp_type, 'constant', nsamples)


@memoize(timeout=300)
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
        chirp_feature_value = chirp_feature_value.reshape(1, (max(chirp_feature_value.shape)))

    settings = pyed.Settings(dist='euclid_squared', norm='max', compute_path=False)

    # if chirp_feature_value.shape != seg_feature_value.shape:
    #     chirp_feature_value = _cached_get_chirp_feature(feature.name, args)
    #     raise Exception('Feature = {}. Shape{} is not the same as {}'.format(feature.name, chirp_feature_value.shape,
    #                                                                          seg_feature_value.shape))
    retval = np.empty((dim0,), dtype=np.float64)

    for d in range(dim0):
        chirp_feature_array = chirp_feature_value[d, :]
        seg_feature_array = seg_feature_value[d, :]
        distance = pyed.Dtw(chirp_feature_array, seg_feature_array, settings=settings, args={})
        retval[d] = distance.get_dist()

    return retval


def xcorr_chirp(feature, seg_feature_value, args):
    chirp_feature_value = _cached_get_chirp_feature(feature.name, args)
    if feature.is_one_dimensional:
        chirp_feature_value = chirp_feature_value.reshape(1, (max(chirp_feature_value.shape)))

    # if chirp_feature_value.shape != seg_feature_value.shape:
    #     chirp_feature_value = _cached_get_chirp_feature(feature.name, args)
    #     raise Exception('Feature = {}. Shape{} is not the same as {}'.format(feature.name, chirp_feature_value.shape,
    #                                                                          seg_feature_value.shape))

    retval = np.max(normxcorr2(chirp_feature_value, seg_feature_value))
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
        return self.method(input, **kwargs)

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
