from django.core.management import BaseCommand

from koe.celery_init import delay_in_production
from koe.feature_utils import extract_database_measurements, construct_ordination, calculate_similarity
from koe.models import Task, DataMatrix, SimilarityIndex, Ordination
from root.models import User

cls2func = {
    DataMatrix.__name__: extract_database_measurements,
    Ordination.__name__: construct_ordination,
    SimilarityIndex.__name__: calculate_similarity
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--task-id', action='store', dest='task_id', required=True, type=int)

        parser.add_argument('--force', action='store_true', dest='force', default=False)

    def handle(self, *args, **options):
        task_id = options['task_id']
        force = options['force']

        task = Task.objects.get(id=task_id)
        superuser = User.objects.get(username='superuser')
        task.user = superuser
        task.save()

        cls = task.target.split(':')[0]

        if cls in cls2func:
            func = cls2func[cls]
            delay_in_production(func, task.id, force=force)
            print('Successfully resumed {}({})'.format(func.__name__, task.id))
        else:
            print('Unknown target {} of task#{}'.format(task.target, task.id))
