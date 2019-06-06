import os
import pickle
from ast import literal_eval

import numpy as np
import plotly
import plotly.graph_objs as go
import plotly.plotly as py
import plotly.io as pio
from django.core.management.base import BaseCommand
from scipy import stats
import colorlover as cl

plotly.tools.set_credentials_file(username='wBIr68ns', api_key='LAK0vePuQsXlQQFYaKJv')

excluded_feature_groups = ['mfc', 'mfcc+', 'mfcc_delta_only', 'lpcoefs']


class TestSuit:
    def __init__(self):
        self.feature_group = ''
        self.params = {}
        self.accuracies = []
        self.ndims = 0


class ClassiferTestSuits:
    def __init__(self, classifier, dimensionality):
        self.classifier = classifier
        self.dimensionality = dimensionality
        self.suits = []


def read_csv(filepath, classifier, dimensionality):
    classifier_test_suits = ClassiferTestSuits(classifier, dimensionality)
    with open(filepath, 'r') as f:
        line = f.readline()
        while line != '':
            parts = line.strip().split('\t')
            if parts[0] == 'id':
                suit = TestSuit()
                while True:
                    line = f.readline()
                    parts = line.strip().split('\t')
                    if parts[0] == 'accuracy':
                        suit.accuracies = np.array(list(map(float, parts[1:])))
                    else:
                        if len(suit.accuracies) == 0:
                            param_name = parts[0]
                            suit.params[param_name] = parts[1:]
                        else:
                            if parts[0] == 'Feature group':
                                line = f.readline()
                                parts = line.strip().split('\t')
                                suit.feature_group = parts[0]
                                suit.ndims = int(parts[1])
                                classifier_test_suits.suits.append(suit)
                                break
            line = f.readline()
    return classifier_test_suits


plotlyMarkerSymbols = ['circle', 'cross', 'square', 'diamond', 'triangle-up', 'star']
nCategoricalColours = 11
# categoricalColourScale = list(cl.scales['11']['div']['Spectral'])
# nCategoricalColours = len(categoricalColourScale)


converters = {
    'svm_rbf': {
        'C': lambda x: np.log10(float(x)),
        'gamma': lambda x: float(x)
    },
    'svm_linear': {
        'C': lambda x: np.log10(float(x)),
    },
    'nnet': {
        'hidden_layer_sizes': lambda x: literal_eval(x)[0]
    },
    'rf': {
        'n_estimators': lambda x: int(np.round(float(x))),
        'min_samples_split': lambda x: int(np.round(float(x))),
        'min_samples_leaf': lambda x: int(np.round(float(x))),
    },
}


def analyse(classifier_test_suitss):
    retval = {}

    for classifier_test_suits in classifier_test_suitss:
        classifier = classifier_test_suits.classifier

        if classifier not in retval:
            retval[classifier] = dict(
                params={},
                accuracies=[],
                groups=[],
                markers={},
                colours={},
                marker_idx=0,
                colour_idx=0
            )
        params = retval[classifier]['params']
        accuracies = retval[classifier]['accuracies']
        groups = retval[classifier]['groups']
        markers = retval[classifier]['markers']
        colours = retval[classifier]['colours']
        marker_idx = retval[classifier]['marker_idx']
        colour_idx = retval[classifier]['colour_idx']

        dimensionality = classifier_test_suits.dimensionality
        if dimensionality == 'pca':
            continue

        suits = [x for x in classifier_test_suits.suits if x.feature_group not in excluded_feature_groups]

        nClasses = len(suits)
        if nClasses <= nCategoricalColours:
            colour = cl.scales[str(nClasses)]['div']['Spectral']
        else:
            colour = cl.to_rgb(cl.interp(cl.scales[str(nCategoricalColours)]['div']['Spectral'], nClasses))

        param_names = list(suits[0].params.keys())

        for suit in suits:
            feature_group = suit.feature_group
            group_name = '{}-{}'.format(feature_group, dimensionality)

            for param_name in param_names:
                converter = converters[classifier][param_name]
                param = suit.params[param_name]
                if param_name not in params:
                    params[param_name] = []
                params[param_name] += [converter(x) for x in param]

            for i in range(len(suit.accuracies)):
                acc = suit.accuracies[i]
                accuracies.append(acc)
                groups.append(group_name)

                if dimensionality not in markers:
                    markers[dimensionality] = plotlyMarkerSymbols[marker_idx]
                    marker_idx += 1
                markers[group_name] = markers[dimensionality]

                if feature_group not in colours:
                    colours[feature_group] = colour[colour_idx]
                    colour_idx += 1
                colours[group_name] = colours[feature_group]

        retval[classifier]['marker_idx'] = marker_idx
        retval[classifier]['colour_idx'] = colour_idx

    for classifier in retval:
        retval[classifier]['accuracies'] = np.array(retval[classifier]['accuracies'])
        retval[classifier]['groups'] = np.array(retval[classifier]['groups'])

    with open('/tmp/hyperopt.pkl', 'wb') as f:
        pickle.dump(retval, f)

    return retval


def visualise(datum):
    for classifier, data in datum.items():
        accuracies = data['accuracies']
        groups = data['groups']
        params = data['params']
        markers = data['markers']
        colours = data['colours']

        scatterClass = go.Scatter

        for param_name, param_values in params.items():
            traces = []
            param_values = np.array(param_values)
            unique_groups = np.unique(groups)
            for group_idx, group in enumerate(unique_groups):
                ind = np.where(groups == group)
                x = param_values[ind].ravel()
                y = accuracies[ind].ravel()

                slope, intercept, r_value, p_value, std_err = stats.linregress(x, y)
                line = slope * x + intercept

                thisSymbol = markers[group]
                thisColour = colours[group]

                trace = scatterClass(
                    name=group.strip(),
                    mode='markers',
                    marker=dict(
                        symbol=thisSymbol,
                        size=5,
                        color=thisColour,
                        line=dict(
                            width=0.5
                        ),
                        opacity=1
                    ),
                    x=x,
                    y=y
                )
                trace1 = scatterClass(
                    name=group.strip(),
                    mode='lines',
                    marker=dict(
                        #     symbol=thisSymbol,
                        #     size=10,
                        color=thisColour,
                        #     line=dict(
                        #         width=0.5
                        #     ),
                        #     opacity=1
                    ),
                    x=x,
                    y=line
                )
                traces.append(trace)
                traces.append(trace1)

            layout = go.Layout(
                hovermode='closest',
                title='Best {} value of {}'.format(param_name, classifier),
                margin=dict(
                    l=50,
                    r=50,
                    b=50,
                    t=50
                ),
                yaxis=dict(
                    title='Accuracy',
                ),
                xaxis=dict(
                    title=param_name,
                )
            )
            fig = go.Figure(data=traces, layout=layout)
            plot = py.iplot(fig, filename='Best {} value of {}'.format(param_name, classifier))
            print('{}'.format(plot.resource))
            pio.write_image(fig, '{}-{}.pdf'.format(classifier, param_name))


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--csv-dir', action='store', dest='csv_dir', required=True, type=str)

    def handle(self, *args, **options):
        csv_dir = options['csv_dir']
        classifiers = ['nnet', 'svm_linear', 'rf', 'svm_rbf']
        dimensionalities = ['full', 'pca']
        num_classes = ['30']
        prefix = 'hyperopt_tmi_'

        # pattern = options['pattern']
        # pattern = re.compile(pattern)

        if not os.path.isdir(csv_dir):
            raise Exception('{} is not a folder'.format(csv_dir))

        classifier_test_suitss = []

        for classifier in classifiers:
            for dimensionality in dimensionalities:
                for num_class in num_classes:
                    filename = '{}{}_{}.{}.tsv'.format(prefix, classifier, dimensionality, num_class)
                    filepath = os.path.join(csv_dir, filename)
                    classifier_test_suits = read_csv(filepath, classifier, dimensionality)
                    classifier_test_suitss.append(classifier_test_suits)

        datum = analyse(classifier_test_suitss)
        visualise(datum)
