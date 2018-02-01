import json
import os

from django.conf import settings
from django.http import HttpResponse

from koe.models import AudioFile, Segment
from koe import wavfile as wf
from koe.utils import array_to_base64


__all__ = ['get_segment_audio']


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

    file_url = os.path.join(settings.BASE_DIR, audio_file.raw_file)
    segment_audio = wf.read_segment(file_url, start, end, mono=True)

    return HttpResponse(json.dumps(dict(fs=audio_file.fs, data=array_to_base64(segment_audio))))
