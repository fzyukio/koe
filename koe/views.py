import json
import os

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.generic import TemplateView, FormView

from koe.forms import SongPartitionForm, FeatureExtrationForm
from koe.model_utils import get_user_databases, get_current_similarity, assert_permission, get_or_error
from koe.models import AudioFile, DatabaseAssignment, DatabasePermission, AudioTrack,\
    DerivedTensorData, FullTensorData, Database
from koe.ts_utils import make_subtensor
from root.models import User, ExtraAttrValue


def populate_context(obj, context, with_similarity=False):
    page_name = obj.__class__.page_name
    user = obj.request.user
    gets = obj.request.GET

    databases, current_database = get_user_databases(user)
    db_assignment = assert_permission(user, current_database, DatabasePermission.VIEW)

    specified_db = gets.get('database', None)
    if specified_db and specified_db != current_database.name:
        current_database = get_or_error(Database, dict(name=specified_db))
        db_assignment = assert_permission(user, current_database, DatabasePermission.VIEW)

        current_database_value = ExtraAttrValue.objects.filter(attr=settings.ATTRS.user.current_database,
                                                               owner_id=user.id, user=user).first()
        current_database_value.value = current_database.id
        current_database_value.save()

    context['databases'] = databases
    context['current_database'] = current_database
    context['current_database_owner_class'] = User.__name__
    context['current_database_owner_id'] = user.id
    context['db_assignment'] = db_assignment

    viewas = gets.get('viewas', user.username)
    viewas = get_or_error(User, dict(username=viewas))
    other_users = DatabaseAssignment.objects.filter(database=current_database, permission__gte=DatabasePermission.VIEW)\
        .values_list('user__id', flat=True)
    other_users = User.objects.filter(id__in=other_users)

    granularity = gets.get('granularity', 'label')
    context['viewas'] = viewas
    context['other_users'] = other_users

    context['granularity'] = granularity
    context['page'] = page_name

    if with_similarity:
        similarities, current_similarity = get_current_similarity(user, current_database)
        context['similarities'] = similarities

        if current_similarity:
            context['current_similarity_owner_class'] = User.__name__
            context['current_similarity'] = current_similarity


class SegmentationView(TemplateView):
    """
    The view of song segmentation page
    """

    template_name = "segmentation.html"

    def get_context_data(self, **kwargs):
        context = super(SegmentationView, self).get_context_data(**kwargs)
        user = self.request.user

        file_id = get_or_error(kwargs, 'file_id')
        audio_file = get_or_error(AudioFile, dict(id=file_id))
        db_assignment = assert_permission(user, audio_file.database, DatabasePermission.VIEW)
        track = audio_file.track
        individual = audio_file.individual
        quality = audio_file.quality
        date = track.date if track else None
        species = individual.species if individual else None

        context['page'] = 'segmentation'
        context['file_id'] = file_id
        context['db_assignment'] = db_assignment
        context['length'] = audio_file.length
        context['fs'] = audio_file.fs

        context['song_info'] = {
            'Length': '{:5.2f} secs'.format(audio_file.length / audio_file.fs),
            'Name': audio_file.name,
            'Species': str(species) if species else 'Unknown',
            'Date': date.strftime(settings.DATE_INPUT_FORMAT) if date else 'Unknown',
            'Quality': quality if quality else 'Unknown',
            'Track': track.name if track else 'Unknown',
            'Individual': individual.name if individual else 'Unknown',
            'Gender': individual.gender if individual else 'Unknown'
        }

        song_extra_attr_values_list = ExtraAttrValue.objects\
            .filter(user=user, attr__klass=AudioFile.__name__, owner_id=audio_file.id)\
            .values_list('attr__name', 'value')

        for attr, value in song_extra_attr_values_list:
            context['song_info']['Song\'s {}'.format(attr)] = value

        return context


class SongPartitionView(FormView):
    """
    The view of song segmentation page
    """

    template_name = "song-partition.html"
    form_class = SongPartitionForm
    page_name = 'song-partition'

    def get_initial(self):
        track_id = self.kwargs.get('track_id', None)
        return dict(track_id=track_id)

    def get_context_data(self, **kwargs):
        context = super(SongPartitionView, self).get_context_data(**kwargs)

        # Note: in FormView, url params exist in self.kwargs, not **kwargs.
        track_id = self.kwargs.get('track_id', None)
        if AudioTrack.objects.filter(id=track_id).exists():
            context['valid'] = True
        context['track_id'] = track_id
        populate_context(self, context)

        return context

    def form_invalid(self, form):
        context = self.get_context_data()
        context['form'] = form
        context['valid'] = False
        return render(self.request, 'partials/track-info-form.html', context=context)

    def form_valid(self, form):
        context = self.get_context_data()
        form_data = form.cleaned_data
        track_name = form_data['name']
        track_id = form_data['track_id']
        date = form_data['date']

        has_error = False
        track = None

        if track_id:
            track = AudioTrack.objects.filter(id=track_id).first()
        if track is None:
            track = AudioTrack.objects.filter(name=track_name).first()
            should_not_have_duplicate = True
        else:
            should_not_have_duplicate = False

        if track and should_not_have_duplicate:
            track_is_non_empty = AudioFile.objects.filter(track=track).exists()
            if track_is_non_empty:
                form.add_error('name', 'Track already exists and is not empty')
                has_error = True

        if not has_error:
            if track is None:
                track = AudioTrack(name=track_name)
            else:
                track.name = track_name

            if date:
                track.date = date

            track.save()
            context['track_id'] = track.id
            context['valid'] = True

        context['form'] = form

        rendered = render(self.request, 'partials/track-info-form.html', context=context)
        return HttpResponse(json.dumps(dict(message=rendered.content.decode('utf-8'))))


class TensorvizView(TemplateView):
    template_name = 'tensorviz.html'

    def get_context_data(self, **kwargs):
        context = super(TensorvizView, self).get_context_data(**kwargs)
        tensor_name = get_or_error(kwargs, 'tensor_name')
        tensor = get_or_error(DerivedTensorData, dict(name=tensor_name))

        context['config_file'] = '/' + tensor.get_config_path()
        return context


class TsnePlotlyView(TemplateView):
    template_name = 'tsne-plotly.html'

    def get_context_data(self, **kwargs):
        context = super(TsnePlotlyView, self).get_context_data(**kwargs)
        tensor_name = get_or_error(kwargs, 'tensor_name')
        tensor = get_or_error(DerivedTensorData, dict(name=tensor_name))

        bytes_path = tensor.get_bytes_path()
        metadata_path = reverse('tsne-meta', kwargs={'tensor_name': tensor.name})

        if not os.path.isfile(bytes_path):
            bytes_path = tensor.full_tensor.get_bytes_path()

        context['metadata_path'] = metadata_path
        context['bytes_path'] = '/' + bytes_path
        context['tensor'] = tensor
        return context


class FeatureExtrationView(FormView):
    form_class = FeatureExtrationForm
    page_name = 'feature-extraction'
    template_name = 'feature-extraction.html'

    def get_context_data(self, **kwargs):
        context = super(FeatureExtrationView, self).get_context_data(**kwargs)
        populate_context(self, context)
        return context

    def form_invalid(self, form):
        context = self.get_context_data()
        rendered = render_to_string('partials/feature-selection-form.html', context=context)

        return HttpResponse(json.dumps(dict(message=dict(html=rendered))))

    def form_valid(self, form):
        form_data = form.cleaned_data

        tensor_id = form_data.get('preset', None)
        tensor = None
        if tensor_id:
            tensor = get_or_error(DerivedTensorData, dict(id=int(tensor_id)))

        if tensor is None:
            features = form_data['features'].order_by('id')
            aggregations = form_data['aggregations'].order_by('id')

            database = form_data['database']
            full_tensor = get_or_error(FullTensorData, dict(database=database))

            annotator_id = form_data['annotator']
            dimreduce = form_data['dimreduce']
            ndims = form_data.get('ndims', None)

            annotator = get_or_error(User, dict(id=annotator_id))

            tensor = make_subtensor(self.request.user, full_tensor, annotator, features, aggregations, dimreduce, ndims)

        if tensor.dimreduce.startswith('tsne'):
            vizurl = reverse('tsne-plotly', kwargs={'tensor_name': tensor.name})
        else:
            vizurl = reverse('tsne', kwargs={'tensor_name': tensor.name})

        return HttpResponse(json.dumps(dict(message=vizurl)))


def get_view(name):
    """
    Get a generic TemplateBased view that uses only common context
    :param name: name of the view. A `name`.html must exist in the template folder
    :return:
    """
    class View(TemplateView):
        page_name = name
        template_name = name + '.html'

        def get_context_data(self, **kwargs):
            context = super(View, self).get_context_data(**kwargs)
            populate_context(self, context)
            return context

    return View.as_view()
