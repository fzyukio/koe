import numpy as np
from PIL import Image
from django.conf import settings
from scipy import signal
from scipy.cluster.hierarchy import linkage

from koe.colourmap import cm_red, cm_green, cm_blue
from koe.management.commands.utils import wav_2_mono
from koe.models import DistanceMatrix, Segment, Coordinate, DatabaseAssignment, Database
from koe.utils import triu2mat, mat2triu
from root.models import ExtraAttrValue
from root.utils import spect_fft_path, wav_path, ensure_parent_folder_exists

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


def get_user_databases(user):
    """
    Return user's current database and the database's current similarity matrix
    :param user:
    :return:
    """
    assigned_databases_ids = DatabaseAssignment.objects.filter(user=user).values_list('database__id', flat=True)
    databases = Database.objects.filter(id__in=assigned_databases_ids)

    current_database_value = ExtraAttrValue.objects.filter(attr=settings.ATTRS.user.current_database, owner_id=user.id,
                                                           user=user).first()

    if current_database_value:
        current_database_id = current_database_value.value
        current_database = databases.get(pk=current_database_id)
    else:
        current_database = databases.first()

    return databases, current_database


def get_current_similarity(user, current_database):
    """
    Return user's current database and the database's current similarity matrix
    :param current_database:
    :param user:
    :return:
    """
    similarities = Coordinate.objects.filter(database=current_database).first()

    if similarities is None:
        return None, None

    current_similarity_value = ExtraAttrValue.objects\
        .filter(attr=settings.ATTRS.user.current_similarity, user=user, owner_id=current_database.id).first()

    if current_similarity_value:
        current_similarity_id = current_similarity_value.value
        current_similarity = Coordinate.objects.get(pk=current_similarity_id)
    else:
        current_similarity = similarities.first()

    return similarities, current_similarity


def extract_spectrogram(segmentation):
    """
    Extract raw sepectrograms for all segments (Not the masked spectrogram from Luscinia) of an audio file given the
    segmentation scheme
    :param segmentation:
    :return:
    """
    segs_info = Segment.objects.filter(segmentation=segmentation).values_list('id', 'start_time_ms', 'end_time_ms')
    audio_file = segmentation.audio_file
    song_name = audio_file.name

    filepath = wav_path(song_name)

    fs, sig = wav_2_mono(filepath)
    duration_ms = len(sig) * 1000 / fs

    _, _, s = signal.stft(sig, fs=fs, window=window,
                          noverlap=noverlap, nfft=window_size, return_onesided=True)
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

    for seg_id, start, end in segs_info:
        roi_start = int(start / duration_ms * width)
        roi_end = int(np.ceil(end / duration_ms * width))

        seg_spect_rgb = file_spect_rgb[:, roi_start:roi_end, :]
        seg_spect_img = Image.fromarray(seg_spect_rgb)
        seg_spect_path = spect_fft_path(str(seg_id), 'syllable')
        ensure_parent_folder_exists(seg_spect_path)

        seg_spect_img.save(seg_spect_path, format='PNG')
