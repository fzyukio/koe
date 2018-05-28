from contextlib import contextmanager

import time


@contextmanager
def tictoc(function_name):
    start = time.time()
    yield
    end = time.time()
    print('{}: finished in {} seconds'.format(function_name, end - start))
