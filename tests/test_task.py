import django
from django.test import TestCase


class TaskTest(TestCase):
    def setUp(self):
        django.setup()

        from koe.models import Task
        from root.models import User

        user = User.objects.get(username="superuser")
        task = Task(user=user)
        task.save()
        self.task_id = task.id
        print("Task ID = {}".format(self.task_id))

    def test_run_task(self):
        from koe.tasks import celery_task_test

        celery_task_test.delay(self.task_id)
