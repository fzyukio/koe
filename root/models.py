import datetime
import string
import uuid

import six
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db import utils
from django.db.models.functions import Cast
from django.db.models.query import QuerySet


def enum(*sequential, **named):
    original_enums = dict(zip(sequential, range(len(sequential))), **named)
    enums = dict((key, value) for key, value in original_enums.items())
    reverse = dict((value, key) for key, value in original_enums.items())
    enums['reverse'] = reverse
    enums['values'] = [value for key, value in original_enums.items()]
    enums['keys'] = [key for key, value in original_enums.items()]
    return type('Enum', (), enums)


class MagicChoices(object):
    """
    Base class for `automatic' Django enum classes,
    extended to support ordering and custom value strings

    Ordering:  `_ORDER' = [value list, ...]
    Strings:   `_STRINGS' = {value: string, ...}
    """

    @classmethod
    def get_name(cls, value):
        for k, v in cls.__dict__.items():
            if not k.startswith('_') and v == value:
                return cls.convert_enum_string(k)
        raise KeyError('no matching key for value: ' + value)

    @classmethod
    def get_associated_value(cls, value, association):
        association_name = '_{}'.format(association.upper())
        associated_values = getattr(cls, association_name, None)
        if associated_values:
            return associated_values[value]
        else:
            return cls.get_name(value)

    @classmethod
    def get_key_val_pairs(cls):
        return {k: v for k, v in cls.__dict__.items() if not k.startswith('_')}

    @classmethod
    def get_aliases(cls):
        return getattr(cls, '_ALIASES', None)

    @staticmethod
    def convert_enum_string(s):
        return string.capwords(s.replace('_', ' '), ' ')

    @classmethod
    def reverse_items(cls):
        return {v: k for k, v in cls.__dict__.items()
                if not k.startswith('_')}

    @classmethod
    def as_choices(cls):
        if hasattr(cls, '_ORDER'):
            _reverse = cls.reverse_items()
            _items = [(_reverse[v], v) for v in cls._ORDER]
        else:
            iteritems = six.iteritems(cls.__dict__)
            real_choices = [(k, v) for k, v in iteritems if not k.startswith('_')]
            _items = sorted(real_choices, key=lambda x: x[1])

        if hasattr(cls, '_STRINGS'):
            return tuple(
                (v, cls._STRINGS[v]) for k, v in _items
                if not k.startswith('_'))
        else:
            return tuple(
                (v, cls.convert_enum_string(k)) for k, v in _items
                if not k.startswith('_'))


class ValueTypes(MagicChoices):
    SHORT_TEXT = 0
    LONG_TEXT = 1
    DATE = 2
    INTEGER = 3
    FLOAT = 4
    BOOLEAN = 6
    BASE64_PNG = 7
    WAVEFORM = 8
    SEQUENCE = 9
    URL = 10
    IMAGE = 11

    _EDITOR = {
        SHORT_TEXT: 'Text',
        LONG_TEXT: 'LongText',
        DATE: 'Date',
        INTEGER: 'Integer',
        FLOAT: 'Float',
        BOOLEAN: 'Checkbox',
        BASE64_PNG: 'Base64PNG',
        IMAGE: 'Image',
        URL: 'Url'
    }

    _FORMATTER = {
        SHORT_TEXT: 'Text',
        LONG_TEXT: 'Text',
        DATE: 'Date',
        INTEGER: 'Integer',
        FLOAT: 'DecimalPoint',
        BOOLEAN: 'Checkmark',
        BASE64_PNG: 'Base64PNG',
        IMAGE: 'Image',
        URL: 'Url'
    }

    _FILTER_TYPE = {
        SHORT_TEXT: 'String',
        LONG_TEXT: 'String',
        DATE: None,
        INTEGER: 'Number',
        FLOAT: 'Number',
        BOOLEAN: 'Boolean',
        BASE64_PNG: None,
        IMAGE: None,
        URL: 'String'
    }

    _SORTABLE = {
        SHORT_TEXT: True,
        LONG_TEXT: False,
        DATE: True,
        INTEGER: True,
        FLOAT: True,
        BOOLEAN: True,
        BASE64_PNG: False,
        IMAGE: False,
        URL: True
    }

    # This is a dictionary of transformable types, e.g. user is allowed to change property type from
    # SHORT_TEXT to LONG_TEXT (or to itself - SHORT_TEXT) but not any other type.
    # BOOL can become FLOAT or INTEGER because boolean is just 1 or 0, but nothing can go to boolean because that
    # doesn't make any sense
    # DATE and IMAGE cannot become anything else
    _ALIASES = {
        SHORT_TEXT: [LONG_TEXT, SHORT_TEXT],
        LONG_TEXT: [SHORT_TEXT, LONG_TEXT],
        INTEGER: [INTEGER, FLOAT],
        FLOAT: [INTEGER, FLOAT],
        BOOLEAN: [BOOLEAN, INTEGER, FLOAT],
        DATE: [DATE],
    }

    @classmethod
    def _get_filter_type(cls, value):
        return ValueTypes._FILTER_TYPE[value]


value_getter = {
    ValueTypes.SHORT_TEXT: lambda s: s,
    ValueTypes.LONG_TEXT: lambda s: s,
    ValueTypes.INTEGER: lambda s: int(s),
    ValueTypes.FLOAT: lambda s: float(s),
    ValueTypes.BOOLEAN: lambda s: bool(s),
    ValueTypes.DATE: lambda s: datetime.datetime.utcfromtimestamp(int(s)).strftime('%Y-%m-%d')
}

value_setter = {
    ValueTypes.SHORT_TEXT: lambda v: v,
    ValueTypes.LONG_TEXT: lambda v: v,
    ValueTypes.INTEGER: lambda v: str(v),
    ValueTypes.FLOAT: lambda v: str(v),
    ValueTypes.BOOLEAN: lambda v: str(v),
    ValueTypes.DATE: lambda v: str(utils.datetime2timestamp(v, '%Y-%m-%d')),
}


class ExtraAttr(models.Model):
    klass = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    type = models.IntegerField(choices=ValueTypes.as_choices())

    class Meta:
        unique_together = ('klass', 'name')

    def __str__(self):
        return '{}\'s {} type {}'.format(self.klass, self.name, self.get_type_display())


class ExtraAttrValue(models.Model):
    user = models.ForeignKey('User', on_delete=models.CASCADE)
    owner_id = models.CharField(max_length=255)
    attr = models.ForeignKey(ExtraAttr, on_delete=models.CASCADE)
    value = models.TextField()

    class Meta:
        unique_together = ('user', 'owner_id', 'attr')

    def __str__(self):
        return '{}\'s {} = {}'.format(self.owner_id, self.attr.name, self.value)


def get_bulk_attrs(objs, attr):
    if isinstance(objs, QuerySet):
        id_2_attr = objs.values_list('id', attr)
        return {x: y for x, y in id_2_attr}
    return {obj.id: getattr(obj, attr) for obj in objs}


def get_bulk_id(objs):
    if isinstance(objs, QuerySet):
        return objs.values_list('id', flat=True)
    return [obj.id for obj in objs]


class AutoSetterGetterMixin:
    @classmethod
    def _get_(cls, objs, attr):
        return get_bulk_attrs(objs, attr)

    @classmethod
    def _set_(cls, objs, attr, value):
        for obj in objs:
            setattr(obj, attr, value)
            obj.save()

    @classmethod
    def _get_extra_(cls, objs, attr, extras):
        user = extras['user']

        retval = {obj.id: None for obj in objs}
        objids = list(retval.keys())

        extra_attr = ExtraAttr.objects.get(klass=cls.__name__, name=attr)
        str2val = value_getter[extra_attr.type]

        values = ExtraAttrValue.objects \
            .filter(user=user, owner_id__in=objids, attr__name=attr).values_list('owner_id', 'value')
        for owner_id, value in values:
            retval[owner_id] = str2val(value)
        return retval

    @classmethod
    def _set_extra_(cls, objs, attr, value, extras):
        user = extras['user']

        if isinstance(objs, QuerySet):
            ids = objs.annotate(strid=Cast('id', models.CharField())).values_list('strid', flat=True)
        else:
            ids = [str(obj.id) for obj in objs]

        extra_attr = ExtraAttr.objects.get(klass=cls.__name__, name=attr)
        val2str = value_setter[extra_attr.type]
        value = val2str(value)

        existings = ExtraAttrValue.objects.filter(user=user, owner_id__in=ids, attr=extra_attr)
        existings_owner_ids = existings.values_list('owner_id', flat=True)
        nonexistings_owner_ids = [x for x in ids if x not in existings_owner_ids]

        existings.update(value=value)
        newly_created = [ExtraAttrValue(user=user, owner_id=id, attr=extra_attr, value=value)
                         for id in nonexistings_owner_ids]

        ExtraAttrValue.objects.bulk_create(newly_created)

    @classmethod
    def get_FIELD(cls, attr):
        return lambda objs, extras: cls._get_(objs, attr)

    @classmethod
    def set_FIELD(cls, attr):
        return lambda objs, value, extras: cls._set_(objs, attr, value)

    @classmethod
    def get_EXTRA_FIELD(cls, attr):
        return lambda objs, extras: cls._get_extra_(objs, attr, extras)

    @classmethod
    def set_EXTRA_FIELD(cls, attr):
        return lambda objs, value, extras: cls._set_extra_(objs, attr, value, extras)


def id_generator(klass):
    uuid_prefix = uuid.uuid4().hex[:2]
    last_obj = klass.objects.all().extra(select={'idint': "CAST(SUBSTR(id, 3) AS UNSIGNED)"}).order_by('idint').last()
    if not last_obj:
        last_id = 0
    else:
        last_id = last_obj.idint
    return '{}{}'.format(uuid_prefix, last_id + 1)


class IdSafeModel(models.Model):
    id = models.CharField(primary_key=True, editable=False, auto_created=False, max_length=255)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self.id:
            self.id = id_generator(self.__class__)
        super(IdSafeModel, self).save(*args, **kwargs)


class StandardModel(IdSafeModel, AutoSetterGetterMixin):
    class Meta:
        abstract = True


class SimpleModel(models.Model, AutoSetterGetterMixin):
    class Meta:
        abstract = True


class User(AbstractUser, StandardModel):
    def get_avatar(self):
        return "https://api.adorable.io/avatars/200/" + self.email

    def generate_id(self):
        hash_suffix = uuid.uuid4().hex[:4]  # grab 4 random characters
        return '{}-{}'.format(self.username, hash_suffix)


class ColumnActionValue(SimpleModel):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    table = models.CharField(max_length=1024)
    column = models.CharField(max_length=1024)
    action = models.CharField(max_length=1024)
    value = models.TextField()

    def __str__(self):
        return '{} {} of column "{}" on table "{}" to {}'.format(self.user, self.action, self.column, self.table,
                                                                 self.value)
