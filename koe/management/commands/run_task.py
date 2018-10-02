from time import sleep

from django.core.management import BaseCommand

from koe.models import Task
from koe.task import TaskRunner
from root.models import User


class Command(BaseCommand):
    def handle(self, *args, **options):
        user = User.objects.get(username='superuser')
        task = Task(user=user)
        task.save()

        runner = TaskRunner(task)
        runner.preparing()

        sleep(1)
        max = 100
        runner.start(max=max)

        for i in range(max):
            sleep(0.01)
            runner.tick()

        sleep(1)
        runner.wrapping_up()

        child_task = Task(user=task.user, parent=task)
        child_task.save()

        child_runner = TaskRunner(child_task)
        child_runner.preparing()

        sleep(1)
        max = 100
        child_runner.start(max=max)

        for i in range(max):
            sleep(0.01)
            child_runner.tick()

        sleep(1)
        child_runner.complete()

        sleep(1)
        runner.complete()
