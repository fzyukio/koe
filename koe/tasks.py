from time import sleep

from koe.celery_init import app
from koe.models import Task
from koe.task import TaskRunner


@app.task(bind=False)
def celery_task_test(task_id):
    task = Task.objects.get(id=task_id)

    runner = TaskRunner(task)

    runner.preparing()

    sleep(5)
    max = 100
    runner.start(max=max)

    for i in range(max):
        sleep(0.1)
        runner.tick()

    sleep(5)
    runner.wrapping_up()

    sleep(5)
    runner.complete()
