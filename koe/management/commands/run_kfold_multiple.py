r"""
For a specific classifier and data source, for each set of features and aggregators, run classification on the data
and export the result.
"""

import datetime
from logging import warning

from django.core.management.base import BaseCommand

import numpy as np
from progress.bar import Bar
from scipy.io import loadmat
from scipy.stats import zscore

from koe.aggregator import enabled_aggregators
from koe.features.feature_extract import feature_whereabout
from koe.ml_utils import classifiers, run_nfolds


aggregators_names = list(enabled_aggregators.keys())
ftgroup_names = [x.__name__[len("koe.features.") :] for x in feature_whereabout.keys()]


def get_data(aggregators_name, ftgroup_name, saved):
    selected_aggregators_names = aggregators_names if aggregators_name == "all" else [aggregators_name]
    selected_ftgroup_names = ftgroup_names if ftgroup_name == "all" else [ftgroup_name]

    selected_keys = ["rawdata:{}:{}".format(a, f) for a in selected_aggregators_names for f in selected_ftgroup_names]

    if len(selected_keys) == 0:
        return None

    retval = []
    for key in selected_keys:
        if key not in saved:
            warning('Missing data {} when running on "all". Omitted for now'.format(key))
        else:
            retval.append(saved[key])

    if len(retval) == 0:
        return retval

    return np.concatenate(retval, axis=1)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--classifier",
            action="store",
            dest="clsf_type",
            required=True,
            type=str,
            help="Can be svm, rf (Random Forest), gnb (Gaussian Naive Bayes), lda",
        )

        parser.add_argument(
            "--matfile",
            action="store",
            dest="matfile",
            required=True,
            type=str,
            help="Name of the .mat file that stores extracted feature values for Matlab",
        )

        parser.add_argument(
            "--norm",
            dest="norm",
            action="store_true",
            default=False,
            help="If true, data will be normalised",
        )

        parser.add_argument(
            "--nfolds",
            action="store",
            dest="nfolds",
            required=False,
            default=100,
            type=int,
        )

        parser.add_argument(
            "--niters",
            action="store",
            dest="niters",
            required=False,
            default=1,
            type=int,
        )

        parser.add_argument("--to-csv", dest="csv_filename", action="store", required=False)

    def handle(self, clsf_type, matfile, norm, nfolds, niters, csv_filename, *args, **options):
        assert clsf_type in classifiers.keys(), "Unknown _classify: {}".format(clsf_type)

        saved = loadmat(matfile)
        sids = saved["sids"].ravel()
        labels = saved["labels"]
        labels = np.array([x.strip() for x in labels])

        classifier = classifiers[clsf_type]
        nsyls = len(sids)

        unique_labels, enum_labels = np.unique(labels, return_inverse=True)
        nlabels = len(unique_labels)

        if csv_filename is None:
            csv_filename = "csv/multiple.csv"

        with open(csv_filename, "a", encoding="utf-8") as f:
            f.write("\nRun time: {}\n".format(datetime.datetime.now()))
            f.write("Classifier={}, normalised={}, nfolds={}, niters={}\n".format(clsf_type, norm, nfolds, niters))
            f.write("Feature group, Aggregation method, Recognition rate\n")
            for aggregators_name in aggregators_names + ["all"]:
                for ftgroup_name in ftgroup_names + ["all"]:
                    rawdata = get_data(aggregators_name, ftgroup_name, saved)
                    if rawdata is None:
                        warning("Data for {}-{} not found. Skip".format(aggregators_name, ftgroup_name))
                    if norm:
                        data = zscore(rawdata)
                    else:
                        data = rawdata

                    if np.any(np.isnan(data)):
                        warning("Data containing NaN - set to 0")
                        data[np.where(np.isnan(data))] = 0

                    bar = Bar(
                        "Running {} normalised={}, feature={}, aggregator={}...".format(
                            clsf_type, norm, ftgroup_name, aggregators_name
                        )
                    )
                    label_prediction_scores, _, _ = run_nfolds(
                        data,
                        nsyls,
                        nfolds,
                        niters,
                        enum_labels,
                        nlabels,
                        classifier,
                        bar,
                    )
                    rate = np.nanmean(label_prediction_scores)
                    std = np.nanstd(label_prediction_scores)
                    result = "{},{},{},{}".format(ftgroup_name, aggregators_name, rate, std)
                    print(result)
                    f.write(result)
                    f.write("\n")
                    f.flush()
