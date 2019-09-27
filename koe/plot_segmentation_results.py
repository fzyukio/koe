import pickle

import matplotlib
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from scipy import stats

#matplotlib.use('TkAgg')
#import matplotlib.pyplot as plt

pkls = {
    'mlp': '/tmp/showcase-mlp/',
    'rnn': '/tmp/showcase/',
    'hma': '/tmp/showcase-harma/',
    'lsk': '/tmp/showcase-lasseck/',
    'l+h': '/tmp/showcase-lasseck-harma/'
}

columns = ['MAP', 'F1', 'Precision', 'Recall']

result_by_type = {c: {t: [] for t in pkls.keys()} for c in columns}

for name, tmpdir in pkls.items():
    result_file = tmpdir + 'results.pkl'
    with open(result_file, 'rb') as f:
        result = pickle.load(f)
        for af_id, (img_filename, score_mAP, score_f1, precision, recall) in result.items():
            result_by_type['MAP'][name].append(score_mAP)
            result_by_type['F1'][name].append(score_f1)
            result_by_type['Precision'][name].append(precision)
            result_by_type['Recall'][name].append(recall)


pdf = PdfPages('segmentation_result_plot.pdf')

for t, result in result_by_type.items():
    data = np.array(list(result_by_type[t].values())).transpose()
    columns = list(result_by_type[t].keys())

    mlp = result_by_type[t]['mlp']
    rnn = result_by_type[t]['rnn']

    _, p = stats.ttest_ind(mlp, rnn)

    fig = plt.figure(figsize=(4, 4), frameon=False)
    plt.boxplot(data, labels=columns, showfliers=False, notch=True)

    ax = plt.gca()
    ax.set_title('Score type: ' + t)
    ax.set_xlabel('t-test(mlp, rnn) = {}'.format(p))

    pdf.savefig(fig)
    plt.close()

pdf.close()


# x = "day"
# y = "total_bill"
# hue = "smoker"
# sns.set(style="whitegrid")
# df = sns.load_dataset("tips")
# ax = sns.boxplot(data=df, x=x, y=y)
# add_stat_annotation(ax, data=df, x=x, y=y, hue=hue,
#                     box_pairs=[(("Thur", "No"), ("Fri", "No")),
#                                  (("Sat", "Yes"), ("Sat", "No")),
#                                  (("Sun", "No"), ("Thur", "Yes"))
#                                 ],
#                     test='t-test_ind', text_format='full', loc='inside', verbose=2)
# plt.legend(loc='upper left', bbox_to_anchor=(1.03, 1))
# plt.show()
