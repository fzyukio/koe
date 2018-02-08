"""
Import syllables (not elements) from luscinia (after songs have been imported)
"""
import io
import os
import re
import sys
from logging import warning

import numpy as np
import psycopg2
import pydub
from PIL import Image
from django.core.management.base import BaseCommand

from koe import wavfile as wf
from koe.management.commands import utils
from koe.management.commands.utils import get_syllable_end_time
from koe.models import AudioFile, Segmentation, Segment, AudioTrack
from root.models import ExtraAttr, ExtraAttrValue, ValueTypes
from root.utils import audio_path, ensure_parent_folder_exists, spect_path

COLOURS = [[69, 204, 255], [73, 232, 62], [255, 212, 50], [232, 75, 48], [170, 194, 102]]
FF_COLOUR = [0, 0, 0]
AXIS_COLOUR = [127, 127, 127]

COLUMN_NAMES = ['Individual Name', 'Song Id', 'Song Name', 'Koe ID', 'Syllable Number', 'Syllable Start', 'Syllable End',
                'Syllable Length', 'Element Count', 'Spectrogram', 'Original Label', 'Label', 'Note', 'Context', 'Min FF', 'Max FF', 'Min Octave',
                'Max Octave', 'Gap Before', 'Gap After', 'Overall instantaneous peak freq', 'Overall peak frequency',
                'Overall Min Freq', 'Overall Max Freq']

LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

name_regex = re.compile('(\w{3})_(\d{4})_(\d{2})_(\d{2})_([\w\d]+)_(\d+)_(\w+)\.(B|EX|VG|G|OK)(\..*)?\.wav')
gender_attr, _ = ExtraAttr.objects.get_or_create(klass=AudioFile.__name__, name='gender', type=ValueTypes.BOOLEAN)
quality_attr, _ = ExtraAttr.objects.get_or_create(klass=AudioFile.__name__, name='quality', type=ValueTypes.SHORT_TEXT)
individual_attr, _ = ExtraAttr.objects.get_or_create(klass=AudioFile.__name__, name='individual',
                                                     type=ValueTypes.SHORT_TEXT)

PY3 = sys.version_info[0] == 3
if PY3:
    str_to_bytes = lambda x: str.encode(x, encoding='LATIN-1')
else:
    str_to_bytes = lambda x: x


def import_pcm(song, cur, song_name):
    song_id = song['songid']
    # Must use cur, not dict_cur otherwise wav will return truncated - for some reason
    cur.execute('select wav from wavs where songid={};'.format(song_id))

    data = cur.fetchone()
    raw_pcm = str_to_bytes(data[0])

    nchannels = song['stereo']
    bitrate = int(song['ssizeinbits'])
    fs = int(song['samplerate'])

    byte_per_frame = int(bitrate / 8)
    nframes_all_channel = int(len(raw_pcm) / byte_per_frame)
    nframes_per_channel = int(nframes_all_channel / nchannels)

    wav_url, wav_file_path = audio_path(song_name, 'wav')
    if not os.path.isfile(wav_file_path):
        array1 = np.frombuffer(raw_pcm, dtype=np.ubyte)
        array2 = array1.reshape((nframes_per_channel, nchannels, byte_per_frame)).astype(np.uint8)

        ensure_parent_folder_exists(wav_file_path)
        wf._write(wav_file_path, fs, array2, bitrate=bitrate)

    mp3_url, mp3_file_path = audio_path(song_name, 'mp3')
    if not os.path.isfile(mp3_file_path):
        ensure_parent_folder_exists(mp3_file_path)
        sound = pydub.AudioSegment.from_wav(wav_file_path)
        sound.export(mp3_file_path, format='mp3')

    audio_file = AudioFile.objects.create(raw_file=wav_url, mp3_file=mp3_url, name=song_name,
                                          length=nframes_per_channel, fs=fs)
    print('Created song {}'.format(song_name))
    return audio_file


def import_song_info(audio_file):
    song_name = audio_file.name

    # Populate info such as individuals, location, ...
    matches = name_regex.match(song_name)
    if matches is None:
        warning('File {} doesn\'t conform to the name pattern'.format(song_name))
    else:
        location = matches.group(1)
        year = matches.group(2)
        month = matches.group(3)
        date = matches.group(4)
        track_id = matches.group(5)

        track_name = '{}_{}_{}_{}'.format(location, year, month, date, track_id)
        track, _ = AudioTrack.objects.get_or_create(name=track_name)
        audio_file.track = track
        audio_file.save()

        gender = matches.group(7) == 'M'
        quality = matches.group(8)
        individual = matches.group(9)
        if individual:
            individual = individual[1:]
        if gender:
            ExtraAttrValue.objects.get_or_create(attr=gender_attr, owner_id=audio_file.id, value=gender)
        if quality:
            ExtraAttrValue.objects.get_or_create(attr=quality_attr, owner_id=audio_file.id,
                                                 value=quality)
        if individual:
            ExtraAttrValue.objects.get_or_create(attr=individual_attr, owner_id=audio_file.id,
                                                 value=individual)


def import_syllables(conn):
    """
    :param pop: 3-char abbr of the population, e.g. 'PKI', 'LBI', etc
    :param conn: the database connection
    :return:
    """
    cur = conn.cursor()
    el_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # Import syllables for all songs
    cur.execute('select sg.name, s.starttime, s.endtime, w.songid from syllable s '
                'join wavs w on s.songid=w.songid '
                'join songdata sg on w.songid=sg.id order by w.filename, s.starttime')
    song_syllable_rows = cur.fetchall()
    songs_2_syllables = {}

    # Song #79 PKI_2017_02_25_WHW028_01_M.EX..PipeClicksGrowlcough.wav has more than one syllable at position 1124:1136.
    # Db Syllable #2924

    for row in song_syllable_rows:
        song_name = row[0].replace(' ', '').replace('$', '')
        syl_starttime = row[1]
        syl_endtime = row[2]
        song_id = row[3]

        el_cur.execute('select starttime, timelength from element where songid={} and starttime >= {} '
                       'and (starttime + timelength) <= {} order by starttime'.format(song_id,
                                                                                      syl_starttime,
                                                                                      syl_endtime))
        el_rows = el_cur.fetchall()
        if len(el_rows) == 0:
            warning('Syllable with starttime={} endtime={} of song: "{}" doesn\'t enclose any syllable.'
                    .format(syl_starttime, syl_endtime, song_name))
            continue

        real_syl_starttime = el_rows[0]['starttime']
        real_syl_endtime = utils.get_syllable_end_time(el_rows)

        syllable = (real_syl_starttime, real_syl_endtime)

        if song_name not in songs_2_syllables:
            syllables = []
            songs_2_syllables[song_name] = syllables
        syllables.append(syllable)

    # delete all existing manual segmentation:
    Segmentation.objects.filter(audio_file__name__in=songs_2_syllables.keys(), source='user').delete()
    for song in songs_2_syllables:
        syllables = songs_2_syllables[song]
        audio_file = AudioFile.objects.filter(name=song).first()
        if audio_file is None:
            warning('File {} has not been imported. Please run import_luscinia_songs again.'
                    ' Ignore for now'.format(song))
            continue

        segmentation = Segmentation()
        segmentation.audio_file = audio_file
        segmentation.source = 'user'
        segmentation.save()

        for syllable in syllables:
            segment = Segment()
            segment.start_time_ms = syllable[0]
            segment.end_time_ms = syllable[1]
            segment.segmentation = segmentation
            segment.save()

        print('Processed song {}'.format(song))


def import_songs(conn):
    song_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    song_cur.execute('select w.framesize, w.stereo, w.samplerate, w.ssizeinbits, w.songid, s.name '
                     'from wavs w join songdata s on w.songid=s.id')
    songs = song_cur.fetchall()
    for song in songs:
        song_name = song['name'].replace(' ', '').replace('$', '')
        audio_file = AudioFile.objects.filter(name=song_name).first()

        # Import WAV data and save as WAV and MP3 files
        if audio_file is None:
            audio_file = import_pcm(song, cur, song_name)

        # import_song_info(audio_file)


def import_spectrograms(conn):
    """
    Export pictures of the syllable with fundamentals
    :param conn:
    :return:
    """
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute('select id, name, maxfreq, dy from songdata s')

    songs_data = cur.fetchall()
    song_info = {}

    for song in songs_data:
        song_name = song['name']
        song_info[song_name.replace(' ', '').replace('$', '')] = (song['id'], song['maxfreq'], song['dy'])

    segments_info = Segment.objects\
        .filter(segmentation__audio_file__name__in=song_info.keys())\
        .values_list('id', 'segmentation__audio_file__name', 'start_time_ms', 'end_time_ms')

    for seg_id, song_name, start, end in segments_info:
        song_id, nyquist, fbin = song_info[song_name]

        cur.execute('select starttime, endtime, songid from syllable where songid={} and starttime<={} and endtime>={}'
                    ' order by starttime'.format(song_id, start, end))
        syl_rows = cur.fetchall()

        if len(syl_rows) == 0:
            warning('Song #{} {} doesn\'t have a syllable at position {}:{}'.format(song_id, song_name, start, end))
            continue

        if len(syl_rows) > 1:
            warning('Song #{} {} has more than one syllable at position {}:{}. Db Syllable #{}'
                    .format(song_id, song_name, start, end, seg_id))

        for syl_idx, syl_row in enumerate(syl_rows):
            syl_starttime = syl_row['starttime']
            syl_endtime = syl_row['endtime']

            cur.execute(
                'select signal, starttime, timelength, fundfreq, gapbefore, gapafter, maxf, dy,'
                'overallpeakfreq1, overallpeakfreq2 '
                'from element where songid={} and starttime >= {} and (starttime + timelength) <= {}'
                    .format(song_id, syl_starttime, syl_endtime))
            el_rows = cur.fetchall()

            if len(el_rows) == 0:
                warning(
                    'Syllable #{} starttime={} endtime={} of song: "{}" doesn\'t enclose any syllable.'
                        .format(1, syl_starttime, syl_endtime, song_name))
                continue

            syl_starttime = el_rows[0]['starttime']
            syl_endtime = get_syllable_end_time(el_rows)

            if nyquist == 0:
                nyquist = el_rows[0]['maxf']
            if fbin == 0:
                fbin = el_rows[0]['dy']

            width = int(syl_endtime - syl_starttime) + 1
            height = int(nyquist / fbin)

            img_data_rgb = np.ones((height, width, 3), dtype=np.uint8) * 255

            for el_idx, el in enumerate(el_rows):
                signal = list(map(int, el['signal'].strip().split(' ')))
                fundfreq = np.array(el['fundfreq'].strip().split(' '), dtype='|S32').astype(np.float) / nyquist * height

                # the first 4 numbers of fundfreq are: max, min, ? (no idea) and ? (no idea), so we ignore them
                fundfreq = fundfreq[4:].astype(np.int)
                i = 0
                ff_row_idx = 0
                while i < len(signal):
                    num_data = signal[i]
                    img_col_idx = signal[i + 1] - syl_starttime

                    # Draw the mask
                    for j in range(2, num_data, 2):
                        _signal_segment_end = signal[i + j]
                        _signal_segment_start = signal[i + j + 1]
                        img_data_rgb[_signal_segment_start:_signal_segment_end, img_col_idx, :] = COLOURS[
                            el_idx % len(COLOURS)]

                    # Add the fundamental (red lines)
                    if ff_row_idx < len(fundfreq):
                        img_row_idx = height - fundfreq[ff_row_idx] - 1

                        img_row_idx_padded_low = max(0, img_row_idx - 2)
                        img_row_idx_padded_high = img_row_idx + 4 - (img_row_idx - img_row_idx_padded_low)
                        img_data_rgb[img_row_idx_padded_low:img_row_idx_padded_high, img_col_idx, :] = FF_COLOUR
                    ff_row_idx += 1
                    i += (num_data + 1)

            img = Image.fromarray(img_data_rgb)
            thumbnail_width = int(img.size[0])
            thumbnail_height = int(img.size[1] * 0.3)

            img = img.resize((thumbnail_width, thumbnail_height))

            if syl_idx > 0:
                warning('Syl_idx > 0')
                _, file_path = spect_path('{}_{}'.format(seg_id, syl_idx))
            else:
                _, file_path = spect_path('{}'.format(seg_id))
            ensure_parent_folder_exists(file_path)

            img.save(file_path, format='PNG')


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            '--dbs',
            action='store',
            dest='dbs',
            required=True,
            type=str,
            help='List of databases, e.g. TMI:TMI_MMR:6666,PKI:PKI_WHW_MMR:6667',
        )

    def handle(self, dbs, *args, **options):
        conns = None
        try:
            conns = utils.get_dbconf(dbs)
            for pop in conns:
                conn = conns[pop]
                import_songs(conn)
                import_syllables(conn)
                import_spectrograms(conn)

        finally:
            for dbconf in conns:
                conn = conns[dbconf]
                if conn is not None:
                    conn.close()