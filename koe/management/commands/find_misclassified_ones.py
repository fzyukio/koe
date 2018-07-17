r"""
Run classifiers and export a)The confusion matrix and b)list of frequently misclassified instances
"""

import numpy as np
from django.core.management.base import BaseCommand
from dotmap import DotMap
from progress.bar import Bar
from scipy.io import loadmat
from scipy.stats import zscore
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA, QuadraticDiscriminantAnalysis as QDA
from sklearn.tree import DecisionTreeClassifier

from koe.utils import accum, sub2ind


def _calc_score(predict_y, test_y, nlabels):
    hits = (predict_y == test_y).astype(np.int)
    misses = 1 - hits
    score = hits.sum() / len(test_y)

    label_hits = np.full((nlabels,), np.nan)
    label_misses = np.full((nlabels,), np.nan)

    unique_test_labels = np.unique(test_y)

    _label_hits = accum(test_y, hits, func=np.sum, dtype=np.int)
    _label_misses = accum(test_y, misses, func=np.sum, dtype=np.int)

    label_hits[unique_test_labels] = _label_hits[unique_test_labels]
    label_misses[unique_test_labels] = _label_misses[unique_test_labels]

    return score, label_hits, label_misses


def _classify(model, train_x, train_y, test_x):
    model = model.fit(train_x, train_y)
    predict_y = model.predict(test_x)
    return predict_y


def random_forest(train_x, train_y, test_x):
    model = DecisionTreeClassifier()
    return _classify(model, train_x, train_y, test_x)


def svm(train_x, train_y, test_x):
    model = SVC(kernel='linear')
    return _classify(model, train_x, train_y, test_x)


def gaussian_nb(train_x, train_y, test_x):
    model = GaussianNB()
    return _classify(model, train_x, train_y, test_x)


def lda(train_x, train_y, test_x):
    model = LDA(n_components=2)
    return _classify(model, train_x, train_y, test_x)


def qda(train_x, train_y, test_x):
    model = QDA(priors=None, reg_param=0.0, store_covariance=False, store_covariances=None, tol=0.0001)
    return _classify(model, train_x, train_y, test_x)


classifiers = {
    'rf': random_forest,
    'svm': svm,
    'gnb': gaussian_nb,
    'lda': lda,
    'qda': qda
}


def run_nfolds(data, sids, nfolds, niters, enum_labels, nlabels, classifier, bar):
    nsyls = len(sids)
    ntrials = nfolds * niters
    if bar:
        bar.max = ntrials

    label_hitrates = np.empty((ntrials, nlabels))
    label_hitrates[:] = np.nan

    ind = 0

    misclassified_counts = np.zeros((nsyls, ), dtype=np.int)
    confusion_matrix = np.zeros((nlabels, nlabels), dtype=np.int)
    label_prediction_scores = [0] * ntrials

    for i in range(niters):
        scrambled_syl_idx = np.arange(nsyls, dtype=np.int)
        np.random.shuffle(scrambled_syl_idx)

        fold_inds = np.linspace(0, nsyls, nfolds + 1, dtype=np.int)
        fold_inds = list(zip(fold_inds[:-1], fold_inds[1:]))

        for k in range(nfolds):
            start_idx, end_idx = fold_inds[k]
            test_inds = np.arange(start_idx, end_idx)
            train_inds = np.concatenate((np.arange(0, start_idx), np.arange(end_idx, nsyls)))

            train_syl_idx = scrambled_syl_idx[train_inds]
            test_syl_idx = scrambled_syl_idx[test_inds]

            train_y = enum_labels[train_syl_idx]
            test_y = enum_labels[test_syl_idx]

            train_x = data[train_syl_idx, :]
            test_x = data[test_syl_idx, :]

            predict_y = classifier(train_x, train_y, test_x)

            score, label_hits, label_misses = _calc_score(predict_y, test_y, nlabels)
            label_prediction_scores[ind] = score

            misclassified = predict_y != test_y
            misclassified_idx = test_syl_idx[misclassified]
            misclassified_counts[misclassified_idx] += 1

            confusion_matrix_ind = sub2ind(confusion_matrix.shape, test_y, predict_y)
            confusion_matrix.ravel()[confusion_matrix_ind] += 1

            ind += 1

            if bar:
                bar.next()
    if bar:
        bar.finish()

    return label_prediction_scores, misclassified_counts, confusion_matrix


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--classifier', action='store', dest='clsf_type', required=True, type=str,
                            help='Can be svm, rf (Random Forest), gnb (Gaussian Naive Bayes), lda', )

        parser.add_argument('--matfile', action='store', dest='matfile', required=True, type=str,
                            help='Name of the .mat file that stores extracted feature values for Matlab', )

        parser.add_argument('--source', action='store', dest='source', required=True, type=str,
                            help='Can be tsne, raw, norm', )

        parser.add_argument('--feature-index', action='store', dest='ft_idx', required=False, type=int)

        parser.add_argument('--nfolds', action='store', dest='nfolds', required=False, default=100, type=int)

        parser.add_argument('--niters', action='store', dest='niters', required=False, default=1, type=int)

        parser.add_argument('--to-csv', dest='csv_filename', action='store', required=False)

    def handle(self, clsf_type, matfile, source, ft_idx, nfolds, niters, csv_filename, *args, **options):
        assert clsf_type in classifiers.keys(), 'Unknown _classify: {}'.format(clsf_type)
        assert source in ['tsne', 'raw', 'norm']

        saved = DotMap(loadmat(matfile))
        sids = saved.sids.ravel()
        clusters = saved.clusters
        dataset = saved.dataset
        labels = saved.labels
        haslabel_ind = np.where(labels != '                              ')[0]

        labels = labels[haslabel_ind]
        labels = np.array([x.strip() for x in labels])
        sids = sids[haslabel_ind]
        clusters = clusters[haslabel_ind, :]
        dataset = dataset[haslabel_ind, :]

        if ft_idx:
            dataset = dataset[:, ft_idx]

        meas = zscore(dataset)

        data_sources = {
            'tsne': clusters,
            'raw': dataset,
            'norm': meas
        }

        data = data_sources[source]

        classifier = classifiers[clsf_type]

        unique_labels, enum_labels = np.unique(labels, return_inverse=True)
        nlabels = len(unique_labels)

        bar = Bar('Running {} on {}...'.format(clsf_type, source))
        label_prediction_scores, misclassified_counts, confusion_matrix = \
            run_nfolds(data, sids, nfolds, niters, enum_labels, nlabels, classifier, bar)

        mean_label_prediction_scores = np.nanmean(label_prediction_scores)
        std_label_prediction_scores = np.nanstd(label_prediction_scores)

        if csv_filename:
            lines = []
            with open(csv_filename, 'w', encoding='utf-8') as f:
                misclassified_counts_sorted_indx = np.argsort(misclassified_counts)[::-1]
                misclassified_counts_sorted = misclassified_counts[misclassified_counts_sorted_indx]
                sids_sorted = sids[misclassified_counts_sorted_indx]
                labels_sorted = labels[misclassified_counts_sorted_indx]

                lines.append('Label prediction mean, stdev,')
                lines.append('{},{},'.format(mean_label_prediction_scores, std_label_prediction_scores))

                lines.append('ID,Label,Misclassification count')
                for sylid, label, count in zip(sids_sorted, labels_sorted, misclassified_counts_sorted):
                    line = '{},{},{}'.format(sylid, label, count)
                    lines.append(line)

                lines[0] += ',,,Confusion Matrix'
                lines[1] += ',,,{}'.format(','.join(unique_labels))

                for i in range(nlabels):
                    lines[i + 2] += ',,{},{}'.format(unique_labels[i], ','.join(list(map(str, confusion_matrix[i,:]))))

                for line in lines:
                    f.write(line)
                    f.write('\n')


