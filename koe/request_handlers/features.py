import numpy as np
from django.db.models import Case
from django.db.models import When

from koe.model_utils import get_or_error
from koe.models import DataMatrix, Segment
from koe.ts_utils import bytes_to_ndarray

__all__ = ['get_datamatrix_file_paths', 'get_sid_info']


def get_sid_info(request):
    sids_path = get_or_error(request.POST, 'path')
    if sids_path.startswith('/'):
        sids_path = sids_path[1:]
    sids = bytes_to_ndarray(sids_path, np.int32)
    preserved = Case(*[When(id=id, then=pos) for pos, id in enumerate(sids)])
    ordered_segs = Segment.objects.filter(id__in=sids).order_by(preserved)
    value_list = ordered_segs.values_list('audio_file__id', 'audio_file__name', 'start_time_ms', 'end_time_ms')
    seg_info = []
    song_info = {}

    for aid, aname, start, end in value_list:
        seg_info.append((aid, start, end))
        song_info[aid] = aname
    retval = seg_info, song_info
    return dict(origin='request_database_access', success=True, warning=None, payload=retval)


def get_datamatrix_file_paths(request):
    dmid = get_or_error(request.POST, 'dmid')
    dm = get_or_error(DataMatrix, dict(id=dmid))

    bytes_path = dm.get_bytes_path()
    sids_path = dm.get_sids_path()
    cols_path = dm.get_cols_path()

    if dm.database:
        database_name = dm.database.name
    else:
        database_name = dm.tmpdb.name

    retval = {'bytes-path': bytes_path, 'sids-path': sids_path, 'database-name': database_name, 'cols-path': cols_path}
    return dict(origin='get_datamatrix_file_paths', success=True, warning=None, payload=retval)
