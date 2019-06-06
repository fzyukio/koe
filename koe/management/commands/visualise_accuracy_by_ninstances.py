import os
import re
import plotly
import plotly.graph_objs as go
import plotly.io as pio

import argparse
import numpy as np
import plotly.plotly as py

from django.core.management.base import BaseCommand
from scipy.stats import ttest_ind

import colorlover as cl

plotly.tools.set_credentials_file(username='wBIr68ns', api_key='LAK0vePuQsXlQQFYaKJv')


class TestSuit:
    def __init__(self):
        self.feature_group = ''
        self.accuracies = []


class ClassiferTestSuits:
    def __init__(self, classifier, dimensionality, num_instance):
        self.classifier = classifier
        self.dimensionality = dimensionality
        self.num_instance = num_instance
        self.suits = []


excluded_feature_groups = ['mfc', 'mfcc+', 'mfcc_delta_only', 'lpcoefs']


def read_csv(filepath, classifier, dimensionality, num_instance):
    classifier_test_suits = ClassiferTestSuits(classifier, dimensionality, num_instance)
    new_section = True
    with open(filepath, 'r') as f:
        line = f.readline()
        while line != '':
            parts = line.strip().split('\t')
            if new_section:
                feature_group = parts[0]
                suit = TestSuit()
                new_section = False
                suit.feature_group = feature_group
                if feature_group not in excluded_feature_groups:
                    classifier_test_suits.suits.append(suit)
            elif parts[0] == 'Accuracy:':
                line = f.readline()
                parts = line.strip().split('\t')
                suit.accuracies = np.array(list(map(float, parts[1:])))
            elif parts[0] == '':
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

        accuracy_rates_all = accuracy_rates_populations['all']
        for feature_group, accuracy_rates in accuracy_rates_populations.items():
            if feature_group != 'all':
                t, p = ttest_ind(accuracy_rates, accuracy_rates_all)
                t_values[feature_group] = t
                p_values[feature_group] = p

        return t_values, p_values


def ttest_compare_num_instances(classifier_test_suitss, classifier, dimensionality, base_ninstances, deriv_ninstances):
    base = {}
    deriv = {}

    for classifier_test_suits in classifier_test_suitss:
        if classifier_test_suits.dimensionality != dimensionality:
            continue
        if classifier_test_suits.classifier != classifier:
            continue
        for suit in classifier_test_suits.suits:
            if suit.feature_group == 'all':
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


nCategoricalColours = 11

rgb_pattern = re.compile('rgb\((\d+), *(\d+), *(\d+)\)')


def add_alpha(rgb, alpha):
    decomposed = rgb_pattern.match(rgb)
    if decomposed is None:
        raise Exception('{} is not RGB pattern'.format(rgb))
    r = decomposed.group(1)
    g = decomposed.group(2)
    b = decomposed.group(3)

    return 'rgba({},{},{},{})'.format(r, g, b, alpha)


def main(csv_dir):
    classifiers = ['nnet', 'svm_linear', 'rf', 'svm_rbf']
    dimensionalities = ['full', 'pca']
    num_instances = ['150-{}'.format(x) for x in range(20, 150, 10)] + ['150']
    prefix = 'kfold_bestparam_tmi'

    if not os.path.isdir(csv_dir):
        raise Exception('{} is not a folder'.format(csv_dir))

    classifier_test_suitss = []

    for classifier in classifiers:
        for dimensionality in dimensionalities:
            for num_instance in num_instances:
                filename = '{}_{}_{}.{}.tsv'.format(prefix, classifier, dimensionality, num_instance)
                filepath = os.path.join(csv_dir, filename)
                classifier_test_suits = read_csv(filepath, classifier, dimensionality, num_instance)
                classifier_test_suitss.append(classifier_test_suits)

    for classifier in classifiers:
        averagess, stdevss = extract_accuracies_by_ninstances(classifier_test_suitss, classifier, 'full', num_instances)

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
            colour = cl.scales[str(nlines)]['div']['Spectral']
        else:
            colour = cl.to_rgb(cl.interp(cl.scales[str(nCategoricalColours)]['div']['Spectral'], nlines))
        for idx, feature_group in enumerate(feature_groups):
            line_colour = colour[idx]
            shade_colour = add_alpha(line_colour, 0.5)

            upper_bound = go.Scatter(
                name='Upper Bound',
                hoverinfo='skip',
                x=ninstances_axis,
                y=accuracy_axis[feature_group] + stdev_axis[feature_group],
                mode='lines',
                line=dict(width=0),
                fillcolor=shade_colour,
                fill='tonexty'
            )

            lower_bound = go.Scatter(
                name='Lower Bound',
                hoverinfo='skip',
                x=ninstances_axis,
                y=accuracy_axis[feature_group] - stdev_axis[feature_group],
                line=dict(width=0),
                mode='lines'
            )

            trace = go.Scatter(
                name=feature_group,
                x=ninstances_axis,
                y=accuracy_axis[feature_group],
                mode='lines+markers',
                marker=dict(
                    symbol='circle',
                    size=5,
                    opacity=1,
                    line=dict(
                        width=0.5
                    )
                ),
                line=dict(color=line_colour),
                fillcolor=shade_colour,
            )

            bounds += [lower_bound, upper_bound]
            traces += [trace]

        data = bounds + traces
        layout = go.Layout(
            yaxis=dict(title='Accuracy'),
            xaxis=dict(title='Number of instances'),
            title='Accuracy by number of instances using {}'.format(classifier),
            showlegend=True)

        fig = go.Figure(data=data, layout=layout)
        plot = py.iplot(fig, filename='Accuracy by number of instances using {}'.format(classifier))
        print('{}: {}'.format(classifier, plot.resource))
        pio.write_image(fig, '{}.pdf'.format(classifier))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Process some integers.')
    parser.add_argument('--csv-dir', action='store', dest='csv_dir', required=True, type=str)
    args = parser.parse_args()

    csv_dir = args.csv_dir
    main(csv_dir)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--csv-dir', action='store', dest='csv_dir', required=True, type=str)

    def handle(self, *args, **options):
        csv_dir = options['csv_dir']
        main(csv_dir)
