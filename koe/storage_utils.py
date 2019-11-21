import os

import numpy as np
from django.conf import settings
from django.db.models import Case
from django.db.models import When

from koe.models import AudioFile
from koe.models import Segment


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


def get_storage_loc_template():
    slashed_url = os.path.join(settings.MEDIA_URL, 'binary', 'features3', '{}')
    unslashed_url = slashed_url[1:]
    return os.path.join(settings.BASE_DIR, unslashed_url)
