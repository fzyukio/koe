import os

from django.core.management.base import BaseCommand

from progress.bar import Bar

from koe.models import AudioFile, Segment
from koe.utils import wav_path
from koe.wavfile import read_segment


already_tested = 0


class Command(BaseCommand):
    def handle(self, *args, **options):
        # audio_file_path = '/Users/yfukuzaw/workspace/koe/user_data/audio/wav/52/201911142.wav'
        # begin_ms = 234
        # end_ms = 544
        # fs, length = get_wav_info(audio_file_path)
        # read_segment(audio_file_path, beg_ms=begin_ms, end_ms=end_ms, mono=True, normalised=True)

        # audio_files = AudioFile.objects.filter(fs__gt=320000)
        #
        # for audio_file in audio_files:
        #     segments = Segment.objects.filter(audio_file=audio_file)
        #     ratio = 48000 / audio_file.fs
        #     duration_ms = int(audio_file.length * 1000 /audio_file.fs)
        #     for segment in segments:
        #         beg_ms = segment.start_time_ms
        #         end_ms = segment.end_time_ms
        #
        #         new_beg = max(0, int(np.round(beg_ms * ratio)))
        #         new_end = min(int(np.round(end_ms * ratio)), duration_ms)
        #
        #         segment.start_time_ms = new_beg
        #         segment.end_time_ms = new_end
        #
        #         sid = segment.id
        #
        #         print('Change syllable #{} from [{} - {}] to [{} - {}]'.format(sid, beg_ms, end_ms, new_beg, new_end))
        #
        #         segment.save()

        audio_files = AudioFile.objects.all()
        num_segments = Segment.objects.all().count()
        num_tested = 0

        bar = Bar("Testing...", max=num_segments)
        for audio_file in audio_files:
            segments = Segment.objects.filter(audio_file=audio_file)
            num_segments = segments.count()
            if num_tested + num_segments < already_tested:
                num_tested += num_segments
                bar.next(num_segments)
                continue

            audio_file_path = wav_path(audio_file)
            for segment in segments:
                begin_ms = segment.start_time_ms
                end_ms = segment.end_time_ms
                if os.path.isfile(audio_file_path):
                    read_segment(
                        audio_file_path,
                        beg_ms=begin_ms,
                        end_ms=end_ms,
                        mono=True,
                        normalised=True,
                    )
                bar.next()
                num_tested += 1

        bar.finish()
