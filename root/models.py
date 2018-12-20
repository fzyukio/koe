import datetime
import string

import six
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db import utils
from django.db.models import Case
from django.db.models import When
from django.db.models.base import ModelBase
from django.db.models.query import QuerySet
from django_bulk_update.helper import bulk_update

__all__ = ['enum', 'MagicChoices', 'ValueTypes', 'ExtraAttr', "ExtraAttrValue", 'AutoSetterGetterMixin',
           'ColumnActionValue', 'User', 'SimpleModel', 'SimpleModel', 'SimpleModel', 'InvitationCode',
           'value_setter', 'value_getter', 'get_bulk_id', 'has_field']


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
        URL: 'Url',
        SEQUENCE: 'Sequence',
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
        URL: 'Url',
        SEQUENCE: 'Sequence',
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
        URL: 'String',
        SEQUENCE: 'String',
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
        URL: True,
        SEQUENCE: True,
    }

    _COPYABLE = {
        SHORT_TEXT: True,
        LONG_TEXT: True,
        DATE: True,
        INTEGER: True,
        FLOAT: True,
        BOOLEAN: False,
        BASE64_PNG: False,
        IMAGE: False,
        URL: True,
        SEQUENCE: False,
    }

    _EXPORTABLE = {
        SHORT_TEXT: True,
        LONG_TEXT: True,
        DATE: True,
        INTEGER: True,
        FLOAT: True,
        BOOLEAN: True,
        BASE64_PNG: False,
        IMAGE: False,
        URL: True,
        SEQUENCE: True,
    }

    _IMPORTABLE = {
        SHORT_TEXT: True,
        LONG_TEXT: True,
        DATE: True,
        INTEGER: True,
        FLOAT: True,
        BOOLEAN: True,
        BASE64_PNG: False,
        IMAGE: False,
        URL: False,
        SEQUENCE: False,
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
        SEQUENCE: [SEQUENCE]
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
    ValueTypes.DATE: lambda s: datetime.datetime.utcfromtimestamp(int(s)).strftime(settings.DATE_INPUT_FORMAT)
}

value_setter = {
    ValueTypes.SHORT_TEXT: lambda v: v,
    ValueTypes.LONG_TEXT: lambda v: v,
    ValueTypes.INTEGER: lambda v: str(v),
    ValueTypes.FLOAT: lambda v: str(v),
    ValueTypes.BOOLEAN: lambda v: str(v),
    ValueTypes.DATE: lambda v: str(utils.datetime2timestamp(v, settings.DATE_INPUT_FORMAT)),
}


class ExtraAttr(models.Model):
    """
    These are the user editable fields that usually can be direct properties of an object model
    However to support multi-user and custom fields, fields like this is detached from the object
    """

    klass = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    type = models.IntegerField(choices=ValueTypes.as_choices())

    class Meta:
        """
        One class can't have two properties with the same name
        """

        unique_together = ('klass', 'name')

    def __str__(self):
        return '{}\'s {} type {}'.format(self.klass, self.name, self.get_type_display())


class ExtraAttrValue(models.Model):
    """
    This model stores the value of the aforementioned ExtraAttr model.
    """

    user = models.ForeignKey('User', on_delete=models.CASCADE)
    owner_id = models.IntegerField()
    attr = models.ForeignKey(ExtraAttr, on_delete=models.CASCADE)
    value = models.TextField()

    class Meta:
        """
        One user can't set two different value to the same attribute of the same object
        """

        unique_together = ('user', 'owner_id', 'attr')

    def __str__(self):
        return '{}\'s {} = {}'.format(self.owner_id, self.attr.name, self.value)


def get_bulk_attrs(objs, attr):
    """
    Return values of an attribute for all objects
    :param objs: an array or QuerySet of objects
    :param attr: name of the attr
    :return: A dict of format {id -> value}
    """
    if isinstance(objs, QuerySet):
        id_2_attr = objs.values_list('id', attr)
        return {x: y for x, y in id_2_attr}
    return {obj.id: getattr(obj, attr) for obj in objs}


def get_bulk_id(objs):
    """
    Similar to get_bulk_attrs but faster for ID
    :param objs: an array or QuerySet of objects
    :return: an array of IDs in the same order
    """
    if isinstance(objs, QuerySet):
        return objs.values_list('id', flat=True)
    return [obj.id for obj in objs]


class AutoSetterGetterMixin:
    @classmethod
    def _get_(cls, objs, attr):
        """
        A shortcut to get_bulk_attrs that can be called on any Model that inherit AutoSetterGetterMixin
        :param objs: an array or QuerySet of objects
        :param attr: name of the attr
        :return: A dict of format {id -> value}
        """
        return get_bulk_attrs(objs, attr)

    @classmethod
    def _set_(cls, objs, attr, value):
        """
        A shortcut to set multiple value to an attribute of multiple objects
        :param objs: an array or QuerySet of objects
        :param attr: name of the attr
        :param value: value to set
        :return:
        """
        if not isinstance(objs, QuerySet):
            ids = [x.id for x in objs]
            preserved = Case(*[When(id=id, then=pos) for pos, id in enumerate(ids)])
            objs = objs[0].__class__.objects.filter(id__in=ids).order_by(preserved)

        if isinstance(value, list):
            for obj, val in zip(objs, value):
                setattr(obj, attr, val)
            bulk_update(objs, update_fields=[attr], batch_size=10000)
        else:
            objs.update(**{attr: value})

    @classmethod
    def _get_extra_(cls, objs, attr, extras):
        """
        A generic getter for any ExtraAttr value, applied on multiple objects at once
        :param objs: an array or QuerySet of objects
        :param attr: name of the extra_attr
        :param extras: must contain the user that is associated with these ExtraAttr
        :return: A dict of format {id -> value}
        """
        user = extras.user

        if isinstance(objs, QuerySet):
            objids = list(objs.values_list('id', flat=True))
        else:
            objids = {obj.id: None for obj in objs}

        retval = {objid: None for objid in objids}

        extra_attr = ExtraAttr.objects.get(klass=cls.__name__, name=attr)
        str2val = value_getter[extra_attr.type]

        values = ExtraAttrValue.objects\
            .filter(user=user, owner_id__in=objids, attr__name=attr).values_list('owner_id', 'value')

        for owner_id, value in values:
            retval[owner_id] = str2val(value)

        return retval

    @classmethod
    def _set_extra_(cls, objs, attr, value, extras):
        """
        A generic setter for any ExtraAttr value, applied on multiple objects at once
        :param objs: an array or QuerySet of objects
        :param attr: name of the attr
        :param extras: must contain the user that is associated with these ExtraAttr
        :return: None
        """
        user = extras.user

        if isinstance(objs, QuerySet):
            ids = frozenset(objs.values_list('id', flat=True))
        else:
            ids = frozenset([obj.id for obj in objs])

        extra_attr = ExtraAttr.objects.get(klass=cls.__name__, name=attr)
        val2str = value_setter[extra_attr.type]
        value = val2str(value)

        existings = ExtraAttrValue.objects.filter(user=user, owner_id__in=ids, attr=extra_attr)
        existings_owner_ids = frozenset(existings.values_list('owner_id', flat=True))
        nonexistings_owner_ids = frozenset([x for x in ids if x not in existings_owner_ids])

        existings.update(value=value)
        newly_created = [ExtraAttrValue(user=user, owner_id=id, attr=extra_attr, value=value)
                         for id in nonexistings_owner_ids]

        ExtraAttrValue.objects.bulk_create(newly_created)

    @classmethod
    def get_FIELD(cls, attr):
        """
        Generate a lambda to call _get_ for one particular attr
        :param attr: name of the attr
        :return: a lambda function that return same results as _get_
        """
        return lambda objs, extras: cls._get_(objs, attr)

    @classmethod
    def set_FIELD(cls, attr):
        """
        Generate a lambda to call _set_ for one particular attr
        :param attr: name of the attr
        :return: a lambda function that return same results as _set_
        """
        return lambda objs, value, extras: cls._set_(objs, attr, value)

    @classmethod
    def get_EXTRA_FIELD(cls, attr):
        """
        Generate a lambda to call _get_extra_ for one particular attr
        :param attr: name of the attr
        :return: a lambda function that return same results as _get_extra_
        """
        return lambda objs, extras: cls._get_extra_(objs, attr, extras)

    @classmethod
    def set_EXTRA_FIELD(cls, attr):
        """
        Generate a lambda to call _set_extra_ for one particular attr
        :param attr: name of the attr
        :return: a lambda function that return same results as _set_extra_
        """
        return lambda objs, value, extras: cls._set_extra_(objs, attr, value, extras)


class SimpleModel(models.Model, AutoSetterGetterMixin):
    """
    An ID Safe Model has ID that cannot be guessed. The ID is small enough to be efficient to send in bulk over the
    wire, but safe enough to prevent injection of any kind.
    """

    id = models.AutoField(primary_key=True, editable=False, auto_created=True, max_length=255)

    class Meta:
        abstract = True


class InvitationCode(SimpleModel):
    """
    Tie a user to an invitation code for managing purpose
    """

    code = models.CharField(max_length=255, unique=True)
    expiry = models.DateTimeField()

    def __str__(self):
        return 'Code: {} expiry {}'.format(self.code, self.expiry)


class User(AbstractUser, SimpleModel):
    """
    A simple User model that uses safe ID
    """

    id = models.AutoField(primary_key=True, editable=False, auto_created=True)
    invitation_code = models.ForeignKey(InvitationCode, on_delete=models.SET_NULL, null=True, blank=True)


class ColumnActionValue(SimpleModel):
    """
    To store values of the columns such as width, position, ...
    So that each user after logging in will see the same grid setting they made before
    Each value is user specific
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    table = models.CharField(max_length=255)
    column = models.CharField(max_length=255)
    action = models.CharField(max_length=255)
    value = models.TextField()

    def __str__(self):
        return '{} {} of column "{}" on table "{}" to {}' \
            .format(self.user, self.action, self.column, self.table, self.value)


def has_field(klass, field):
    """
    Check if field exists in model
    :param klass:
    :param field:
    :return:
    """
    if isinstance(klass, ModelBase):
        fields = [x.name for x in klass._meta.fields]
        return field in fields
    return False


def get_field(klass, name):
    """
    Get the field object given name
    :param klass:
    :param field:
    :return: None if name is not a valid field
    """
    if isinstance(klass, ModelBase):
        fields = {x.name: x for x in klass._meta.fields}
        return fields.get(name, None)
    return None
