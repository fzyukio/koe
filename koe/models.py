import hashlib
import sys
import numpy as np

from django.db import models
from django.db.models.query import QuerySet

from scipy.cluster.hierarchy import linkage

from koe.utils import base64_to_array, array_to_base64, triu2mat, mat2triu
from root.models import StandardModel, SimpleModel, ExtraAttr, ExtraAttrValue, AutoSetterGetterMixin
from root.utils import spect_path

PY3 = sys.version_info[0] == 3
if PY3:
    import builtins
else:
    import __builtin__ as builtins

try:
    builtins.profile
except AttributeError:
    builtins.profile = lambda x: x


class NumpyArrayField(models.TextField):

    def __init__(self, *args, **kwargs):
        super(NumpyArrayField, self).__init__(*args, **kwargs)

    def to_python(self, value):
        if isinstance(value, NumpyArrayField):
            return value

        if value is None:
            return value

        return base64_to_array(value)

    def from_db_value(self, value, expression, connection):
        if value is None:
            return value
        return base64_to_array(value)

    def get_prep_value(self, value):
        if value is None:
            return None
        if not isinstance(value, np.ndarray):
            raise TypeError('value must be a numpy array')
        return array_to_base64(value)


class AudioTrack(StandardModel):
    name = models.CharField(max_length=1024)

    def __str__(self):
        return self.name


class AudioFile(StandardModel):
    raw_file = models.CharField(max_length=1024, unique=True)
    mp3_file = models.CharField(max_length=1024, unique=True)
    track = models.ForeignKey(AudioTrack, default=None, null=True, blank=True, on_delete=models.CASCADE)
    fs = models.IntegerField()
    length = models.IntegerField()
    name = models.CharField(max_length=1024)

    def __str__(self):
        return self.name


# Create a nested dictionary from the ClusterNode's returned by SciPy
def add_node(node, idx_2_seg_id, parent, root_dist):
    # First create the new node and append it to its parent's children
    new_node = dict(dist=root_dist-node.dist, children=[])

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
        add_node(node.left, idx_2_seg_id, new_node, root_dist)
    if node.right:
        add_node(node.right, idx_2_seg_id, new_node, root_dist)


def dist_from_root(tree):
    last_idx = tree.shape[0]
    indices = np.ndarray((last_idx+1, ), dtype=np.uint32)
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
    # root_dist = tree[-1, 2] / 2
    return indices, distances


def upgma_dist(segments_ids, dm):
    all_segments_ids = np.array(list(Segment.objects.all().order_by('id').values_list('id', flat=True)))

    ids_str = ''.join(map(str, all_segments_ids))
    chksum = hashlib.md5(ids_str.encode('ascii')).hexdigest()

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


class Segment(models.Model, AutoSetterGetterMixin):
    start_time_ms = models.IntegerField()
    end_time_ms = models.IntegerField()

    segmentation = models.ForeignKey('Segmentation', on_delete=models.CASCADE)

    @classmethod
    def bulk_get_segment_info(cls, segs, extras):
        rows = []
        if isinstance(segs, QuerySet):
            attr_values_list = list(segs.values_list('id', 'start_time_ms', 'end_time_ms',
                                                     'segmentation__audio_file__name'))
        else:
            attr_values_list = [(x.id, x.start_time_ms, x.end_time_ms, x.segmentation.audio_file.name) for x in segs]
        extra_attrs = ExtraAttr.objects.filter(klass=cls.__name__)
        extra_attr_values_list = ExtraAttrValue.objects.filter(attr__in=extra_attrs, owner_id__in=segs)\
            .values_list('owner_id', 'attr__name', 'value')

        extra_attr_values_lookup = {}
        for id, attr, value in extra_attr_values_list:
            if id not in extra_attr_values_lookup:
                extra_attr_values_lookup[id] = {}
            attr_dict = extra_attr_values_lookup[id]
            attr_dict[attr] = value

        ids = [x[0] for x in attr_values_list]

        dm = extras['dm']
        dm = DistanceMatrix.objects.get(id=dm)

        indices, distances = upgma_dist(ids, dm)

        for i in range(len(attr_values_list)):
            id, start, end, song = attr_values_list[i]
            dist = distances[i]
            index = indices[i]
            spect_img, _ = spect_path(str(id))
            duration = end-start
            row = dict(id=id, start_time_ms=start, end_time_ms=end, duration=duration, song=song, spectrogram=spect_img,
                       distance=dist, dtw_index=index)
            attr_dict = extra_attr_values_lookup.get(str(id), {})
            for attr in attr_dict:
                row[attr] = attr_dict[attr]
            rows.append(row)
        return rows

    def __str__(self):
        return '{} - {}:{}'.format(self.segmentation.audio_file.name, self.start_time_ms, self.end_time_ms)

    class Meta:
        ordering = ('segmentation', 'start_time_ms')


class Segmentation(StandardModel):
    """
    Represents a segmentation scheme, which aggregate all segments
    """
    audio_file = models.ForeignKey(AudioFile, null=True, on_delete=models.CASCADE)
    source = models.CharField(max_length=1023)

    def get_segment_count(self):
        return Segment.objects.filter(segmentation=self).count()

    def get_segments(self):
        segments = Segment.objects.filter(segmentation=self).order_by('start_time_norm')
        return segments

    def __str__(self):
        return '{} by {}'.format(self.audio_file.name, self.source)


class DistanceMatrix(StandardModel):
    ids = NumpyArrayField()
    triu = NumpyArrayField()
    chksum = models.CharField(max_length=8)
    algorithm = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        ids_str = ''.join(map(str, self.ids))
        self.chksum = hashlib.md5(ids_str.encode('ascii')).hexdigest()
        super(DistanceMatrix, self).save(*args, **kwargs)

    class Meta:
        unique_together = ('chksum', 'algorithm')
