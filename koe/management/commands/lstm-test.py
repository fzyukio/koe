r"""
Train a LSTM on audio segments.
"""

from django.core.management.base import BaseCommand

import numpy as np
from numpy import random

from koe.rnn_models import OneHotSequenceProvider
from koe.rnn_train import train


def generate_sequences(n_samples=1000, max_seq_len=20, min_seq_len=3, max_value=1000, shape1=1):
    """
    Create a dataset of dynamic length sequences. Two kinds of sequences are generated:
     1. Linear: random start, but continuous thereafter, e.g. [6,7,8,9]; [10, 11, 12, 13, 14, 15]
     2. Random:  random numbers
    The sequences can be two dimensional, row-based
    :param n_samples: number of sequences
    :param max_seq_len: max length
    :param min_seq_len: min length
    :param max_value: max value of any data point
    :param shape1: size of the second dimension
    :return: list of sequences and their respective labels, e.g. ['linear', 'random', 'random', 'linear', ...]
    """
    data = []
    labels = []
    for i in range(n_samples):
        # Random sequence length
        length = random.randint(min_seq_len, max_seq_len)
        # Add a random or linear int sequence (50% prob)
        s = []
        if random.random() < 0.5:
            # Generate a linear sequence
            label = "linear"
            for i in range(shape1):
                rand_start = random.randint(0, max_value - length)
                s_ = np.arange(rand_start, rand_start + length).reshape((length, 1))
                s.append(s_)
        else:
            # Generate a random sequence
            label = "random"
            for i in range(shape1):
                s_ = random.randint(0, max_value, size=length).reshape((length, 1))
                s.append(s_)
        data.append(np.hstack(s))
        labels.append(label)
    return data, labels


class Command(BaseCommand):
    def handle(self, *args, **options):
        data, labels = generate_sequences(n_samples=1500, max_seq_len=212, min_seq_len=4, max_value=1000, shape1=1)
        data_provider = OneHotSequenceProvider(data, labels)
        train(data_provider, nfolds=10, name="toy1")
