import os
import numpy as np
from PIL import Image
from django.conf import settings
from django.db import models
from scipy import signal
from scipy.cluster.hierarchy import linkage

from koe.celery import app
from koe.colourmap import cm_red, cm_green, cm_blue
from koe.management.commands.utils import wav_2_mono
from koe.models import DistanceMatrix, Segment, DatabaseAssignment, Database, DatabasePermission, TemporaryDatabase,\
    AudioFile
from koe.utils import triu2mat, mat2triu
from root.exceptions import CustomAssertionError
from root.models import ExtraAttrValue
from root.utils import spect_fft_path, wav_path, ensure_parent_folder_exists, audio_path

window_size = 256
noverlap = 256 * 0.75
window = signal.get_window('hann', 256)
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
        new_node['seg-id'] = idx_2_seg_id[idx]

    if 'children' in parent:
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
    all_segments_ids = np.array(list(Segment.objects.all().order_by('id').values_list('id', flat=True)))
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

    tree = linkage(triu, method='average')
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
    assigned_databases_ids = DatabaseAssignment.objects.filter(user=user).values_list('database__id', flat=True)
    databases = Database.objects.filter(id__in=assigned_databases_ids)
    return databases


def get_user_databases(user):
    """
    Return user's current database and the database's current similarity matrix
    :param user:
    :return:
    """
    current_database_value = ExtraAttrValue.objects.filter(attr=settings.ATTRS.user.current_database, owner_id=user.id,
                                                           user=user).first()
    db_class = Database
    if current_database_value:
        current_database_value = current_database_value.value
        if '_' in current_database_value:
            db_class_name, current_database_id = current_database_value.split('_')
            if db_class_name == TemporaryDatabase.__name__:
                db_class = TemporaryDatabase
        else:
            current_database_id = current_database_value

        current_database = db_class.objects.get(pk=current_database_id)

    else:
        databases = get_user_accessible_databases(user)
        current_database = databases.first()
        if current_database is not None:
            ExtraAttrValue.objects.create(attr=settings.ATTRS.user.current_database, owner_id=user.id, user=user,
                                          value='{}_{}'.format(db_class, current_database.id))

    return current_database


def extract_spectrogram(audio_file):
    """
    Extract raw sepectrograms for all segments (Not the masked spectrogram from Luscinia) of an audio file
    :param audio_file:
    :return:
    """
    segs_info = Segment.objects.filter(audio_file=audio_file).values_list('tid', 'start_time_ms', 'end_time_ms')

    missing_segs_info = []

    for tid, start, end in segs_info:
        seg_spect_path = spect_fft_path(tid, 'syllable')
        ensure_parent_folder_exists(seg_spect_path)
        if os.path.isfile(seg_spect_path):
            missing_segs_info.append((seg_spect_path, start, end))

    if len(missing_segs_info) > 0:

        song_name = audio_file.name

        filepath = wav_path(song_name)

        fs, sig = wav_2_mono(filepath)
        duration_ms = len(sig) * 1000 / fs

        _, _, s = signal.stft(sig, fs=fs, window=window, noverlap=noverlap, nfft=window_size, return_onesided=True)
        file_spect = np.abs(s * scale)

        height, width = np.shape(file_spect)
        file_spect = np.flipud(file_spect)

        file_spect = np.log10(file_spect)
        file_spect = ((file_spect - global_min_spect_pixel) / interval64)
        file_spect[np.isinf(file_spect)] = 0
        file_spect = file_spect.astype(np.int)

        file_spect = file_spect.reshape((width * height,), order='C')
        file_spect[file_spect >= 64] = 63
        file_spect_rgb = np.empty((height, width, 3), dtype=np.uint8)
        file_spect_rgb[:, :, 0] = cm_red[file_spect].reshape(
            (height, width)) * 255
        file_spect_rgb[:, :, 1] = cm_green[file_spect].reshape(
            (height, width)) * 255
        file_spect_rgb[:, :, 2] = cm_blue[file_spect].reshape(
            (height, width)) * 255

        for path, start, end in missing_segs_info:
            roi_start = int(start / duration_ms * width)
            roi_end = int(np.ceil(end / duration_ms * width))

            seg_spect_rgb = file_spect_rgb[:, roi_start:roi_end, :]
            seg_spect_img = Image.fromarray(seg_spect_rgb)

            seg_spect_img.save(path, format='PNG')


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

    db_assignment = DatabaseAssignment.objects \
        .filter(user=user, database=database, permission__gte=required_level).first()
    if db_assignment is None or db_assignment.permission < required_level:
        raise CustomAssertionError('On database {} you ({}) don\'t have permission to {}'.format(
            database.name, user.username, DatabasePermission.get_name(required_level).lower()
        ))

    return db_assignment


def assert_values(value, value_range):
    if value not in value_range:
        raise CustomAssertionError('Invalid value {}'.format(value))


def get_or_error(obj, key):
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
        if isinstance(key, dict):
            error = 'No {} with {} exists'.format(
                obj.__name__.lower(), ', '.join(['{}={}'.format(k, v) for k, v in key.items()])
            )
            raise CustomAssertionError(error)
        raise CustomAssertionError('{} doesn\'t exist'.format(key))

    return value


@app.task(bind=False)
def delete_segments_async():
    segments = Segment.fobjs.filter(active=False)
    this_vl = segments.values_list('id', 'tid')
    this_tids = [x[1] for x in this_vl]
    this_sids = [x[0] for x in this_vl]

    other_vl = Segment.objects.filter(tid__in=this_tids).values_list('id', 'tid')

    tid2ids = {x: [] for x in this_tids}
    path_template = spect_fft_path('{}', 'syllable')

    for id, tid in other_vl:
        tid2ids[tid].append(id)

    # These segmnents might share the same spectrogram with other segments. Only delete the spectrogramn
    # if there is only one segment (ID) associated with the syllable's TID
    for tid, ids in tid2ids.items():
        if len(ids) == 1:
            spect_path = path_template.format(tid)
            if os.path.isfile(spect_path):
                os.remove(spect_path)

    ExtraAttrValue.objects.filter(attr__klass=Segment.__name__, owner_id__in=this_sids).delete()
    segments.delete()


@app.task(bind=False)
def delete_audio_files_async():
    audio_files = AudioFile.fobjs.filter(active=False)
    audio_files_ids = audio_files.values_list('id', flat=True)

    ExtraAttrValue.objects.filter(attr__klass=AudioFile.__name__, owner_id__in=audio_files_ids).delete()

    # If the audio file is not original - just delete the model
    # Otherwise, search if there are clones. If there are, make one of the clones the new original
    # If there is no clone, delete the real audio files (wav and mp4)

    for af in audio_files:
        if af.original is None:
            clones = AudioFile.objects.filter(original=af).order_by('id')
            first_clone = clones.first()
            if first_clone:
                clones.update(original=first_clone)
                first_clone.original = None
                first_clone.save()
            else:
                af_name = af.name
                if not af_name.endswith('.wav'):
                    af_name += '.wav'
                wav = wav_path(af_name)
                mp4 = audio_path(af_name, settings.AUDIO_COMPRESSED_FORMAT)
                if os.path.isfile(wav):
                    os.remove(wav)
                if os.path.isfile(mp4):
                    os.remove(mp4)
        af.delete()
