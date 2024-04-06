import os
from collections import Counter

from django.conf import settings
from django.db import models

import numpy as np
from celery.utils.log import get_task_logger
from PIL import Image
from scipy import signal
from scipy.cluster.hierarchy import linkage

from koe.celery_init import app
from koe.colourmap import cm_blue, cm_green, cm_red
from koe.models import (
    AudioFile,
    Database,
    DatabaseAssignment,
    DatabasePermission,
    DistanceMatrix,
    Segment,
    TemporaryDatabase,
)
from koe.utils import audio_path, get_abs_spect_path, mat2triu, triu2mat, wav_path
from koe.wavfile import get_wav_info, read_segment
from root.exceptions import CustomAssertionError
from root.models import ExtraAttrValue
from root.utils import ensure_parent_folder_exists


celerylogger = get_task_logger(__name__)

window_size = 256
noverlap = 256 * 0.75
window = signal.get_window("hann", 256)
low_bound = 800
scale = window.sum()
global_min_spect_pixel = -9.421019554138184
global_max_spect_pixel = 2.8522987365722656
global_spect_pixel_range = global_max_spect_pixel - global_min_spect_pixel
interval64 = global_spect_pixel_range / 63


def add_node(node, idx_2_seg_id, parent, root_triu):
    """
    Create a nested dictionary from the ClusterNode's returned by SciPy.
    This function will be called recursively to traverse the dendrogram tree and adding info to the nodes
    Useful to create a visual representation of this tree
    :param node: the current node in the tree
    :param idx_2_seg_id: a dict to provide index of the leaves
    :param parent: parent of this leave
    :param root_triu: This is the height of the tree from the root to the furthest leaf
    :return: None
    """
    # First create the new node and append it to its parent's children
    new_node = dict(dist=root_triu - node.dist, children=[])

    idx = node.id
    if idx in idx_2_seg_id:
        new_node["seg-id"] = idx_2_seg_id[idx]

    if "children" in parent:
        parent["children"].append(new_node)
    else:
        for k in new_node:
            parent[k] = new_node[k]

    # Recursively add the current node's children
    if node.left:
        add_node(node.left, idx_2_seg_id, new_node, root_triu)
    if node.right:
        add_node(node.right, idx_2_seg_id, new_node, root_triu)


def dist_from_root(tree):
    """
    Calculate the distance from each node to the root
    :param tree: the dendrogram tree
    :return: two np arrays: indices is the positions of the leaves and distances the distances to the root
    """
    last_idx = tree.shape[0]
    indices = np.ndarray((last_idx + 1,), dtype=np.uint32)
    distances = np.ndarray((last_idx + 1,), dtype=np.float32)
    for i in range(last_idx):
        branch = tree[i, :]
        l1 = int(branch[0])
        l2 = int(branch[1])
        dist = branch[2]
        if l1 <= last_idx:
            indices[l1] = i
            distances[l1] = dist / 2
        if l2 <= last_idx:
            indices[l2] = i
            distances[l2] = dist / 2
    return indices, distances


def upgma_triu(segments_ids, dm):
    """
    Perform UPGMA given a distance matrix
    :param segments_ids: an array of Segment IDs
    :param dm: ID of a DistanceMatrix
    :return: two arrays: indices is the positions of the leaves and distances the distances to the root
    """
    all_segments_ids = np.array(list(Segment.objects.all().order_by("id").values_list("id", flat=True)))
    chksum = DistanceMatrix.calc_chksum(all_segments_ids)

    if dm is None:
        return [0] * len(segments_ids)
    assert chksum == dm.chksum

    mat_idx = np.searchsorted(all_segments_ids, segments_ids)
    triu = dm.triu
    distmat = triu2mat(triu)
    distmat = distmat[:, mat_idx][mat_idx, :]
    distmat[np.isnan(distmat)] = 0
    triu = mat2triu(distmat)

    tree = linkage(triu, method="average")
    indices, distances = dist_from_root(tree)

    return indices.tolist(), distances.tolist()


def natural_order(tree):
    """
    Put leaf nodes of a clustered tree into their natural order. This is the order in which the nodes appear in the
    dendrographic display of this tree

    Example: given the following tree:
            1            9      0.14822
            4            7       0.3205
            5            6       0.3336
            8           11      0.41462
            0            3      0.44112
           10           13      0.58161
            2           12      0.69368
           14           15      0.77539
           16           17      0.89688

    The dendrogram will look like this:
                +__1
        +-------|__9
        |
        |       ___4
        |----+-|___7
        |    |_____8
        |
        |  +-------0
        |--|_______5
        |
        |    +_____6
        +-+--|_____7
          |________3

    The natural order is [1 9 4 7 8 0 5 6 7 3]
    :param tree: result of scipy.cluster.hierarchy.linkage
    :return: the natural order
    """
    nnodes = tree.shape[0] + 1

    branches = [None] * tree.shape[0]
    row_idxs = np.arange(0, nnodes - 1, dtype=np.int32)

    for idx in row_idxs:
        join = tree[idx]
        left = int(join[0])
        right = int(join[1])
        distance = join[2]

        if left < nnodes and right < nnodes:
            branches[idx] = [left, right], distance
        elif left < nnodes <= right:
            node_idx = right - nnodes
            node = branches[node_idx]
            branches[node_idx] = 0
            node[0].append(left)
            branches[idx] = node[0], node[1]

        elif left >= nnodes > right:
            node_idx = left - nnodes
            node = branches[node_idx]
            branches[node_idx] = 0
            node[0].append(right)
            branches[idx] = node[0], node[1]
        else:
            left_node_idx = left - nnodes
            left_node = branches[left_node_idx]
            branches[left_node_idx] = 0

            right_node_idx = right - nnodes
            right_node = branches[right_node_idx]
            branches[right_node_idx] = 0

            left_node_distance = left_node[1]
            right_node_distance = right_node[1]

            if left_node_distance < right_node_distance:
                node_leaves = left_node[0] + right_node[0]
                distance = left_node_distance
            else:
                node_leaves = right_node[0] + left_node[0]
                distance = right_node_distance

            branches[idx] = node_leaves, distance

    return branches[-1][0]


def get_user_accessible_databases(user):
    assigned_databases_ids = DatabaseAssignment.objects.filter(user=user).values_list("database__id", flat=True)
    databases = Database.objects.filter(id__in=assigned_databases_ids)
    return databases


def get_user_databases(user):
    """
    Return user's current database and the database's current similarity matrix
    :param user:
    :return:
    """
    current_database_value = ExtraAttrValue.objects.filter(
        attr=settings.ATTRS.user.current_database, owner_id=user.id, user=user
    ).first()
    db_class = Database
    if current_database_value:
        current_database_value = current_database_value.value
        if "_" in current_database_value:
            db_class_name, current_database_id = current_database_value.split("_")
            if db_class_name == TemporaryDatabase.__name__:
                db_class = TemporaryDatabase
        else:
            current_database_id = current_database_value

        current_database = db_class.objects.filter(pk=current_database_id).first()

    else:
        databases = get_user_accessible_databases(user)
        current_database = databases.first()
        if current_database is not None:
            ExtraAttrValue.objects.create(
                attr=settings.ATTRS.user.current_database,
                owner_id=user.id,
                user=user,
                value="{}_{}".format(db_class, current_database.id),
            )

    return current_database


def extract_spectrogram(audio_file, segs_info):
    """
    Extract raw sepectrograms for all segments (Not the masked spectrogram from Luscinia) of an audio file
    :param audio_file:
    :return:
    """
    filepath = wav_path(audio_file)

    fs, duration = get_wav_info(filepath)
    if not os.path.isfile(filepath):
        raise CustomAssertionError("File {} not found".format(audio_file.name))

    for tid, start, end in segs_info:
        seg_spect_path = get_abs_spect_path(tid)
        ensure_parent_folder_exists(seg_spect_path)

        sig = read_segment(
            filepath,
            beg_ms=start,
            end_ms=end,
            mono=True,
            normalised=True,
            return_fs=False,
            retype=True,
            winlen=window_size,
        )
        _, _, s = signal.stft(
            sig,
            fs=fs,
            window=window,
            noverlap=noverlap,
            nfft=window_size,
            return_onesided=True,
        )
        spect = np.abs(s * scale)

        height, width = np.shape(spect)
        spect = np.flipud(spect)

        spect = np.log10(spect)
        spect = (spect - global_min_spect_pixel) / interval64
        spect[np.isinf(spect)] = 0
        spect = spect.astype(int)

        spect = spect.reshape((width * height,), order="C")
        spect[spect >= 64] = 63
        spect_rgb = np.empty((height, width, 3), dtype=np.uint8)
        spect_rgb[:, :, 0] = cm_red[spect].reshape((height, width)) * 255
        spect_rgb[:, :, 1] = cm_green[spect].reshape((height, width)) * 255
        spect_rgb[:, :, 2] = cm_blue[spect].reshape((height, width)) * 255

        # roi_start = int(start / duration_ms * width)
        # roi_end = int(np.ceil(end / duration_ms * width))

        # seg_spect_rgb = file_spect_rgb[:, roi_start:roi_end, :]
        seg_spect_img = Image.fromarray(spect_rgb)

        seg_spect_img.save(seg_spect_path, format="PNG")
        celerylogger.info("spectrogram {} created".format(seg_spect_path))


def assert_permission(user, database, required_level):
    """
    Assert that user has enough permission
    :param user:
    :param database:
    :param required_level:
    :return: if user does have permission, return the database assignment
    """
    if database is None:
        return None

    db_assignment = DatabaseAssignment.objects.filter(
        user=user, database=database, permission__gte=required_level
    ).first()
    if db_assignment is None or db_assignment.permission < required_level:
        raise CustomAssertionError(
            "On database {} you ({}) don't have permission to {}".format(
                database.name,
                user.username,
                DatabasePermission.get_name(required_level).lower(),
            )
        )

    return db_assignment


def assert_values(value, value_range):
    if value not in value_range:
        raise CustomAssertionError("Invalid value {}".format(value))


def get_or_error(obj, key, errmsg=None):
    """
    Get key or filter Model for given attributes. If None found, error
    :param obj: can be dict, Model class name, or a generic object
    :param key: can be a string or a dict containing query filters
    :return: the value or object if found
    """
    if isinstance(obj, dict):
        value = obj.get(key, None)
    elif issubclass(obj, models.Model):
        value = obj.objects.filter(**key).first()
    else:
        value = getattr(obj, key, None)
    if value is None:
        if errmsg is None:
            if isinstance(key, dict):
                errmsg = "No {} with {} exists".format(
                    obj.__name__.lower(),
                    ", ".join(["{}={}".format(k, v) for k, v in key.items()]),
                )

            else:
                errmsg = "{} doesn't exist".format(key)
        raise CustomAssertionError(errmsg)
    return value


@app.task(bind=False)
def delete_segments_async(*args, **kwargs):
    segments = Segment.fobjs.filter(active=False)
    this_vl = segments.values_list("id", "tid")
    this_tids = [x[1] for x in this_vl]
    this_sids = [x[0] for x in this_vl]

    other_vl = Segment.fobjs.filter(tid__in=this_tids).values_list("id", "tid")

    tid2ids = {x: [] for x in this_tids}

    for id, tid in other_vl:
        tid2ids[tid].append(id)

    # These segmnents might share the same spectrogram with other segments. Only delete the spectrogramn
    # if there is only one segment (ID) associated with the syllable's TID
    for tid, ids in tid2ids.items():
        if len(ids) == 1:
            spect_path = get_abs_spect_path(tid)
            if os.path.isfile(spect_path):
                os.remove(spect_path)
                celerylogger.info("Spectrogram {} deleted.".format(spect_path))

    ExtraAttrValue.objects.filter(attr__klass=Segment.__name__, owner_id__in=this_sids).delete()
    segments.delete()


@app.task(bind=False)
def delete_audio_files_async(*args, **kwargs):
    audio_files = AudioFile.fobjs.filter(active=False)

    # Mark all segments belong to these audio files as to be deleted, then delete them
    segments = Segment.objects.filter(audio_file__in=audio_files)
    segments.update(active=False)
    delete_segments_async()

    # Now delete the audio files
    audio_files_ids = audio_files.values_list("id", flat=True)

    ExtraAttrValue.objects.filter(attr__klass=AudioFile.__name__, owner_id__in=audio_files_ids).delete()

    # If the audio file is not original - just delete the model
    # Otherwise, search if there are clones. If there are, make one of the clones the new original
    # If there is no clone, delete the real audio files (wav and mp4)

    for af in audio_files:
        if af.original is None:
            clones = AudioFile.objects.filter(original=af).order_by("id")
            first_clone = clones.first()

            # If there are clones, make the first clone original of the remaining
            # Also move the real audio file to the database's folder of the clone
            if first_clone:
                old_wav_file = wav_path(af)
                old_mp4_file = audio_path(af, settings.AUDIO_COMPRESSED_FORMAT)

                clones.update(original=first_clone)
                first_clone.original = None
                first_clone.save()

                new_wav_file = wav_path(first_clone)
                new_mp4_file = audio_path(first_clone, settings.AUDIO_COMPRESSED_FORMAT)

                os.rename(old_wav_file, new_wav_file)
                os.rename(old_mp4_file, new_mp4_file)

            # Otherwise, delete the audio files too
            else:
                wav = wav_path(af)
                mp4 = audio_path(af, settings.AUDIO_COMPRESSED_FORMAT)
                if os.path.isfile(wav):
                    os.remove(wav)
                if os.path.isfile(mp4):
                    os.remove(mp4)
        af.delete()


@app.task(bind=False)
def delete_database_async(*args, **kwargs):
    databases = Database.fobjs.filter(active=False)

    # Delete all audio files that belong to this database (which will also delete all segments)
    audio_files = AudioFile.objects.filter(database__in=databases)
    audio_files.update(active=False)
    delete_audio_files_async()

    # Now we can safely remove this database
    databases.delete()


def get_labels_by_sids(sids, label_level, annotator, min_occur=None):
    sid2lbl = {
        x: y.lower()
        for x, y in ExtraAttrValue.objects.filter(
            attr__name=label_level, owner_id__in=sids, user=annotator
        ).values_list("owner_id", "value")
    }

    labels = []
    no_label_ids = []

    if min_occur is not None:
        occurs = Counter(sid2lbl.values())

        segment_to_labels = {}
        for segid, label in sid2lbl.items():
            if occurs[label] >= min_occur:
                segment_to_labels[segid] = label
        for id in sids:
            label = segment_to_labels.get(id, None)
            if label is None:
                no_label_ids.append(id)
            labels.append(label)
        return np.array(labels), np.array(no_label_ids, dtype=np.int32)
    else:
        segment_to_labels = {}
        for segid, label in sid2lbl.items():
            segment_to_labels[segid] = label
        for id in sids:
            label = segment_to_labels.get(id, None)
            if label is None:
                no_label_ids.append(id)
            labels.append(label)
        return np.array(labels), np.array(no_label_ids, dtype=np.int32)


def exclude_no_labels(sids, tids, labels, no_label_ids):
    no_label_inds = np.searchsorted(sids, no_label_ids)

    sids_mask = np.full((len(sids),), True, dtype=np.bool)
    sids_mask[no_label_inds] = False

    if tids is not None:
        return sids[sids_mask], tids[sids_mask], labels[sids_mask]
    else:
        return sids[sids_mask], tids, labels[sids_mask]


def select_instances(sids, tids, labels, num_instances):
    label_sorted_indices = np.argsort(labels)
    sorted_labels = labels[label_sorted_indices]

    uniques, counts = np.unique(sorted_labels, return_counts=True)

    if np.any(counts < num_instances):
        raise ValueError(
            "Value of num_instances={} is too big - there are classes that have less than {} instances".format(
                num_instances, num_instances
            )
        )

    nclasses = len(uniques)
    indices_to_add = []

    for i in range(nclasses):
        label = uniques[i]
        instance_indices = np.where(labels == label)[0]
        np.random.shuffle(instance_indices)

        indices_to_add_i = instance_indices[:num_instances]
        indices_to_add.append(indices_to_add_i)

    indices_to_add = np.concatenate(indices_to_add)

    if tids is not None:
        return sids[indices_to_add], tids[indices_to_add], labels[indices_to_add]
    else:
        return sids[indices_to_add], tids, labels[indices_to_add]
