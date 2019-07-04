from logging import warning

import numpy as np
import hashlib
from abc import abstractmethod

from koe.model_utils import get_labels_by_sids


class NameMerger(object):
    @abstractmethod
    def merge(self, cls_names):
        pass


class SimpleNameMerger(NameMerger):
    def merge(self, cls_names):
        """
        Merge class names by joining them with -&-
        :param cls_names: a list of names
        :return:
        """
        return ' -&- '.join(cls_names)


class Md5NameMerger(NameMerger):
    def __init__(self):
        self.md5s = []

    def merge(self, cls_names):
        joined = ' -&- '.join(cls_names)
        hash_object = hashlib.md5(joined.encode())
        md5_full = hash_object.hexdigest()

        start_index = 0
        md5 = md5_full[start_index:start_index + 6]
        while md5 in self.md5s:
            start_index += 1
            md5 = md5_full[start_index:start_index + 6]
        self.md5s.append(md5)
        return md5


def merge_labels(clusters, classes_info, sids, enum2label, class_name_merge_func):
    """
    Create a new mapping from syllable id (sid in database) to their new class index.
     The class index is the index of the cluster where the original class belongs.
     E.g. syllable 123456 originally belongs to class 1, and syllable 234567 originally belongs to class 2
     Class 1 and 2 now merges into cluster #3.
     Accordingly, syllable 123456 and 234567 is now mapped to cluster #3
    :param class_name_merge_func: function to help merge class names
    :param clusters: an array of N element, where N is the number of original classes. Value at element #i is the
                     index of the cluster class #i now belongs, e.g. if originally there are 10 classes and clusters is
                     [0 0 1 3 1 2 2 0 1 3], it is interpreted that:
       class index    0 1 2 3 4 5 6 7 8 9
       cluster #0 ->  ^ ^           ^
       cluster #1 ->      ^   ^       ^
       cluster #2 ->            ^ ^
       cluster #3 ->        ^           ^
                     class #0, #1, #7 now belong to cluster #0
                     class #2, #4, #8 now belong to cluster #1
                     class #5, #6 now belong to cluster #2
                     class #3, #9 now belong to cluster #3
    :param classes_info: a map from (original) class index to list of sind (indices of syllables in the array sids)
                         e.g. given 10 classes, classes_info looks something like:
                         {0: [1,4,6,9,31], 1:[2,17, 5, 22], ...}
    :param sids: array of syllable id (sid in database). The array indices of them is used in classes_info
    :param enum2label: a map from class index to the actual label given in the database
    :return: (sid_to_cluster_base_1, merged_enum2label_base1) where:
           sid_to_cluster_base_1: a map from syllable id (sid) to the cluster index (base 1) its original class
                                  belongs to
           merged_enum2label_base1: a map from cluster index (base 1) to a new label. This new label is a concatenation
                                    of all its constituent class labels
    """
    sid_to_cluster_base_1 = {}
    merged_enum2label_base1 = {}
    for current_class_idx, merged_class_idx in enumerate(clusters):
        merged_class_idx_base_1 = merged_class_idx + 1

        sinds = classes_info[current_class_idx]
        for sind in sinds:
            sid = sids[sind]
            sid_to_cluster_base_1[sid] = merged_class_idx_base_1

        current_class_label = enum2label[current_class_idx]
        if merged_class_idx_base_1 in merged_enum2label_base1:
            merged_enum2label_base1[merged_class_idx_base_1].append(current_class_label)
        else:
            merged_enum2label_base1[merged_class_idx_base_1] = [current_class_label]

    for merged_class_idx in list(merged_enum2label_base1.keys()):
        class_labels = merged_enum2label_base1[merged_class_idx]
        merged_enum2label_base1[merged_class_idx] = class_name_merge_func(class_labels)

    return sid_to_cluster_base_1, merged_enum2label_base1


def get_clustering_based_on_user_annotation(annotator, label_level, sids):
    if label_level is None:
        label_level = 'label'
    labels, no_label_ids = get_labels_by_sids(sids, label_level, annotator, min_occur=None)
    if len(no_label_ids) > 0:
        warning('Syllables with no labels found!. These will be given label "__NONE__" but this will affect the'
                ' accuracy of the network graph')
        continue_option = input('Continue with this warning in mind? Y/n')
        if continue_option != 'Y':
            exit(0)

    unique_labels, enum_labels = np.unique(labels, return_inverse=True)
    return unique_labels, enum_labels
