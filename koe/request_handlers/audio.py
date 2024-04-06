import io
import json
import os
from io import BufferedWriter
from logging import warning

from django.conf import settings
from django.core.files import File
from django.http import HttpResponse
from django.utils import timezone

import numpy as np
import pydub
from memoize import memoize

from koe import wavfile
from koe.grid_getters import get_sequence_info_empty_songs
from koe.model_utils import assert_permission, get_or_error
from koe.models import AudioFile, AudioTrack, Database, DatabasePermission, Individual, Segment
from koe.utils import audio_path
from koe.wavfile import get_wav_info, read_segment, read_wav_info, write, write_24b
from root.exceptions import CustomAssertionError
from root.models import ExtraAttrValue
from root.utils import data_path, ensure_parent_folder_exists


__all__ = [
    "get_segment_audio_data",
    "import_audio_chunk",
    "get_audio_file_url",
    "import_audio_file",
    "get_audio_files_urls",
    "merge_audio_chunks",
]


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
    wav_file_path = data_path("audio/wav/{}".format(database_id), "{}.wav".format(audio_file_name))
    chunk = wavfile.read_segment(wav_file_path, start, end, normalised=False, mono=True)

    audio_segment = pydub.AudioSegment(chunk.tobytes(), frame_rate=fs, sample_width=chunk.dtype.itemsize, channels=1)

    audio_segment = _match_target_amplitude(audio_segment)

    out = io.BytesIO()
    audio_segment.export(out, format=settings.AUDIO_COMPRESSED_FORMAT)
    binary_content = out.getvalue()
    out.close()

    response = HttpResponse()
    response.write(binary_content)
    response["Content-Type"] = "audio/" + settings.AUDIO_COMPRESSED_FORMAT
    response["Content-Length"] = len(binary_content)
    return response


def get_segment_audio_data(request):
    """
    Return a playable audio segment given the segment id
    :param request: must specify segment-id, this is the ID of a Segment object to be played
    :return: a binary blob specified as audio/ogg (or whatever the format is), playable and volume set to -10dB
    """
    user = request.user

    segment_id = get_or_error(request.POST, "segment-id")
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


def _import_and_convert_audio_file(
    database,
    file,
    max_fs,
    real_fs=None,
    audio_file=None,
    track=None,
    start=None,
    end=None,
):
    file_already_exists = False
    if isinstance(file, BufferedWriter):
        file_already_exists = True
        name_ext = os.path.basename(file.name)
    else:
        name_ext = file.name

    if name_ext.lower().endswith(".wav"):
        name_no_ext = name_ext[:-4]
    else:
        name_no_ext = name_ext

    # Need a unique name (database-wide) for new file
    if audio_file is None:
        is_unique = not AudioFile.objects.filter(database=database, name=name_no_ext).exists()
        if not is_unique:
            raise CustomAssertionError("File {} already exists".format(name_no_ext))
    elif audio_file.name != name_no_ext:
        raise CustomAssertionError("Impossible! File name in your table and in the database don't match")

    wav_name = data_path("audio/wav/{}".format(database.id), "{}.wav".format(name_no_ext))
    name_compressed = data_path(
        "audio/{}/{}".format(settings.AUDIO_COMPRESSED_FORMAT, database.id),
        "{}.{}".format(name_no_ext, settings.AUDIO_COMPRESSED_FORMAT),
    )

    fake_wav_name = wav_name + ".bak"

    if not file_already_exists:
        with open(wav_name, "wb") as wav_file:
            wav_file.write(file.read())

    _fs, length, noc = get_wav_info(wav_name, return_noc=True)

    # If real_fs is provided, it is absolute -- otherwise it is what we can really read from the file
    if real_fs is None:
        real_fs = _fs

    fake_fs = None
    # If real_fs is not what we read from the file, then the file is fake, and we must restore the original file
    # to do that we rename the wav file that we just stored (which is fake) to .bak, then change the sample rate
    # back to the original and store the original file as .wav
    if real_fs != _fs:
        os.rename(wav_name, fake_wav_name)
        _change_fs_without_resampling(fake_wav_name, real_fs, wav_name)
        audio = pydub.AudioSegment.from_file(fake_wav_name)
        os.remove(fake_wav_name)

    # Otherwise, if real_fs is more than max_fs, we must create a fake file for the sake of converting to mp3:
    elif real_fs > max_fs:
        fake_fs = max_fs
        _change_fs_without_resampling(wav_name, fake_fs, fake_wav_name)
        audio = pydub.AudioSegment.from_file(fake_wav_name)
        os.remove(fake_wav_name)
    # Otherwise the file is ordinary - no need to fake it
    else:
        audio = pydub.AudioSegment.from_file(wav_name)

    ensure_parent_folder_exists(name_compressed)
    audio.export(name_compressed, format=settings.AUDIO_COMPRESSED_FORMAT)

    if audio_file is None:
        if track is None:
            track = AudioTrack.objects.get_or_create(name="TBD")[0]
        individual = Individual.objects.get_or_create(name="TBD")[0]
        audio_file = AudioFile(
            name=name_no_ext,
            length=length,
            fs=real_fs,
            database=database,
            track=track,
            start=start,
            end=end,
            fake_fs=fake_fs,
            added=timezone.now(),
            noc=noc,
            individual=individual,
        )
        audio_file.save()
        if track.name == "TBD":
            track.name = str(audio_file.id)
            track.save()
        individual.name = str(audio_file.id)
        individual.save()
    else:
        audio_file.start = start
        audio_file.end = end
        audio_file.length = length
        audio_file.save()

    return audio_file


def import_audio_chunk(request):
    """
    To facilitate sending big files, Dropzone allows uploading by chunk
    Each chunk is uploaded in one request. This function will save this chunk to the database
    by using the chunk's index as enumeration appended to the file's name
    :param request:
    :return:
    """
    user = request.user
    params = request.POST

    database_id = get_or_error(request.POST, "database")
    database = get_or_error(Database, dict(id=database_id))
    assert_permission(user, database, DatabasePermission.ADD_FILES)

    file = File(file=request.FILES["file"])
    name = params["dzFilename"]
    chunk_index = int(params["dzChunkIndex"])

    if name.lower().endswith(".wav"):
        name = name[:-4]

    wav_file_path = data_path("audio/wav/{}".format(database_id), name + ".wav")

    if chunk_index == 0:
        is_unique = not AudioFile.objects.filter(database=database, name=name).exists()

        if not is_unique:
            raise CustomAssertionError("Error: file {} already exists in this database".format(name))

    chunk_file_path = wav_file_path + "__" + str(chunk_index)
    with open(chunk_file_path, "wb") as f:
        f.write(file.read())

    return dict(origin="import_audio_chunk", success=True, warning=None, payload=None)


def merge_audio_chunks(request):
    """
    This action should be called after the last audio chunk is uploaded.
    It will merge all the saved chunks (foo.wav__1, foo.wav__2, etc...) into foo.wav
    And import to the database
    :param request:
    :return:
    """
    user = request.user
    params = request.POST
    name = params["name"]
    chunk_count = int(params["chunkCount"])
    max_fs = int(request.POST.get("browser-fs", 0))

    if name.lower().endswith(".wav"):
        name = name[:-4]

    database_id = get_or_error(request.POST, "database")
    database = get_or_error(Database, dict(id=database_id))
    assert_permission(user, database, DatabasePermission.ADD_FILES)

    wav_file_path = data_path("audio/wav/{}".format(database_id), name + ".wav")

    with open(wav_file_path, "wb") as combined_file:
        for i in range(chunk_count):
            chunk_file_path = wav_file_path + "__" + str(i)
            with open(chunk_file_path, "rb") as chunk_file:
                combined_file.write(chunk_file.read())

    (
        size,
        comp,
        num_channels,
        fs,
        sbytes,
        block_align,
        bitrate,
        bytes,
        dtype,
    ) = read_wav_info(wav_file_path)
    if comp == 3:
        warning("File is IEEE format. Convert to standard WAV")
        audio = pydub.AudioSegment.from_file(wav_file_path)
        audio.export(wav_file_path, format="wav")

    audio_file = _import_and_convert_audio_file(database, combined_file, max_fs)

    for i in range(chunk_count):
        chunk_file_path = wav_file_path + "__" + str(i)
        os.remove(chunk_file_path)

    added_files = AudioFile.objects.filter(id=audio_file.id)
    _, rows = get_sequence_info_empty_songs(added_files)
    return dict(origin="merge_audio_chunks", success=True, warning=None, payload=rows)


def _change_fs_without_resampling(wav_file, new_fs, new_name):
    """
    Create a new wav file with the a new (fake) sample rate, without changing the actual data.
    This is necessary if the frequency of the wav file is higher than the maximum sample rate that the browser supports
    :param wav_file: path to the original wav file
    :param new_fs: the new sample rate
    :return: the path of the faked wav file
    """
    (
        size,
        comp,
        num_channels,
        rate,
        sbytes,
        block_align,
        bitrate,
        bytes,
        dtype,
    ) = read_wav_info(wav_file)
    ubyte_data = read_segment(wav_file, 0, None, normalised=False, retype=False)
    byte_length = ubyte_data.size
    nframes_per_channel = byte_length // block_align
    byte_per_frame = bitrate // 8

    uint8_data = ubyte_data.reshape((nframes_per_channel, num_channels, byte_per_frame)).astype(np.uint8)

    if bitrate == 24:
        write_24b(new_name, new_fs, uint8_data)
    else:
        write(new_name, new_fs, uint8_data, bitrate=bitrate)


def import_audio_file(request):
    """
    Store uploaded file (only wav is accepted)
    :param request: must contain a list of files and the id of the database to be stored against
    :return:
    """
    user = request.user
    f = request.FILES["file"]

    database_id = get_or_error(request.POST, "database-id")
    item = json.loads(get_or_error(request.POST, "item"))
    real_fs = int(get_or_error(request.POST, "real-fs"))
    max_fs = int(get_or_error(request.POST, "browser-fs"))
    track_id = get_or_error(request.POST, "track-id")

    database = get_or_error(Database, dict(id=database_id))
    track = get_or_error(AudioTrack, dict(id=track_id))
    assert_permission(user, database, DatabasePermission.ADD_FILES)

    start = item["start"]
    end = item["end"]
    song_id = item["id"]

    file = File(file=f)

    audio_file = None
    if not isinstance(song_id, str) or not song_id.startswith("new:"):
        audio_file = AudioFile.objects.filter(database=database, id=song_id).first()

    audio_file = _import_and_convert_audio_file(database, file, max_fs, real_fs, audio_file, track, start, end)

    quality = item.get("quality", None)
    individual_name = item.get("individual", None)
    note = item.get("note", None)
    type = item.get("type", None)
    sex = item.get("sex", None)

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

    return dict(
        origin="import_audio_file",
        success=True,
        warning=None,
        payload=dict(id=audio_file.id, name=audio_file.name),
    )


def get_audio_file_url(request):
    user = request.user

    file_id = get_or_error(request.POST, "file-id")
    audio_file = get_or_error(AudioFile, dict(id=file_id))
    assert_permission(user, audio_file.database, DatabasePermission.VIEW)

    # The audio file might have sample rate being faked - this is the only sample rate value the browser can see.
    # It has no idea what the real fs is unless we tell it.
    # However, when converted to MP3, the real fs can be changed anyways. For example, 44100Hz (wav) -> 48000 (mp3)
    # in which case there is a difference in real_fs and what the browser can see.
    # In this case we must tell the browser to use 48000 as the real_fs of the mp3 file.
    # We do that by omitting real_fs (returning NULL to the browser)
    # real_fs = None
    # if audio_file.fake_fs is not None:
    real_fs = audio_file.fs

    # if audio_file.fs > 48000:
    #     real_fs = audio_file.fs

    retval = {
        "url": audio_path(audio_file, settings.AUDIO_COMPRESSED_FORMAT, for_url=True),
        "real-fs": real_fs,
        "length": audio_file.length,
    }
    return dict(origin="get_audio_file_url", success=True, warning=None, payload=retval)


def get_audio_files_urls(request):
    user = request.user

    file_ids = get_or_error(request.POST, "file-ids")
    file_ids = json.loads(file_ids)
    format = request.POST.get("format", settings.AUDIO_COMPRESSED_FORMAT)
    audio_files = AudioFile.objects.filter(id__in=file_ids)
    database_ids = audio_files.values_list("database", flat=True).distinct()
    databases = Database.objects.filter(id__in=database_ids)
    for database in databases:
        assert_permission(user, database, DatabasePermission.VIEW)

    file_paths = []
    for audio_file in audio_files:
        file_path = audio_path(audio_file, format, for_url=True)
        file_paths.append(file_path)

    return dict(origin="get_audio_files_urls", success=True, warning=None, payload=file_paths)
