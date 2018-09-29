r"""
Clustering validation.
"""

import numpy as np
from django.core.management.base import BaseCommand
from dotmap import DotMap
from progress.bar import Bar
from scipy.io import loadmat
from scipy.stats import zscore

from koe.ml_utils import run_nfolds, classifiers


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
        if source == 'tsne':
            fnames = ['Dim{}'.format(x) for x in range(clusters.shape[1])]
        else:
            if ft_idx:
                fnames = saved.fnames[ft_idx]
            else:
                fnames = saved.fnames

        classifier = classifiers[clsf_type]
        nsyls = len(sids)

        unique_labels, enum_labels = np.unique(labels, return_inverse=True)
        nlabels = len(unique_labels)

        bar = Bar('Running {} on {}...'.format(clsf_type, source))
        label_prediction_scores, label_hitrates, importancess = \
            run_nfolds(data, nsyls, nfolds, niters, enum_labels, nlabels, classifier, bar)

        mean_label_prediction_scores = np.nanmean(label_prediction_scores)
        std_label_prediction_scores = np.nanstd(label_prediction_scores)

        if csv_filename:
            with open(csv_filename, 'w', encoding='utf-8') as f:
                f.write('Label prediction mean\t stdev\t {}\n'.format('\t '.join(unique_labels)))
                f.write('{}\t {}\t {}\n'.format(mean_label_prediction_scores, std_label_prediction_scores,
                                                '\t'.join(map(str, np.nanmean(label_hitrates, 0)))))
                f.write('Importances: \n')
                f.write('{}\n'.format('\t'.join(fnames)))
                f.write('{}\n'.format('\t'.join(map(str, np.mean(importancess, 0)))))
        else:
            print('{} by {}: mean = {} std = {}'.format(clsf_type, source, mean_label_prediction_scores,
                                                        std_label_prediction_scores))
