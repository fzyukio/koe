import datetime
import hashlib
import os
import pickle
import re
from abc import abstractmethod
from logging import warning

from django.utils import timezone
import django.db.models.options as options
import numpy as np
from django.conf import settings
from django.db import models
from django.db.models.signals import post_delete
from django.dispatch import receiver
from sortedcontainers import SortedDict

from koe.utils import base64_to_array, array_to_base64
from root.exceptions import CustomAssertionError
from root.models import SimpleModel, User, MagicChoices, ValidateOnUpdateQuerySet
from root.utils import ensure_parent_folder_exists
from koe.utils import history_path, pickle_path, wav_path, audio_path

__all__ = [
    'NumpyArrayField', 'AudioTrack', 'Species', 'Individual', 'Database', 'DatabasePermission', 'AccessRequest',
    'DatabaseAssignment', 'AudioFile', 'Segment', 'DistanceMatrix', 'Coordinate', 'HistoryEntry', 'TemporaryDatabase',
    'Task', 'DataMatrix', 'Ordination', 'SimilarityIndex', 'Preference', 'InvitationCode'
]


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


class AudioTrack(SimpleModel):
    """
    A track is a whole raw audio recording containing many songs.
    """

    name = models.CharField(max_length=255, unique=True)
    date = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name


class Species(SimpleModel):
    genus = models.CharField(max_length=32)
    species = models.CharField(max_length=32)

    class Meta:
        unique_together = ['species', 'genus']

    def __str__(self):
        return '{} {}'.format(self.genus, self.species)


class Individual(SimpleModel):
    """
    Represents a bird.
    """

    name = models.CharField(max_length=255, unique=True)
    gender = models.CharField(max_length=16, null=True, blank=True)
    species = models.ForeignKey(Species, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return self.name


class Database(SimpleModel):
    """
    This works as a separator between different sets of audio files that are not related.
    E.g. a database of bellbirds and a database of dolphin sounds...
    """

    name = models.CharField(max_length=255, unique=True)

    def is_real(self):
        return True

    def __str__(self):
        return self.name

    def save(self, **kwargs):
        if not re.match("^[a-zA-Z0-9_]+$", self.name):
            raise CustomAssertionError('Database name must be non-empty and can only contain alphabets, digits and '
                                       'underscores')
        super(Database, self).save(**kwargs)

    def get_assigned_permission(self, user):
        da = DatabaseAssignment.objects.filter(database=self, user=user).first()
        if da:
            return da.permission
        else:
            return 0

    @classmethod
    def validate(cls, key_val_pairs):
        if 'name' in key_val_pairs:
            name = key_val_pairs['name']
            if not re.match('^[a-zA-Z0-9_-]+$', name):
                raise CustomAssertionError('Name can only contain alphabets, numbers, dashes and underscores')

    @classmethod
    def filter(cls, extras):
        user = extras.user

        assigned_db_ids = DatabaseAssignment.objects.filter(user=user).values_list('database__id')
        return Database.objects.filter(id__in=assigned_db_ids)

    @classmethod
    def get_row_editability(cls, databases, extras):
        user = extras.user
        retval = {database.id: False for database in databases}
        editable_db = DatabaseAssignment.objects\
            .filter(database__in=databases, user=user, permission__gte=DatabasePermission.ASSIGN_USER)\
            .values_list('database__id', flat=True)

        for id in editable_db:
            retval[id] = True
        return retval


class DatabasePermission(MagicChoices):
    VIEW = 100
    ANNOTATE = 200
    IMPORT_DATA = 300
    COPY_FILES = 400
    DOWNLOAD_FILES = 450
    ADD_FILES = 500
    MODIFY_SEGMENTS = 600
    DELETE_FILES = 700
    ASSIGN_USER = 800


class DatabaseAssignment(SimpleModel):
    """
    Grant user access to database with this
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    database = models.ForeignKey(Database, on_delete=models.CASCADE)
    permission = models.IntegerField(choices=DatabasePermission.as_choices())
    expiry = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return 'Database {} assigned to user {} with {} permission'.format(
            self.database.name, self.user.username, self.get_permission_display()
        )

    class Meta:
        unique_together = ('user', 'database', 'permission')
        ordering = ('user', 'database', 'permission')

    def can_view(self):
        return self.user.is_superuser or self.permission >= DatabasePermission.VIEW

    def can_annotate(self):
        return self.user.is_superuser or self.permission >= DatabasePermission.ANNOTATE

    def can_copy_files(self):
        return self.user.is_superuser or self.permission >= DatabasePermission.COPY_FILES

    def can_download_files(self):
        return self.user.is_superuser or self.permission >= DatabasePermission.DOWNLOAD_FILES

    def can_add_files(self):
        return self.user.is_superuser or self.permission >= DatabasePermission.ADD_FILES

    def can_modify_segments(self):
        return self.user.is_superuser or self.permission >= DatabasePermission.MODIFY_SEGMENTS

    def can_delete_files(self):
        return self.user.is_superuser or self.permission >= DatabasePermission.DELETE_FILES

    def can_assign_user(self):
        return self.user.is_superuser or self.permission >= DatabasePermission.ASSIGN_USER

    @classmethod
    def get_row_editability(cls, das, extras):
        database_id = extras.database
        user = extras.user
        das = das.filter(database=database_id)

        user_permission = das.filter(user=user).first()
        user_is_owner = user_permission is not None and user_permission.permission >= DatabasePermission.ASSIGN_USER

        retval = {da.id: user_is_owner for da in das}

        # Forbid owners from changing their own permission - prevent database from having no owner at all.
        retval[user_permission.id] = False
        return retval


class ActiveManager(models.Manager):
    def get_queryset(self):
        return ValidateOnUpdateQuerySet(self.model, using=self._db).filter(active=True)


class AudioFile(SimpleModel):
    """
    Represent a song
    """

    fs = models.IntegerField()

    # For high frequency audios, provide a lower sample rate (fake_fs) to prevent the browser from downsampling audio
    # WAV file is stored with original fs, but mp3 file is converted with the faked fs one to circumvent the MP3 specs
    fake_fs = models.IntegerField(null=True, blank=True)
    length = models.IntegerField()
    name = models.CharField(max_length=255)
    # file_name = models.CharField(max_length=255)
    track = models.ForeignKey(AudioTrack, null=True, blank=True, on_delete=models.SET_NULL)
    individual = models.ForeignKey(Individual, null=True, blank=True, on_delete=models.SET_NULL)
    quality = models.CharField(max_length=255, null=True, blank=True)
    database = models.ForeignKey(Database, on_delete=models.CASCADE)
    start = models.IntegerField(null=True, blank=True)
    end = models.IntegerField(null=True, blank=True)

    # To facilitate copying database - when an AudioFile object is copied, another object is created
    # with the same name but different database, and reference this object as its original
    original = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True)

    active = models.BooleanField(default=True)
    objects = ActiveManager()
    fobjs = models.Manager()

    class Meta:
        unique_together = ['name', 'database']

    def __str__(self):
        return self.name

    def is_original(self):
        """
        An AudioFile object is original if it doesn't reference any one
        :return: True if it is original
        """
        return self.original is None

    @classmethod
    def set_species(cls, objs, value, extras={}):
        value = value.strip()
        if value:
            parts = value.split(' ')
            if len(parts) != 2:
                raise CustomAssertionError('Species name must consist of Genus and Species')

            genus, species_code = parts
            species, _ = Species.objects.get_or_create(genus=genus, species=species_code)
            Individual.objects.filter(audiofile__in=objs).update(species=species)

    @classmethod
    def set_individual(cls, objs, name, extras={}):
        individual, _ = Individual.objects.get_or_create(name=name)
        AudioFile.objects.filter(id__in=[x.id for x in objs]).update(individual=individual)

    @classmethod
    def set_track(cls, objs, name, extras={}):
        track, _ = AudioTrack.objects.get_or_create(name=name)
        AudioFile.objects.filter(id__in=[x.id for x in objs]).update(track=track)

    @classmethod
    def set_gender(cls, objs, value, extras={}):
        Individual.objects.filter(audiofile__in=objs).update(gender=value)

    @classmethod
    def set_date(cls, objs, value, extras={}):
        if value is None or value.strip() == '':
            date = None
        else:
            try:
                date = datetime.datetime.strptime(value, settings.DATE_INPUT_FORMAT).date()
            except Exception as e:
                raise CustomAssertionError('Invalid date: {}'.format(value))

        AudioTrack.objects.filter(audiofile__in=objs).update(date=date)

    @classmethod
    def set_name(cls, objs, name, extras={}):
        if len(objs) != 1:
            raise CustomAssertionError('Can\'t set the same name to more than 1 song.')
        obj = objs[0]

        if obj.name != name and AudioFile.objects.filter(database=obj.database, name=name).exists():
            raise CustomAssertionError('File {} already exists'.format(name))

        # If audio file is original, change the actual audio files' names as well
        if obj.is_original():
            old_name = obj.name
            old_name_wav = wav_path(obj)
            old_name_compressed = audio_path(obj, settings.AUDIO_COMPRESSED_FORMAT)

            try:
                obj.name = name
                obj.save()
                new_name_wav = wav_path(obj)
                new_name_compressed = audio_path(obj, settings.AUDIO_COMPRESSED_FORMAT)

                os.rename(old_name_wav, new_name_wav)
                os.rename(old_name_compressed, new_name_compressed)
            except Exception as e:
                obj.name = old_name
                obj.save()
                raise CustomAssertionError('Error changing name')
        else:
            obj.name = name
            obj.save()

    @classmethod
    def get_table_editability(cls, *args, **kwargs):
        return set_editable_for_real_db(*args, **kwargs)


class Segment(SimpleModel):
    """
    A segment of a song
    """

    # Time ID - unique for each combination of (song name, start and end). Recalculate if end/begin changes
    tid = models.IntegerField(null=True, blank=False)

    start_time_ms = models.IntegerField()
    end_time_ms = models.IntegerField()

    audio_file = models.ForeignKey(AudioFile, on_delete=models.CASCADE)

    # Some measurements
    mean_ff = models.FloatField(null=True)
    min_ff = models.FloatField(null=True)
    max_ff = models.FloatField(null=True)

    active = models.BooleanField(default=True)
    objects = ActiveManager()
    fobjs = models.Manager()

    def __str__(self):
        return '{} - {}:{}'.format(self.audio_file.name, self.start_time_ms, self.end_time_ms)

    class Meta:
        ordering = ('audio_file', 'start_time_ms')

    @classmethod
    def get_table_editability(cls, *args, **kwargs):
        return set_editable_for_real_db(*args, **kwargs)


options.DEFAULT_NAMES += 'attrs',


class PicklePersistedModel(SimpleModel):
    """
    Abstract base for models that need to persist its attributes not in the database but in a pickle file
    Any attributes can be added to the model by declaring `attrs = ('attribute1', 'attribute2',...) in class Meta
    """

    class Meta:
        abstract = True

    def __init__(self, *args, **kwargs):
        super(PicklePersistedModel, self).__init__(*args, **kwargs)

        # Load the persisted data on to the model from its pickle file
        self.load()

    def save(self, *args, **kwargs):
        """
        Save the object and then use its ID to store a pickle file contaning all the attrs as declared
        Pickle file will be stored in user_data/pickle/<class name>/
        :param args:
        :param kwargs:
        :return: None
        """
        super(PicklePersistedModel, self).save(*args, **kwargs)

        fpath = pickle_path(self.id, self.__class__.__name__)
        ensure_parent_folder_exists(fpath)

        mdict = {}
        for attr in self._meta.attrs:
            mdict[attr] = getattr(self, attr)

        with open(fpath, 'wb') as f:
            pickle.dump(mdict, f, pickle.HIGHEST_PROTOCOL)

    def load(self):
        """
        Load the persisted data on to the model from its pickle file
        Not to be called when the model is being constructed
        :return: None
        """
        if self.id:
            fpath = pickle_path(self.id, self.__class__.__name__)
            if os.path.isfile(fpath):
                with open(fpath, 'rb') as f:
                    mdict = pickle.load(f)
                for attr in self._meta.attrs:
                    # _attr = '_{}'.format(attr)
                    setattr(self, attr, mdict[attr])
                self._loaded = True
            else:
                warning('Can\'t restore data for {} #{}. File {} not found'
                        .format(self.__class__.__name__, self.id, fpath))

    def __str__(self):
        retval = ['{} #{}: '.format(self.__class__.__name__, self.id)]
        for attr in self._meta.attrs:
            retval.append('{}: {}'.format(attr, getattr(self, attr, None)))

        return ', '.join(retval)


class AlgorithmicModelMixin(models.Model):
    """
    This is an abstract for models that can be distinguished by the attribute algorithm
    """

    algorithm = models.CharField(max_length=255)
    database = models.ForeignKey(Database, on_delete=models.CASCADE)

    class Meta:
        abstract = True

    def __str__(self):
        standard_str = super(AlgorithmicModelMixin, self).__str__()
        extras = 'Database: {} algorithm: {}'.format(self.database.name, self.algorithm)
        return '{}, {}'.format(standard_str, extras)


class IdOrderedModel(PicklePersistedModel):
    """
    This is an abstract for models that have a unique list of IDs as its attribute.
      To facilitate querying, we store a checksum of the concatenated list as a unique field in the database
      The checksum is calculated automatically upon saving
    """

    chksum = models.CharField(max_length=24)

    class Meta:
        abstract = True

    @classmethod
    def calc_chksum(cls, ids):
        ids_str = ''.join(map(str, ids))
        return hashlib.md5(ids_str.encode('ascii')).hexdigest()[:24]

    def save(self, *args, **kwargs):
        self.chksum = IdOrderedModel.calc_chksum(self.ids)
        super(IdOrderedModel, self).save(*args, **kwargs)


class DistanceMatrix(AlgorithmicModelMixin, IdOrderedModel):
    """
    To store the upper triangle (triu) of a distance matrix
    """

    class Meta:
        unique_together = ('chksum', 'algorithm', 'database')
        attrs = ('ids', 'triu')


class Coordinate(AlgorithmicModelMixin, IdOrderedModel):
    """
    To store a list of coordinates together with the clustered tree and the sorted natural order of the elements
    """

    class Meta:
        unique_together = ('chksum', 'algorithm', 'database')
        attrs = ('ids', 'coordinates', 'tree', 'order')


class TemporaryDatabase(IdOrderedModel):
    """
    To store the upper triangle (triu) of a distance matrix
    """

    name = models.CharField(max_length=255, unique=False)
    _databases = models.CharField(max_length=255, null=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = [('chksum', 'user'), ('user', 'name')]
        attrs = ('ids',)

    def get_databases(self):
        if not self._databases:
            ids = self.ids
            databases = set(Segment.objects.filter(id__in=ids).values_list('audio_file__database', flat=True))
            self._databases = ','.join(list(map(str, databases)))
            self.save()

        return Database.objects.filter(id__in=list(map(int, self._databases.split(','))))

    def get_assigned_permission(self, user):
        databases = self.get_databases()
        ps = DatabaseAssignment.objects.filter(database__in=databases, user=user).values_list('permission', flat=True)
        if len(ps) > 0:
            return min(ps)
        else:
            return DatabasePermission.VIEW

    @classmethod
    def validate(cls, key_val_pairs):
        if 'name' in key_val_pairs:
            name = key_val_pairs['name']
            if not re.match('^[a-zA-Z0-9_-]+$', name):
                raise CustomAssertionError('Name can only contain alphabets, numbers, dashes and underscores')

    def save(self, *args, **kwargs):
        if not re.match('^[a-zA-Z0-9_-]+$', self.name):
            raise CustomAssertionError('Name can only contain alphabets, numbers, dashes and underscores')
        super(TemporaryDatabase, self).save(*args, **kwargs)


class HistoryEntry(SimpleModel):
    """
    Represent a snapshot of the current user's workspace.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    version = models.IntegerField(default=1)
    note = models.TextField(null=True, blank=True)
    time = models.DateTimeField()
    filename = models.CharField(max_length=255)
    database = models.ForeignKey(Database, on_delete=models.SET_NULL, null=True, blank=False)
    type = models.CharField(max_length=32, default='labels')

    class Meta:
        ordering = ['-time', 'user', 'database']

    def save(self, *args, **kwargs):
        """
        Deduce the filename from username and timestamp - so this field always have a uniform format
        :param args:
        :param kwargs:
        :return:
        """
        if not self.filename:
            self.filename = '{}-{}.zip'.format(self.user.username, self.time.strftime('%Y-%m-%d_%H-%M-%S_%Z'))
        super(HistoryEntry, self).save(*args, **kwargs)

    @classmethod
    def get_row_editability(cls, hes, extras):
        database_id = extras.database
        user = extras.user
        hes = hes.filter(database=database_id)
        retval = {he.id: he.user == user for he in hes}
        return retval


class AccessRequest(SimpleModel):
    """
    Record a database access request from user so that a database admin can response
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    database = models.ForeignKey(Database, on_delete=models.CASCADE)
    permission = models.IntegerField(choices=DatabasePermission.as_choices(), default=DatabasePermission.VIEW)
    resolved = models.BooleanField(default=False)

    class Meta:
        unique_together = ['user', 'database']

    def __str__(self):
        resolved_or_not = '[RESOLVED] ' if self.resolved else ''
        return '{}{} requested {} permission on {}'.format(
            resolved_or_not, self.user.username, self.get_permission_display(), self.database.name
        )


class Feature(SimpleModel):
    name = models.CharField(max_length=255, unique=True)
    is_fixed_length = models.BooleanField()
    is_one_dimensional = models.BooleanField()

    def __str__(self):
        return self.name


class Aggregation(SimpleModel):
    name = models.CharField(max_length=255, unique=True)
    enabled = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class TaskProgressStage(MagicChoices):
    NOT_STARTED = 100
    PREPARING = 200
    RUNNING = 300
    WRAPPING_UP = 400
    COMPLETED = 500
    ERROR = 600


class NonDbTask:
    def __init__(self, **kwargs):
        self.id = 0
        self.user = kwargs.get('user', None)
        self.parent = kwargs.get('parent', None)
        self.stage = TaskProgressStage.NOT_STARTED
        self.created = timezone.now()
        self.started = None
        self.completed = None
        self.pc_complete = 0.
        self.message = None
        self.target = None

    def save(self):
        pass


class Task(SimpleModel):
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    started = models.DateTimeField(null=True, default=None, blank=True)
    completed = models.DateTimeField(null=True, default=None, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    stage = models.IntegerField(choices=TaskProgressStage.as_choices(), default=TaskProgressStage.NOT_STARTED)
    pc_complete = models.FloatField(default=0.)
    message = models.TextField(null=True, default=None, blank=True)
    target = models.CharField(max_length=255, null=True, default=None, blank=True)

    def __str__(self):
        if self.parent is None:
            return 'Task #{} owner: {} Stage: {} - {:3.1f}pc completed'.format(
                self.id, self.user.id, self.get_stage_display(), self.pc_complete
            )
        else:
            return 'Subtask #{} from Task #{} owner: {} Stage: {} - {:3.1f}pc completed'.format(
                self.id, self.parent.id, self.user.id, self.get_stage_display(), self.pc_complete
            )

    def is_completed(self):
        return self.stage == TaskProgressStage.COMPLETED


class BinaryStoredMixin:
    @abstractmethod
    def _get_path(self, ext):
        pass

    def get_sids_path(self):
        return self._get_path('ids')

    def get_tids_path(self):
        return self._get_path('tids')

    def get_bytes_path(self):
        return self._get_path('bytes')


class DataMatrix(SimpleModel, BinaryStoredMixin):
    """
    Stores extracted feature values of selected IDs
    """

    name = models.CharField(max_length=255)
    database = models.ForeignKey(Database, on_delete=models.SET_NULL, null=True, blank=True)
    tmpdb = models.ForeignKey(TemporaryDatabase, on_delete=models.SET_NULL, null=True, blank=True)
    features_hash = models.CharField(max_length=255)
    aggregations_hash = models.CharField(max_length=255, null=True, blank=True)
    ndims = models.IntegerField()
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True)

    def save(self, **kwargs):
        if self.database is None and self.tmpdb is None:
            raise Exception('Either database or tmpdb must be provided')
        super(DataMatrix, self).save(**kwargs)

    def _get_path(self, ext):
        return os.path.join(settings.MEDIA_URL, 'measurement', str(self.id), '{}.{}'.format(self.id, ext))[1:]

    def get_cols_path(self):
        return self._get_path('cols')

    def __str__(self):
        if self.database:
            return '{}: {}'.format(self.database.name, self.name)
        else:
            return '{}: {}'.format(self.tmpdb.name, self.name)


class Ordination(SimpleModel, BinaryStoredMixin):
    dm = models.ForeignKey(DataMatrix, on_delete=models.CASCADE)
    method = models.CharField(max_length=255)
    ndims = models.IntegerField()
    params = models.CharField(max_length=255, default='')
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True)

    def _get_path(self, ext):
        return os.path.join(settings.MEDIA_URL, 'ordination', str(self.id), '{}.{}'.format(self.id, ext))[1:]

    def __str__(self):
        return '{}_{}_{}'.format(self.dm, self.method, self.ndims)

    def get_name(self):
        return '{}_{}_{}'.format(self.dm.name, self.method, self.ndims)

    @classmethod
    def clean_params(cls, params):
        """
        Valid params at least must have the correct syntax, that is, they must construct a dictionary
        :param params:
        :return:
        """
        param_dict = cls.params_to_kwargs(params)
        cleaned_params_list = []
        for key, value in param_dict.items():
            cleaned_params_list.append('{}={}'.format(key, repr(value)))
        return ','.join(cleaned_params_list)

    @classmethod
    def params_to_kwargs(cls, params):
        """
        Valid params at least must have the correct syntax, that is, they must construct a dictionary
        :param params:
        :return:
        """
        param_dict = eval('dict(' + params + ')')
        param_dict = SortedDict(param_dict)
        return param_dict


class SimilarityIndex(SimpleModel, BinaryStoredMixin):
    dm = models.ForeignKey(DataMatrix, on_delete=models.CASCADE)
    ord = models.ForeignKey(Ordination, on_delete=models.CASCADE, null=True, blank=True)
    task = models.ForeignKey(Task, on_delete=models.SET_NULL, null=True, blank=True)

    def _get_path(self, ext):
        return os.path.join(settings.MEDIA_URL, 'similarity', str(self.id), '{}.{}'.format(self.id, ext))[1:]

    def __str__(self):
        if self.ord:
            return self.ord.get_name()
        return self.dm.name


class TensorData(SimpleModel):
    name = models.CharField(max_length=255, unique=True)
    created = models.DateTimeField(auto_now_add=True)
    database = models.ForeignKey(Database, on_delete=models.CASCADE)
    features_hash = models.CharField(max_length=255)
    aggregations_hash = models.CharField(max_length=255)

    class Meta:
        abstract = True


class FullTensorData(TensorData, BinaryStoredMixin):
    def _get_path(self, ext):
        return os.path.join(settings.MEDIA_URL, 'oss_data', self.name, '{}.{}'.format(self.name, ext))[1:]

    def get_cols_path(self):
        return self._get_path('cols')


class DerivedTensorData(TensorData):
    full_tensor = models.ForeignKey(FullTensorData, on_delete=models.CASCADE, null=True, blank=True)
    dimreduce = models.CharField(max_length=255)
    ndims = models.IntegerField(null=True, blank=True)
    annotator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='annotator')
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='creator')

    def get_config_path(self):
        return os.path.join(settings.MEDIA_URL, 'oss_data', self.full_tensor.name, '{}.json'.format(self.name))[1:]

    def get_bytes_path(self):
        return os.path.join(settings.MEDIA_URL, 'oss_data', self.full_tensor.name, '{}.bytes'.format(self.name))[1:]


class Preference(SimpleModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    key = models.CharField(max_length=255)
    value = models.TextField()

    class Meta:
        unique_together = ['user', 'key']


class InvitationCode(SimpleModel):
    """
    Tie a user to an invitation code for managing purpose
    """

    code = models.CharField(max_length=255, unique=True)
    database = models.ForeignKey(Database, on_delete=models.CASCADE)
    permission = models.IntegerField(choices=DatabasePermission.as_choices())
    expiry = models.DateTimeField()

    def __str__(self):
        return 'Code: {} expiry {}'.format(self.code, self.expiry)


class MergingInfo(SimpleModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateTimeField(auto_now_add=True)
    info = models.TextField()


@receiver(post_delete, sender=HistoryEntry)
def _history_delete(sender, instance, **kwargs):
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


@receiver(post_delete)
def _mymodel_delete(sender, instance, **kwargs):
    """
    When a PicklePersistedModel is deleted, also delete its pickle file
    :param sender:
    :param instance:
    :param kwargs:
    :return:
    """
    if isinstance(instance, PicklePersistedModel):
        filepath = pickle_path(instance.id, instance.__class__.__name__)
        print('Delete {}'.format(filepath))
        if os.path.isfile(filepath):
            os.remove(filepath)
        else:
            warning('File {} doesnot exist.'.format(filepath))


def set_editable_for_real_db(extras):
    database_id = extras.get('database', None)
    tmpdb_id = extras.get('tmpdb', None)
    user = extras['user']

    if database_id:
        permission = Database.objects.get(id=database_id).get_assigned_permission(user)
    elif tmpdb_id:
        permission = TemporaryDatabase.objects.get(id=tmpdb_id).get_assigned_permission(user)
    else:
        raise CustomAssertionError('database or tmpdb is required')

    return permission >= DatabasePermission.ANNOTATE
