from logging import warning

from django.core.management import BaseCommand

from koe.celery_init import delay_in_production
from koe.feature_utils import extract_database_measurements, construct_ordination, calculate_similarity
from koe.models import Task, DataMatrix, SimilarityIndex, Ordination, TaskProgressStage
from root.exceptions import CustomAssertionError

cls2func = {
    DataMatrix.__name__: extract_database_measurements,
    Ordination.__name__: construct_ordination,
    SimilarityIndex.__name__: calculate_similarity
}


def run_task(task, use_celery, force, send_email, remove_dead):
    cls = task.target.split(':')[0]

    if cls in cls2func:
        func = cls2func[cls]
        dead = True
        try:
            print('==============================================')
            print('Resuming {}({})'.format(func.__name__, task.id))
            if use_celery:
                delay_in_production(func, task.id, force=force, send_email=send_email, raise_err=True)
            else:
                func(task.id, force=force, send_email=send_email, raise_err=True)
            print('Successfully resumed {}({})'.format(func.__name__, task.id))
            dead = False
        except Ordination.DoesNotExist:
            warning('Task {} is likely outdated and cannot resume'.format(task.id))
        except CustomAssertionError as e:
            errmsg = str(e)
            if errmsg == 'Measurement cannot be extracted because your database doesn\'t contain any segments.':
                warning('Task {} is invalid and cannot resume'.format(task.id))
        except AssertionError as e:
            errmsg = str(e)
            if errmsg == 'Cannot construct ordination because its DataMatrix failed':
                warning('Task {} is invalid and cannot resume'.format(task.id))
        except ValueError as e:
            errmsg = str(e)
            if 'must be between 0 and min' in errmsg:
                warning('Task {} is invalid and cannot resume'.format(task.id))
        except FileNotFoundError as e:
            warning('Task {} is invalid and cannot resume'.format(task.id))
        except Exception as e:
            dead = False
            raise
        finally:
            print('==============================================')
            if dead and remove_dead:
                task.delete()
    else:
        print('Unknown target {} of task#{}'.format(task.target, task.id))


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--task-id', action='store', dest='task_id', required=False, default=None, type=int)

        parser.add_argument('--force', action='store_true', dest='force', default=False)

        parser.add_argument('--remove-dead', action='store_true', dest='remove_dead', default=False)

        parser.add_argument('--send-email', action='store', dest='send_email', default=None, type=str)

        parser.add_argument('--use-celery', action='store_true', dest='use_celery', default=False)

    def handle(self, *args, **options):
        task_id = options['task_id']
        force = options['force']
        remove_dead = options['remove_dead']
        send_email = options['send_email']
        use_celery = options['use_celery']

        if task_id and remove_dead:
            warning('If a single task id is given it will not be removed when failed. '
                    '--remove-dead is used only in bulk')

        if task_id:
            task = Task.objects.get(id=task_id)
            run_task(task, use_celery, force, send_email, remove_dead=False)

        else:
            tasks = Task.objects.exclude(stage=TaskProgressStage.COMPLETED).filter(parent=None)

            if remove_dead:
                Task.objects.exclude(stage=TaskProgressStage.COMPLETED).exclude(parent=None).delete()
            for task in tasks:
                run_task(task, use_celery, force, send_email, remove_dead)
