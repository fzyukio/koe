import csv
import datetime
import io
import json
import os
import zipfile

import pydub
from django.conf import settings
from django.utils import timezone
from django.core.files import File
from django.db import transaction
from django.http import HttpResponse
from django.views.generic import TemplateView
from dotmap import DotMap

from koe.grid_getters import _get_sequence_info_empty_songs, bulk_get_segments_for_audio
from koe.model_utils import get_user_databases, extract_spectrogram, get_current_similarity
from koe.models import AudioFile, Segment, HistoryEntry, Segmentation, Database, DatabaseAssignment, \
    DatabasePermission, Individual, Species, AudioTrack, AccessRequest
from root.models import ExtraAttrValue, ExtraAttr, User
from root.utils import history_path, ensure_parent_folder_exists, wav_path, audio_path, spect_fft_path

__all__ = ['get_segment_audio', 'save_history', 'import_history', 'delete_history', 'create_database',
           'import_audio_files', 'import_audio_metadata', 'delete_songs', 'save_segmentation',
           'request_database_access', 'approve_database_access', 'copy_files']


def match_target_amplitude(sound, loudness):
    """
    Set the volume of an AudioSegment object to be a certain loudness
    :param sound: an AudioSegment object
    :param loudness: usually -10db is a good number
    :return: the modified sound
    """
    change_in_dBFS = loudness - sound.dBFS
    if change_in_dBFS > 0:
        return sound.apply_gain(change_in_dBFS)
    return sound


def save_history(request):
    """
    Save a copy of all ExtraAttrValue (labels, notes, ...) in a HistoryEntry
    :param request: must specify a comment to store with this copy
    :return: name of the zip file created
    :version: 2.0.0
    """
    version = 2
    comment = request.POST['comment']
    database_id = request.POST['database']
    user = request.user
    database = Database.objects.filter(id=database_id).first()
    if not database:
        raise ValueError('No such database: {}. Abort.'.format(database_id))
    db_assignment = DatabaseAssignment.objects.filter(user=user, database=database).first()
    if db_assignment is None or not db_assignment.can_view():
        raise PermissionError('You don\'t have permission to view from this database. '
                              'Are you messing with Javascript?')

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

    he = HistoryEntry.objects.create(user=user, time=timezone.now())
    heid = he.id

    ExtraAttrValue.objects.create(owner_id=heid, user=user, value=comment, attr=settings.ATTRS.history.note)
    ExtraAttrValue.objects.create(owner_id=heid, user=user, value=version, attr=settings.ATTRS.history.version)
    ExtraAttrValue.objects.create(owner_id=heid, user=user, value=database_id, attr=settings.ATTRS.history.database)

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
    version_id = request.POST['version-id']
    he = HistoryEntry.objects.get(id=version_id)
    creator = he.user
    if creator != request.user:
        raise Exception('Only {} can delete this version'.format(creator.username))

    he.delete()
    return True


def get_segment_audio(request):
    """
    Return a playable audio segment given the file name and the endpoints (in range [0.0 -> 1.0]) where the segment
    begins and ends
    :param request: must specify segment-id, this is the ID of a Segment object to be played
    :return: a binary blob specified as audio/ogg (or whatever the format is), playable and volume set to -10dB
    """
    segment_id = request.POST.get('segment-id', None)
    file_id = request.POST.get('file-id', None)

    if segment_id is None and file_id is None:
        raise Exception('Need segment or file argument')
    if segment_id is not None and file_id is not None:
        raise Exception('Can\'t have both segment and file arguments')

    if file_id:
        audio_file = AudioFile.objects.filter(pk=file_id).first()
        compressed_url = audio_path(audio_file.name, settings.AUDIO_COMPRESSED_FORMAT)
        if os.path.isfile(compressed_url):
            with open(compressed_url, 'rb') as f:
                binary_content = f.read()
        else:
            wav_url = wav_path(audio_file.name)
            song = pydub.AudioSegment.from_file(wav_url)
            out = io.BytesIO()
            song.export(out, format=settings.AUDIO_COMPRESSED_FORMAT)
            binary_content = out.getvalue()
    else:
        segment = Segment.objects.filter(pk=segment_id).first()
        audio_file = segment.segmentation.audio_file
        start = segment.start_time_ms
        end = segment.end_time_ms

        compressed_url = audio_path(audio_file.name, settings.AUDIO_COMPRESSED_FORMAT)
        if os.path.isfile(compressed_url):
            valid_path = compressed_url
        else:
            valid_path = wav_path(audio_file.name)

        song = pydub.AudioSegment.from_file(valid_path)
        audio_segment = song[start:end]

        out = io.BytesIO()
        audio_segment.export(out, format=settings.AUDIO_COMPRESSED_FORMAT)
        binary_content = out.getvalue()

    response = HttpResponse()
    response.write(binary_content)
    response['Content-Type'] = 'audio/' + settings.AUDIO_COMPRESSED_FORMAT
    response['Content-Length'] = len(binary_content)
    return response


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
        raise ValueError('No ID or file provided. Abort.')

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
        raise ValueError('This is not a Koe history file')
    try:
        new_entries = json.loads(content)
    except Exception:
        raise ValueError('The history content is malformed and cannot be parsed.')

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
        # ExtraAttrValue.objects.filter(user=user).exclude(attr__klass=User.__name__).delete()
        for attr_id, owner_ids in attrs_to_values.items():
            ExtraAttrValue.objects.filter(user=user, owner_id__in=owner_ids, attr__id=attr_id).delete()
        ExtraAttrValue.objects.bulk_create(extra_attr_values)

    return True


def import_audio_files(request):
    """
    Store uploaded files (only wav is accepted)
    :param request: must contain a list of files and the id of the database to be stored against
    :return:
    """
    user = request.user
    files = request.FILES.getlist('files', None)
    database_id = request.POST.get('database', None)
    cls = request.POST.get('cls', None)

    if not files:
        raise ValueError('No files uploaded. Abort.')
    if not database_id:
        raise ValueError('No database specified. Abort.')
    if not cls:
        raise ValueError('No class specified. Abort.')

    database = Database.objects.filter(id=database_id).first()
    if not database:
        raise ValueError('No such database: {}. Abort.'.format(database_id))

    db_assignment = DatabaseAssignment.objects.filter(user=user, database=database).first()
    if db_assignment is None or not db_assignment.can_add_files():
        raise PermissionError('You don\'t have permission to upload files to this database')

    added_files = []

    for f in files:
        file = File(file=f)
        fullname = file.name
        name, ext = os.path.splitext(fullname)

        # Removing the preceeding dot, e.g. ".wav" -> "wav"
        ext = ext[1:]

        unique_name = fullname
        is_unique = not AudioFile.objects.filter(name=unique_name).exists()
        postfix = 0
        while not is_unique:
            postfix += 1
            unique_name = '{}({}).{}'.format(name, postfix, ext)
            is_unique = not AudioFile.objects.filter(name=unique_name).exists()

        unique_name_wav = wav_path(unique_name)
        unique_name_compressed = audio_path(unique_name, settings.AUDIO_COMPRESSED_FORMAT)

        with open(unique_name_wav, 'wb') as wav_file:
            wav_file.write(file.read())

        audio = pydub.AudioSegment.from_file(unique_name_wav)

        ensure_parent_folder_exists(unique_name_compressed)
        audio.export(unique_name_compressed, format=settings.AUDIO_COMPRESSED_FORMAT)

        fs = audio.frame_rate
        length = audio.raw_data.__len__() // audio.frame_width
        audio_file = AudioFile.objects.create(name=unique_name, length=length, fs=fs, database=database)
        added_files.append(audio_file)

    _, rows = _get_sequence_info_empty_songs(added_files)
    return rows


def import_audio_metadata(request):
    """
    Store uploaded files (csv only)
    :param request: must contain a list of files and the id of the database to be stored against
    :return:
    """
    user = request.user
    file = request.FILES.get('file', None)
    database_id = request.POST.get('database', None)

    if not file:
        raise ValueError('No file uploaded. Abort.')
    if not database_id:
        raise ValueError('No database specified. Abort.')

    database = Database.objects.filter(id=database_id).first()
    if not database:
        raise ValueError('No such database: {}. Abort.'.format(database_id))

    db_assignment = DatabaseAssignment.objects.filter(user=user, database=database).first()
    if db_assignment is None or not db_assignment.can_add_files():
        raise PermissionError('You don\'t have permission to upload files to this database')

    file_data = file.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(file_data))

    supplied_fields = reader.fieldnames
    required_fields = ['filename', 'genus', 'species', 'quality', 'date', 'individual', 'gender', 'track']
    missing_fields = [x for x in required_fields if x not in supplied_fields]

    if missing_fields:
        raise ValueError('Field(s) {} are required but not found in your CSV file'.format(','.join(missing_fields)))

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
            date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()

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


def delete_songs(request):
    """
    Delete audio files given ids. Also remove all existing audio files.
    :param request: must contain a list of ids and the id of the database where these files come from
    :return:
    """
    user = request.user
    ids = json.loads(request.POST['ids'])
    database_id = request.POST['database']

    # Check that the user has permission to delete files from this database
    database = Database.objects.filter(id=database_id).first()
    if not database:
        raise ValueError('No such database: {}. Abort.'.format(database_id))
    db_assignment = DatabaseAssignment.objects.filter(user=user, database=database).first()
    if db_assignment is None or not db_assignment.can_delete_files():
        raise PermissionError('You don\'t have permission to delete files from this database. '
                              'Are you messing with Javascript?')

    # Check that the ids to delete actually come from this database
    audio_files = AudioFile.objects.filter(id__in=ids)
    audio_files_ids = audio_files.values_list('id', flat=True)

    non_existent_ids = [x for x in ids if x not in audio_files_ids]

    if non_existent_ids:
        raise PermissionError('You\'re trying to delete files that don\'t belong to database {}. '
                              'Are you messing with Javascript?'.format(database.name))

    audio_files.delete()
    return True


def create_database(request):
    name = request.POST.get('name', None)
    user = request.user

    if not name:
        raise ValueError('Database name is required.')

    if Database.objects.filter(name=name).exists():
        raise ValueError('Database with name {} already exists.'.format(name))

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
    items = json.loads(request.POST['items'])
    file_id = request.POST['file-id']
    audio_file = AudioFile.objects.get(id=file_id)
    segmentation, _ = Segmentation.objects.get_or_create(audio_file=audio_file, source='user')

    segments = Segment.objects.filter(segmentation=segmentation)

    new_segments = []
    old_segments = []
    for item in items:
        id = item['id']
        if isinstance(id, str) and id.startswith('new:'):
            segment = Segment(segmentation=segmentation, start_time_ms=item['start'],
                              end_time_ms=item['end'])
            new_segments.append(segment)
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

    for segment in to_delete:
        segment_id = segment.id
        seg_spect_path = spect_fft_path(str(segment_id), 'syllable')
        if os.path.isfile(seg_spect_path):
            os.remove(seg_spect_path)

    with transaction.atomic():
        for segment in to_update:
            segment.save()
        for segment in to_delete:
            segment.delete()

        Segment.objects.bulk_create(new_segments)

    extract_spectrogram(segmentation)

    segments = Segment.objects.filter(segmentation=segmentation)
    _, rows = bulk_get_segments_for_audio(segments, DotMap(file_id=file_id))
    return rows


def request_database_access(request):
    user = request.user
    database_id = request.POST.get('database-id', None)
    if not database_id:
        raise ValueError('No database is specified.')

    database = Database.objects.filter(id=database_id).first()
    if database is None:
        raise ValueError('No such database exists.')

    requested_permission = DatabasePermission.ANNOTATE
    already_granted = DatabaseAssignment.objects\
        .filter(user=user, database=database, permission__gte=requested_permission).exists()

    if already_granted:
        raise ValueError('You\'re already granted equal or greater permission.')

    access_request = AccessRequest.objects.filter(user=user, database=database).first()
    if access_request and access_request.permission >= requested_permission:
        raise ValueError('You\'ve already requested equal or greater permission.')

    if access_request is None:
        access_request = AccessRequest(user=user, database=database)

    access_request.permission = requested_permission
    access_request.save()
    return True


def approve_database_access(request):
    you = request.user
    request_id = request.POST.get('request-id', None)
    if not request_id:
        raise ValueError('No request is specified.')

    access_request = AccessRequest.objects.filter(id=request_id).first()
    if access_request is None:
        raise ValueError('No such request exists.')

    person_asking_for_access = access_request.user
    permission_to_grant = access_request.permission
    database = access_request.database

    has_grant_privilege = DatabaseAssignment.objects \
        .filter(user=you, database=database, permission__gte=DatabasePermission.ASSIGN_USER).exists()

    if not has_grant_privilege:
        raise ValueError('You don\'t have permission to grant access on this database.')

    database_assignment = DatabaseAssignment.objects.filter(user=person_asking_for_access, database=database).first()

    if database_assignment and database_assignment.permission >= permission_to_grant:
        access_request.resolved = True
        access_request.save()
        raise ValueError('User\'s already granted equal or greater permission.')

    if database_assignment is None:
        database_assignment = DatabaseAssignment(user=person_asking_for_access, database=database)

    with transaction.atomic():
        database_assignment.permission = permission_to_grant
        database_assignment.save()
        access_request.resolved = True
        access_request.save()

    return True


def copy_files(request):
    """
    Copy files from the source database to the target database, not copying the actual files, but everything database-
    wise is copied, so the copies don't affect the original.
    :param request:
    :return:
    """
    user = request.user
    ids = json.loads(request.POST.get('ids', '{}'))

    if not ids:
        raise ValueError('No song IDs specified.')

    target_database_name = request.POST.get('target-database-name', None)
    if target_database_name is None:
        raise ValueError('No target database name specified.')

    source_database_id = request.POST.get('source-database-id', None)
    if source_database_id is None:
        raise ValueError('No source database specified.')

    target_database = Database.objects.filter(name=target_database_name).first()
    if target_database is None:
        raise ValueError('Target database {} doesn\'t exist.'.format(target_database_name))

    source_database = Database.objects.filter(id=source_database_id).first()
    if source_database is None:
        raise ValueError('Source database doesn\'t exist.')

    has_copy_privilege = DatabaseAssignment.objects\
        .filter(user=user, database=source_database, permission__gte=DatabasePermission.COPY_FILES).first()

    if not has_copy_privilege:
        raise ValueError('You don\'t have permission to copy files from the source database')

    has_add_files_privilege = DatabaseAssignment.objects \
        .filter(user=user, database=target_database, permission__gte=DatabasePermission.ADD_FILES).first()

    if not has_add_files_privilege:
        raise ValueError('You don\'t have permission to copy files to the target database')

    # Make sure all those IDs belong to the source database
    source_audio_files = AudioFile.objects.filter(id__in=ids, database=source_database)
    if len(source_audio_files) != len(ids):
        raise ValueError('There\'s a mismatch between the song IDs you provided and the actual songs in the database')

    song_values = source_audio_files\
        .values_list('id', 'fs', 'length', 'name', 'track', 'individual', 'quality', 'original')
    old_song_id_to_name = {x[0]: x[3] for x in song_values}
    old_song_names = old_song_id_to_name.values()
    old_song_ids = old_song_id_to_name.keys()

    # Make sure there is no duplication:
    duplicate_audio_files = AudioFile.objects.filter(id__in=ids, database=target_database, name__in=old_song_names)
    if duplicate_audio_files:
        raise ValueError('Some file(s) you\'re trying to copy already exist in {}'.format(target_database_name))

    song_segmentation_values = Segmentation.objects\
        .filter(audio_file__in=source_audio_files).values_list('id', 'audio_file')

    # not all AudioFiles have Segmentation - so this is to keep track of which Segmentations need to be copied
    song_old_id_to_segmentation_old_id = {x[1]: x[0] for x in song_segmentation_values}

    # We need this to get all Segments that need to be copied - again, because not all AudioFiles have Segmentation
    segmentations_old_ids = song_old_id_to_segmentation_old_id.values()

    # We need to map old and new IDs of AudioFiles so that we can copy their ExtraAttrValue later
    songs_old_id_to_new_id = {}

    # We need to map old and new IDs of Segmentation so that we can bulk create new Segments for the new Segmentation
    # based on the old Segments of the old Segmentation
    segmentation_old_id_to_new_id = {}

    # We need this to query back the Segments after they have been bulk created (bulk-creation doesn't return the actual
    # IDs)
    new_segmentation_ids = []

    # Create Song and Segmentation objects one by one because they can't be bulk created
    for old_id, fs, length, name, track, individual, quality, original in song_values:
        # Make sure that we always point to the true original. E.g if AudioFile #2 is a copy of #1 and someone makes
        # a copy of AudioFile #2, the new AudioFile must still reference #1 as its original

        original_id = old_id if original is None else original

        audio_file = AudioFile.objects.create(fs=fs, length=length, name=name, track_id=track, individual_id=individual,
                                              quality=quality, original_id=original_id, database=target_database)

        old_segmentation_id = song_old_id_to_segmentation_old_id.get(old_id, None)
        if old_segmentation_id:
            segmentation = Segmentation.objects.create(source='user', audio_file=audio_file)
            segmentation_old_id_to_new_id[old_segmentation_id] = segmentation.id
            new_segmentation_ids.append(segmentation.id)

        songs_old_id_to_new_id[old_id] = audio_file.id

    segments = Segment.objects.filter(segmentation__source='user', segmentation__in=segmentations_old_ids)
    segments_values = segments.values_list('id', 'start_time_ms', 'end_time_ms', 'mean_ff', 'min_ff', 'max_ff',
                                           'segmentation__audio_file__name', 'segmentation__id')

    # We need this to map old and new IDs of Segments so that we can copy their ExtraAttrValue later
    # The only reliable way to map new to old Segments is through the pair (start_time_ms, end_time_ms) since they are
    # constrained to be unique
    segments_old_id_to_start_end = {x[0]: (x[1], x[2]) for x in segments_values}

    new_segmentations_info = {}
    for seg_id, start, end, mean_ff, min_ff, max_ff, song_name, old_segmentation_id in segments_values:
        segment_info = (seg_id, start, end, mean_ff, min_ff, max_ff)
        if old_segmentation_id not in new_segmentations_info:
            new_segmentations_info[old_segmentation_id] = [segment_info]
        else:
            new_segmentations_info[old_segmentation_id].append(segment_info)

    segments_to_copy = []
    for old_segmentation_id, segment_info in new_segmentations_info.items():
        for seg_id, start, end, mean_ff, min_ff, max_ff in segment_info:
            segmentation_id = segmentation_old_id_to_new_id[old_segmentation_id]

            segment = Segment(start_time_ms=start, end_time_ms=end, mean_ff=mean_ff, min_ff=min_ff, max_ff=max_ff,
                              segmentation_id=segmentation_id)
            segments_to_copy.append(segment)

    Segment.objects.bulk_create(segments_to_copy)

    copied_segments = Segment.objects.filter(segmentation__in=new_segmentation_ids)
    copied_segments_values = copied_segments.values_list('id', 'start_time_ms', 'end_time_ms')
    segments_new_start_end_to_new_id = {(x[1], x[2]): x[0] for x in copied_segments_values}

    # Based on two maps: from new segment (start,end) key to their ID and old segment's ID to (start,end) key
    # we can now map Segment new IDs -> old IDs
    segments_old_id_to_new_id = {}
    for old_segment_id, segment_start_end in segments_old_id_to_start_end.items():
        new_segment_id = segments_new_start_end_to_new_id[segment_start_end]
        segments_old_id_to_new_id[old_segment_id] = new_segment_id

    # Query all ExtraAttrValue of Songs, and make duplicate by replacing old song IDs by new song IDs
    old_song_extra_attrs = ExtraAttrValue.objects\
        .filter(owner_id__in=old_song_ids, user=user).values_list('owner_id', 'attr', 'value')
    new_song_extra_attrs = []
    for old_song_id, attr_id, value in old_song_extra_attrs:
        new_song_id = songs_old_id_to_new_id[old_song_id]
        new_song_extra_attrs.append(ExtraAttrValue(user=user, attr_id=attr_id, value=value, owner_id=new_song_id))

    old_segment_ids = segments_old_id_to_start_end.keys()

    # Query all ExtraAttrValue of Segments, and make duplicate by replacing old IDs by new IDs
    old_segment_extra_attrs = ExtraAttrValue.objects \
        .filter(owner_id__in=old_segment_ids, user=user).values_list('owner_id', 'attr', 'value')
    new_segment_extra_attrs = []
    for old_segment_id, attr_id, value in old_segment_extra_attrs:
        new_segment_id = segments_old_id_to_new_id[int(old_segment_id)]
        new_segment_extra_attrs.append(ExtraAttrValue(user=user, attr_id=attr_id, value=value, owner_id=new_segment_id))

    # Now bulk create
    ExtraAttrValue.objects.bulk_create(new_song_extra_attrs)
    ExtraAttrValue.objects.bulk_create(new_segment_extra_attrs)

    return True


def populate_context(context, user, with_similarity=False):
    databases, current_database = get_user_databases(user)
    db_assignment = DatabaseAssignment.objects.get(database=current_database, user=user)
    inaccessible_databases = Database.objects.exclude(id__in=databases)

    databases_own = DatabaseAssignment.objects\
        .filter(user=user, permission__gte=DatabasePermission.ASSIGN_USER).values_list('database', flat=True)

    pending_requests = AccessRequest.objects.filter(database__in=databases_own, resolved=False)

    context['databases'] = databases
    context['current_database'] = current_database
    context['current_database_owner_class'] = User.__name__
    context['inaccessible_databases'] = inaccessible_databases
    context['db_assignment'] = db_assignment
    context['pending_requests'] = pending_requests

    if with_similarity:
        similarities, current_similarity = get_current_similarity(user, current_database)
        context['similarities'] = similarities.values_list('id', 'algorithm')

        if current_similarity:
            context['current_similarity'] = (current_similarity.id, current_similarity.algorithm, User.__name__)


class IndexView(TemplateView):
    """
    The view to index page
    """

    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        user = self.request.user

        populate_context(context, user, True)

        context['page'] = 'index'
        return context


class ExemplarsView(TemplateView):
    template_name = "exemplars.html"

    def get_context_data(self, **kwargs):
        context = super(ExemplarsView, self).get_context_data(**kwargs)
        user = self.request.user
        cls = kwargs.get('class', 'label')

        populate_context(context, user)

        context['cls'] = cls
        context['page'] = 'exemplars'
        context['subpage'] = 'exemplars/{}'.format(cls)

        return context


class SongsView(TemplateView):
    """
    The view to index page
    """

    template_name = 'songs.html'

    def get_context_data(self, **kwargs):
        context = super(SongsView, self).get_context_data(**kwargs)
        user = self.request.user
        cls = kwargs.get('class', 'label')

        populate_context(context, user)

        context['cls'] = cls
        context['page'] = 'songs'
        context['subpage'] = 'songs/{}'.format(cls)
        return context


class SegmentationView(TemplateView):
    """
    The view of song segmentation page
    """

    template_name = "segmentation.html"

    def get_context_data(self, **kwargs):
        context = super(SegmentationView, self).get_context_data(**kwargs)
        user = self.request.user
        file_id = kwargs['file_id']
        audio_file = AudioFile.objects.filter(id=file_id).first()
        if audio_file is None:
            raise Exception('No such file')

        db_assignment = DatabaseAssignment.objects.get(database=audio_file.database, user=user)

        context['page'] = 'segmentation'
        context['file_id'] = file_id
        context['length'] = audio_file.length
        context['fs'] = audio_file.fs
        context['db_assignment'] = db_assignment
        return context
