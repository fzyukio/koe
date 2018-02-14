import sys

import psycopg2
from django.core.management.base import BaseCommand

from koe.management.commands import utils
from koe.management.commands.import_luscinia import import_pcm, get_wav_info
from koe.models import AudioFile
from root.utils import wav_path

PY3 = sys.version_info[0] == 3
if PY3:
    str_to_bytes = lambda x: str.encode(x, encoding='LATIN-1')
else:
    str_to_bytes = lambda x: x


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
        # Correct false wav info
        for af in AudioFile.objects.all():
            wav_file_path = wav_path(af.name, 'wav')
            fs, length = get_wav_info(wav_file_path)
            if fs != af.fs or length != af.length:
                print('Correct file {}, originally length={} fs={}, now length={}, fs={}'.format(af.name, af.length, af.fs, length, fs))
                af.fs = fs
                af.length = length
                af.save()

        conns = None
        try:
            conns = utils.get_dbconf(dbs)
            for pop in conns:
                conn = conns[pop]
                cur = conn.cursor()
                bitrate = 16
                song_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

                song_cur.execute('select w.framesize, w.stereo, w.samplerate, w.ssizeinbits, w.songid, s.name '
                                 'from wavs w join songdata s on w.songid=s.id where w.ssizeinbits={}'.format(bitrate))

                songs = song_cur.fetchall()
                for song in songs:
                    song_name = song['name']
                    # Import WAV data and save as WAV and MP3 files
                    wav_file_path = '/tmp/{}'.format(song_name)
                    mp3_file_path = '/tmp/{}.mp3'.format(song_name)
                    fs, length = import_pcm(song, cur, song_name, wav_file_path, mp3_file_path)

                    fs1, length1 = get_wav_info(wav_file_path)

                    if fs != fs1 or length != length1:
                        print('-------SHIT--------')

                    print('Song {} length = {} fs = {} time = {}, length1 = {} fs1 = {} time1 = {}'
                          .format(song_name, length, fs, length / fs, length1, fs1, length1 / fs1))
        finally:
            for dbconf in conns:
                conn = conns[dbconf]
                if conn is not None:
                    conn.close()