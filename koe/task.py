from django.utils import timezone
from progress.bar import Bar

from koe.models import TaskProgressStage, DataMatrix, Ordination, SimilarityIndex
from root.utils import SendEmailThread

stage_dict = {x: TaskProgressStage.get_name(x) for x in TaskProgressStage.reverse_items()}


def send_email(task, success):
    if success:
        subject = '[Koe] Job finished'
        template = 'job-finished'
    else:
        subject = '[Koe] Job failed'
        template = 'job-failed'

    user = task.user
    cls, objid = task.target.split(':')
    objid = int(objid)
    context = {}
    if cls == DataMatrix.__name__:
        context['dm'] = DataMatrix.objects.get(id=objid)
    elif cls == Ordination.__name__:
        context['ord'] = Ordination.objects.get(id=objid)
    else:
        context['sim'] = SimilarityIndex.objects.get(id=objid)

    send_email_thread = SendEmailThread(subject, template, [user.email], context=context)
    send_email_thread.start()


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
        self.task.pc_complete = 100.
        self.task.save()
        self._advance(TaskProgressStage.COMPLETED)
        if self.task.parent is None:
            send_email(self.task, True)

    def error(self, e):
        from django.conf import settings
        error_tracker = settings.ERROR_TRACKER
        error_tracker.captureException()
        self._advance(TaskProgressStage.ERROR, str(e))
        if self.task.parent is None:
            send_email(self.task, False)

    def _change_suffix(self):
        stage_name = stage_dict[self.task.stage]
        if self.task.stage == TaskProgressStage.RUNNING:
            self.bar.suffix = stage_name + ' - %(percent).1f%%'
        else:
            self.bar.suffix = stage_name

    def tick(self):
        pc_complete = (self.bar.index + 1) * 100 / self.bar.max
        self.task.pc_complete = pc_complete
        self.task.save()
        self.bar.next()

    def _advance(self, next_stage, message=None):
        if self.task.stage >= TaskProgressStage.COMPLETED:
            self.task.stage = TaskProgressStage.NOT_STARTED

        if self.task.stage == TaskProgressStage.COMPLETED:
            raise Exception('Task has already finished')

        if next_stage <= self.task.stage:
            raise Exception('Already at or passed that stage')

        if next_stage >= TaskProgressStage.COMPLETED:
            self.task.completed = timezone.now()

        if next_stage == TaskProgressStage.RUNNING:
            self.task.started = timezone.now()

        self.task.stage = next_stage
        self.task.message = message
        self.task.save()

        self._change_suffix()
        self.bar.next()
