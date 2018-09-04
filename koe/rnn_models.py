import numpy as np
from numpy import random

from koe.utils import one_hot, split_kfold_classwise, split_classwise


def inds2dataset(inds, data, labels, lens):
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
        dataset.lens.append(lens[ind])
    return dataset


class DataSet:
    def __init__(self, other=None):
        """
        Default and copy constructor
        :param other: another instance of dataset from which data is copied
        """
        self.data = other.data if other else []
        self.labels = other.labels if other else []
        self.lens = other.lens if other else []
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
            self.lens.append(lens_[ind])

    def all(self):
        return self.data, self.labels, self.lens

    def out_of_batch(self):
        return self.batch_id == len(self.data)

    def next(self, batch_size):
        # Shuffle the data before repeating from batch 0
        if self.out_of_batch():
            self.shuffle()
            self.batch_id = 0

        next_batch_id = min(self.batch_id + batch_size, len(self.data))

        batch_data = self.data[self.batch_id:next_batch_id]
        batch_labels = self.labels[self.batch_id:next_batch_id]
        batch_lens = self.lens[self.batch_id:next_batch_id]
        self.batch_id = next_batch_id
        return batch_data, batch_labels, batch_lens

    def make_foldable(self, enum_labels):
        return FoldedDataSet(enum_labels, self)


class FoldedDataSet(DataSet):
    def __init__(self, enum_labels, dataset):
        super(FoldedDataSet, self).__init__(dataset)
        self.folds = None
        self.fold_id = 0
        self.enum_labels = enum_labels

    def split_kfold(self, k):
        """
        This facilitates k-fold validation for the training process.
        Iterate through the folds, when the last fold is called, shuffle the dataset and divide into k-folds again
        :param k: number of folds to be divided
        :return:
        """
        if self.folds is None or len(self.folds) != k:
            self.folds = split_kfold_classwise(self.enum_labels, k)
            self.fold_id = 0
        elif self.fold_id >= len(self.folds) - 1:
            self.shuffle()
            self.folds = split_kfold_classwise(self.enum_labels, k)
            self.fold_id = 0
        else:
            self.fold_id += 1

        fold = self.folds[self.fold_id]
        trainset = inds2dataset(fold['train'], self.data, self.labels, self.lens)
        validset = inds2dataset(fold['test'], self.data, self.labels, self.lens)

        return trainset, validset


class DataProvider:
    def __init__(self, data, labels, use_pseudo_end=False):
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
        assert len(data) == len(labels)
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
        for matrix, matrix_len in zip(data, self.lens):
            matrix = (matrix - self.mins) / data_range
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

    def get_sets(self, test_ratio=0.1):
        """
        Split the data into training and test set, based on the ratio given
        :param test_ratio: ratio of test data vs all data
        :return: one FoldedDataset (which further splits non-test data into train and validate sets), and one Dataset
                 containing the test set
        """
        assert test_ratio < 0.5, 'Test set must be less than training set'

        foldable, test = split_classwise(self.enum_labels, test_ratio=test_ratio)
        foldable_enum_labels = self.enum_labels[foldable]

        foldableset = inds2dataset(foldable, self.data, self.labels, self.lens).make_foldable(foldable_enum_labels)
        testset = inds2dataset(test, self.data, self.labels, self.lens)

        return foldableset, testset
