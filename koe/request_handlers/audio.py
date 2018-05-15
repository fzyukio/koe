import io
import os

import pydub
from django.conf import settings
from django.core.files import File
from django.http import HttpResponse

from koe import wavfile
from koe.grid_getters import get_sequence_info_empty_songs
from koe.model_utils import assert_permission, \
    get_or_error
from koe.models import AudioFile, Segment, Database, DatabasePermission
from root.utils import ensure_parent_folder_exists, wav_path, audio_path

__all__ = ['get_segment_audio_data', 'import_audio_files', 'get_audio_file_url']


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


def get_segment_audio_data(request):
    """
    Return a playable audio segment given the segment id
    :param request: must specify segment-id, this is the ID of a Segment object to be played
    :return: a binary blob specified as audio/ogg (or whatever the format is), playable and volume set to -10dB
    """
    user = request.user

    segment_id = get_or_error(request.POST, 'segment-id')
    segment = get_or_error(Segment, dict(id=segment_id))
    audio_file = segment.segmentation.audio_file
    assert_permission(user, audio_file.database, DatabasePermission.VIEW)

    start = segment.start_time_ms
    end = segment.end_time_ms

    wav_file_path = wav_path(audio_file.name)
    chunk = wavfile.read_segment(wav_file_path, start, end, mono=True, normalised=False)
    audio_segment = pydub.AudioSegment(
        chunk.tobytes(),
        frame_rate=audio_file.fs,
        sample_width=chunk.dtype.itemsize,
        channels=1
    )

    audio_segment = _match_target_amplitude(audio_segment)

    out = io.BytesIO()
    audio_segment.export(out, format=settings.AUDIO_COMPRESSED_FORMAT)
    binary_content = out.getvalue()

    response = HttpResponse()
    response.write(binary_content)
    response['Content-Type'] = 'audio/' + settings.AUDIO_COMPRESSED_FORMAT
    response['Content-Length'] = len(binary_content)
    return response


def import_audio_files(request):
    """
    Store uploaded files (only wav is accepted)
    :param request: must contain a list of files and the id of the database to be stored against
    :return:
    """
    user = request.user
    files = request.FILES.getlist('files', None)

    database_id = get_or_error(request.POST, 'database')
    database = get_or_error(Database, dict(id=database_id))
    assert_permission(user, database, DatabasePermission.ADD_FILES)

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

    _, rows = get_sequence_info_empty_songs(added_files)
    return rows


def get_audio_file_url(request):
    user = request.user

    file_id = get_or_error(request.POST, 'file-id')
    audio_file = get_or_error(AudioFile, dict(id=file_id))
    assert_permission(user, audio_file.database, DatabasePermission.VIEW)

    return audio_path(audio_file.name, settings.AUDIO_COMPRESSED_FORMAT, for_url=True)
