from django.core.management import BaseCommand

from koe.models import Task
from koe.tasks import celery_task_test
from root.models import User


class Command(BaseCommand):
    def handle(self, *args, **options):
        user = User.objects.get(username='superuser')
        task = Task(user=user)
        task.save()

        celery_task_test.delay(task.id)
