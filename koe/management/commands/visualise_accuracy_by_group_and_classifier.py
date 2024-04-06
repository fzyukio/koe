import argparse
import os
import re

from django.core.management.base import BaseCommand

import colorlover as cl
import numpy as np
import plotly
import plotly.graph_objs as go
import plotly.io as pio
import plotly.plotly as py
from scipy.stats import ttest_ind


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


def extract_accuracies_by_ninstances(classifier_test_suitss, classifier, dimensionality):
    stdevs = {}
    averages = {}

    for classifier_test_suits in classifier_test_suitss:
        if classifier_test_suits.dimensionality != dimensionality:
            continue
        if classifier_test_suits.classifier != classifier:
            continue
        for suit in classifier_test_suits.suits:
            mean = np.mean(suit.accuracies)
            stdev = np.std(suit.accuracies)
            stdevs[suit.feature_group] = stdev
            averages[suit.feature_group] = mean
    return averages, stdevs


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
    num_instance = 100
    prefix = "kfold_bestparam_tmi"

    if not os.path.isdir(csv_dir):
        raise Exception("{} is not a folder".format(csv_dir))

    classifier_test_suitss = []

    for classifier in classifiers:
        for dimensionality in dimensionalities:
            filename = "{}_{}_{}.{}.tsv".format(prefix, classifier, dimensionality, num_instance)
            filepath = os.path.join(csv_dir, filename)
            classifier_test_suits = read_csv(filepath, classifier, dimensionality, num_instance)
            classifier_test_suitss.append(classifier_test_suits)

    for dimensionality in dimensionalities:
        feature_group_props = {}
        for classifier in classifiers:
            averages, stdevs = extract_accuracies_by_ninstances(classifier_test_suitss, classifier, dimensionality)
            nlines = len(averages)
            if nlines <= nCategoricalColours:
                colour = cl.scales[str(nlines)]["div"]["Spectral"]
            else:
                colour = cl.to_rgb(cl.interp(cl.scales[str(nCategoricalColours)]["div"]["Spectral"], nlines))

            for idx, feature_group in enumerate(averages):
                if feature_group not in feature_group_props:
                    feature_group_props[feature_group] = dict(x=[], y=[], stdev=[], colour=[])
                props = feature_group_props[feature_group]
                props["x"].append(classifier)
                props["y"].append(1 - averages[feature_group])
                props["stdev"].append(stdevs[feature_group])
                props["colour"].append(colour[idx])

        traces = []
        for feature_group, props in feature_group_props.items():
            print(feature_group)
            print(props)
            trace = go.Bar(
                x=props["x"],
                y=props["y"],
                name=feature_group,
                error_y=dict(type="data", array=props["stdev"], visible=True),
                marker=dict(color=props["colour"]),
            )
            traces.append(trace)

        layout = go.Layout(barmode="group", showlegend=True)
        fig = go.Figure(data=traces, layout=layout)
        plot = py.iplot(
            fig,
            filename="Accuracy and error bar all classifier. Dimensions = {}. Ninstances = {}".format(
                dimensionality, num_instance
            ),
        )
        print(plot.resource)
        pio.write_image(fig, "{}-{}.pdf".format(dimensionality, num_instance))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument("--csv-dir", action="store", dest="csv_dir", required=True, type=str)
    args = parser.parse_args()

    csv_dir = args.csv_dir
    main(csv_dir)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("--csv-dir", action="store", dest="csv_dir", required=True, type=str)

    def handle(self, *args, **options):
        csv_dir = options["csv_dir"]
        main(csv_dir)
