import sys
import time
from random import shuffle

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis as LDA
from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis as QDA
from sklearn.ensemble import RandomForestClassifier
from sklearn.manifold import TSNE
from sklearn.metrics import confusion_matrix
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.svm import SVC

from koe.utils import accum, split_classwise


__all__ = []


def _calc_score(predict_y, true_y, nlabels, with_cfmat=False):
    """
    Calculate various scoring of the prediction.
    :param predict_y: predicted value (enumerated)
    :param true_y: actual value (enumerated)
    :param nlabels: number of labels (true_y might not have all labels)
    :param with_cfmat: if True will return confusiion matrix
    :return: score( percentage correct)
             label_hits (ndarray of hit count for each label. Labels not present in true_y will have count of NaN)
             label_misses similar to label_hits but count the misses
             cf_matrix (optional) the confusion matrix (nlabels x nlabels)
    """
    hits = (predict_y == true_y).astype(int)
    misses = 1 - hits
    score = hits.sum() / len(true_y)

    label_hits = np.full((nlabels,), np.nan)
    label_misses = np.full((nlabels,), np.nan)

    unique_test_labels = np.unique(true_y)

    _label_hits = accum(true_y, hits, func=np.sum, dtype=int)
    _label_misses = accum(true_y, misses, func=np.sum, dtype=int)

    label_hits[unique_test_labels] = _label_hits[unique_test_labels]
    label_misses[unique_test_labels] = _label_misses[unique_test_labels]

    if with_cfmat:
        cf_matrix = confusion_matrix(true_y, predict_y)
        return score, label_hits, label_misses, cf_matrix
    else:
        return score, label_hits, label_misses


def _classify(model, train_x, train_y, test_x, test_y, nlabels, with_cfmat=False):
    model = model.fit(train_x, train_y)
    predict_y = model.predict(test_x)
    return _calc_score(predict_y, test_y, nlabels, with_cfmat)


def random_forest(train_x, train_y, test_x, test_y, nlabels, with_cfmat=False, **kwargs):
    model = RandomForestClassifier(**kwargs)
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels, with_cfmat)
    retval = list(retval) + [model.feature_importances_]
    return retval


def dummy(train_x, train_y, test_x, test_y, nlabels, with_cfmat=False, **kwargs):
    predict_y = np.copy(test_y)
    shuffle(predict_y)
    retval = _calc_score(predict_y, test_y, nlabels, with_cfmat)
    retval = list(retval) + [None]
    return retval


def svm_linear(train_x, train_y, test_x, test_y, nlabels, with_cfmat=False, **kwargs):
    model = SVC(kernel="linear", **kwargs)
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels, with_cfmat)

    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]
    return retval


def svm_rbf(train_x, train_y, test_x, test_y, nlabels, with_cfmat=False, **kwargs):
    model = SVC(kernel="rbf", **kwargs)
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels, with_cfmat)

    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]
    return retval


def gaussian_nb(train_x, train_y, test_x, test_y, nlabels, with_cfmat=False):
    model = GaussianNB()
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels, with_cfmat)
    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]
    return retval


def lda(train_x, train_y, test_x, test_y, nlabels, with_cfmat=False):
    model = LDA(n_components=2)
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels, with_cfmat)
    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]

    return retval


def qda(train_x, train_y, test_x, test_y, nlabels, with_cfmat=False):
    model = QDA(
        priors=None,
        reg_param=0.0,
        store_covariance=False,
        store_covariances=None,
        tol=0.0001,
    )
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels, with_cfmat)
    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]
    return retval


def nnet(train_x, train_y, test_x, test_y, nlabels, with_cfmat=False, **kwargs):
    model = MLPClassifier(**kwargs)
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels, with_cfmat)

    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]
    return retval


def cnn(train_x, train_y, test_x, test_y, nlabels, with_cfmat=False, **kwargs):
    from koe.neuralnet_models import ConvolutionalNeuralNetwork

    model = ConvolutionalNeuralNetwork(**kwargs)
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels, with_cfmat)
    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]
    return retval


def knn(train_x, train_y, test_x, test_y, nlabels, with_cfmat=False, **kwargs):
    model = KNeighborsClassifier(**kwargs)
    retval = _classify(model, train_x, train_y, test_x, test_y, nlabels, with_cfmat)
    fake_importances = np.zeros((train_x.shape[1],))
    retval = list(retval) + [fake_importances]
    return retval


classifiers = {
    "rf": random_forest,
    "svm_linear": svm_linear,
    "svm_rbf": svm_rbf,
    "gnb": gaussian_nb,
    "lda": lda,
    "qda": qda,
    "nnet": nnet,
    "dummy": dummy,
    "knn": knn,
}


def run_clustering(dataset, dim_reduce, n_components, n_dims=3):
    assert 2 <= n_dims <= 3, "TSNE can only produce 2 or 3 dimensional result"
    if dim_reduce:
        dim_reduce_func = dim_reduce(n_components=n_components)
        dataset = dim_reduce_func.fit_transform(dataset, y=None)
        if hasattr(dim_reduce_func, "explained_variance_ratio_"):
            print(
                "Cumulative explained variation for {} principal components: {}".format(
                    n_components, np.sum(dim_reduce_func.explained_variance_ratio_)
                )
            )

    time_start = time.time()
    tsne = TSNE(n_components=n_dims, verbose=1, perplexity=10, n_iter=4000)
    tsne_results = tsne.fit_transform(dataset)
    print("t-SNE done! Time elapsed: {} seconds".format(time.time() - time_start))
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
        folds = split_classwise(enum_labels, nfolds)

        for fold in folds:
            test_syl_idx = fold["test"]
            train_syl_idx = fold["train"]

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


def get_ratios(ratio, nparts=3):
    """
    Convert ratio from string to list of float
    :param ratio: in form xx:yy or xx:yy:zz, must add up to 100, must be non-negative
    :param nparts: either 2 (for format xx:yy) or 3 (for format xx:yy:zz)
    :return: a list of float numbers that add up to 1.0
    """
    assert 2 <= nparts <= 3
    parts = ratio.split(":")
    if nparts == 3:
        error_message = (
            "Ratio must be in format xx:yy:zz as positive percentages of the train, valid and test set. "
            "E.g.80:10:10"
        )
    else:
        error_message = (
            "Ratio must be in format xx:yy as positive percentages of the train and valid set. " "E.g.80:20"
        )
    assert len(parts) == nparts, error_message

    try:
        ratios = np.array(list(map(int, parts)))
        assert np.all(ratios >= 0)
        assert np.sum(ratios) == 100
        return [x / 100.0 for x in ratios]
    except Exception:
        print(error_message, file=sys.stderr)
