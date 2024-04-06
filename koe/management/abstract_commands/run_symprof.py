"""
Given a matrix of class-level acoustic measurements (by averaging constituent syllables)
- Calc the distance matrix
- Do this n times:
  + Permute the matrix by swapping measurements of class A with class B randomly
  + Calc and store the distance matrix

- Move from top to bottom, at each cut-off value: (M)
    - Calc the distance rankings (R)
      + Calc the distance rankings
      + Store the rankings
    - Calculate the range of values of the permuted rankings (Rs)
    - Test if (R) is statistically different from Rs,
      + if so:
         + Move to the right cut, repeat (M)
         + Move to the left cut, repeat (M)
      + if not:
         + return
"""

import json
import os
from abc import abstractmethod

from django.conf import settings
from django.core.management import BaseCommand

import numpy as np
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import pdist
from scipy.stats import ttest_1samp, zscore

from koe.feature_utils import pca_optimal


def calc_ranking(class_measures):
    class_dist = pdist(class_measures)
    sorted_dist = np.sort(class_dist)
    return sorted_dist


class Permuter(object):
    @abstractmethod
    def __init__(self, *args):
        self.iterable_cols = None

    def permute(self, class_measures):
        nclasses, nfeatures = class_measures.shape
        # for each feature (each column), randomly swap the measurements between classes
        # We do this by copying the data from the source column to another column using a random mapping
        # e.g. destination[:, feature_index] = source[random_column_idx, feature_index]
        new_class_measures = np.ndarray((nclasses, nfeatures), dtype=class_measures.dtype)

        for feature_index in self.iterable_cols:
            random_row_inds = np.arange(nclasses)
            np.random.shuffle(random_row_inds)

            new_class_measures[:, feature_index] = class_measures[random_row_inds, :][:, feature_index]
        return new_class_measures


class PcaPermuter(Permuter):
    def __init__(self, nfeatures, *args):
        super(PcaPermuter, self).__init__(*args)
        self.iterable_cols = range(nfeatures)


class FeatureGroupPermuter(Permuter):
    def __init__(self, col_inds, *args):
        super(FeatureGroupPermuter, self).__init__(*args)
        self.iterable_cols = [np.arange(start, end) for start, end in col_inds.values()]


def are_rankings_structural(measures, dist_triu, permuter, significance, ntrials):
    if len(dist_triu) < 3:
        return False
    original_rankings = np.sort(dist_triu)
    rankings = np.ndarray((ntrials, original_rankings.shape[0]))
    for i in range(ntrials):
        new_class_measures = permuter.permute(measures)
        rankings[i, :] = calc_ranking(new_class_measures)

    # Trial_mean is an array of len(dist_triu) elements, so is trial_std and random_deviations
    trial_mean = np.mean(rankings, axis=0)
    random_deviations = np.abs(rankings - trial_mean)

    # mean_random_deviations is an array of ntrials elements
    mean_random_deviations = np.sum(random_deviations, axis=1)

    observed_deviation = np.sum(np.abs(original_rankings - trial_mean))

    # Tree is structural if the real rankings are different from a random draw from permuted rankings
    # that is, if there are less than x% (e.g. 5%) of random deviations larger than the observed deviation

    p_value = np.sum(mean_random_deviations > observed_deviation) / ntrials
    if measures.shape[0] <= 20:
        print("p_value is {}".format(p_value))
    return p_value < significance


def is_variance_structural(measures, dist_triu, permuter, significance, ntrials):
    if measures.shape[1] < 3:
        return False

    dist_variances = np.ndarray((ntrials,))
    observed_dist_variance = np.var(dist_triu)

    for i in range(ntrials):
        new_class_measures = permuter.permute(measures)
        class_dist_triu = pdist(new_class_measures)
        dist_variances[i] = np.var(class_dist_triu)

    t_value, p_value = ttest_1samp(dist_variances, observed_dist_variance)

    # # mean_random_deviations is an array of ntrials elements
    # mean_random_deviations = np.sum(random_deviations, axis=1)
    #
    # observed_deviation = np.sum(np.abs(original_rankings - trial_mean))
    #
    # # Tree is structural if the real rankings are different from a random draw from permuted rankings
    # # that is, if there are less than x% (e.g. 5%) of random deviations larger than the observed deviation

    # p_value = np.sum(mean_random_deviations > observed_deviation) / ntrials
    # if measures.shape[0] <= 20:
    print("p_value = {}, t_value={}".format(p_value, t_value))
    return p_value < significance


structure_checkers = {
    "rankings": are_rankings_structural,
    "variance": is_variance_structural,
}


def cut_tree_get_leaves(tree, height):
    cluster = cut_tree(tree, height=height)
    leaves = []
    nleaves = cluster.max() + 1
    for i in range(nleaves):
        leaf_class_inds = np.where(cluster == i)[0]
        leaves.append(leaf_class_inds)
    return leaves


def recursive_simprof(
    global_measures,
    permuter,
    global_cls_inds,
    clusters,
    min_cluster_size=3,
    max_deviation=0.05,
    ntrials=100,
    is_structural=are_rankings_structural,
):
    print("Considering {} classes".format(len(global_cls_inds)))
    if global_cls_inds.shape[0] < min_cluster_size:
        clusters.append(global_cls_inds)
        return

    local_measures = global_measures[global_cls_inds, :]
    local_to_global_inds = {x: y for x, y in enumerate(global_cls_inds)}

    dist_triu = pdist(local_measures)
    local_tree = linkage(dist_triu, method="complete")
    cutoff = local_tree[:, 2].max()

    if is_structural(local_measures, dist_triu, permuter, max_deviation, ntrials):
        leaves = cut_tree_get_leaves(local_tree, cutoff)
        for leaf_class_inds in leaves:
            leaf_class_global_inds = np.array([local_to_global_inds[i] for i in leaf_class_inds])
            recursive_simprof(
                global_measures,
                permuter,
                leaf_class_global_inds,
                clusters,
                min_cluster_size,
                max_deviation,
                ntrials,
                is_structural,
            )
    else:
        clusters.append(global_cls_inds)


def get_permuter(nfeatures, feature_grouper, dm) -> Permuter:
    if feature_grouper == "pca":
        permuter = PcaPermuter(nfeatures)
    else:
        feature_cols = os.path.join(settings.BASE_DIR, dm.get_cols_path())
        with open(feature_cols, "r", encoding="utf-8") as f:
            col_inds = json.load(f)
        permuter = FeatureGroupPermuter(col_inds)
    return permuter


class SymprofCommand(BaseCommand):
    def __init__(self, *args, **kwargs):
        super(SymprofCommand, self).__init__(*args, **kwargs)
        self.feature_grouper = None
        self.pca_explained = None
        self.pca_dimension = None
        self.max_deviation = None
        self.structural_checker = None

    @abstractmethod
    def get_class_measures_info(self, options):
        pass

    @abstractmethod
    def post_init(self, options):
        self.feature_grouper = options["feature_grouper"]
        self.pca_explained = options["pca_explained"]
        self.pca_dimension = options["pca_dimension"]
        self.max_deviation = options["max_deviation"]
        structure_type = options["structure_type"]
        self.structural_checker = structure_checkers[structure_type]

    @abstractmethod
    def visualise(self, dist_triu, cls_labels, syl_labels, clusters):
        pass

    def process_class_measures(self, original_measures):
        if self.feature_grouper == "pca":
            explained, pcaed_measures = pca_optimal(
                original_measures,
                self.pca_dimension * 2,
                self.pca_explained,
                self.pca_dimension,
            )
            pcaed_measures = zscore(pcaed_measures)
            print("explained = {}, data.shape= {}".format(explained, pcaed_measures.shape))
            dist_triu = pdist(pcaed_measures)
            return dist_triu, pcaed_measures
        else:
            dist_triu = pdist(original_measures)
            return dist_triu, original_measures

    @abstractmethod
    def perform_symprof(self, dist_triu, measures, feature_grouper):
        pass

    def add_arguments(self, parser):
        super(SymprofCommand, self).add_arguments(parser)
        parser.add_argument(
            "--feature-grouper",
            action="store",
            dest="feature_grouper",
            default="pca",
            type=str,
        )
        parser.add_argument(
            "--pca-explained",
            action="store",
            dest="pca_explained",
            default=0.95,
            type=float,
        )
        parser.add_argument(
            "--pca-dimension",
            action="store",
            dest="pca_dimension",
            default=30,
            type=int,
        )
        parser.add_argument(
            "--max-deviation",
            action="store",
            dest="max_deviation",
            default=0.05,
            type=float,
        )
        parser.add_argument(
            "--structure-type",
            action="store",
            dest="structure_type",
            default="rankings",
            type=str,
        )

    def handle(self, *args, **options):
        self.post_init(options)

        (
            class_measures,
            classes_info,
            nlabels,
            cls_labels,
            syl_labels,
        ) = self.get_class_measures_info(options)
        dist_triu, processed_measures = self.process_class_measures(class_measures)

        nclasses, nfeatures = processed_measures.shape
        permuter = get_permuter(nfeatures, self.feature_grouper, self.dm)

        clusters = self.perform_symprof(dist_triu, processed_measures, permuter)

        self.visualise(dist_triu, cls_labels, syl_labels, clusters)
