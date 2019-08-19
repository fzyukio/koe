from django.core.management import BaseCommand

from koe.celery_init import delay_in_production
from koe.feature_utils import extract_database_measurements, construct_ordination, calculate_similarity
from koe.models import Task, DataMatrix, SimilarityIndex, Ordination

cls2func = {
    DataMatrix.__name__: extract_database_measurements,
    Ordination.__name__: construct_ordination,
    SimilarityIndex.__name__: calculate_similarity
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--task-id',
            action='store',
            dest='task_id',
            required=True,
            type=int,
        )

    def handle(self, *args, **options):
        task_id = options['task_id']
        task = Task.objects.get(id=task_id)

        cls = task.target.split(':')[0]

        if cls in cls2func:
            func = cls2func[cls]
            delay_in_production(func, task.id)
            print('Successfully resumed {}({})'.format(func.__name__, task.id))
        else:
            print('Unknown target {} of task#{}'.format(task.target, task.id))
