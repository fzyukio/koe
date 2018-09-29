"""
Run tsne with different numbers of dimensions, svm and export result
"""

import numpy as np
from django.core.management.base import BaseCommand
from dotmap import DotMap
from progress.bar import Bar
from scipy.io import loadmat
from scipy.io import savemat
from scipy.stats import zscore

from koe.ml_utils import run_clustering, classifiers, run_nfolds

from sklearn.decomposition import PCA, FastICA

reduce_funcs = {
    'ica': FastICA,
    'pca': PCA,
    'none': None
}


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--classifier', action='store', dest='clsf_type', required=True, type=str,
                            help='Can be svm, rf (Random Forest), gnb (Gaussian Naive Bayes), lda', )

        parser.add_argument('--matfile', action='store', dest='matfile', required=True, type=str,
                            help='Name of the .mat file that stores extracted feature values for Matlab', )

        parser.add_argument('--nfolds', action='store', dest='nfolds', required=False, default=100, type=int)

        parser.add_argument('--niters', action='store', dest='niters', required=False, default=1, type=int)

        parser.add_argument('--ndims', action='store', dest='ndims', required=False, type=int)

        parser.add_argument('--reduce-type', action='store', dest='reduce_type', required=False, type=str)

    def handle(self, clsf_type, matfile, nfolds, niters, ndims, reduce_type, *args, **options):
        assert clsf_type in classifiers.keys(), 'Unknown classifier: {}'.format(clsf_type)
        assert reduce_type in reduce_funcs.keys(), 'Unknown function: {}'.format(reduce_type)

        saved = DotMap(loadmat(matfile))
        sids = saved.sids.ravel()
        dataset = saved.dataset
        dataset = zscore(dataset)
        labels = saved.labels
        labels = np.array([x.strip() for x in labels])
        haslabel_ind = np.where(labels != '')[0]

        labels = labels[haslabel_ind]
        sids = sids[haslabel_ind]
        dataset = dataset[haslabel_ind, :]
        nsyls = len(sids)
        unique_labels, enum_labels = np.unique(labels, return_inverse=True)
        nlabels = len(unique_labels)
        classifier = classifiers[clsf_type]
        reduce_func = reduce_funcs[reduce_type]

        bar = Bar('RUnning TSNE with {} dimensions'.format(ndims))

        if ndims:
            tsne_name = 'tsne_{}_{}'.format(reduce_type, ndims)
            if tsne_name not in saved:
                tsne_results = run_clustering(dataset, dim_reduce=reduce_func, n_components=ndims)
                saved[tsne_name] = tsne_results
                savemat(matfile, saved)
            else:
                tsne_results = saved[tsne_name]
        else:
            if 'tsne_full' not in saved:
                tsne_results = run_clustering(dataset, None, None)
                saved.tsne_full = tsne_results
                savemat(matfile, saved)
            else:
                tsne_results = saved.tsne_full

        label_prediction_scores, _, _ = run_nfolds(tsne_results, nsyls, nfolds, niters, enum_labels, nlabels,
                                                   classifier, bar)

        rate = np.nanmean(label_prediction_scores)
        std = np.nanstd(label_prediction_scores)

        print('{}, {}'.format(rate, std))
