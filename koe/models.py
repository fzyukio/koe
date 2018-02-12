import hashlib
import os
import pickle
import sys
from logging import warning

import numpy as np
from django.db import models
from django.db.models.query import QuerySet
from django.db.models.signals import post_delete
from django.dispatch import receiver

from koe.utils import base64_to_array, array_to_base64
from root.models import StandardModel, SimpleModel, ExtraAttr, ExtraAttrValue, AutoSetterGetterMixin, User
from root.utils import audio_path, history_path, ensure_parent_folder_exists, data_path

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
    """
    A class that faciliates storing and retrieving numpy array in database.
    The undelying value in database is a base64 string
    """
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
    """
    A track is a whole raw audio recording containing many songs.
    """
    name = models.CharField(max_length=255, unique=True)
    date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name


class Individual(StandardModel):
    """
    Represents a bird.
    """
    name = models.CharField(max_length=255)
    gender = models.CharField(max_length=16)

    def __str__(self):
        return self.name


class AudioFile(StandardModel):
    """
    Represent a song
    """
    fs = models.IntegerField()
    length = models.IntegerField()
    name = models.CharField(max_length=255, unique=True)
    track = models.ForeignKey(AudioTrack, null=True, blank=True, on_delete=models.SET_NULL)
    individual = models.ForeignKey(Individual, null=True, blank=True, on_delete=models.SET_NULL)
    quality = models.CharField(max_length=2, null=True, blank=True)

    @property
    def file_path(self):
        return audio_path(self.name, 'wav')

    @property
    def mp3_path(self):
        return audio_path(self.name, 'mp3')

    def __str__(self):
        return self.name


class Segment(models.Model, AutoSetterGetterMixin):
    """
    A segment of a song
    """
    start_time_ms = models.IntegerField()
    end_time_ms = models.IntegerField()

    # Different people/algorithms might segment a song differently, so a segment
    # can't be a direct dependency of a Song. It must depend on a Segmentation object
    segmentation = models.ForeignKey('Segmentation', on_delete=models.CASCADE)

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

    def __str__(self):
        return '{} by {}'.format(self.audio_file.name, self.source)


class CompareAlgorithm(StandardModel):
    """
    Name of algorithm
    """
    name = models.CharField(max_length=255)


class DistanceMatrix(StandardModel):
    chksum = models.CharField(max_length=24)
    algorithm = models.ForeignKey(CompareAlgorithm, on_delete=models.CASCADE)

    @classmethod
    def calc_chksum(cls, ids):
        ids_str = ''.join(map(str, ids))
        return hashlib.md5(ids_str.encode('ascii')).hexdigest()[:24]

    def save(self, *args, **kwargs):
        fpath = data_path('pickle', self.chksum)
        ensure_parent_folder_exists(fpath)
        if hasattr(self, '_ids'):
            ids = self._ids
        else:
            ids = self.ids

        if hasattr(self, '_triu'):
            triu = self._triu
        else:
            triu = self.triu

        with open(fpath, 'wb') as f:
            loaded = dict(ids=ids, triu=triu)
            pickle.dump(loaded, f, pickle.HIGHEST_PROTOCOL)

        super(DistanceMatrix, self).save(*args, **kwargs)

    def load(self):
        fpath = data_path('pickle', self.chksum)
        with open(fpath, 'rb') as f:
            loaded = pickle.load(f)
            self._ids = loaded['ids']
            self._triu = loaded['triu']

    @property
    def ids(self):
        if not hasattr(self, '_ids'):
            self.load()
        return self._ids

    @property
    def triu(self):
        if not hasattr(self, '_triu'):
            self.load()
        return self._triu

    @ids.setter
    def ids(self, val):
        self._ids = val

    @triu.setter
    def triu(self, val):
        self._triu = val

    class Meta:
        unique_together = ('chksum', 'algorithm')


class ValueForSorting(StandardModel):
    """
    Currently unused
    """
    segment = models.ForeignKey(Segment, on_delete=models.CASCADE)
    algorithm = models.ForeignKey(CompareAlgorithm, on_delete=models.CASCADE)
    value = models.FloatField()

    class Meta:
        unique_together = ('segment', 'algorithm')


class HistoryEntry(StandardModel):
    """
    Represent a snapshot of the current user's workspace.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    time = models.DateTimeField()
    filename = models.CharField(max_length=255)

    def save(self, *args, **kwargs):
        """
        Deduce the filename from username and timestamp - so this field always have a uniform format
        :param args:
        :param kwargs:
        :return:
        """
        self.filename = '{}-{}.zip'.format(self.user.username, self.time.strftime('%Y-%m-%d_%H-%M-%S'))
        super(HistoryEntry, self).save(*args, **kwargs)

    @classmethod
    def get_url(cls, objs, extras):
        """
        :return: a dict with key=id and value=the Markdown-styled url
        """
        if isinstance(objs, QuerySet):
            values_list = objs.values_list('id', 'filename')
        else:
            values_list = [(x.id, x.filename) for x in objs]

        retval = {}

        for id, filename in values_list:
            url = '{}'.format(history_path(filename))
            retval[id] = '[{}]({})'.format(url, filename)

        return retval

    @classmethod
    def get_creator(cls, objs, extras):
        """
        We need this because otherwise the table will display user ID
        :return: a dict with key=id and value=name of the user.
        """
        if isinstance(objs, QuerySet):
            values_list = objs.values_list('id', 'user__username')
        else:
            values_list = [(x.id, x.user.username) for x in objs]

        retval = {}

        for id, username in values_list:
            retval[id] = username

        return retval


@receiver(post_delete, sender=HistoryEntry)
def _mymodel_delete(sender, instance, **kwargs):
    """
    When a HistoryEntry is deleted, also delete its ZIP file
    :param sender:
    :param instance:
    :param kwargs:
    :return:
    """
    filepath = history_path(instance.filename)
    print('Delete {}'.format(filepath))
    if os.path.isfile(filepath):
        os.remove(filepath)
    else:
        warning('File {} doesnot exist.'.format(filepath))

