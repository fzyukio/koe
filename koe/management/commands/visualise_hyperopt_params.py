import pickle

import numpy as np
import plotly
import plotly.graph_objs as go
import plotly.plotly as py
from django.core.management.base import BaseCommand

from scipy import stats

plotly.tools.set_credentials_file(username='wBIr68ns', api_key='LAK0vePuQsXlQQFYaKJv')

excluded_feature_groups = ['mfc', 'mfcc+', 'mfcc_delta_only', 'lpcoefs']


def main():
    with open('/tmp/hyperopt.pkl', 'rb') as f:
        saved = pickle.load(f)

    for classifier, data in saved.items():
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
                feature_group, dimensionality = group.split('-')
                if feature_group in excluded_feature_groups:
                    continue
                if dimensionality == 'pca':
                    continue
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
                        size=10,
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
                    # marker=dict(
                    #     symbol=thisSymbol,
                    #     size=10,
                        color=thisColour,
                    #     line=dict(
                    #         width=0.5
                    #     ),
                    #     opacity=1
                    # ),
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


if __name__ == '__main__':
    main()


class Command(BaseCommand):
    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        main()
