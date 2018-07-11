r"""
For a specific classifier and data source, for each set of features and aggregators, run classification on the data
and export the result.
"""

import numpy as np
from django.core.management.base import BaseCommand
from dotmap import DotMap
from progress.bar import Bar
from scipy.io import loadmat
from scipy.stats import zscore

from koe.features.feature_extract import feature_whereabout, feature_map
from koe.management.commands.run_kfold_validation import run_nfolds, classifiers

aggregator_groups = {
    'stats': [np.mean, np.median, np.std, ],
    'dtw_chirp': [
        ('dtw_chirp', 'pipe'),
        ('dtw_chirp', 'squeak-up'),
        ('dtw_chirp', 'squeak-down'),
        ('dtw_chirp', 'squeak-convex'),
        ('dtw_chirp', 'squeak-concave')
    ]
}


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
        fnames = [x.strip() for x in saved.fnames]

        classifier = classifiers[clsf_type]
        nsyls = len(sids)

        unique_labels, enum_labels = np.unique(labels, return_inverse=True)
        nlabels = len(unique_labels)

        done = []

        if csv_filename is None:
            csv_filename = 'multiple_{}_{}.csv'.format(clsf_type, source)

        with open(csv_filename, 'w', encoding='utf-8') as f:
            f.write('Feature group, Aggratation method, Recognition rate\n')
            for aggregators_name, aggregators in aggregator_groups.items():
                for ftgroup_module, ftgroup in feature_whereabout.items():
                    ftgroup_name = ftgroup_module.__name__[len('koe.features.'):]
                    ft_names = [x[0] for x in ftgroup]
                    fnames_modifs = []

                    for ft_name in ft_names:
                        feature = feature_map[ft_name]
                        if feature.is_fixed_length:
                            fnames_modifs.append(ft_name)
                        else:
                            for aggregator in aggregators:
                                if isinstance(aggregator, tuple) and aggregator[0] == 'dtw_chirp':
                                    chirp_type = aggregator[1]
                                    fnames_modif = '{}_{}_{}'.format(ft_name, 'chirp', chirp_type)
                                else:
                                    fnames_modif = '{}_{}'.format(ft_name, aggregator.__name__)
                                fnames_modifs.append(fnames_modif)

                    matched = []
                    ft_inds = []

                    for fnames_modif in fnames_modifs:
                        for idx, fname in enumerate(fnames):
                            if fname.startswith(fnames_modif):
                                matched.append(fname)
                                ft_inds.append(idx)

                    ft_inds = np.array(ft_inds)
                    ft_inds.sort()
                    ft_inds_key = '-'.join(map(str, ft_inds))
                    if ft_inds_key not in done:
                        done.append(ft_inds_key)

                        bar = Bar('Running {} on {}...'.format(clsf_type, source))
                        data_ = data[:, ft_inds]
                        label_prediction_scores, _, _ = run_nfolds(data_, nsyls, nfolds, niters, enum_labels, nlabels,
                                                                   classifier, bar)
                        rate = np.nanmean(label_prediction_scores)
                        result = '{},{},{}'.format(ftgroup_name, aggregators_name, rate)
                        print(result)
                        f.write(result)
                        f.write('\n')
                        f.flush()
