import datetime
import io
import json
import os
import zipfile

import numpy as np
import pydub
from django.conf import settings
from django.core import serializers
from django.db import transaction
from django.http import HttpResponse
from django.views.generic import TemplateView

from koe.models import AudioFile, Segment, HistoryEntry, DistanceMatrix
from root.models import ExtraAttrValue
from root.utils import history_path, ensure_parent_folder_exists

__all__ = ['get_segment_audio', 'download_history', 'import_history', 'delete_history']

# Use this to change the volume of the segment. Audio segment will be increased in volume if its maximum does not
# reached this level, and vise verse
normalised_max = pow(2, 31)


def match_target_amplitude(sound, target_dBFS):
    change_in_dBFS = target_dBFS - sound.dBFS
    if change_in_dBFS > 0:
        return sound.apply_gain(change_in_dBFS)
    return sound


def download_history(request):
    extra_attr_values = ExtraAttrValue.objects.filter(user=request.user)
    retval = serializers.serialize('json', extra_attr_values)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_BZIP2, False) as zip_file:
        zip_file.writestr('root.extraattrvalue.json', retval)
    binary_content = zip_buffer.getvalue()

    he = HistoryEntry.objects.create(user=request.user, time=datetime.datetime.now())

    filename = he.filename
    filepath = history_path(filename)
    ensure_parent_folder_exists(filepath)

    with open(filepath, 'wb') as f:
        f.write(binary_content)

    return HttpResponse(filepath)


def delete_history(request):
    version_id = request.POST['version-id']
    try:
        HistoryEntry.objects.get(id=version_id).delete()
        return HttpResponse('ok')
    except Exception as e:
        return HttpResponse(e)


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

    song = pydub.AudioSegment.from_mp3(file_url)
    song_length = len(song)
    start = int(np.floor(song_length * start))
    end = int(np.ceil(song_length * end))
    audio_segment = song[start:end]

    # audio_segment = match_target_amplitude(audio_segment, -10)

    out = io.BytesIO()
    audio_segment.export(out, format='mp3')
    binary_content = out.getvalue()

    response = HttpResponse()
    response.write(binary_content)
    response['Content-Type'] = 'audio/mp3'
    response['Content-Length'] = len(binary_content)
    return response


def import_history(request):
    version_id = request.POST['version-id']
    he = HistoryEntry.objects.get(id=version_id)
    filepath = history_path(he.filename)

    with zipfile.ZipFile(filepath, "r") as zip_file:
        content = zip_file.read('root.extraattrvalue.json')
        new_entries = json.loads(content)

    extra_attr_values = []
    for entry in new_entries:
        owner_id = entry['fields']['owner_id']
        value = entry['fields']['value']
        attr_id = entry['fields']['attr']
        extra_attr_value = ExtraAttrValue(owner_id=owner_id, value=value, user=request.user)
        extra_attr_value.attr_id = attr_id
        extra_attr_values.append(extra_attr_value)

    with transaction.atomic():
        try:
            ExtraAttrValue.objects.filter(user=request.user).delete()
            ExtraAttrValue.objects.bulk_create(extra_attr_values)
            return HttpResponse('ok')
        except Exception as e:
            return HttpResponse(e)


class IndexView(TemplateView):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        dms = DistanceMatrix.objects.all().values_list('id', 'algorithm')
        dms = list(dms)
        context['dms'] = dms
        context['page'] = 'index'
        return context
