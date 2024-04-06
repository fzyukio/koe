r"""
Run to extract features of given segment ID and export the feature matrix with segment labels to a matlab file

e.g.
python manage.py extract_features --csv=/tmp/bellbirds.csv --h5file=bellbird-lbi.h5 --matfile=/tmp/mt-lbi.mat \
                                  --features="frequency_modulation;spectral_continuity;mean_frequency"

--> extracts full features (see features/feature_extract.py for the full list)
            of segments in file /tmp/bellbirds.csv (created by segment_select)
            stores the features in bellbird-lbi.h5
            then use three features (frequency_modulation;spectral_continuity;mean_frequency) (aggregated by mean,
            median, std) to construct a feature matrix (9 dimensions). Store this matrix with the labels (second column
            in /tmp/bellbirds.csv) to file /tmp/mt-lbi.mat
"""

from django.core.management.base import BaseCommand

from koe.feature_utils import (
    calculate_similarity,
    construct_ordination,
    extract_database_measurements,
)
from koe.models import DataMatrix, Ordination, SimilarityIndex, Task, TaskProgressStage


cls2func = {
    DataMatrix.__name__: extract_database_measurements,
    Ordination.__name__: construct_ordination,
    SimilarityIndex.__name__: calculate_similarity,
}


class Command(BaseCommand):
    def handle(self, *args, **options):
        for task in Task.objects.filter(parent=None, stage__lt=TaskProgressStage.COMPLETED).exclude(target=None):
            cls = task.target.split(":")[0]

            if cls in cls2func:
                func = cls2func[cls]
                func.delay(task.id)
                print("Successfully resumed {}({})".format(func.__name__, task.id))
            else:
                print("Unknown target {} of task#{}".format(task.target, task.id))
