import numpy as np
import plotly
import plotly.graph_objs as go
import plotly.plotly as py
from django.core.management.base import BaseCommand

plotly.tools.set_credentials_file(username='wBIr68ns', api_key='LAK0vePuQsXlQQFYaKJv')

excluded_feature_groups = ['mfc', 'mfcc+', 'mfcc_delta_only', 'lpcoefs']


import colorlover as cl
nCategoricalColours = 11


def main(tsv):
    with open(tsv, 'r') as f:
        line = f.readline()
        params = {}
        while line != '':
            parts = line.strip().split('\t')
            line = f.readline()
            if parts[0] == 'id':
                continue
            if parts[0] == 'accuracy':
                accuracies = np.array(list(map(float, parts[1:])))
            else:
                params[parts[0]] = np.array(list(map(float, parts[1:])))

    import statsmodels.api as sm
    X = np.vstack(params.values()).T
    X2 = sm.add_constant(X)
    est = sm.OLS(accuracies, X2)
    est2 = est.fit()
    print(est2.summary())
    print(list(params.keys()))


    # nClasses = len(params)
    # if nClasses <= nCategoricalColours:
    #     colour = cl.scales[str(nClasses)]['div']['Spectral']
    # else:
    #     colour = cl.to_rgb(cl.interp(cl.scales[str(nCategoricalColours)]['div']['Spectral'], nClasses))
    #
    # ind = 0
    # traces = []
    # for param_name, param_value in params.items():
    #     trace = go.Scatter(
    #         name=param_name,
    #         mode='markers',
    #         marker=dict(
    #             symbol='circle',
    #             size=5,
    #             color=colour[ind],
    #             line=dict(
    #                 width=0.5
    #             ),
    #             opacity=1
    #         ),
    #         x=param_value,
    #         y=accuracies
    #     )
    #     ind += 1
    #
    #     traces.append(trace)
    #
    #     layout = go.Layout(
    #         hovermode='closest',
    #         title='MFCC performance using nnet while varying {}'.format(param_name),
    #         margin=dict(
    #             l=50,
    #             r=50,
    #             b=50,
    #             t=50
    #         ),
    #         yaxis=dict(
    #             title='Accuracy',
    #         ),
    #         xaxis=dict(
    #             title=param_name,
    #         )
    #     )
    #     fig = go.Figure(data=traces, layout=layout)
    #     plot = py.iplot(fig, filename='MFCC performance using nnet while varying {}'.format(param_name))
    #     print('{}'.format(plot.resource))
        # pio.write_image(fig, '{}-{}.pdf'.format(classifier, param_name))


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--tsv', action='store', dest='tsv', required=True, type=str)
        pass

    def handle(self, *args, **options):
        tsv = options['tsv']
        main(tsv)
