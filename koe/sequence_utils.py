import numpy as np
from nltk import ngrams

from koe.models import Segment
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


def songs_to_syl_seqs(songs, sid2label, enums2labels):
    """
    Convert songs into sequences of label (as enumerated)
    :param enums2labels:
    :param songs:
    :param sid2label:
    :return:
    """
    segs = Segment.objects.filter(audio_file__in=songs).order_by('audio_file__name', 'start_time_ms')
    values = segs.values_list('id', 'audio_file__id')

    label_set = set(sid2label.values())
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
            segs_info = [pseudo_start_id]
            song_sequences[song_id] = segs_info
        else:
            segs_info = song_sequences[song_id]

        segs_info.append(seg_info)

    for segs_info in song_sequences.values():
        segs_info.append(pseudo_end_id)

    return song_sequences


def calc_class_ajacency(database, label_level, annotator_name, enum_labels, nlabels):
    classes_info = [[] for _ in range(nlabels)]
    for sidx, enum_label in enumerate(enum_labels):
        classes_info[enum_label].append(sidx)

    segs = Segment.objects.filter(audio_file__database=database)
    songs, enums2labels = get_sequences(segs, label_level, annotator_name)
    sequences = songs.values()
    elements = enums2labels.keys()
    numel = len(elements)
    distmat = np.zeros((numel, numel), dtype=np.int32)

    for sequence in sequences:
        grams = ngrams(sequence, 2)
        for x, y in grams:
            distmat[x, y] += 1
            distmat[y, x] += 1

    # the first row, last row, first column, last column are distances to the pseudo start and pseudo end node
    # So we must remove them first
    distmat = distmat[1:-1, 1:-1]
    return distmat, classes_info


def calc_class_dist_by_adjacency(distmat):
    # currently this distmat contains reversed distance, e.g a pair (A,B) has high "distance" if they're found adjacent
    # to each other often -- so we need to reverse this.

    # To avoid overwhelming the entire distance matrix by having some highly repeated pair, we convert the distance to
    # logarithmic scale, then reverse it

    distmat = np.log10(distmat)

    max_distance = np.max(distmat)
    distmat = max_distance - distmat
    distmat[np.where(np.isinf(distmat))] = max_distance + 1

    return distmat


def calc_class_dist_by_syllable_features(enum_labels, nlabels, distmat, method=np.mean):
    classes_info = [[] for _ in range(nlabels)]
    for sidx, enum_label in enumerate(enum_labels):
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
