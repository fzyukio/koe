import sys

import numpy as np
from scipy.cluster.hierarchy import linkage

from koe.models import DistanceMatrix, Segment
from koe.utils import triu2mat, mat2triu

PY3 = sys.version_info[0] == 3
if PY3:
    import builtins
else:
    import __builtin__ as builtins

try:
    builtins.profile
except AttributeError:
    builtins.profile = lambda x: x


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
