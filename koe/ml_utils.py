import time

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA, QuadraticDiscriminantAnalysis as QDA
from sklearn.manifold import TSNE
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from koe.utils import accum
from koe.utils import split_kfold_classwise


def _calc_score(predict_y, test_y, nlabels):
    hits = (predict_y == test_y).astype(np.int)
    misses = 1 - hits
    score = hits.sum() / len(test_y)

    label_hits = np.full((nlabels,), np.nan)
    label_misses = np.full((nlabels,), np.nan)

    unique_test_labels = np.unique(test_y)

    _label_hits = accum(test_y, hits, func=np.sum, dtype=np.int)
    _label_misses = accum(test_y, misses, func=np.sum, dtype=np.int)

    label_hits[unique_test_labels] = _label_hits[unique_test_labels]
    label_misses[unique_test_labels] = _label_misses[unique_test_labels]

    return score, label_hits, label_misses


def _classify(model, train_x, train_y, test_x, test_y, nlabels):
    model = model.fit(train_x, train_y)
    predict_y = model.predict(test_x)
    return _calc_score(predict_y, test_y, nlabels)


def random_forest(train_x, train_y, test_x, test_y, nlabels):
    model = DecisionTreeClassifier()
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels)
    retval = list(retval) + [model.feature_importances_]
    return retval


def svm(train_x, train_y, test_x, test_y, nlabels):
    model = SVC(kernel='linear')
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels)

    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]
    return retval


def gaussian_nb(train_x, train_y, test_x, test_y, nlabels):
    model = GaussianNB()
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels)
    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]
    return retval


def lda(train_x, train_y, test_x, test_y, nlabels):
    model = LDA(n_components=2)
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels)
    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]

    return retval


def qda(train_x, train_y, test_x, test_y, nlabels):
    model = QDA(priors=None, reg_param=0.0, store_covariance=False, store_covariances=None, tol=0.0001)
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels)
    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]
    return retval


classifiers = {
    'rf': random_forest,
    'svm': svm,
    'gnb': gaussian_nb,
    'lda': lda,
    'qda': qda
}


def run_clustering(dataset, dim_reduce, n_components, n_dims=3):
    assert 2 <= n_dims <= 3, 'TSNE can only produce 2 or 3 dimensional result'
    if dim_reduce:
        dim_reduce_func = dim_reduce(n_components=n_components)
        dataset = dim_reduce_func.fit_transform(dataset, y=None)
        if hasattr(dim_reduce_func, 'explained_variance_ratio_'):
            print('Cumulative explained variation for {} principal components: {}'
                  .format(n_components, np.sum(dim_reduce_func.explained_variance_ratio_)))

    time_start = time.time()
    tsne = TSNE(n_components=n_dims, verbose=1, perplexity=10, n_iter=4000)
    tsne_results = tsne.fit_transform(dataset)
    print('t-SNE done! Time elapsed: {} seconds'.format(time.time() - time_start))
    return tsne_results


def run_nfolds(data, nsyls, nfolds, niters, enum_labels, nlabels, classifier, bar):
    ntrials = nfolds * niters
    if bar:
        bar.max = ntrials

    label_prediction_scores = [0] * ntrials
    label_hitss = [0] * ntrials
    label_missess = [0] * ntrials
    label_hitrates = np.empty((ntrials, nlabels))
    label_hitrates[:] = np.nan
    importancess = np.empty((ntrials, data.shape[1]))

    ind = 0

    for i in range(niters):
        folds = split_kfold_classwise(enum_labels, nfolds)

        for fold in folds:
            test_syl_idx = fold['test']
            train_syl_idx = fold['train']

            train_y = enum_labels[train_syl_idx]
            test_y = enum_labels[test_syl_idx]

            train_x = data[train_syl_idx, :]
            test_x = data[test_syl_idx, :]

            score, label_hits, label_misses, importances = classifier(train_x, train_y, test_x, test_y, nlabels)

            label_prediction_scores[ind] = score
            label_hitss[ind] = label_hits
            label_missess[ind] = label_misses

            label_hitrate = label_hits / (label_hits + label_misses).astype(np.float)

            label_hitrates[ind, :] = label_hitrate
            importancess[ind, :] = importances

            ind += 1

            if bar:
                bar.next()
    if bar:
        bar.finish()

    return label_prediction_scores, label_hitrates, importancess
