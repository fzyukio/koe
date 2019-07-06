from collections import Counter

import numpy as np
from nltk import ngrams
from scipy.spatial import distance

from koe.models import Segment, AudioFile
from koe.utils import triu2mat
from root.models import ExtraAttr, ExtraAttrValue


def get_sequences(segs, granularity, viewas):
    values = segs.values_list('id', 'audio_file__id')
    seg_ids = segs.values_list('id', flat=True)

    label_attr = ExtraAttr.objects.get(klass=Segment.__name__, name=granularity)
    labels = ExtraAttrValue.objects.filter(attr=label_attr, owner_id__in=seg_ids, user__username=viewas)\
        .values_list('owner_id', 'value')

    seg_id_to_label = {x: y for x, y in labels}
    label_set = set(seg_id_to_label.values())
    labels2enums = {y: x + 1 for x, y in enumerate(label_set)}

    enums2labels = {x: y for y, x in labels2enums.items()}
    pseudo_end_id = len(label_set) + 1
    enums2labels[pseudo_end_id] = '__PSEUDO_END__'
    enums2labels[0] = '__PSEUDO_START__'

    seg_id_to_label_enum = {x: labels2enums[y] for x, y in seg_id_to_label.items()}

    # Bagging song syllables by song name
    songs = {}

    for value in values:
        seg_id = value[0]
        song_id = value[1]

        label2enum = seg_id_to_label_enum.get(seg_id, None)
        seg_info = label2enum

        if song_id not in songs:
            segs_info = [0]
            songs[song_id] = segs_info
        else:
            segs_info = songs[song_id]

        segs_info.append(seg_info)

    for segs_info in songs.values():
        segs_info.append(pseudo_end_id)

    return songs, enums2labels


def songs_to_syl_seqs(songs, sid2label, enums2labels, use_pseudo=True):
    """
    Convert songs into sequences of label (as enumerated)
    :param use_pseudo:
    :param enums2labels:
    :param songs:
    :param sid2label:
    :return:
    """
    segs = Segment.objects.filter(audio_file__in=songs).order_by('audio_file__name', 'start_time_ms')
    values = segs.values_list('id', 'audio_file__id')

    label_set = set(sid2label.values())

    if use_pseudo:
        pseudo_end_id = len(label_set) + 1
        pseudo_start_id = 0
        enums2labels[pseudo_end_id] = '__PSEUDO_END__'
        enums2labels[pseudo_start_id] = '__PSEUDO_START__'

    # Bagging song syllables by song name
    song_sequences = {}

    for value in values:
        seg_id = value[0]
        song_id = value[1]

        label2enum = sid2label.get(seg_id, None)
        seg_info = label2enum

        if song_id not in song_sequences:
            if use_pseudo:
                segs_info = [pseudo_start_id]
            else:
                segs_info = []
            song_sequences[song_id] = segs_info
        else:
            segs_info = song_sequences[song_id]

        segs_info.append(seg_info)

    for segs_info in song_sequences.values():
        if use_pseudo:
            segs_info.append(pseudo_end_id)

    return song_sequences


def calc_class_ajacency(database, syl_label_enum_arr, enum2label, id2enumlabel, count_style='symmetric',
                        count_circular=True):
    assert count_style in ['symmetric', 'asymmetric', 'separate']
    nlabels = len(enum2label)
    classes_info = [[] for _ in range(nlabels)]
    for sidx, enum_label in enumerate(syl_label_enum_arr):
        classes_info[enum_label].append(sidx)

    songs = AudioFile.objects.filter(database=database)
    sequences = songs_to_syl_seqs(songs, id2enumlabel, enum2label, use_pseudo=False)
    adjacency_mat = np.zeros((nlabels, nlabels), dtype=np.int32)

    for sequence in sequences.values():
        grams = ngrams(sequence, 2)
        for x, y in grams:
            adjacency_mat[x, y] += 1

    if not count_circular:
        np.fill_diagonal(adjacency_mat, 0)

    if count_style == 'symmetric':
        adjacency_mat += adjacency_mat.T
    elif count_style == 'separate':
        adjacency_mat = np.concatenate((adjacency_mat, adjacency_mat.T), axis=1)

    return adjacency_mat, classes_info


def calc_class_dist_by_syllable_features(syl_label_enum_arr, nlabels, distmat, method=np.mean):
    classes_info = [[] for _ in range(nlabels)]
    for sidx, enum_label in enumerate(syl_label_enum_arr):
        classes_info[enum_label].append(sidx)

    class_dist = np.zeros((nlabels, nlabels))
    for class_idx in range(nlabels - 1):
        this_class_ids = classes_info[class_idx]
        for next_class_idx in range(class_idx + 1, nlabels):
            next_class_ids = classes_info[next_class_idx]
            sub_distmat = distmat[this_class_ids, :][:, next_class_ids]
            sub_distance = method(sub_distmat)
            class_dist[class_idx, next_class_idx] = class_dist[next_class_idx, class_idx] = sub_distance
    return class_dist, classes_info


def calc_class_dist_by_adjacency(adjacency_mat, syl_label_enum_arr, return_triu=False):
    # currently this distmat contains reversed distance, e.g a pair (A,B) has high "distance" if they're found adjacent
    # to each other often -- so we need to reverse this.

    # To avoid overwhelming the entire distance matrix by having some highly repeated pair, we convert the distance to
    # logarithmic scale, then reverse it

    # distmat = np.log10(distmat)
    #
    # max_distance = np.max(distmat)
    # distmat = max_distance - distmat
    # distmat[np.where(np.isinf(distmat))] = max_distance + 1

    counter = Counter(syl_label_enum_arr)
    nlabels = len(counter)
    frequencies = np.array([counter[i] for i in range(nlabels)])

    adjacency_mat_fw_norm = adjacency_mat / frequencies[:, None]
    adjacency_mat_bw_norm = adjacency_mat / frequencies

    coordinates = np.concatenate((adjacency_mat_fw_norm, adjacency_mat_bw_norm), axis=1)

    dist_triu = distance.pdist(coordinates, 'euclidean')
    if return_triu:
        return dist_triu

    distmat = triu2mat(dist_triu)
    return distmat
