from abc import abstractmethod


class LRFunc:
    @abstractmethod
    def __init__(self, *args, **kwargs):
        pass

    @abstractmethod
    def get_lr(self, *args, **kwargs):
        pass


class LRFuncConstant(LRFunc):
    def __init__(self, lr, *args, **kwargs):
        self.lr = lr
        super(LRFuncConstant, self).__init__(args, kwargs)

    def get_lr(self, *args, **kwargs):
        return self.lr


class LRFuncExpDecay(LRFunc):
    def __init__(self, start_lr, finish_lr, decay_steps, *args, **kwargs):
        assert 0 < finish_lr < start_lr, "start_lr must be > finish_lr and both must be positive"
        assert decay_steps > 0, "decay_steps must be positive"

        self.starter_learning_rate = start_lr
        self.finish_learning_rate = finish_lr
        self.decay_rate = finish_lr / start_lr
        self.decay_steps = decay_steps

        super(LRFuncExpDecay, self).__init__(args, kwargs)

    def get_lr(self, global_step, *args, **kwargs):
        return self.starter_learning_rate * pow(self.decay_rate, (global_step / self.decay_steps))


lrfunc_classes = {"constant": LRFuncConstant, "expdecay": LRFuncExpDecay}
