import io
import json
import os
import numpy as np
import pydub
import array

from django.conf import settings
from django.http import HttpResponse

from koe.models import AudioFile, Segment
from koe import wavfile as wf
from koe.utils import array_to_base64


__all__ = ['get_segment_audio']

# Use this to change the volume of the segment. Audio segment will be increased in volume if its maximum does not
# reached this level, and vise verse
normalised_max = pow(2, 31)


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
    segment_audio = wf.read_segment(file_url, start, end, mono=True, normalised=False)
    segment_audio = np.left_shift(segment_audio, 7)

    max_volume = np.max(segment_audio)
    gain = int(normalised_max / max_volume)
    segment_audio *= gain


    audio_segment = pydub.AudioSegment(
        segment_audio.tobytes(),
        frame_rate=audio_file.fs,
        sample_width=segment_audio.dtype.itemsize,
        channels=1
    )

    out = io.BytesIO()

    audio_segment.export('/tmp/blah1.mp3', format='mp3')
    # audio_segment_original = pydub.AudioSegment.from_wav(file_url)
    # audio_segment_original.export('/tmp/blah2.mp3', format='mp3')
    #
    # sound = pydub.AudioSegment.from_file(file_url)
    # samples = sound.get_array_of_samples()
    #
    # shifted_samples = np.right_shift(samples, 1)
    #
    # # now you have to convert back to an array.array
    # shifted_samples_array = array.array(sound.array_type, shifted_samples)
    #
    # new_sound = sound._spawn(shifted_samples_array)
    # new_sound.export('/tmp/blah3.mp3', format='mp3')

    # return HttpResponse(out.getvalue(), content_type='audio/mpeg')

    f = open('/tmp/blah1.mp3', "rb")
    response = HttpResponse()
    response.write(f.read())
    response['Content-Type'] = 'audio/mp3'
    response['Content-Length'] = os.path.getsize('/tmp/blah1.mp3')
    return response

    # response = HttpResponse(fsock, content_type="audio/mpeg")
    # # response['Content-Disposition'] = 'attachment; filename=filename.mp3'
    # return response

    # return HttpResponse(json.dumps(dict(fs=audio_file.fs, data=array_to_base64(segment_audio))))
