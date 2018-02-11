import array

import pydub
from django.core.management import BaseCommand
from django.test import RequestFactory

from koe.models import *
from koe import wavfile

request_factory = RequestFactory()


class Command(BaseCommand):
    def handle(self, wf=None, *args, **options):
        # target_dBFS = -10
        # afs = AudioFile.objects.all().values_list('name', flat=True)
        # for af in afs:
        #     file_url = audio_path(af, 'wav')
        #     song = pydub.AudioSegment.from_mp3(file_url)
        #     change_in_dBFS = target_dBFS - song.dBFS
        #
        #     if change_in_dBFS < 0:
        #         song.apply_gain(change_in_dBFS)
        #         print('{:.2f}: {}'.format(song.dBFS, af))

        pkls = ['/tmp/TMI_2015_10_06_CHJ023_01_F.G.HBr-WM.(A).wav.pkl', '/tmp/TMI_2015_10_13_CHJ025_03_M.G.RBr-lBM.(A).wav.pkl', '/tmp/TMI_2015_10_23_CHJ029_01_M.G.lBdG-YM.(A).wav.pkl', '/tmp/TMI_2015_10_23_CHJ029_02_M.G.lBdG-YM.(A).wav.pkl', '/tmp/TMI_2015_10_23_CHJ030_01_M.VG.lBdG-YM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ036_01_M.G.lBBk-OM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ036_02_M.G.lBBk-OM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ037_01_M.G.RdB-OM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ037_02_M.G.RdB-OM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ037_03_M.G.RdB-OM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ037_04_M.G.RdB-OM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ037_05_M.G.RdB-OM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ037_06_M.G.RdB-OM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ037_07_M.G.RdB-OM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ037_08_M.G.RdB-OM.(A).wav.pkl', '/tmp/TMI_2015_10_31_CHJ037_09_M.G.RdB-OM.(A).wav.pkl', '/tmp/TMI_2015_11_08_CHJ042_01_F.G.HY-WM.(A).wav.pkl', '/tmp/TMI_2015_11_25_CHJ050_01_F.G.HY-WM.(A).wav.pkl', '/tmp/TMI_2015_11_26_CHJ052_01_F.G.HR-RM.(A).wav.pkl', '/tmp/TMI_2015_12_01_CHJ054_01_M.G.RW-M.(A).wav.pkl', '/tmp/TMI_2015_12_12_CHJ065_01_F.G.lBO-BM.(A).wav.pkl', '/tmp/TMI_2015_12_12_CHJ066_01_F.G.lBO-BM.(A).wav.pkl', '/tmp/TMI_2015_12_31_CHJ070_01_F.G.lBO-BM.(A).wav.pkl']
        for pkl in pkls:
            with open(pkl, 'rb') as f:
                loaded = pickle.load(f)
            raw_pcm = loaded['raw_pcm']
            nchannels = loaded['nchannels']
            bitrate = loaded['bitrate']
            fs = loaded['fs']
            song_name = loaded['name']

            byte_per_frame = int(bitrate / 8)
            nframes_all_channel = int(len(raw_pcm) / byte_per_frame)
            nframes_per_channel = int(nframes_all_channel / nchannels)
            length = nframes_per_channel

            array1 = np.frombuffer(raw_pcm, dtype=np.ubyte)
            array2 = array1.reshape((nframes_per_channel, nchannels, byte_per_frame)).astype(np.uint8)

            data = array.array('i', raw_pcm)

            sound = pydub.AudioSegment(data=data, sample_width=byte_per_frame, frame_rate=fs, channels=nchannels)
            samples = sound.get_array_of_samples()


            sound.export('/tmp/fix-{}'.format(song_name), 'wav')
            wavfile.write('/tmp/bad-{}'.format(song_name), fs, array2, bitrate=bitrate)