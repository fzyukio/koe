from django.utils import timezone
from progress.bar import Bar

from koe.models import TaskProgressStage

stage_dict = {x: TaskProgressStage.get_name(x) for x in TaskProgressStage.reverse_items()}


class TaskRunner:
    def __init__(self, task):
        self.task = task
        if task.parent is None:
            prefix = 'Task #{} owner: {}'.format(task.id, task.user.username)
        else:
            prefix = '--Subtask #{} from Task #{} owner: {}'.format(task.parent.id, task.id, task.user.username)

        self.bar = Bar(prefix, max=1)
        self.bar.index = -1
        self.bar.next()
        self._change_suffix()

    def preparing(self):
        self._advance(TaskProgressStage.PREPARING)

    def start(self, max=100):
        self.bar.max = max
        self.bar.index = -1
        self._advance(TaskProgressStage.RUNNING)

    def wrapping_up(self):
        # print('wrapping-up')
        self._advance(TaskProgressStage.WRAPPING_UP)

    def complete(self):
        self._advance(TaskProgressStage.COMPLETED)

    def error(self, e):
        from django.conf import settings
        error_tracker = settings.ERROR_TRACKER
        error_tracker.captureException()
        self._advance(TaskProgressStage.ERROR, str(e))

    def _change_suffix(self):
        stage_name = stage_dict[self.task.stage]
        if self.task.stage == TaskProgressStage.RUNNING:
            self.bar.suffix = stage_name + ' - %(percent).1f%%'
        else:
            self.bar.suffix = stage_name

    def tick(self):
        pc_complete = (self.bar.index + 1) / self.bar.max
        self.task.pc_complete = pc_complete
        self.task.save()
        self.bar.next()

    def _advance(self, next_stage, message=None):
        if self.task.stage >= TaskProgressStage.COMPLETED:
            raise Exception('Task has already finished')

        if next_stage <= self.task.stage:
            raise Exception('Already at or passed that stage')

        if next_stage >= TaskProgressStage.COMPLETED:
            self.task.completed = timezone.now()

        self.task.stage = next_stage
        self.task.message = message
        self.task.save()

        self._change_suffix()
        self.bar.next()
