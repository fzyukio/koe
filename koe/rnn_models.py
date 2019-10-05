import numpy as np
from numpy import random

from koe.utils import one_hot, split_classwise
from root.utils import zip_equal


def inds2dataset(inds, data, labels, lens=None):
    """
    Collect data by given indices & stuff them in a separate dataset
    :param inds: column indices of the selected data points
    :param data: full data set
    :param labels: full label set
    :param lens: full lens set
    :return: a sub DataSet
    """
    dataset = DataSet()
    dataset.size = len(inds)
    for ind in inds:
        dataset.data.append(data[ind])
        dataset.labels.append(labels[ind])
        if lens:
            dataset.lens.append(lens[ind])
    return dataset


class DataSet:
    def __init__(self, origin=None):
        """
        Default and copy constructor
        :param origin: another instance of dataset from which data is copied
        """
        self.data = origin.data if origin else []
        self.labels = origin.labels if origin else []
        self.lens = origin.lens if origin else []
        self.batch_id = 0
        self.size = 0

    def shuffle(self):
        """
        Randomise the data points, their labels and lens in the same way
        :return:
        """
        length = len(self.data)
        inds = np.arange(length)
        random.shuffle(inds)

        data_ = self.data
        labels_ = self.labels
        lens_ = self.lens

        self.data = []
        self.labels = []
        self.lens = []

        for ind in inds:
            self.data.append(data_[ind])
            self.labels.append(labels_[ind])
            if lens_:
                self.lens.append(lens_[ind])

    def all(self):
        return self.data, self.labels, self.lens

    def next(self, batch_size):
        # Shuffle the data before repeating from batch 0
        if self.batch_id == len(self.data):
            self.shuffle()
            self.batch_id = 0

        next_batch_id = min(self.batch_id + batch_size, len(self.data))

        batch_data = self.data[self.batch_id:next_batch_id]
        batch_labels = self.labels[self.batch_id:next_batch_id]
        batch_lens = self.lens[self.batch_id:next_batch_id]
        self.batch_id = next_batch_id
        return batch_data, batch_labels, batch_lens

    def make_trainable(self, enum_labels):
        return TrainableSet(enum_labels, self)


class TrainableSet(DataSet):
    def __init__(self, enum_labels, dataset):
        super(TrainableSet, self).__init__(dataset)
        self.folds = None
        self.fold_id = 0
        self.enum_labels = enum_labels

    def make_folds(self, nfolds, ratio=None):
        if ratio is None:
            ratio = 1. / nfolds
        self.folds = split_classwise(self.enum_labels, ratio, nfolds)
        return self.folds

    def get_fold(self, k):
        fold = self.folds[k]
        train = fold['train']
        valid = fold['test']

        trainset = inds2dataset(train, self.data, self.labels, self.lens)
        validset = inds2dataset(valid, self.data, self.labels, self.lens)

        return trainset, validset


class DataProvider:
    def __init__(self, data, labels, balanced=False):
        assert len(data) == len(labels)
        self.data = data
        self.labels = labels
        self.balanced = balanced
        self.lens = None
        self.unique_labels, self.enum_labels = np.unique(labels, return_inverse=True)
        self.folds = None

    def split(self, ratio, limits=None):
        fold = split_classwise(self.enum_labels, ratio, nfolds=1, balanced=self.balanced, limits=limits)
        train = fold[0]['train']
        test = fold[0]['test']

        trainable_enum_labels = self.enum_labels[train]

        trainset = inds2dataset(train, self.data, self.labels, self.lens).make_trainable(trainable_enum_labels)
        testset = inds2dataset(test, self.data, self.labels, self.lens)

        return trainset, testset


class EnumDataProvider(DataProvider):
    def __init__(self, data, labels, balanced=False):
        super(EnumDataProvider, self).__init__(data, labels, balanced)
        self.labels_original = self.labels
        self.labels = self.enum_labels


class OneHotSequenceProvider(DataProvider):
    def __init__(self, data, labels, balanced=False, use_pseudo_end=False):
        """
        Convert row-based data and nominal labels (e.g. using strings) into data suitable for a dynamic RNN.
        Each data sequence is a np.ndarray, they must have the same number of rows. They can have diff nums of columns.
        These conditions are strictly enforced.
        The data is normalised using global min and max (to range [0-1]).
        To facilitate RNN, sequences other than the longest ones will be appended with zero rows to the same length
        Labels are made one-hot binarised

        :param data: list of row-based data sequences
        :param labels: list of correct labels
        :param use_pseudo_end: if true, the end of each data sequence will be appended with a row filled by value 2
                               we chose 2 as it is outside of the data range
        """
        super(OneHotSequenceProvider, self).__init__(data, labels, balanced)
        self.labels, self.unique_labels, self.enum_labels = one_hot(labels)

        # Find min-max of data
        # All element in data must be np.array with the same shape[0]
        shape1 = None
        ndims = None
        self.lens = []
        for matrix in data:
            assert isinstance(matrix, np.ndarray)
            if ndims is None:
                ndims = matrix.ndim
                assert 0 < ndims < 3
                if ndims == 2:
                    shape1 = matrix.shape[1]
                else:
                    shape1 = 1
            else:
                assert ndims == matrix.ndim
                if ndims == 2:
                    assert shape1 == matrix.shape[1]

            matrix_len = matrix.shape[0]

            if use_pseudo_end:
                # Later we will add a "pseudo_end" to the end of each sequence, so the length will increase to 1
                # Don't see any point of adding a "pseudo_start" - but worth trying
                matrix_len += 1

            self.lens.append(matrix_len)

        data_concat = np.concatenate(data, axis=0)
        self.mins = np.min(data_concat, axis=0, keepdims=True)
        self.maxs = np.max(data_concat, axis=0, keepdims=True)
        data_range = self.maxs - self.mins

        max_seq_len = np.max(self.lens)

        pseudo_end = np.full((1, shape1), 2, dtype=data_concat.dtype)

        # The mins and maxs are basis for normalise the data (to [0 - 1]
        self.data = []
        for matrix, matrix_len in zip_equal(data, self.lens):
            matrix = (matrix - self.mins) / data_range
            if matrix.ndim == 1:
                matrix = matrix.reshape((matrix.shape[0], 1))
            # Pad sequence for dimension consistency
            padding = np.zeros((max_seq_len - matrix_len, shape1))
            if use_pseudo_end:
                matrix = np.concatenate([matrix, pseudo_end, padding], axis=0)
            else:
                matrix = np.concatenate([matrix, padding], axis=0)
            self.data.append(matrix)

        self.input_len = shape1
        self.output_len = self.n_classes = len(self.unique_labels)
        self.seq_max_len = max_seq_len
