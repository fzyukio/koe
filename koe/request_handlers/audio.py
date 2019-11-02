import io
import json
import wave

import pydub
from coverage.annotate import os
from django.conf import settings
from django.core.files import File
from django.http import HttpResponse
from memoize import memoize

from koe import wavfile
from koe.grid_getters import get_sequence_info_empty_songs
from koe.model_utils import assert_permission, get_or_error
from koe.models import AudioFile, Segment, Database, DatabasePermission, AudioTrack, Individual
from koe.utils import audio_path, get_wav_info
from root.exceptions import CustomAssertionError
from root.models import ExtraAttrValue
from root.utils import ensure_parent_folder_exists, data_path

__all__ = ['get_segment_audio_data', 'import_audio_files', 'get_audio_file_url', 'import_audio_file',
           'get_audio_files_urls']


def _match_target_amplitude(sound, loudness=-10):
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


@memoize(timeout=None)
def _cached_get_segment_audio_data(audio_file_name, database_id, fs, start, end):
    wav_file_path = data_path('audio/wav/{}'.format(database_id), '{}.wav'.format(audio_file_name))
    chunk = wavfile.read_segment(wav_file_path, start, end, normalised=False, mono=True)

    audio_segment = pydub.AudioSegment(
        chunk.tobytes(),
        frame_rate=fs,
        sample_width=chunk.dtype.itemsize,
        channels=1
    )

    audio_segment = _match_target_amplitude(audio_segment)

    out = io.BytesIO()
    audio_segment.export(out, format=settings.AUDIO_COMPRESSED_FORMAT)
    binary_content = out.getvalue()
    out.close()

    response = HttpResponse()
    response.write(binary_content)
    response['Content-Type'] = 'audio/' + settings.AUDIO_COMPRESSED_FORMAT
    response['Content-Length'] = len(binary_content)
    return response


def get_segment_audio_data(request):
    """
    Return a playable audio segment given the segment id
    :param request: must specify segment-id, this is the ID of a Segment object to be played
    :return: a binary blob specified as audio/ogg (or whatever the format is), playable and volume set to -10dB
    """
    user = request.user

    segment_id = get_or_error(request.POST, 'segment-id')
    segment = get_or_error(Segment, dict(id=segment_id))
    audio_file = segment.audio_file
    assert_permission(user, audio_file.database, DatabasePermission.VIEW)

    start = segment.start_time_ms
    end = segment.end_time_ms

    if audio_file.is_original():
        database_id = audio_file.database.id
        audio_file_name = audio_file.name
    else:
        database_id = audio_file.original.database.id
        audio_file_name = audio_file.original.name

    return _cached_get_segment_audio_data(audio_file_name, database_id, audio_file.fs, start, end)


def _import_and_convert_audio_file(database, file, max_fs, audio_file=None, track=None, start=None, end=None):
    name = file.name
    if name.lower().endswith('.wav'):
        name = name[:-4]

    # Need a unique name (database-wide) for new file
    if audio_file is None:
        is_unique = not AudioFile.objects.filter(database=database, name=name).exists()
        if not is_unique:
            raise CustomAssertionError('File {} already exists'.format(name))
    elif audio_file.name != name:
        raise CustomAssertionError('Impossible! File name in your table and in the database don\'t match')

    name_wav = data_path('audio/wav/{}'.format(database.id), '{}.wav'.format(name))
    name_compressed = data_path('audio/{}/{}'.format(settings.AUDIO_COMPRESSED_FORMAT, database.id),
                                '{}.{}'.format(name, settings.AUDIO_COMPRESSED_FORMAT))

    with open(name_wav, 'wb') as wav_file:
        wav_file.write(file.read())

    fs, length = get_wav_info(name_wav)

    # If fake_fs is provided, this audio has higher frequency than most browsers can support. So
    # we use this fake_fs to circumvent MP3 specification, but WAV file is stored with original FS
    if max_fs < fs:
        fake_fs = max_fs
        faked_wav = change_fs_without_resampling(name_wav, fake_fs)
        audio = pydub.AudioSegment.from_file(faked_wav)
        os.remove(faked_wav)
    else:
        fake_fs = None
        audio = pydub.AudioSegment.from_file(name_wav)

    ensure_parent_folder_exists(name_compressed)
    audio.export(name_compressed, format=settings.AUDIO_COMPRESSED_FORMAT)

    if audio_file is None:
        audio_file = AudioFile(name=name, length=length, fs=fs, database=database, track=track, start=start, end=end,
                               fake_fs=fake_fs)
    else:
        audio_file.start = start
        audio_file.end = end
        audio_file.length = length

    audio_file.save()

    return audio_file


def import_audio_files(request):
    """
    Store uploaded files (only wav is accepted)
    :param request: must contain a list of files and the id of the database to be stored against
    :return:
    """
    user = request.user
    files = request.FILES.values()

    database_id = get_or_error(request.POST, 'database')
    database = get_or_error(Database, dict(id=database_id))
    max_fs = int(get_or_error(request.POST, 'max-fs'))
    assert_permission(user, database, DatabasePermission.ADD_FILES)

    added_files = []
    not_importable_filenames = []
    importable_files = []

    for f in files:
        file = File(file=f)
        name = file.name
        if name.lower().endswith('.wav'):
            name = name[:-4]

        is_unique = not AudioFile.objects.filter(database=database, name=name).exists()

        if not is_unique:
            not_importable_filenames.append(name)
        else:
            importable_files.append(file)

    if len(not_importable_filenames) > 0:
        raise CustomAssertionError('Error: No files were imported because the following files already exist: {}'
                                   .format(', '.join(not_importable_filenames)))
    else:
        for file in importable_files:
            audio_file = _import_and_convert_audio_file(database, file, max_fs)
            added_files.append(audio_file)

        added_files = AudioFile.objects.filter(database=database, name__in=[x.name for x in added_files])
        _, rows = get_sequence_info_empty_songs(added_files)
        return rows


def change_fs_without_resampling(wav_file, fake_fs):
    """
    Create a new wav file with the a new (fake) sample rate, without changing the actual data.
    This is necessary if the frequency of the wav file is higher than the maximum sample rate that the browser supports
    :param wav_file: path to the original wav file
    :param fake_fs: the new sample rate
    :return: the path of the faked wav file
    """
    spf = wave.open(wav_file, 'rb')
    num_channels = spf.getnchannels()
    swidth = spf.getsampwidth()
    signal = spf.readframes(-1)
    spf.close()

    fake_wav_location = wav_file + '.bak'

    wf = wave.open(fake_wav_location, 'wb')
    wf.setnchannels(num_channels)
    wf.setsampwidth(swidth)
    wf.setframerate(fake_fs)
    wf.writeframes(signal)
    wf.close()

    return fake_wav_location


def import_audio_file(request):
    """
    Store uploaded file (only wav is accepted)
    :param request: must contain a list of files and the id of the database to be stored against
    :return:
    """
    user = request.user
    f = request.FILES['file']

    database_id = get_or_error(request.POST, 'database-id')
    item = json.loads(get_or_error(request.POST, 'item'))
    max_fs = int(request.POST.get('max-fs', None))
    track_id = get_or_error(request.POST, 'track-id')

    database = get_or_error(Database, dict(id=database_id))
    track = get_or_error(AudioTrack, dict(id=track_id))
    assert_permission(user, database, DatabasePermission.ADD_FILES)

    start = item['start']
    end = item['end']
    song_id = item['id']

    file = File(file=f)

    audio_file = None
    if not isinstance(song_id, str) or not song_id.startswith('new:'):
        audio_file = AudioFile.objects.filter(database=database, id=song_id).first()

    audio_file = _import_and_convert_audio_file(database, file, max_fs, audio_file, track, start, end)

    quality = item.get('quality', None)
    individual_name = item.get('individual', None)
    note = item.get('note', None)
    type = item.get('type', None)
    sex = item.get('sex', None)

    if individual_name is not None:
        individual = Individual.objects.filter(name=individual_name).first()
        if individual is None:
            individual = Individual.objects.create(name=individual_name, gender=sex)
        elif sex is not None:
            individual.gender = sex
            individual.save()

        audio_file.individual = individual

    if quality:
        audio_file.quality = quality

    audio_file.save()
    audio_file_attrs = settings.ATTRS.audio_file
    if note:
        extra_attr_value = ExtraAttrValue.objects.filter(user=user, owner_id=audio_file.id, attr=audio_file_attrs.note)
        extra_attr_value.value = note

    if type:
        extra_attr_value = ExtraAttrValue.objects.create(user=user, owner_id=audio_file.id, attr=audio_file_attrs.type)
        extra_attr_value.value = type

    return dict(id=audio_file.id, name=audio_file.name)


def get_audio_file_url(request):
    user = request.user

    file_id = get_or_error(request.POST, 'file-id')
    audio_file = get_or_error(AudioFile, dict(id=file_id))
    assert_permission(user, audio_file.database, DatabasePermission.VIEW)

    # The audio file might have sample rate being faked - this is the only sample rate value the browser can see.
    # It has no idea what the real fs is unless we tell it
    real_fs = audio_file.fs

    return {'url': audio_path(audio_file, settings.AUDIO_COMPRESSED_FORMAT, for_url=True), 'real-fs': real_fs}


def get_audio_files_urls(request):
    user = request.user

    file_ids = get_or_error(request.POST, 'file-ids')
    file_ids = json.loads(file_ids)
    format = request.POST.get('format', settings.AUDIO_COMPRESSED_FORMAT)
    audio_files = AudioFile.objects.filter(id__in=file_ids)
    database_ids = audio_files.values_list('database', flat=True).distinct()
    databases = Database.objects.filter(id__in=database_ids)
    for database in databases:
        assert_permission(user, database, DatabasePermission.VIEW)

    file_paths = []
    for audio_file in audio_files:
        file_path = audio_path(audio_file, format, for_url=True)
        file_paths.append(file_path)

    return file_paths
