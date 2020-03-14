import os

from django.conf import settings
from django.core.management.base import BaseCommand

from koe.models import Segment, AudioFile
from root.models import ExtraAttrValue


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
            help='Search pattern',
        )

    def handle(self, commit, *args, **options):
        segment_ids = frozenset(Segment.objects.values_list('id', flat=True))
        mask_path = os.path.join(settings.MEDIA_URL, 'spect', 'mask')[1:]
        compressed_format = settings.AUDIO_COMPRESSED_FORMAT

        existing_masks = os.listdir(mask_path)

        for existing_mask in existing_masks:
            try:
                existing_mask_id = int(existing_mask[:-4])
                if existing_mask_id not in segment_ids:
                    filepath = '{}/{}'.format(mask_path, existing_mask)
                    print('Mask file {} is a ghost'.format(filepath))
                    if commit:
                        os.remove(filepath)
            except ValueError:
                print('Found weird named files: {}/{}'.format(mask_path, existing_mask))

        spect_path = os.path.join(settings.MEDIA_URL, 'spect', 'syllable')[1:]

        existing_spects = os.listdir(spect_path)

        for existing_spect in existing_spects:
            try:
                existing_spect_id = int(existing_spect[:-4])
                if existing_spect_id not in segment_ids:
                    filepath = '{}/{}'.format(spect_path, existing_spect)
                    print('Spect file {} is a ghost'.format(filepath))
                    if commit:
                        os.remove(filepath)
            except ValueError:
                print('Found weird named files: {}/{}'.format(spect_path, existing_spect))

        audio_file_names = AudioFile.objects.values_list('name', flat=True)
        audio_file_names_wav = []
        audio_file_names_compressed = []
        compressed_ext = '.{}'.format(compressed_format)
        for audio_file_name in audio_file_names:
            if audio_file_name.lower().endswith('.wav'):
                clean_name = audio_file_name[:-4]
            else:
                clean_name = audio_file_name
            audio_file_names_wav.append(clean_name + '.wav')
            audio_file_names_compressed.append(clean_name + compressed_ext)

        audio_file_names_wav = frozenset(audio_file_names_wav)
        audio_file_names_compressed = frozenset(audio_file_names_compressed)

        wav_path = os.path.join(settings.MEDIA_URL, 'audio', 'wav')[1:]
        compressed_path = os.path.join(settings.MEDIA_URL, 'audio', compressed_format)[1:]
        existing_wavs = os.listdir(wav_path)
        existing_compressed_files = os.listdir(compressed_path)

        ghost_wavs = [x for x in existing_wavs if x not in audio_file_names_wav]
        ghost_compressed_files = [x for x in existing_compressed_files if x not in audio_file_names_compressed]

        for wav in ghost_wavs:
            filepath = '{}/{}'.format(wav_path, wav)
            if os.path.isfile(filepath):
                print('Wav file {} is a ghost'.format(filepath))
                if commit:
                    os.remove(filepath)

        for compressed in ghost_compressed_files:
            filepath = '{}/{}'.format(compressed_path, compressed)
            if os.path.isfile(filepath):
                print('Compressed file {} is a ghost'.format(filepath))
                if commit:
                    os.remove(filepath)

        attr_values = ExtraAttrValue.objects.filter(attr__klass=Segment.__name__)
        attr_value_vl = attr_values.values_list('id', 'owner_id')
        ghost_attr_values = []
        for id, owner_id in attr_value_vl:
            if owner_id not in segment_ids:
                ghost_attr_values.append(id)

        print('Found {} ghost ExtraAttrValue of Segment'.format(len(ghost_attr_values)))
        if commit:
            ExtraAttrValue.objects.filter(id__in=ghost_attr_values).delete()

        audio_file_ids = frozenset(AudioFile.objects.values_list('id', flat=True))
        attr_values = ExtraAttrValue.objects.filter(attr__klass=AudioFile.__name__).exclude(owner_id__in=audio_file_ids)
        print('Found {} ghost ExtraAttrValue of AudioFile'.format(attr_values.count()))
        if commit:
            attr_values.delete()
