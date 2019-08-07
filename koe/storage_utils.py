import os

import numpy as np
from django.db.models import Case
from django.db.models import When

from koe.models import Segment, AudioFile
from root.utils import data_path


def get_sids_tids(database, population_name=None):
    """
    Get ids and tids from all syllables in this database
    :param database:
    :return: sids, tids. sorted by sids
    """
    audio_files = AudioFile.objects.filter(database=database)
    if population_name:
        audio_files = [x for x in audio_files if x.name.startswith(population_name)]
    segments = Segment.objects.filter(audio_file__in=audio_files)
    segments_info = segments.values_list('id', 'tid')

    tids = []
    sids = []
    for sid, tid in segments_info:
        tids.append(tid)
        sids.append(sid)
    tids = np.array(tids, dtype=np.int32)
    sids = np.array(sids, dtype=np.int32)
    sids_sort_order = np.argsort(sids)
    sids = sids[sids_sort_order]
    tids = tids[sids_sort_order]

    return sids, tids


def get_tids(sids):
    preserved = Case(*[When(id=id, then=pos) for pos, id in enumerate(sids)])
    tids = Segment.objects.filter(id__in=sids).order_by(preserved).values_list('tid', flat=True)
    return np.array(tids, dtype=np.int32)


def get_binstorage_locations(features, aggregators):
    """
    Deduce the locations of feature binary files and feature-aggregator binary files from their names
    Then return these locations in two dictionaries for lookup convenience
    :param features:
    :param aggregators:
    :return:
    """
    # feature to binstorage's files
    f2bs = {}
    # feature+aggregation to binstorage's files
    fa2bs = {}

    for feature in features:
        feature_name = feature.name
        index_filename = data_path('binary/features', '{}.idx'.format(feature_name), for_url=False)
        value_filename = data_path('binary/features', '{}.val'.format(feature_name), for_url=False)
        f2bs[feature] = (index_filename, value_filename)

        if feature not in fa2bs:
            fa2bs[feature] = {}
        for aggregator in aggregators:
            aggregator_name = aggregator.get_name()
            folder = os.path.join('binary', 'features', feature_name)

            index_filename = data_path(folder, '{}.idx'.format(aggregator_name), for_url=False)
            value_filename = data_path(folder, '{}.val'.format(aggregator_name), for_url=False)
            fa2bs[feature][aggregator] = (index_filename, value_filename)
    return f2bs, fa2bs
