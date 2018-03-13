"""
Import syllables (not elements) from luscinia (after songs have been imported)
"""
import array
import contextlib
import datetime
import os
import re
import sys
import wave
from logging import warning

import numpy as np
import psycopg2
import pydub
from PIL import Image
from django.core.management.base import BaseCommand
from progress.bar import Bar
from scipy import signal

from koe import wavfile as wf
from koe.colourmap import *
from koe.management.commands import utils
from koe.management.commands.utils import get_syllable_end_time, wav_2_mono
from koe.models import AudioFile, Segmentation, Segment, AudioTrack, Individual, Database, DatabaseAssignment, \
    DatabasePermission
from root.models import ExtraAttr, ExtraAttrValue, ValueTypes, User
from root.utils import wav_path, mp3_path, ensure_parent_folder_exists, spect_fft_path, spect_mask_path

COLOURS = [[69, 204, 255], [73, 232, 62], [255, 212, 50], [232, 75, 48], [170, 194, 102]]
FF_COLOUR = [0, 0, 0]
AXIS_COLOUR = [127, 127, 127]

window_size = 256
noverlap = 256 * 0.75
window = signal.get_window('hann', 256)
low_bound = 800
scale = window.sum()
roi_max_width = 1200
roi_pad_width = 10

global_min_spect_pixel = -9.421019554138184
global_max_spect_pixel = 2.8522987365722656
global_spect_pixel_range = global_max_spect_pixel - global_min_spect_pixel
interval64 = global_spect_pixel_range / 63


name_regex = re.compile('(\w{3})_(\d{4})_(\d{2})_(\d{2})_([\w\d]+)_(\d+)_(\w+)\.(B|EX|VG|G|OK)(\.[^ ]*)?\.wav')
note_attr, _ = ExtraAttr.objects.get_or_create(klass=AudioFile.__name__, name='note', type=ValueTypes.LONG_TEXT)


PY3 = sys.version_info[0] == 3
if PY3:
    str_to_bytes = lambda x: str.encode(x, encoding='LATIN-1')
else:
    str_to_bytes = lambda x: x


def get_wav_info(audio_file):
    """
    Retuen fs and length of an audio without readng the entire file
    :param audio_file:
    :return:
    """
    with contextlib.closing(wave.open(audio_file, 'r')) as f:
        nframes = f.getnframes()
        rate = f.getframerate()
    return rate, nframes


def import_pcm(song, cur, song_name, wav_file_path=None, mp3_url=None):
    if wav_file_path is None:
        wav_file_path = wav_path(song_name)
    if mp3_url is None:
        mp3_url = mp3_path(song_name)

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

    if not os.path.isfile(mp3_url):
        ensure_parent_folder_exists(mp3_url)
        sound = pydub.AudioSegment.from_wav(wav_file_path)
        sound.export(mp3_url, format='mp3')

    return fs, length


def import_song_info(conn, user):
    song_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    song_cur.execute('select i.name as iname, s.call_context, s.name as sname from songdata s join individual i on s.individualid=i.id')
    songs = song_cur.fetchall()

    audio_files = AudioFile.objects.all()
    db_song_name_to_obj = {x.name : x for x in audio_files}

    bar = Bar('Importing song info ...', max=len(songs))

    for song in songs:
        song_name = song['sname']
        audio_file = db_song_name_to_obj.get(song_name, None)

        if audio_file:
            audio_file_id = audio_file.id
            # Populate info such as individuals, location, ...
            matches = name_regex.match(song_name)
            if matches is None:
                warning('File {} doesn\'t conform to the name pattern'.format(song_name))
            else:
                location = matches.group(1)
                bar.next()

                day = int(matches.group(4))
                year = int(matches.group(2))
                month = int(matches.group(3))

                date = datetime.date(year, month, day)
                track_id = matches.group(5)
                gender = matches.group(7)
                quality = matches.group(8)
                song_note = song['call_context']
                individual_name = song['iname']

                track_name = '{}_{}_{}'.format(location, date.strftime('%Y-%m-%d'), track_id)

                track, _ = AudioTrack.objects.get_or_create(name=track_name, date=date)

                individual, _ = Individual.objects.get_or_create(name=individual_name, gender=gender)
                audio_file.track = track
                audio_file.individual = individual
                audio_file.quality = quality
                audio_file.save()

                if song_note and song_note.strip() != 'null':
                    ExtraAttrValue.objects.get_or_create(user=user, attr=note_attr, owner_id=audio_file_id, value=song_note)

    bar.finish()


def import_syllables(conn):
    """
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
        song_name = row[0]
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

    bar = Bar('Importing syllables ...', max=len(songs_2_syllables))
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

        # print('Processed song {}'.format(song))
        bar.next()
    bar.finish()


def import_songs(conn, database):
    song_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    song_cur.execute('select w.framesize, w.stereo, w.samplerate, w.ssizeinbits, w.songid, s.name '
                     'from wavs w join songdata s on w.songid=s.id')
    songs = song_cur.fetchall()
    bar = Bar('Importing song PCM ...', max=len(songs))
    for song in songs:
        song_name = song['name']
        audio_file = AudioFile.objects.filter(name=song_name).first()

        # Import WAV data and save as WAV and MP3 files
        fs, length = import_pcm(song, cur, song_name)
        bar.song_name = song_name
        bar.next()
        if audio_file is None:
            AudioFile.objects.create(name=song_name, length=length, fs=fs, database=database)
    bar.finish()


def import_signal_mask(conn):
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
        song_info[song_name] = (song['id'], song['maxfreq'], song['dy'])

    segments_info = Segment.objects\
        .filter(segmentation__audio_file__name__in=song_info.keys())\
        .values_list('id', 'segmentation__audio_file__name', 'start_time_ms', 'end_time_ms')

    n = len(segments_info)
    bar = Bar('Importing segments ...', max=n)

    for seg_id, song_name, start, end in segments_info:
        if song_name not in song_info:
            continue
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
                'select starttime, timelength, fundfreq, gapbefore, gapafter, maxf, dy,'
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

            syl_max_ff = 0
            syl_min_ff = 999999
            syl_combined_ff = None

            for el_idx, el in enumerate(el_rows):
                # signal = list(map(int, el['signal'].strip().split(' ')))
                fundfreq = np.array(el['fundfreq'].strip().split(' '), dtype='|S32').astype(np.float)
                el_max_ff = fundfreq[0]
                el_min_ff = fundfreq[1]

                # the first 4 numbers of fundfreq are: max, min, ? (no idea) and ? (no idea), so we ignore them
                fundfreq = fundfreq[4:]
                if el_idx == 0:
                    syl_combined_ff = fundfreq
                else:
                    syl_combined_ff = np.concatenate((syl_combined_ff, fundfreq))

                fundfreq = (fundfreq / nyquist * height).astype(np.int)

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

                syl_max_ff = max(syl_max_ff, el_max_ff)
                syl_min_ff = min(syl_min_ff, el_min_ff)
            syl_mean_ff = np.mean(syl_combined_ff)

            Segment.objects.filter(id=seg_id).update(mean_ff=syl_mean_ff)
            Segment.objects.filter(id=seg_id).update(max_ff=syl_max_ff)
            Segment.objects.filter(id=seg_id).update(min_ff=syl_min_ff)

            img = Image.fromarray(img_data_rgb)
            thumbnail_width = int(img.size[0])
            thumbnail_height = int(img.size[1] * 0.3)

            img = img.resize((thumbnail_width, thumbnail_height))

            if syl_idx > 0:
                warning('Syl_idx > 0')
                file_path = spect_mask_path('{}_{}'.format(seg_id, syl_idx))
            else:
                file_path = spect_mask_path('{}'.format(seg_id))
            ensure_parent_folder_exists(file_path)

            img.save(file_path, format='PNG')
        bar.next()
    bar.finish()


def extract_spectrogram():
    """
    Extract raw sepectrograms for all segments (Not the masked spectrogram from Luscinia)
    :return:
    """
    values_list = Segment.objects.values_list('id', 'segmentation__audio_file__id', 'segmentation__audio_file__name','start_time_ms', 'end_time_ms')
    audio_to_segs = {}
    for id, song_id, song_name, start, end in values_list:
        key = (song_name, song_id)
        if key not in audio_to_segs:
            audio_to_segs[key] = [(id, start, end)]
        else:
            audio_to_segs[key].append((id, start, end))

    n = len(audio_to_segs)
    bar = Bar('Exporting spects ...', max=n)

    for (song_name, song_id), seg_list in audio_to_segs.items():
        count = 0
        for seg_id, start, end in seg_list:
            seg_spect_path = spect_fft_path(str(seg_id), 'syllable')
            if os.path.isfile(seg_spect_path):
                count += 1
        if count == len(seg_list):
            bar.next()
            continue

        filepath = wav_path(song_name)

        fs, sig = wav_2_mono(filepath)
        duration_ms = len(sig) * 1000 / fs

        _, _, s = signal.stft(sig, fs=fs, window=window, noverlap=noverlap, nfft=window_size, return_onesided=True)
        file_spect = np.abs(s * scale)

        height, width = np.shape(file_spect)
        file_spect = np.flipud(file_spect)

        try:

            file_spect = np.log10(file_spect)
            file_spect = ((file_spect - global_min_spect_pixel) / interval64)
            file_spect[np.isinf(file_spect)] = 0
            file_spect = file_spect.astype(np.int)

            file_spect = file_spect.reshape((width * height,), order='C')
            file_spect[file_spect >= 64] = 63
            file_spect_rgb = np.empty((height, width, 3), dtype=np.uint8)
            file_spect_rgb[:, :, 0] = cm_red[file_spect].reshape((height, width)) * 255
            file_spect_rgb[:, :, 1] = cm_green[file_spect].reshape((height, width)) * 255
            file_spect_rgb[:, :, 2] = cm_blue[file_spect].reshape((height, width)) * 255

            file_spect_img = Image.fromarray(file_spect_rgb)
            file_spect_path = spect_fft_path(song_id, 'song')
            ensure_parent_folder_exists(file_spect_path)
            if not os.path.isfile(file_spect_path):
                file_spect_img.save(file_spect_path, format='PNG')

            for seg_id, start, end in seg_list:
                roi_start = int(start / duration_ms * width)
                roi_end = int(np.ceil(end / duration_ms * width))

                seg_spect_rgb = file_spect_rgb[:, roi_start:roi_end, :]
                seg_spect_img = Image.fromarray(seg_spect_rgb)
                seg_spect_path = spect_fft_path(str(seg_id), 'syllable')
                ensure_parent_folder_exists(seg_spect_path)

                if not os.path.isfile(seg_spect_path):
                    seg_spect_img.save(seg_spect_path, format='PNG')

        except Exception as e:
            warning('Error occured at song id: {}'.format(song_id))
            raise e

        bar.next()
    bar.finish()


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

        parser.add_argument(
            '--database-name',
            action='store',
            dest='database_name',
            required=True,
            type=str,
            help='E.g Bellbird, Whale, ...',
        )

        parser.add_argument(
            '--owner',
            action='store',
            dest='username',
            default='wesley',
            type=str,
            help='Name of the person who owns this database',
        )

    def handle(self, dbs, database_name, username, *args, **options):
        user = User.objects.get(username=username)
        database = Database.objects.get_or_create(name=database_name)
        DatabaseAssignment.objects.get_or_create(user=user, database=database, permission=DatabasePermission.EDIT)

        conns = None
        try:
            conns = utils.get_dbconf(dbs)
            for pop in conns:
                conn = conns[pop]
                import_songs(conn, database)
                import_syllables(conn)
                import_signal_mask(conn)
                import_song_info(conn, user)

        finally:
            for dbconf in conns:
                conn = conns[dbconf]
                if conn is not None:
                    conn.close()

        extract_spectrogram()