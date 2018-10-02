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
import uuid

from django.core.management.base import BaseCommand

from koe.feature_utils import extract_database_measurements
from koe.model_utils import get_or_error
from koe.models import Feature, Database, Task, Aggregation, DataMatrix
from root.models import User


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )
        parser.add_argument('--celery', action='store_true', dest='celery', default=False,
                            help='Whether to run this as a celery task', )

    def handle(self, *args, **options):
        database_name = options['database_name']
        celery = options['celery']

        database = get_or_error(Database, dict(name__iexact=database_name))

        features = Feature.objects.all().order_by('id')
        aggregations = Aggregation.objects.filter(enabled=True).order_by('id')

        features_hash = '-'.join(list(map(str, features.values_list('id', flat=True)[:2])))
        aggregations_hash = '-'.join(list(map(str, aggregations.values_list('id', flat=True)[:2])))

        dm = DataMatrix(database=database)
        dm.ndims = 0
        dm.name = uuid.uuid4().hex
        dm.features_hash = features_hash
        dm.aggregations_hash = aggregations_hash
        dm.save()

        user = User.objects.get(username='superuser')
        task = Task(user=user, target='{}:{}'.format(DataMatrix.__class__.__name__, dm.id))

        task.save()

        dm.task = task
        dm.save()

        if celery:
            extract_database_measurements.delay(task.id)
        else:
            extract_database_measurements(task.id)
