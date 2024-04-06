import argparse
import os
import re
from collections import Counter

from django.core.management.base import BaseCommand

import colorlover as cl
import numpy as np
import plotly
import plotly.graph_objs as go
import plotly.io as pio
import plotly.plotly as py
from scipy.stats import ttest_ind

from koe.features.feature_extract import feature_map
from koe.management.commands.lstm import exclude_no_labels, get_labels_by_sids
from koe.model_utils import get_or_error
from koe.models import Aggregation, Database, DataMatrix, Feature
from koe.storage_utils import get_tids
from koe.ts_utils import bytes_to_ndarray
from root.models import ExtraAttrValue, User


nCategoricalColours = 11
rgb_pattern = re.compile("rgb\((\d+), *(\d+), *(\d+)\)")
plotly.tools.set_credentials_file(username="wBIr68ns", api_key="LAK0vePuQsXlQQFYaKJv")


class TestSuit:
    def __init__(self):
        self.feature_group = ""
        self.accuracies = []


class ClassiferTestSuits:
    def __init__(self, classifier, dimensionality, num_instance):
        self.classifier = classifier
        self.dimensionality = dimensionality
        self.num_instance = num_instance
        self.suits = []


excluded_feature_groups = ["mfc", "mfcc+", "mfcc_delta_only", "lpcoefs"]


def read_csv(filepath, classifier, dimensionality, num_instance):
    classifier_test_suits = ClassiferTestSuits(classifier, dimensionality, num_instance)
    new_section = True
    with open(filepath, "r") as f:
        line = f.readline()
        while line != "":
            parts = line.strip().split("\t")
            if new_section:
                feature_group = parts[0]
                suit = TestSuit()
                new_section = False
                suit.feature_group = feature_group
                if feature_group not in excluded_feature_groups:
                    classifier_test_suits.suits.append(suit)
            elif parts[0] == "Accuracy:":
                line = f.readline()
                parts = line.strip().split("\t")
                suit.accuracies = np.array(list(map(float, parts[1:])))
            elif parts[0] == "":
                new_section = True
            line = f.readline()
    return classifier_test_suits


def ttest_compare_feature_groups(classifier_test_suitss, classifier, dimensionality, num_instance):
    t_values = {}
    p_values = {}

    for classifier_test_suits in classifier_test_suitss:
        if classifier_test_suits.dimensionality != dimensionality:
            continue
        if classifier_test_suits.num_instance != num_instance:
            continue
        if classifier_test_suits.classifier != classifier:
            continue

        accuracy_rates_populations = {}
        for suit in classifier_test_suits.suits:
            accuracy_rates_populations[suit.feature_group] = suit.accuracies

        accuracy_rates_all = accuracy_rates_populations["all"]
        for feature_group, accuracy_rates in accuracy_rates_populations.items():
            if feature_group != "all":
                t, p = ttest_ind(accuracy_rates, accuracy_rates_all)
                t_values[feature_group] = t
                p_values[feature_group] = p

        return t_values, p_values


def ttest_compare_num_instances(
    classifier_test_suitss,
    classifier,
    dimensionality,
    base_ninstances,
    deriv_ninstances,
):
    base = {}
    deriv = {}

    for classifier_test_suits in classifier_test_suitss:
        if classifier_test_suits.dimensionality != dimensionality:
            continue
        if classifier_test_suits.classifier != classifier:
            continue
        for suit in classifier_test_suits.suits:
            if suit.feature_group == "all":
                if classifier_test_suits.num_instance == base_ninstances:
                    base[classifier_test_suits.classifier] = suit
                else:
                    deriv[classifier_test_suits.classifier] = suit
                break


def extract_accuracies_by_ninstances(classifier_test_suitss, classifier, dimensionality, ninstances):
    stdevss = {x: {} for x in ninstances}
    averagess = {x: {} for x in ninstances}

    for classifier_test_suits in classifier_test_suitss:
        if classifier_test_suits.dimensionality != dimensionality:
            continue
        if classifier_test_suits.classifier != classifier:
            continue
        ninstance = classifier_test_suits.num_instance
        stdevs = stdevss[ninstance]
        averages = averagess[ninstance]
        for suit in classifier_test_suits.suits:
            mean = np.mean(suit.accuracies)
            stdev = np.std(suit.accuracies)
            stdevs[suit.feature_group] = stdev
            averages[suit.feature_group] = mean
    return averagess, stdevss


def add_alpha(rgb, alpha):
    decomposed = rgb_pattern.match(rgb)
    if decomposed is None:
        raise Exception("{} is not RGB pattern".format(rgb))
    r = decomposed.group(1)
    g = decomposed.group(2)
    b = decomposed.group(3)

    return "rgba({},{},{},{})".format(r, g, b, alpha)


def main(csv_dir):
    classifiers = ["nnet", "svm_linear", "rf", "svm_rbf"]
    dimensionalities = ["full", "pca"]
    num_instances = ["150-{}".format(x) for x in range(20, 150, 10)] + ["150"]
    prefix = "kfold_bestparam_tmi"

    if not os.path.isdir(csv_dir):
        raise Exception("{} is not a folder".format(csv_dir))

    classifier_test_suitss = []

    for classifier in classifiers:
        for dimensionality in dimensionalities:
            for num_instance in num_instances:
                filename = "{}_{}_{}.{}.tsv".format(prefix, classifier, dimensionality, num_instance)
                filepath = os.path.join(csv_dir, filename)
                classifier_test_suits = read_csv(filepath, classifier, dimensionality, num_instance)
                classifier_test_suitss.append(classifier_test_suits)

    for classifier in classifiers:
        averagess, stdevss = extract_accuracies_by_ninstances(
            classifier_test_suitss, classifier, "full", num_instances
        )

        ninstances_axis = list(averagess.keys())
        stdev_axis = {}
        accuracy_axis = {}
        feature_groups = []
        for ninstance in averagess:
            for feature_group in averagess[ninstance]:
                if feature_group not in feature_groups:
                    feature_groups.append(feature_group)
                    stdev_axis[feature_group] = []
                    accuracy_axis[feature_group] = []

                stdev_axis[feature_group].append(stdevss[ninstance][feature_group])
                accuracy_axis[feature_group].append(averagess[ninstance][feature_group])

        for ninstance in averagess:
            for feature_group in averagess[ninstance]:
                stdev_axis[feature_group] = np.array(stdev_axis[feature_group])
                accuracy_axis[feature_group] = np.array(accuracy_axis[feature_group])

        bounds = []
        traces = []
        nlines = len(feature_groups)
        if nlines <= nCategoricalColours:
            colour = cl.scales[str(nlines)]["div"]["Spectral"]
        else:
            colour = cl.to_rgb(cl.interp(cl.scales[str(nCategoricalColours)]["div"]["Spectral"], nlines))
        for idx, feature_group in enumerate(feature_groups):
            line_colour = colour[idx]
            shade_colour = add_alpha(line_colour, 0.5)

            upper_bound = go.Scatter(
                name="Upper Bound",
                hoverinfo="skip",
                x=ninstances_axis,
                y=accuracy_axis[feature_group] + stdev_axis[feature_group],
                mode="lines",
                line=dict(width=0),
                fillcolor=shade_colour,
                fill="tonexty",
            )

            lower_bound = go.Scatter(
                name="Lower Bound",
                hoverinfo="skip",
                x=ninstances_axis,
                y=accuracy_axis[feature_group] - stdev_axis[feature_group],
                line=dict(width=0),
                mode="lines",
            )

            trace = go.Scatter(
                name=feature_group,
                x=ninstances_axis,
                y=accuracy_axis[feature_group],
                mode="lines+markers",
                marker=dict(symbol="circle", size=5, opacity=1, line=dict(width=0.5)),
                line=dict(color=line_colour),
                fillcolor=shade_colour,
            )

            bounds += [lower_bound, upper_bound]
            traces += [trace]

        data = bounds + traces
        layout = go.Layout(
            yaxis=dict(title="Accuracy"),
            xaxis=dict(title="Number of instances"),
            title="Accuracy by number of instances using {}".format(classifier),
            showlegend=True,
        )

        fig = go.Figure(data=data, layout=layout)
        plot = py.iplot(fig, filename="Accuracy by number of instances using {}".format(classifier))
        print("{}: {}".format(classifier, plot.resource))
        pio.write_image(fig, "{}.pdf".format(classifier))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument("--csv-dir", action="store", dest="csv_dir", required=True, type=str)
    args = parser.parse_args()

    csv_dir = args.csv_dir
    main(csv_dir)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--database-name",
            action="store",
            dest="database_name",
            required=True,
            type=str,
            help="E.g Bellbird, Whale, ..., case insensitive",
        )

        parser.add_argument(
            "--annotator-name",
            action="store",
            dest="annotator_name",
            default="superuser",
            type=str,
            help="Name of the person who owns this database, case insensitive",
        )

        parser.add_argument(
            "--label-level",
            action="store",
            dest="label_level",
            default="label",
            type=str,
            help="Level of labelling to use",
        )

        parser.add_argument(
            "--min-occur",
            action="store",
            dest="min_occur",
            default=2,
            type=int,
            help="Ignore syllable classes that have less than this number of instances",
        )

    def handle(self, *args, **options):
        database_name = options["database_name"]
        annotator_name = options["annotator_name"]
        label_level = options["label_level"]
        min_occur = options["min_occur"]

        database = get_or_error(Database, dict(name__iexact=database_name))
        annotator = get_or_error(User, dict(username__iexact=annotator_name))

        features = Feature.objects.all().order_by("id")
        aggregations = Aggregation.objects.filter(enabled=True).order_by("id")

        enabled_features = []
        for f in features:
            if f.name in feature_map:
                enabled_features.append(f)

        features_hash = "-".join(list(map(str, [x.id for x in enabled_features])))
        aggregations_hash = "-".join(list(map(str, aggregations.values_list("id", flat=True))))

        dm = DataMatrix.objects.filter(
            database=database,
            features_hash=features_hash,
            aggregations_hash=aggregations_hash,
        ).last()
        if dm is None:
            raise Exception("No full data matrix for database {}".format(database_name))

        dm_sids_path = dm.get_sids_path()
        dm_tids_path = dm.get_tids_path()

        _sids = bytes_to_ndarray(dm_sids_path, np.int32)
        _sids, sort_order = np.unique(_sids, return_index=True)

        try:
            _tids = bytes_to_ndarray(dm_tids_path, np.int32)
            _tids = _tids[sort_order]
        except FileNotFoundError:
            _tids = get_tids(_sids)

        labels, no_label_ids = get_labels_by_sids(_sids, label_level, annotator, min_occur)

        if len(no_label_ids) > 0:
            sids, tids, labels = exclude_no_labels(_sids, _tids, labels, no_label_ids)

        sid2lbl = {
            x: y.lower()
            for x, y in ExtraAttrValue.objects.filter(
                attr__name=label_level, owner_id__in=_sids, user=annotator
            ).values_list("owner_id", "value")
        }

        occurs = Counter(sid2lbl.values())
        layout = go.Layout(
            xaxis=dict(
                tickmode="linear",
                ticks="outside",
                dtick=10,
            ),
        )

        x = list(occurs.values())
        x_min = np.min(x)
        data = [
            go.Histogram(
                x=x,
                xbins=dict(start=x_min, end=200, size=10),
                # histnorm='probability'
            )
        ]
        fig = go.Figure(data=data, layout=layout)

        plot = py.iplot(fig, filename="Histogram of class distribution")

        print(plot.resource)
        pio.write_image(fig, "histogram.pdf")
