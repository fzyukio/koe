import io
import os

import numpy as np
import pydub
from django.conf import settings
from django.http import HttpResponse

from koe import wavfile as wf
from koe.models import AudioFile, Segment

__all__ = ['get_segment_audio']

# Use this to change the volume of the segment. Audio segment will be increased in volume if its maximum does not
# reached this level, and vise verse
normalised_max = pow(2, 31)


def match_target_amplitude(sound, target_dBFS):
    change_in_dBFS = target_dBFS - sound.dBFS
    return sound.apply_gain(change_in_dBFS)


def get_segment_audio(request):
    segment_id = request.POST.get('segment-id', None)

    if segment_id is None:
        start = float(request.POST['start'])
        end = float(request.POST['end'])
        file_id = request.POST['file-id']
        audio_file = AudioFile.objects.filter(pk=file_id).first()
    else:
        segment = Segment.objects.filter(pk=segment_id).first()
        audio_file = segment.segmentation.audio_file
        duration_ms = audio_file.length * 1000 / audio_file.fs
        start = segment.start_time_ms / duration_ms
        end = segment.end_time_ms / duration_ms

    file_url = os.path.join(settings.BASE_DIR, audio_file.mp3_path)
    # segment_audio = wf.read_segment(file_url, start, end, mono=True, normalised=False)
    # segment_audio = np.left_shift(segment_audio, 7)

    song = pydub.AudioSegment.from_mp3(file_url)
    song_length = len(song)
    start = int(np.floor(song_length * start))
    end = int(np.floor(song_length * end))
    audio_segment = song[start:end]
    # max_volume = np.max(segment_audio)
    # gain = int(normalised_max / max_volume)
    # gain = int(normalised_max / max_volume)
    # segment_audio *= gain
    #
    # audio_segment = pydub.AudioSegment(
    #     segment_audio.tobytes(),
    #     frame_rate=audio_file.fs,
    #     sample_width=segment_audio.dtype.itemsize,
    #     channels=1
    # )

    audio_segment = match_target_amplitude(audio_segment, -10)

    out = io.BytesIO()
    audio_segment.export(out, format='mp3')
    binary_content = out.getvalue()

    response = HttpResponse()
    response.write(binary_content)
    response['Content-Type'] = 'audio/mp3'
    response['Content-Length'] = len(binary_content)
    return response
