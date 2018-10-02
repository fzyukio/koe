from time import sleep

import django

from django.test import TestCase


class TaskTest(TestCase):
    def setUp(self):
        django.setup()

        from koe.task import TaskRunner
        from koe.models import Task
        from root.models import User

        user = User.objects.get(username='superuser')
        task = Task(user=user)
        task.save()

        self.task = TaskRunner(task)

    def tearDown(self):
        super(TaskTest, self).tearDown()

    def test_run_task(self):
        self.task.preparing()

        sleep(5)
        max = 100
        self.task.start(max=max)

        for i in range(max):
            sleep(0.1)
            self.task.tick()

        sleep(5)
        self.task.wrapping_up()

        sleep(5)
        self.task.complete()
