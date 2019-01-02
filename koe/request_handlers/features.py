from koe.model_utils import get_or_error
from koe.models import DataMatrix

__all__ = ['get_datamatrix_file_paths']


def get_datamatrix_file_paths(request):
    dmid = get_or_error(request.POST, 'dmid')
    dm = get_or_error(DataMatrix, dict(id=dmid))

    bytes_path = dm.get_bytes_path()
    sids_path = dm.get_sids_path()
    if dm.database:
        database_name = dm.database.name
    else:
        database_name = dm.tmpdb.name

    return {'bytes-path': bytes_path, 'sids-path': sids_path, 'database-name': database_name}
