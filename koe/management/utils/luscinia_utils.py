import array
import os
import sys

import numpy as np
import pydub
from django.conf import settings

from koe import wavfile as wf
from koe.wavfile import get_wav_info
from koe.utils import wav_path, audio_path
from root.utils import ensure_parent_folder_exists

PY3 = sys.version_info[0] == 3
if PY3:
    def str_to_bytes(x):
        return str.encode(x, encoding='LATIN-1')
else:
    def str_to_bytes(x):
        return x


def get_syllable_end_time(el_rows):
    """
    The reason for this is we can't rely on the last element to find where the syllable actually ends, despite they
    being sorted by starttime. The last element always start later than the element before it but it could be too short
    it finishes before the previous element finishes

    :param el_rows:
    :return:
    """
    end_time = -1
    for row in el_rows:
        el_end_time = row['starttime'] + row['timelength']
        if el_end_time > end_time:
            end_time = el_end_time
    return end_time


def get_dbconf(dbs):
    import psycopg2
    import psycopg2.extras
    conns = {}

    for dbconf in dbs.split(','):
        abbr, dbname, port = dbconf.split(':')
        port = int(port)
        conn = psycopg2.connect(
            "dbname={} user=sa password='sa' host=localhost port={}".format(dbname, port))
        conn.set_client_encoding('LATIN1')
        conns[abbr] = conn

    return conns


def import_pcm(song, cur, audio_file, wav_file_path=None, compressed_url=None):
    if wav_file_path is None:
        wav_file_path = wav_path(audio_file)
    if compressed_url is None:
        compressed_url = audio_path(audio_file, settings.AUDIO_COMPRESSED_FORMAT)

    if not os.path.isfile(wav_file_path):
        # print('Importing {}'.format(song_name))
        song_id = song['songid']
        cur.execute('select wav from wavs where songid={};'.format(song_id))

        data = cur.fetchone()
        raw_pcm = str_to_bytes(data[0])

        nchannels = song['stereo']
        bitrate = int(song['ssizeinbits'])
        fs = int(song['samplerate'])

        byte_per_frame = int(bitrate / 8)
        nframes_all_channel = int(len(raw_pcm) / byte_per_frame)
        nframes_per_channel = int(nframes_all_channel / nchannels)
        length = nframes_per_channel
        ensure_parent_folder_exists(wav_file_path)

        if bitrate == 24:
            array1 = np.frombuffer(raw_pcm, dtype=np.ubyte)
            array2 = array1.reshape((nframes_per_channel, nchannels, byte_per_frame)).astype(np.uint8)
            wf.write_24b(wav_file_path, fs, array2)
        else:
            data = array.array('i', raw_pcm)
            sound = pydub.AudioSegment(data=data, sample_width=byte_per_frame, frame_rate=fs, channels=nchannels)
            sound.export(wav_file_path, 'wav')
    else:
        fs, length = get_wav_info(wav_file_path)

    if not os.path.isfile(compressed_url):
        ensure_parent_folder_exists(compressed_url)
        sound = pydub.AudioSegment.from_wav(wav_file_path)
        sound.export(compressed_url, format=settings.AUDIO_COMPRESSED_FORMAT)

    return fs, length
