import csv
import datetime
import io
import json
import os
import zipfile

import pydub
from django.conf import settings
from django.core import serializers
from django.core.files import File
from django.db import transaction
from django.http import HttpResponse
from django.views.generic import TemplateView

from koe.model_utils import get_currents, extract_spectrogram
from koe.models import AudioFile, Segment, HistoryEntry, Segmentation, Database, DatabaseAssignment, \
    DatabasePermission, Individual, Species, AudioTrack
from root.models import ExtraAttrValue, ExtraAttr, User
from root.utils import history_path, ensure_parent_folder_exists, wav_path, audio_path, spect_fft_path

__all__ = ['get_segment_audio', 'save_history', 'import_history', 'delete_history', 'create_database',
           'import_audio_files', 'import_audio_metadata', 'delete_songs', 'save_segmentation']


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
    """
    comment = request.POST['comment']
    comment_attr = ExtraAttr.objects.filter(klass=HistoryEntry.__name__, name='note').first()

    _, _, _, current_database = get_currents(request.user)

    segments_ids = Segment.objects.filter(segmentation__audio_file__database=current_database) \
        .values_list('id', flat=True)

    extra_attr_values = ExtraAttrValue.objects \
        .filter(user=request.user, owner_id__in=segments_ids) \
        .exclude(attr__klass=User.__name__)

    retval = serializers.serialize('json', extra_attr_values)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_BZIP2, False) as zip_file:
        zip_file.writestr('root.extraattrvalue.json', retval)
    binary_content = zip_buffer.getvalue()

    he = HistoryEntry.objects.create(user=request.user, time=datetime.datetime.now())
    ExtraAttrValue.objects.create(owner_id=he.id, user=request.user, value=comment, attr=comment_attr)

    filename = he.filename
    filepath = history_path(filename)
    ensure_parent_folder_exists(filepath)

    with open(filepath, 'wb') as f:
        f.write(binary_content)

    return HttpResponse(filename)


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
    return HttpResponse('ok')


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
        with open(audio_file.file_path, 'rb') as f:
            binary_content = f.read()
    else:
        segment = Segment.objects.filter(pk=segment_id).first()
        audio_file = segment.segmentation.audio_file
        start = segment.start_time_ms
        end = segment.end_time_ms

        exts = [settings.AUDIO_COMPRESSED_FORMAT, 'wav']
        for ext in exts:
            file_url = audio_path(audio_file.name, ext, for_url=False)
            if os.path.isfile(file_url):
                song = pydub.AudioSegment.from_file(file_url)
                audio_segment = song[start:end]
                audio_segment = match_target_amplitude(audio_segment, -10)

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
    :return: 'ok' if everything goes well. Otherwise the error message.
    """
    version_id = request.POST.get('version-id', None)
    zip_file = request.FILES.get('zipfile', None)

    if not (version_id or zip_file):
        raise ValueError('No ID or file provided. Abort.')

    if version_id:
        he = HistoryEntry.objects.get(id=version_id)
        file = open(history_path(he.filename), 'rb')
    else:
        file = File(file=zip_file)

    with zipfile.ZipFile(file, "r") as zip_file:
        try:
            content = zip_file.read('root.extraattrvalue.json')
        except KeyError:
            raise ValueError('This is not a Koe history file')
        try:
            new_entries = json.loads(content)
        except Exception:
            raise ValueError('The history content is malformed and cannot be parsed.')
    file.close()

    extra_attr_values = []
    for entry in new_entries:
        owner_id = entry['fields']['owner_id']
        value = entry['fields']['value']
        attr_id = entry['fields']['attr']
        extra_attr_value = ExtraAttrValue(owner_id=owner_id, value=value, user=request.user)
        extra_attr_value.attr_id = attr_id
        extra_attr_values.append(extra_attr_value)

    # Wrap all DB modification in one transaction to utilise the roll-back ability when things go wrong
    with transaction.atomic():
        ExtraAttrValue.objects.filter(user=request.user).exclude(attr__klass=User.__name__).delete()
        ExtraAttrValue.objects.bulk_create(extra_attr_values)
        return HttpResponse('ok')


def import_audio_files(request):
    """
    Store uploaded files (only wav is accepted)
    :param request: must contain a list of files and the id of the database to be stored against
    :return:
    """
    user = request.user
    files = request.FILES.getlist('files', None)
    database_id = request.POST.get('database', None)

    if not files:
        raise ValueError('No files uploaded. Abort.')
    if not database_id:
        raise ValueError('No database specified. Abort.')

    database = Database.objects.filter(id=database_id).first()
    if not database:
        raise ValueError('No such database: {}. Abort.'.format(database_id))

    db_assignment = DatabaseAssignment.objects.filter(user=user, database=database).first()
    if db_assignment is None or not db_assignment.can_add_files():
        raise PermissionError('You don\'t have permission to upload files to this database')

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
        AudioFile.objects.create(name=unique_name, length=length, fs=fs, database=database)

    return HttpResponse('ok')


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

    existing_audio_files = AudioFile.objects.filter(name__in=filename_to_metadata.keys())

    with transaction.atomic():
        for audio_file in existing_audio_files:
            individual, quality, track = filename_to_metadata[audio_file.name]
            audio_file.individual = individual
            audio_file.quality = quality
            audio_file.track = track
            audio_file.save()

    return HttpResponse('ok')


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

    audio_files_names = list(audio_files.values_list('name', flat=True))
    audio_files.delete()

    fails = []
    exts = ['wav', settings.AUDIO_COMPRESSED_FORMAT]
    for name in audio_files_names:
        try:
            for ext in exts:
                file_path = audio_path(name, ext)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        except Exception:
            fails.append(name)

    if fails:
        raise RuntimeError('Unable to remove files: {}'.format('\n'.format(fails)))

    return HttpResponse('ok')


def create_database(request):
    name = request.POST.get('name', None)
    user = request.user

    if not name:
        return HttpResponse('Database name is required.')

    if Database.objects.filter(name=name).exists():
        return HttpResponse('Database with name {} already exists.'.format(name))

    database = Database(name=name)
    database.save()

    # Now assign this database to this user, and switch the working database to this new one
    DatabaseAssignment(user=user, database=database, permission=DatabasePermission.ANNOTATE).save()

    extra_attr = ExtraAttr.objects.get(klass=User.__name__, name='current-database')
    extra_attr_value, _ = ExtraAttrValue.objects.get_or_create(user=user, attr=extra_attr, owner_id=user.id)
    extra_attr_value.value = database.id
    extra_attr_value.save()

    return HttpResponse('')


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

    return HttpResponse('ok')


class IndexView(TemplateView):
    """
    The view to index page
    """

    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        user = self.request.user

        similarities, current_similarity, databases, current_database = get_currents(user)

        context['similarities'] = similarities.values_list('id', 'algorithm')
        context['databases'] = databases.values_list('id', 'name')
        context['current_database'] = (current_database.id, current_database.name, User.__name__)
        if current_similarity:
            context['current_similarity'] = (current_similarity.id, current_similarity.algorithm, User.__name__)
        context['page'] = 'index'
        return context


class ExemplarsView(TemplateView):
    template_name = "exemplars.html"

    def get_context_data(self, **kwargs):
        context = super(ExemplarsView, self).get_context_data(**kwargs)
        user = self.request.user
        cls = kwargs.get('class', 'label')

        _, _, databases, current_database = get_currents(user)

        context['databases'] = databases.values_list('id', 'name')
        context['current_database'] = (current_database.id, current_database.name, User.__name__)
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

        _, _, databases, current_database = get_currents(user)
        db_assignment = DatabaseAssignment.objects.get(database=current_database, user=user)

        context['databases'] = databases.values_list('id', 'name')
        context['current_database'] = (current_database.id, current_database.name, User.__name__)
        context['cls'] = cls
        context['page'] = 'songs'
        context['subpage'] = 'songs/{}'.format(cls)
        context['db_assignment'] = db_assignment
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
