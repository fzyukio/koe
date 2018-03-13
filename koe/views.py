import datetime
import io
import json
import os
import zipfile

import markdown
import numpy as np
import pydub
from django.conf import settings
from django.core import serializers
from django.core.files import File
from django.db import transaction
from django.http import HttpResponse
from django.views.generic import FormView
from django.views.generic import TemplateView
from mdx_audio import AudioExtension

from koe.forms import HelpEditForm
from koe.model_utils import get_currents
from koe.models import AudioFile, Segment, HistoryEntry, Coordinate, DatabaseAssignment, DatabasePermission, Database
from root.models import ExtraAttrValue, ExtraAttr, User
from root.utils import history_path, ensure_parent_folder_exists

__all__ = ['get_segment_audio', 'save_history', 'import_history', 'delete_history']

# Use this to change the volume of the segment. Audio segment will be increased in volume if its maximum does not
# reached this level, and vise verse
normalised_max = pow(2, 31)

md = markdown.Markdown(safe_mode='escape', extensions=['fenced_code', 'tables', 'oembed', AudioExtension()])


def match_target_amplitude(sound, loudness):
    """
    Set the volume of an AudioSegment object to be a certain loudness
    :param sound: an AudioSegment object
    :param loudness: usually -10db is a good number
    :return: the modified sound
    """
    change_in_dBFS = loudness - sound.dBFS
    if change_in_dBFS > 0:
        return sound.apply_gain(change_in_dBFS)
    return sound


def save_history(request):
    """
    Save a copy of all ExtraAttrValue (labels, notes, ...) in a HistoryEntry
    :param request: must specify a comment to store with this copy
    :return: name of the zip file created
    """
    comment = request.POST['comment']
    comment_attr = ExtraAttr.objects.filter(klass=HistoryEntry.__name__, name='note').first()

    extra_attr_values = ExtraAttrValue.objects.filter(user=request.user).exclude(attr__klass=User.__name__)
    retval = serializers.serialize('json', extra_attr_values)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_BZIP2, False) as zip_file:
        zip_file.writestr('root.extraattrvalue.json', retval)
    binary_content = zip_buffer.getvalue()

    he = HistoryEntry.objects.create(user=request.user, time=datetime.datetime.now())
    ExtraAttrValue.objects.create(owner_id=he.id, user=request.user, value=comment, attr=comment_attr)

    filename = he.filename
    filepath = history_path(filename)
    ensure_parent_folder_exists(filepath)

    with open(filepath, 'wb') as f:
        f.write(binary_content)

    return HttpResponse(filename)


def delete_history(request):
    """
    Delete a HistoryEntry given its id
    :param request: must specify version-id
    :return:
    """
    version_id = request.POST['version-id']
    he = HistoryEntry.objects.get(id=version_id)
    creator = he.user
    if creator != request.user:
        raise Exception('Only {} can delete this version'.format(creator.username))

    he.delete()
    return HttpResponse('ok')


def get_segment_audio(request):
    """
    Return a playable audio segment given the file name and the endpoints (in range [0.0 -> 1.0]) where the segment
    begins and ends
    :param request: must specify segment-id, this is the ID of a Segment object to be played
    :return: a binary blob specified as audio/mp3, playable and volume set to -10dB
    """
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

    audio_segment = match_target_amplitude(audio_segment, -10)

    out = io.BytesIO()
    audio_segment.export(out, format='mp3')
    binary_content = out.getvalue()

    response = HttpResponse()
    response.write(binary_content)
    response['Content-Type'] = 'audio/mp3'
    response['Content-Length'] = len(binary_content)
    return response


def import_history(request):
    """
    Import a HistoryEntry from any user to this user.
    If this operation fails, the database is intact.
    :param request: must specify either : version-id, which is the id of the HistoryEntry object to be imported to
                                          or FILES['zipfile'] which should be created somewhere by Koe for someone
    :return: 'ok' if everything goes well. Otherwise the error message.
    """
    version_id = request.POST.get('version-id', None)
    zip_file = request.FILES.get('zipfile', None)

    if not (version_id or zip_file):
        raise ValueError('No ID or file provided. Abort.')

    if version_id:
        he = HistoryEntry.objects.get(id=version_id)
        file = open(history_path(he.filename), 'rb')
    else:
        file = File(file=zip_file)

    with zipfile.ZipFile(file, "r") as zip_file:
        try:
            content = zip_file.read('root.extraattrvalue.json')
        except KeyError as e:
            raise ValueError('This is not a Koe history file')
        try:
            new_entries = json.loads(content)
        except Exception as e:
            raise ValueError('The history content is malformed and cannot be parsed.')
    file.close()

    extra_attr_values = []
    for entry in new_entries:
        owner_id = entry['fields']['owner_id']
        value = entry['fields']['value']
        attr_id = entry['fields']['attr']
        extra_attr_value = ExtraAttrValue(owner_id=owner_id, value=value, user=request.user)
        extra_attr_value.attr_id = attr_id
        extra_attr_values.append(extra_attr_value)

    # Wrap all DB modification in one transaction to utilise the roll-back ability when things go wrong
    with transaction.atomic():
        ExtraAttrValue.objects.filter(user=request.user).exclude(attr__klass=User.__name__).delete()
        ExtraAttrValue.objects.bulk_create(extra_attr_values)
        return HttpResponse('ok')


class IndexView(TemplateView):
    """
    The view to index page
    """
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super(IndexView, self).get_context_data(**kwargs)
        user =self.request.user

        similarities, current_similarity, databases, current_database = get_currents(user)

        context['similarities'] = similarities.values_list('id', 'algorithm')
        context['databases'] = databases.values_list('id', 'name')
        context['current_database'] = (current_database.id, current_database.name, User.__name__)
        context['current_similarity'] = (current_similarity.id, current_similarity.algorithm, User.__name__)
        context['page'] = 'index'
        return context
