import io
import json
import zipfile

from django.core.files import File
from django.db import transaction
from django.utils import timezone

from koe.model_utils import assert_permission, \
    get_or_error
from koe.models import Segment, HistoryEntry, Database, DatabasePermission
from root.exceptions import CustomAssertionError
from root.models import ExtraAttrValue, User
from root.utils import history_path, ensure_parent_folder_exists

__all__ = ['save_history', 'import_history', 'delete_history']


def save_history(request):
    """
    Save a copy of all ExtraAttrValue (labels, notes, ...) in a HistoryEntry
    :param request: must specify a comment to store with this copy
    :return: name of the zip file created
    :version: 2.0.0
    """
    version = 3
    user = request.user

    comment = get_or_error(request.POST, 'comment')
    database_id = get_or_error(request.POST, 'database')
    database = get_or_error(Database, dict(id=database_id))
    assert_permission(user, database, DatabasePermission.VIEW)

    segments_ids = Segment.objects.filter(segmentation__audio_file__database=database, segmentation__source='user') \
        .values_list('id', flat=True)

    extra_attr_values = list(ExtraAttrValue.objects.filter(user=user, owner_id__in=segments_ids)
                             .exclude(attr__klass=User.__name__).values_list('owner_id', 'attr__id', 'value'))

    meta = dict(database=database_id, user=user.id, version=version)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_BZIP2, False) as zip_file:
        zip_file.writestr('meta.json', json.dumps(meta))
        zip_file.writestr('root.extraattrvalue.json', json.dumps(extra_attr_values))

    binary_content = zip_buffer.getvalue()

    he = HistoryEntry.objects.create(user=user, time=timezone.now(), database=database, version=version, note=comment)
    filename = he.filename
    filepath = history_path(filename)
    ensure_parent_folder_exists(filepath)

    with open(filepath, 'wb') as f:
        f.write(binary_content)

    return filename


def delete_history(request):
    """
    Delete a HistoryEntry given its id
    :param request: must specify version-id
    :return:
    """
    version_id = get_or_error(request.POST, 'version-id')
    he = HistoryEntry.objects.get(id=version_id)
    creator = he.user
    if creator != request.user:
        raise CustomAssertionError('Only {} can delete this version'.format(creator.username))

    he.delete()
    return True


def import_history(request):
    """
    Import a HistoryEntry from any user to this user.
    If this operation fails, the database is intact.
    :param request: must specify either : version-id, which is the id of the HistoryEntry object to be imported to
                                          or FILES['zipfile'] which should be created somewhere by Koe for someone
    :return: True if everything goes well.
    """
    version_id = request.POST.get('version-id', None)
    zip_file = request.FILES.get('zipfile', None)
    user = request.user

    if not (version_id or zip_file):
        raise CustomAssertionError('No ID or file provided. Abort.')

    if version_id:
        he = HistoryEntry.objects.get(id=version_id)
        file = open(history_path(he.filename), 'rb')
    else:
        file = File(file=zip_file)

    filelist = {}
    with zipfile.ZipFile(file, "r") as zip_file:
        namelist = zip_file.namelist()
        for name in namelist:
            filelist[name] = zip_file.read(name)

    version = 1
    if 'meta.json' in filelist:
        meta = json.loads(filelist['meta.json'])
        version = meta['version']

    try:
        content = filelist['root.extraattrvalue.json']
    except KeyError:
        raise CustomAssertionError('This is not a Koe history file')
    try:
        new_entries = json.loads(content)
    except Exception:
        raise CustomAssertionError('The history content is malformed and cannot be parsed.')

    extra_attr_values = []
    attrs_to_values = {}
    for entry in new_entries:
        if version == 1:
            owner_id = entry['fields']['owner_id']
            value = entry['fields']['value']
            attr_id = entry['fields']['attr']
        else:
            owner_id, attr_id, value = entry

        if attr_id not in attrs_to_values:
            attrs_to_values[attr_id] = [owner_id]
        else:
            attrs_to_values[attr_id].append(owner_id)

        extra_attr_value = ExtraAttrValue(owner_id=owner_id, value=value, user=user)
        extra_attr_value.attr_id = attr_id
        extra_attr_values.append(extra_attr_value)

    # Wrap all DB modification in one transaction to utilise the roll-back ability when things go wrong
    with transaction.atomic():
        for attr_id, owner_ids in attrs_to_values.items():
            ExtraAttrValue.objects.filter(user=user, owner_id__in=owner_ids, attr__id=attr_id).delete()

    ExtraAttrValue.objects.bulk_create(extra_attr_values)

    return True
