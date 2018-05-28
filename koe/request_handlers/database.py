import csv
import datetime
import io
import json
import os
from django.conf import settings
from shutil import copyfile

from django.db import transaction, IntegrityError
from django.db.models import Count
from dotmap import DotMap

from koe.grid_getters import bulk_get_segments_for_audio
from koe.model_utils import extract_spectrogram, assert_permission, \
    get_or_error
from koe.models import AudioFile, Segment, Database, DatabaseAssignment, \
    DatabasePermission, Individual, Species, AudioTrack, AccessRequest
from root.exceptions import CustomAssertionError
from root.models import ExtraAttrValue, ExtraAttr, User
from root.utils import spect_fft_path, \
    spect_mask_path

__all__ = ['create_database', 'import_audio_metadata', 'delete_audio_files', 'save_segmentation', 'get_label_options',
           'request_database_access', 'approve_database_access', 'copy_audio_files', 'delete_segments']


def import_audio_metadata(request):
    """
    Store uploaded files (csv only)
    :param request: must contain a list of files and the id of the database to be stored against
    :return:
    """
    user = request.user

    file = get_or_error(request.FILES, 'file')
    database_id = get_or_error(request.POST, 'database')
    database = get_or_error(Database, dict(id=database_id))
    assert_permission(user, database, DatabasePermission.ADD_FILES)

    file_data = file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(file_data))

    supplied_fields = reader.fieldnames
    required_fields = ['filename', 'genus', 'species', 'quality', 'date', 'individual', 'gender', 'track']
    missing_fields = [x for x in required_fields if x not in supplied_fields]

    if missing_fields:
        raise CustomAssertionError(
            'Field(s) {} are required but not found in your CSV file'.format(','.join(missing_fields)))

    filename_to_metadata = {}

    existing_individuals = {(x.name, x.species.genus, x.species.species): x for x in Individual.objects.all()
                            if x.species is not None}
    existing_species = {(x.genus, x.species): x for x in Species.objects.all()}
    existing_tracks = {x.name: x for x in AudioTrack.objects.all()}

    for row in reader:
        filename = row['filename']
        species_code = row['species']
        genus = row['genus']
        quality = row['quality']
        individual_name = row['individual']
        gender = row['gender']
        date_str = row['date']
        track_name = row['track']
        date = None
        if date_str:
            date = datetime.datetime.strptime(date_str, settings.DATE_INPUT_FORMAT).date()

        species_key = (genus, species_code)
        if species_key in existing_species:
            species = existing_species[species_key]
        else:
            species = Species(genus=genus, species=species_code)
            species.save()
            existing_species[species_key] = species

        individual_key = (individual_name, genus, species_code)
        if individual_key in existing_individuals:
            individual = existing_individuals[individual_key]
        else:
            individual = existing_individuals.get(individual_key, None)
            if individual is None:
                individual = Individual(name=individual_name, gender=gender, species=species)
                individual.save()
                existing_individuals[individual_key] = individual

        if track_name in existing_tracks:
            track = existing_tracks[track_name]
        else:
            track = AudioTrack(name=track_name, date=date)
            track.save()
            existing_tracks[track_name] = track

        filename_to_metadata[filename] = (individual, quality, track)

    existing_audio_files = AudioFile.objects.filter(name__in=filename_to_metadata.keys(), database=database)

    with transaction.atomic():
        for audio_file in existing_audio_files:
            individual, quality, track = filename_to_metadata[audio_file.name]
            audio_file.individual = individual
            audio_file.quality = quality
            audio_file.track = track
            audio_file.save()

    return True


def delete_audio_files(request):
    """
    Delete audio files given ids. Also remove all existing audio files.
    :param request: must contain a list of ids and the id of the database where these files come from
    :return:
    """
    user = request.user
    ids = json.loads(get_or_error(request.POST, 'ids'))
    database_id = get_or_error(request.POST, 'database')
    database = get_or_error(Database, dict(id=database_id))
    assert_permission(user, database, DatabasePermission.DELETE_FILES)

    # Check that the ids to delete actually come from this database
    audio_files = AudioFile.objects.filter(id__in=ids)
    audio_files_ids = audio_files.values_list('id', flat=True)

    non_existent_ids = [x for x in ids if x not in audio_files_ids]

    if non_existent_ids:
        raise CustomAssertionError('You\'re trying to delete files that don\'t belong to database {}. '
                                   'Are you messing with Javascript?'.format(database.name))

    associated_segments_ids = Segment.objects.filter(audio_file__in=audio_files_ids)\
        .values_list('id', flat=True)

    for segment_id in associated_segments_ids:
        seg_spect_path = spect_fft_path(segment_id, 'syllable')
        if os.path.isfile(seg_spect_path):
            os.remove(seg_spect_path)

        seg_mask_path = spect_mask_path(segment_id)
        if os.path.isfile(seg_mask_path):
            os.remove(seg_mask_path)

    ExtraAttrValue.objects.filter(attr__klass=Segment.__name__, owner_id__in=associated_segments_ids).delete()

    ExtraAttrValue.objects.filter(attr__klass=AudioFile.__name__, owner_id__in=audio_files_ids).delete()
    audio_files.delete()
    return True


def create_database(request):
    user = request.user
    name = get_or_error(request.POST, 'name')
    if name == '':
        raise CustomAssertionError('Please provide a proper name.')

    if Database.objects.filter(name=name).exists():
        raise CustomAssertionError('Database with name {} already exists.'.format(name))

    database = Database(name=name)
    database.save()

    # Now assign this database to this user, and switch the working database to this new one
    DatabaseAssignment(user=user, database=database, permission=DatabasePermission.ASSIGN_USER).save()

    extra_attr = ExtraAttr.objects.get(klass=User.__name__, name='current-database')
    extra_attr_value, _ = ExtraAttrValue.objects.get_or_create(user=user, attr=extra_attr, owner_id=user.id)
    extra_attr_value.value = database.id
    extra_attr_value.save()

    return True


def save_segmentation(request):
    """
    Save the segmentation scheme sent from the client. Compare with the existing segmentation, there are three cases:
    1. segments that currently exist but not found in the client's scheme - they need to be deleted
    2. segments that currently exist and found in the client's scheme - they need to be updated
    3. segments that doesn't currently exist but found in the client's scheme - they need to be created

    Finally, create or update the spectrogram image (not the mask - can't do anything about the mask)
    :param request:
    :return:
    """
    user = request.user
    items = json.loads(get_or_error(request.POST, 'items'))
    file_id = int(get_or_error(request.POST, 'file-id'))
    audio_file = get_or_error(AudioFile, dict(id=file_id))
    assert_permission(user, audio_file.database, DatabasePermission.MODIFY_SEGMENTS)
    segments = Segment.objects.filter(audio_file=audio_file)

    new_segments = []
    old_segments = []
    for item in items:
        id = item['id']
        if isinstance(id, str) and id.startswith('new:'):
            segment = Segment(audio_file=audio_file, start_time_ms=item['start'], end_time_ms=item['end'])
            label = item.get('label', None)
            family = item.get('label_family', None)
            subfamily = item.get('label_subfamily', None)

            new_segments.append((segment, label, family, subfamily))
        else:
            old_segments.append(item)

    id_to_exiting_item = {x['id']: x for x in old_segments}

    to_update = []
    to_delete = []

    for segment in segments:
        id = segment.id
        if id in id_to_exiting_item:
            item = id_to_exiting_item[id]
            segment.start_time_ms = item['start']
            segment.end_time_ms = item['end']

            to_update.append(segment)
        else:
            to_delete.append(segment)

    to_delete_segment_ids = []
    for segment in to_delete:
        segment_id = segment.id
        to_delete_segment_ids.append(segment_id)
        seg_spect_path = spect_fft_path(segment_id, 'syllable')
        if os.path.isfile(seg_spect_path):
            os.remove(seg_spect_path)

    ExtraAttrValue.objects.filter(attr__klass=Segment.__name__, owner_id__in=to_delete_segment_ids).delete()
    label_attr = ExtraAttr.objects.get(klass=Segment.__name__, name='label')
    family_attr = ExtraAttr.objects.get(klass=Segment.__name__, name='label_family')
    subfamily_attr = ExtraAttr.objects.get(klass=Segment.__name__, name='label_subfamily')

    with transaction.atomic():
        for segment in to_update:
            segment.save()
        for segment in to_delete:
            segment.delete()

        for segment, label, family, subfamily in new_segments:
            segment.save()
            if label:
                ExtraAttrValue.objects.create(user=user, attr=label_attr, owner_id=segment.id, value=label)
            if family:
                ExtraAttrValue.objects.create(user=user, attr=family_attr, owner_id=segment.id, value=family)
            if subfamily:
                ExtraAttrValue.objects.create(user=user, attr=subfamily_attr, owner_id=segment.id, value=subfamily)

    extract_spectrogram(audio_file)

    segments = Segment.objects.filter(audio_file=audio_file)
    _, rows = bulk_get_segments_for_audio(segments, DotMap(file_id=file_id, user=user))
    return rows


def request_database_access(request):
    user = request.user

    database_id = get_or_error(request.POST, 'database-id')
    database = get_or_error(Database, dict(id=database_id))

    requested_permission = DatabasePermission.ANNOTATE
    already_granted = DatabaseAssignment.objects \
        .filter(user=user, database=database, permission__gte=requested_permission).exists()

    if already_granted:
        raise CustomAssertionError('You\'re already granted equal or greater permission.')

    access_request = AccessRequest.objects.filter(user=user, database=database).first()
    if access_request and access_request.permission >= requested_permission:
        raise CustomAssertionError('You\'ve already requested equal or greater permission.')

    if access_request is None:
        access_request = AccessRequest(user=user, database=database)

    access_request.permission = requested_permission
    access_request.save()
    return True


def approve_database_access(request):
    you = request.user

    request_id = get_or_error(request.POST, 'request-id')
    access_request = get_or_error(AccessRequest, dict(id=request_id))

    person_asking_for_access = access_request.user
    permission_to_grant = access_request.permission
    database = access_request.database

    assert_permission(you, database, DatabasePermission.ASSIGN_USER)

    database_assignment = DatabaseAssignment.objects.filter(user=person_asking_for_access, database=database).first()

    if database_assignment and database_assignment.permission >= permission_to_grant:
        access_request.resolved = True
        access_request.save()
        raise CustomAssertionError('User\'s already granted equal or greater permission.')

    if database_assignment is None:
        database_assignment = DatabaseAssignment(user=person_asking_for_access, database=database)

    with transaction.atomic():
        database_assignment.permission = permission_to_grant
        database_assignment.save()
        access_request.resolved = True
        access_request.save()

    return True


def copy_audio_files(request):
    """
    Copy files from the source database to the target database, not copying the actual files, but everything database-
    wise is copied, so the copies don't affect the original.
    :param request:
    :return:
    """
    user = request.user
    ids = json.loads(get_or_error(request.POST, 'ids'))
    target_database_name = get_or_error(request.POST, 'target-database-name')
    source_database_id = get_or_error(request.POST, 'source-database-id')
    target_database = get_or_error(Database, dict(name=target_database_name))
    source_database = get_or_error(Database, dict(id=source_database_id))
    assert_permission(user, source_database, DatabasePermission.COPY_FILES)
    assert_permission(user, target_database, DatabasePermission.ADD_FILES)

    # Make sure all those IDs belong to the source database
    source_audio_files = AudioFile.objects.filter(id__in=ids, database=source_database)
    if len(source_audio_files) != len(ids):
        raise CustomAssertionError(
            'There\'s a mismatch between the song IDs you provided and the actual songs in the database')

    song_values = source_audio_files \
        .values_list('id', 'fs', 'length', 'name', 'track', 'individual', 'quality', 'original')
    old_song_id_to_name = {x[0]: x[3] for x in song_values}
    old_song_names = old_song_id_to_name.values()
    old_song_ids = old_song_id_to_name.keys()

    # Make sure there is no duplication:
    duplicate_audio_files = AudioFile.objects.filter(database=target_database, name__in=old_song_names)
    if duplicate_audio_files:
        raise CustomAssertionError(
            'Some file(s) you\'re trying to copy already exist in {}'.format(target_database_name))

    # We need to map old and new IDs of AudioFiles so that we can copy their ExtraAttrValue later
    songs_old_id_to_new_id = {}

    # Create Song objects one by one because they can't be bulk created
    for old_id, fs, length, name, track, individual, quality, original in song_values:
        # Make sure that we always point to the true original. E.g if AudioFile #2 is a copy of #1 and someone makes
        # a copy of AudioFile #2, the new AudioFile must still reference #1 as its original

        original_id = old_id if original is None else original

        audio_file = AudioFile.objects.create(fs=fs, length=length, name=name, track_id=track, individual_id=individual,
                                              quality=quality, original_id=original_id, database=target_database)

        songs_old_id_to_new_id[old_id] = audio_file.id

    segments = Segment.objects.filter(audio_file__in=songs_old_id_to_new_id.keys())
    segments_values = segments.values_list('id', 'start_time_ms', 'end_time_ms', 'mean_ff', 'min_ff', 'max_ff',
                                           'audio_file__name', 'audio_file__id')

    # We need this to map old and new IDs of Segments so that we can copy their ExtraAttrValue later
    # The only reliable way to map new to old Segments is through the pair (start_time_ms, end_time_ms, song_name)
    # since they are guaranteed to be unique
    segments_old_id_to_start_end = {x[0]: (x[1], x[2], x[6]) for x in segments_values}

    new_segments_info = {}
    for seg_id, start, end, mean_ff, min_ff, max_ff, song_name, song_old_id in segments_values:
        segment_info = (seg_id, start, end, mean_ff, min_ff, max_ff)
        if song_old_id not in new_segments_info:
            new_segments_info[song_old_id] = [segment_info]
        else:
            new_segments_info[song_old_id].append(segment_info)

    segments_to_copy = []
    for song_old_id, segment_info in new_segments_info.items():
        for seg_id, start, end, mean_ff, min_ff, max_ff in segment_info:
            song_new_id = songs_old_id_to_new_id[song_old_id]

            segment = Segment(start_time_ms=start, end_time_ms=end, mean_ff=mean_ff, min_ff=min_ff, max_ff=max_ff,
                              audio_file_id=song_new_id)
            segments_to_copy.append(segment)

    Segment.objects.bulk_create(segments_to_copy)

    copied_segments = Segment.objects.filter(audio_file__in=songs_old_id_to_new_id.values())
    copied_segments_values = copied_segments.values_list('id', 'start_time_ms', 'end_time_ms', 'audio_file__name')
    segments_new_start_end_to_new_id = {(x[1], x[2], x[3]): x[0] for x in copied_segments_values}

    # Based on two maps: from new segment (start,end) key to their ID and old segment's ID to (start,end) key
    # we can now map Segment new IDs -> old IDs
    segments_old_id_to_new_id = {}
    for old_segment_id, segment_start_end in segments_old_id_to_start_end.items():
        new_segment_id = segments_new_start_end_to_new_id[segment_start_end]
        old_segment_id = int(old_segment_id)
        new_segment_id = int(new_segment_id)
        segments_old_id_to_new_id[old_segment_id] = new_segment_id

    # Query all ExtraAttrValue of Songs, and make duplicate by replacing old song IDs by new song IDs
    song_attrs = ExtraAttr.objects.filter(klass=AudioFile.__name__)
    old_song_extra_attrs = ExtraAttrValue.objects \
        .filter(owner_id__in=old_song_ids, user=user, attr__in=song_attrs).values_list('owner_id', 'attr', 'value')
    new_song_extra_attrs = []
    for old_song_id, attr_id, value in old_song_extra_attrs:
        new_song_id = songs_old_id_to_new_id[old_song_id]
        new_song_extra_attrs.append(ExtraAttrValue(user=user, attr_id=attr_id, value=value, owner_id=new_song_id))

    old_segment_ids = segments_old_id_to_start_end.keys()

    # Query all ExtraAttrValue of Segments, and make duplicate by replacing old IDs by new IDs
    segment_attrs = ExtraAttr.objects.filter(klass=Segment.__name__)
    old_segment_extra_attrs = ExtraAttrValue.objects \
        .filter(owner_id__in=old_segment_ids, user=user, attr__in=segment_attrs)\
        .values_list('owner_id', 'attr', 'value')
    new_segment_extra_attrs = []
    for old_segment_id, attr_id, value in old_segment_extra_attrs:
        new_segment_id = segments_old_id_to_new_id[int(old_segment_id)]
        new_segment_extra_attrs.append(ExtraAttrValue(user=user, attr_id=attr_id, value=value, owner_id=new_segment_id))

    # Now bulk create
    ExtraAttrValue.objects.filter(owner_id__in=songs_old_id_to_new_id.values(), attr__in=song_attrs).delete()

    try:
        ExtraAttrValue.objects.bulk_create(new_song_extra_attrs)
    except IntegrityError as e:
        raise CustomAssertionError(e)

    ExtraAttrValue.objects.filter(owner_id__in=segments_old_id_to_new_id.values(), attr__in=segment_attrs).delete()

    try:
        ExtraAttrValue.objects.bulk_create(new_segment_extra_attrs)
    except IntegrityError as e:
        raise CustomAssertionError(e)

    for old_segment_id, new_segment_id in segments_old_id_to_new_id.items():
        # Copy spectrograms / signal masks:
        new_mask_img = spect_mask_path(new_segment_id)
        new_spect_img = spect_fft_path(new_segment_id, 'syllable')

        old_mask_img = spect_mask_path(old_segment_id)
        old_spect_img = spect_fft_path(old_segment_id, 'syllable')

        if os.path.isfile(old_mask_img):
            copyfile(old_mask_img, new_mask_img)

        if os.path.isfile(old_spect_img):
            copyfile(old_spect_img, new_spect_img)

    return True


def delete_segments(request):
    user = request.user
    ids = json.loads(get_or_error(request.POST, 'ids'))
    database_id = get_or_error(request.POST, 'database-id')
    database = get_or_error(Database, dict(id=database_id))
    assert_permission(user, database, DatabasePermission.MODIFY_SEGMENTS)

    segments = Segment.objects.filter(id__in=ids, audio_file__database=database)
    ids = segments.values_list('id', flat=True)

    for segment_id in ids:
        seg_spect_path = spect_fft_path(segment_id, 'syllable')
        if os.path.isfile(seg_spect_path):
            os.remove(seg_spect_path)

        seg_mask_path = spect_mask_path(segment_id)
        if os.path.isfile(seg_mask_path):
            os.remove(seg_mask_path)

    ExtraAttrValue.objects.filter(attr__klass=Segment.__name__, owner_id__in=ids).delete()
    segments.delete()
    return True


def get_label_options(request):
    file_id = json.loads(get_or_error(request.POST, 'file-id'))
    audio_file = get_or_error(AudioFile, dict(id=file_id))
    database = audio_file.database
    user = request.user

    assert_permission(user, database, DatabasePermission.VIEW)
    all_segment_ids = list(Segment.objects.filter(audio_file__database=database).values_list('id', flat=True))

    label_attr = ExtraAttr.objects.get(klass=Segment.__name__, name='label')
    family_attr = ExtraAttr.objects.get(klass=Segment.__name__, name='label_family')
    subfamily_attr = ExtraAttr.objects.get(klass=Segment.__name__, name='label_subfamily')

    extra_attr_values = ExtraAttrValue.objects.filter(user=user, owner_id__in=all_segment_ids)
    labels_and_counts = extra_attr_values.filter(attr=label_attr).values_list('value').annotate(c=Count('value'))
    families_and_counts = extra_attr_values.filter(attr=family_attr).values_list('value').annotate(c=Count('value'))
    subfams_and_counts = extra_attr_values.filter(attr=subfamily_attr).values_list('value').annotate(c=Count('value'))

    labels_to_counts = {l: c for l, c in labels_and_counts}
    fams_to_counts = {l: c for l, c in families_and_counts}
    subfams_to_counts = {l: c for l, c in subfams_and_counts}

    retval = {'label': labels_to_counts, 'label_family': fams_to_counts, 'label_subfamily': subfams_to_counts}

    return retval
