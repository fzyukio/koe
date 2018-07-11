r"""
Test clustering by k-NN
"""

import numpy as np
from django.core.management.base import BaseCommand
from dotmap import DotMap
from ml_metrics import mapk
from progress.bar import Bar
from scipy.io import loadmat
from scipy.spatial.distance import pdist
from scipy.stats import zscore

from koe.utils import accum, triu2mat


def sorted_labels_by_prevalence_then_distance(neighbour_labels, neighbour_distances, distance_func):
    # labels = np.array(['a', 'a', 'b', 'c', 'b', 'a', 'c', 'd'])
    # dists = np.array([0.1, 0.1, 0.3, 0.3, 0.5, 0.2, 0.4, 0.6])
    # indices = np.array([0, 1, 2, 3, 4, 5, 6, 7])

    sorted_indices = np.argsort(neighbour_distances)
    closests = sorted_indices[0:7]
    closests_labels = neighbour_labels[closests]
    unique_labels, indices = np.unique(closests_labels, return_inverse=True)

    prevalences = np.bincount(indices)

    closests_distances = neighbour_distances[closests]
    mean_distance_by_labels = accum(indices, closests_distances, func=distance_func, dtype=np.float)

    # Now, lexsort sorts everything ascendingly. We want the prevalences to be sorted descendingly and distances
    # ascendingly. So we must negate prevalences
    sorted_indices_by_prevalence_then_mean_distance = np.lexsort((0 - prevalences, mean_distance_by_labels))

    sorted_labels = unique_labels[sorted_indices_by_prevalence_then_mean_distance]

    return sorted_labels


def k_nearest(distmat, train_labels, nlabels, k, map_order):
    # Leave one out K nearest neighbour
    # Find the nearest 5 neighbours & find out which label dominates
    element_count = distmat.shape[0]

    actual_labels = []
    predicted_labels = []

    for j in range(element_count):
        distances_from_j = distmat[j, :]
        sorted_indices = np.argsort(distances_from_j)
        closests_indices = sorted_indices[1:k + 1]
        closests_labels = train_labels[closests_indices]
        closests_distances = distances_from_j[closests_indices]

        predicted_label = sorted_labels_by_prevalence_then_distance(closests_labels, closests_distances, np.mean)

        predicted_labels.append(predicted_label)
        actual_labels.append([train_labels[j]])

    label_prediction_map_score = mapk(actual_labels, predicted_labels, map_order)

    hits = np.array([1 if a in p else 0 for a, p in zip(actual_labels, predicted_labels)], dtype=np.int)
    misses = np.array([0 if a in p else 1 for a, p in zip(actual_labels, predicted_labels)],
                      dtype=np.int)

    label_hits = np.full((nlabels,), np.nan)
    label_misses = np.full((nlabels,), np.nan)

    unique_test_labels = np.unique(train_labels)

    _label_hits = accum(train_labels, hits, func=np.sum, dtype=np.int)
    _label_misses = accum(train_labels, misses, func=np.sum, dtype=np.int)

    label_hits[unique_test_labels] = _label_hits[unique_test_labels]
    label_misses[unique_test_labels] = _label_misses[unique_test_labels]

    return label_prediction_map_score, label_hits, label_misses


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--source', action='store', dest='source', required=True, type=str,
                            help='Can be tsne, raw, norm', )

        parser.add_argument('--matfile', ction='store', dest='matfile', required=False, type=str,
                            help='Name of the .mat file that stores extracted feature values for Matlab', )

        parser.add_argument('--niters', action='store', dest='niters', required=False, default=1, type=int)

        parser.add_argument('--to-csv', dest='csv_filename', action='store', required=False)

    def handle(self, source, matfile, niters, csv_filename, *args, **options):
        assert source in ['tsne', 'raw', 'norm']

        saved = DotMap(loadmat(matfile))
        sids = saved.sids.ravel()
        clusters = saved.clusters
        dataset = saved.dataset
        meas = zscore(dataset)
        labels = saved.labels
        haslabel_ind = np.where(labels != '                              ')[0]

        labels = labels[haslabel_ind]
        labels = np.array([x.strip() for x in labels])
        sids = sids[haslabel_ind]
        clusters = clusters[haslabel_ind, :]

        unique_labels, enum_labels = np.unique(labels, return_inverse=True)
        nlabels = len(unique_labels)

        data_sources = {
            'tsne': clusters,
            'raw': dataset,
            'norm': meas
        }

        data = data_sources[source]
        disttriu = pdist(data)
        distmat = triu2mat(disttriu)

        label_prediction_scores = [0] * niters
        label_hitss = [0] * niters
        label_missess = [0] * niters
        label_hitrates = np.empty((niters, len(unique_labels)))
        label_hitrates[:] = np.nan

        num_left_in = int(len(sids) * 0.9)

        if not csv_filename:
            csv_filename = 'knn_by_{}.csv'.format(source)

        with open(csv_filename, 'w', encoding='utf-8') as f:
            f.write('Label prediction mean\tstdev\t{}\n'.format('\t'.join(unique_labels)))
            scrambled_syl_idx = np.arange(len(sids), dtype=np.int)

            bar = Bar('Running knn...', max=niters)
            for iteration in range(niters):
                np.random.shuffle(scrambled_syl_idx)
                train_syl_idx = scrambled_syl_idx[:num_left_in]

                train_y = enum_labels[train_syl_idx]
                trained_distmat = distmat[train_syl_idx, :][:, train_syl_idx]

                label_prediction_score, label_hits, label_misses = k_nearest(trained_distmat, train_y, nlabels, 1, 1)

                label_prediction_scores[iteration] = label_prediction_score
                label_hitss[iteration] = label_hits
                label_missess[iteration] = label_misses

                label_hitrate = label_hits / (label_hits + label_misses).astype(np.float)
                label_hitrates[iteration, :] = label_hitrate

                bar.next()
            bar.finish()

            f.write('{}\t{}\t{}\n'.format(np.nanmean(label_prediction_scores),
                                          np.nanstd(label_prediction_scores),
                                          '\t'.join(map(str, np.nanmean(label_hitrates, 0)))))
