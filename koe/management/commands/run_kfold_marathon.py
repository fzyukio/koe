r"""
For a specific classifier and data source, do the following:
 - Determine the recognition rates (mean and std) when all features are used.
 - Set the cutoff value to be mean - std
 - Start with one feature
 - Repeat:
     - Run the classifier and determine the feature that yields the highest score
     - If this highest score is >= the cutoff value, finish and report
     - Otherwise, increase the number of features. In the next round, determine the feature that when bundled with
      the best features that have been selected in the previous rounds, yield the best result
"""

import numpy as np
from django.core.management.base import BaseCommand
from dotmap import DotMap
from progress.bar import Bar
from scipy.io import loadmat
from scipy.stats import zscore

from koe.ml_utils import classifiers, run_nfolds


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--classifier', action='store', dest='clsf_type', required=True, type=str,
                            help='Can be svm, rf (Random Forest), gnb (Gaussian Naive Bayes), lda', )

        parser.add_argument('--matfile', action='store', dest='matfile', required=True, type=str,
                            help='Name of the .mat file that stores extracted feature values for Matlab', )

        parser.add_argument('--source', action='store', dest='source', required=True, type=str,
                            help='Can be raw or norm', )

        parser.add_argument('--nfolds', action='store', dest='nfolds', required=False, default=100, type=int)

        parser.add_argument('--niters', action='store', dest='niters', required=False, default=1, type=int)

        parser.add_argument('--to-csv', dest='csv_filename', action='store', required=False)

    def handle(self, clsf_type, matfile, source, nfolds, niters, csv_filename, *args, **options):
        assert clsf_type in classifiers.keys(), 'Unknown _classify: {}'.format(clsf_type)
        assert source in ['raw', 'norm']

        saved = DotMap(loadmat(matfile))
        sids = saved.sids.ravel()
        dataset = saved.dataset
        labels = saved.labels
        haslabel_ind = np.where(labels != '                              ')[0]

        labels = labels[haslabel_ind]
        labels = np.array([x.strip() for x in labels])
        sids = sids[haslabel_ind]

        dataset = dataset[haslabel_ind]
        meas = zscore(dataset)

        data_sources = {
            'raw': dataset,
            'norm': meas
        }

        data = data_sources[source]
        fnames = saved.fnames
        nfeatures = len(fnames)

        classifier = classifiers[clsf_type]
        nsyls = len(sids)

        unique_labels, enum_labels = np.unique(labels, return_inverse=True)
        nlabels = len(unique_labels)

        max_rates = []
        best_fts_ids = []
        best_fts_names = []

        # What is the recognition rate when all features are used?
        bar = Bar('Running {} on {} using all features ...'.format(clsf_type, source))
        label_prediction_scores, _, _ = run_nfolds(data, nsyls, nfolds, niters, enum_labels, nlabels, classifier, bar)
        mean_label_prediction_scores = np.nanmean(label_prediction_scores)
        std_label_prediction_scores = np.nanstd(label_prediction_scores)

        cutoff = mean_label_prediction_scores - std_label_prediction_scores
        print('Cutoff value is {}'.format(cutoff))
        i = 0

        if csv_filename is None:
            csv_filename = 'marathon_{}_{}.csv'.format(clsf_type, source)
        with open(csv_filename, 'w', encoding='utf-8') as f:
            f.write('Feature name, Recognition rate\n')
            f.flush()
            while True:
                rates = np.full((nfeatures,), np.nan)

                bar = Bar('Running {} on {}...'.format(clsf_type, source), max=nfeatures)

                for j in range(nfeatures):
                    if j in best_fts_ids:
                        bar.next()
                        continue

                    combined_ft_inds = np.concatenate((np.array(best_fts_ids, dtype=int), np.array([j], dtype=int)))

                    data_ = data[:, combined_ft_inds]

                    label_prediction_scores, _, _ = run_nfolds(data_, nsyls, nfolds, niters, enum_labels, nlabels,
                                                               classifier, None)
                    rates[j] = np.nanmean(label_prediction_scores)
                    bar.next()
                bar.finish()

                best_fts_id = np.nanargmax(rates)
                best_fts_name = fnames[best_fts_id]
                max_rate = rates[best_fts_id]

                best_fts_ids.append(best_fts_id)
                best_fts_names.append(best_fts_name)
                max_rates.append(max_rate)

                print('nFeatures={} Rate={} Ft={}'.format(i + 1, max_rate, best_fts_name))
                f.write('{},{}\n'.format(best_fts_name, max_rate))
                f.flush()

                i += 1
                if i >= nfeatures or max_rate >= cutoff:
                    break
