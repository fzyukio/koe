import json

from django.conf import settings
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.generic import TemplateView, FormView

from koe.feature_utils import extract_database_measurements, construct_ordination, calculate_similarity
from koe.forms import SongPartitionForm, FeatureExtrationForm, ContactUsForm, OrdinationExtractionForm,\
    SimilarityExtractionForm
from koe.model_utils import get_user_databases, get_or_error
from koe.models import AudioFile, AudioTrack,\
    DerivedTensorData, Database, TemporaryDatabase, DataMatrix, Task, TaskProgressStage, Ordination, SimilarityIndex
from koe.request_handlers.templates import populate_context
from root.models import User, ExtraAttrValue
from root.utils import SendEmailThread, get_referrer_pathname
from root.views import can_have_exception


class SegmentationView(TemplateView):
    """
    The view of song segmentation page
    """

    template_name = "segmentation.html"
    page_name = "segmentation"

    def get_context_data(self, **kwargs):
        context = super(SegmentationView, self).get_context_data(**kwargs)
        populate_context(self, context)
        user = self.request.user

        file_id = get_or_error(kwargs, 'file_id')
        audio_file = get_or_error(AudioFile, dict(id=file_id))
        track = audio_file.track
        individual = audio_file.individual
        quality = audio_file.quality
        date = track.date if track else None
        species = individual.species if individual else None

        context['file_id'] = file_id
        context['length'] = audio_file.length
        context['fs'] = audio_file.fs
        context['database'] = audio_file.database.id

        context['song_info'] = {
            'Length': '{:5.2f} secs'.format(audio_file.length / audio_file.fs),
            'Name': audio_file.name,
            'Species': str(species) if species else 'Unknown',
            'Date': date.strftime(settings.DATE_INPUT_FORMAT) if date else 'Unknown',
            'Quality': quality if quality else 'Unknown',
            'Track': track.name if track else 'Unknown',
            'Individual': individual.name if individual else 'Unknown',
            'Sex': individual.gender if individual else 'Unknown'
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
        referrer_pathname = get_referrer_pathname(self.request)
        context = super(SongPartitionView, self).get_context_data(**kwargs)

        # Note: in FormView, url params exist in self.kwargs, not **kwargs.
        track_id = self.kwargs.get('track_id', None)
        if AudioTrack.objects.filter(id=track_id).exists():
            context['valid'] = True
        context['track_id'] = track_id
        context['referrer_pathname'] = referrer_pathname
        populate_context(self, context)

        return context

    def form_invalid(self, form):
        context = self.get_context_data()
        context['form'] = form
        context['valid'] = False
        rendered = render_to_string('partials/track-info-form.html', context=context)
        return HttpResponse(json.dumps(dict(message=rendered)))

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

        rendered = render_to_string('partials/track-info-form.html', context=context)
        return HttpResponse(json.dumps(dict(message=rendered)))


class TensorvizView(TemplateView):
    template_name = 'tensorviz.html'

    def get_context_data(self, **kwargs):
        context = super(TensorvizView, self).get_context_data(**kwargs)
        tensor_name = get_or_error(kwargs, 'tensor_name')
        tensor = get_or_error(DerivedTensorData, dict(name=tensor_name))

        context['config_file'] = '/' + tensor.get_config_path()
        return context


def get_incomplete_tasks(target_class):
    all_incomplete_dms = target_class.objects.filter(task__stage__lt=TaskProgressStage.COMPLETED)
    subtasks = Task.objects.filter(parent__in=all_incomplete_dms.values_list('task', flat=True),
                                   stage__lt=TaskProgressStage.COMPLETED)
    task2subs = {}
    for sub in subtasks:
        task_id = sub.parent.id
        if task_id in task2subs:
            task2subs[task_id].append(sub)
        else:
            task2subs[task_id] = [sub]

    dms2tasks = [(dm, task2subs.get(dm.task.id, [])) for dm in all_incomplete_dms]
    return dms2tasks


class FeatureExtrationView(FormView):
    form_class = FeatureExtrationForm
    page_name = 'feature-extraction'
    template_name = 'feature-extraction.html'

    def get_context_data(self, **kwargs):
        context = super(FeatureExtrationView, self).get_context_data(**kwargs)
        populate_context(self, context)
        database = context['current_database']

        if database is not None:
            if isinstance(database, TemporaryDatabase):
                data_matrices = DataMatrix.objects.filter(tmpdb=database)
            else:
                data_matrices = DataMatrix.objects.filter(database=database)

            completed_dms = data_matrices.filter(Q(task=None) | Q(task__stage__gte=TaskProgressStage.COMPLETED))
            incomplete_dms = data_matrices.filter(task__stage__lt=TaskProgressStage.COMPLETED)

            context['completed_dms'] = completed_dms
            context['incomplete_dms'] = incomplete_dms
        context['all_incomplete_dms2tasks'] = get_incomplete_tasks(DataMatrix)

        return context

    def form_invalid(self, form):
        context = self.get_context_data()
        rendered = render_to_string('partials/feature-selection-form.html', context=context)

        return HttpResponse(json.dumps(dict(message=dict(success=False, html=rendered))))

    def form_valid(self, form):
        post_data = self.request.POST
        user = self.request.user
        form_data = form.cleaned_data
        name = form_data.get('name', None)
        data_matrix = form_data.get('data_matrix', None)

        has_error = False

        if data_matrix:
            form.add_error('data_matrix', 'Already extracted')
            has_error = True

        if 'database' in post_data:
            database_id = int(post_data['database'])
            database = get_or_error(Database, dict(id=int(database_id)))
            if DataMatrix.objects.filter(database=database, name=name).exists():
                form.add_error('name', 'This name is already taken')
                has_error = True
            dm = DataMatrix(database=database)
        else:
            database_id = get_or_error(post_data, 'tmpdb')
            database = get_or_error(TemporaryDatabase, dict(id=int(database_id)))
            if DataMatrix.objects.filter(tmpdb=database, name=name).exists():
                form.add_error('name', 'This name is already taken')
                has_error = True
            dm = DataMatrix(tmpdb=database)

        if has_error:
            context = self.get_context_data()
            context['form'] = form
            rendered = render_to_string('partials/feature-selection-form.html', context=context)
            return HttpResponse(json.dumps(dict(message=dict(success=False, html=rendered))))

        features = form_data['features'].order_by('id')
        aggregations = form_data['aggregations'].order_by('id')

        dm.name = name
        dm.ndims = 0
        dm.features_hash = '-'.join(list(map(str, features.values_list('id', flat=True))))
        dm.aggregations_hash = '-'.join(list(map(str, aggregations.values_list('id', flat=True))))
        dm.save()

        task = Task(user=user, target='{}:{}'.format(DataMatrix.__name__, dm.id))
        task.save()
        dm.task = task
        dm.save()

        extract_database_measurements.delay(task.id)

        context = self.get_context_data()
        context['task'] = task
        rendered = render_to_string('partials/feature-extraction-tasks.html', context=context)
        return HttpResponse(json.dumps(dict(message=dict(success=True, html=rendered))))


class OrdinationExtrationView(FormView):
    form_class = OrdinationExtractionForm
    page_name = 'ordination-extraction'
    template_name = 'ordination-extraction.html'

    def get_context_data(self, **kwargs):
        context = super(OrdinationExtrationView, self).get_context_data(**kwargs)
        populate_context(self, context)
        database = context['current_database']

        if database is not None:
            if isinstance(database, TemporaryDatabase):
                data_matrices = DataMatrix.objects.filter(tmpdb=database)
            else:
                data_matrices = DataMatrix.objects.filter(database=database)

            completed_dms = data_matrices.filter(Q(task=None) | Q(task__stage__gte=TaskProgressStage.COMPLETED))
            all_ords = Ordination.objects.filter(dm__in=completed_dms)

            completed_ords = all_ords.filter(Q(task=None) | Q(task__stage__gte=TaskProgressStage.COMPLETED))
            # incomplete_ords = all_ords.filter(task__stage__lt=TaskProgressStage.COMPLETED)

            context['completed_dms'] = completed_dms
            context['completed_ords'] = completed_ords
            # context['incomplete_ords'] = incomplete_ords
        context['all_incomplete_ords2tasks'] = get_incomplete_tasks(Ordination)

        return context

    def form_invalid(self, form):
        context = self.get_context_data()
        rendered = render_to_string('partials/ordination-selection-form.html', context=context)

        return HttpResponse(json.dumps(dict(message=dict(success=False, html=rendered))))

    def form_valid(self, form):
        user = self.request.user
        form_data = form.cleaned_data
        ord_id = form_data.get('ordination', None)

        has_error = False

        if ord_id:
            form.add_error('ordination', 'Already extracted')
            has_error = True

        dm_id = form_data['data_matrix']
        method = form_data['method']
        ndims = form_data['ndims']
        params = form_data['params']
        params = Ordination.clean_params(params)

        dm = get_or_error(DataMatrix, dict(id=dm_id))
        if Ordination.objects.filter(dm=dm, method=method, ndims=ndims, params=params).exists():
            form.add_error('ordination', 'Already extracted')
            has_error = True

        if has_error:
            context = self.get_context_data()
            context['form'] = form
            rendered = render_to_string('partials/ordination-selection-form.html', context=context)
            return HttpResponse(json.dumps(dict(message=dict(success=False, html=rendered))))

        ord = Ordination(dm=dm, method=method, ndims=ndims, params=params)
        ord.save()

        task = Task(user=user, target='{}:{}'.format(Ordination.__name__, ord.id))
        task.save()
        ord.task = task
        ord.save()

        construct_ordination.delay(task.id)

        context = self.get_context_data()
        context['task'] = task
        rendered = render_to_string('partials/ordination-extraction-tasks.html', context=context)
        return HttpResponse(json.dumps(dict(message=dict(success=True, html=rendered))))


class SimilarityExtrationView(FormView):
    form_class = SimilarityExtractionForm
    page_name = 'similarity-extraction'
    template_name = 'similarity-extraction.html'

    def get_context_data(self, **kwargs):
        context = super(SimilarityExtrationView, self).get_context_data(**kwargs)
        populate_context(self, context)
        database = context['current_database']

        if database is not None:
            if isinstance(database, TemporaryDatabase):
                data_matrices = DataMatrix.objects.filter(tmpdb=database)
            else:
                data_matrices = DataMatrix.objects.filter(database=database)

            completed_dms = data_matrices.filter(Q(task=None) | Q(task__stage__gte=TaskProgressStage.COMPLETED))
            all_ords = Ordination.objects.filter(dm__in=completed_dms)

            completed_ords = all_ords.filter(Q(task=None) | Q(task__stage__gte=TaskProgressStage.COMPLETED))

            context['completed_dms'] = completed_dms
            context['completed_ords'] = completed_ords

        context['all_incomplete_sims2tasks'] = get_incomplete_tasks(SimilarityIndex)

        return context

    def form_invalid(self, form):
        context = self.get_context_data()
        rendered = render_to_string('partials/similarity-selection-form.html', context=context)

        return HttpResponse(json.dumps(dict(message=dict(success=False, html=rendered))))

    def form_valid(self, form):
        user = self.request.user
        form_data = form.cleaned_data
        ord_id = form_data.get('ordination', None)
        dm_id = form_data.get('data_matrix', None)

        has_error = False

        if (not ord_id and not dm_id) or (ord_id and dm_id):
            form.add_error('ordination', 'Either ordination or data matrix must be chosen, but not both')
            form.add_error('data_matrix', 'Either ordination or data matrix must be chosen, but not both')
            has_error = True

        if dm_id:
            dm = get_or_error(DataMatrix, dict(id=dm_id))
            si = SimilarityIndex.objects.filter(dm=dm).first()
            if si is not None:
                form.add_error('data_matrix', 'Already extracted')
                has_error = True
            else:
                si = SimilarityIndex(dm=dm)
        else:
            ord = get_or_error(Ordination, dict(id=ord_id))
            si = SimilarityIndex.objects.filter(ord=ord).first()
            if si is not None:
                form.add_error('ordination', 'Already extracted')
                has_error = True
            else:
                si = SimilarityIndex(ord=ord, dm=ord.dm)

        if has_error:
            context = self.get_context_data()
            context['form'] = form
            rendered = render_to_string('partials/similarity-selection-form.html', context=context)
            return HttpResponse(json.dumps(dict(message=dict(success=False, html=rendered))))

        si.save()

        task = Task(user=user, target='{}:{}'.format(SimilarityIndex.__name__, si.id))
        task.save()
        si.task = task
        si.save()

        calculate_similarity.delay(task.id)

        context = self.get_context_data()
        context['task'] = task
        rendered = render_to_string('partials/similarity-extraction-tasks.html', context=context)
        return HttpResponse(json.dumps(dict(message=dict(success=True, html=rendered))))


class ContactUsView(FormView):
    template_name = 'contact-us.html'
    page_name = 'contact-us'
    form_class = ContactUsForm

    def get_context_data(self, **kwargs):
        referrer_pathname = get_referrer_pathname(self.request)
        context = super(ContactUsView, self).get_context_data(**kwargs)
        context['referrer_pathname'] = referrer_pathname
        return context

    def form_invalid(self, form):
        context = self.get_context_data()
        rendered = render_to_string('partials/contact-us-form.html', context=context)

        return HttpResponse(json.dumps(dict(message=dict(success=False, html=rendered))))

    def form_valid(self, form, **kwargs):
        data = form.cleaned_data

        superuser = User.objects.get(username='superuser')

        subject = 'Someone just contacted Koe'
        template = 'contact-received'

        send_email_thread = SendEmailThread(subject, template, [superuser.email], context=data)
        send_email_thread.start()

        rendered = render_to_string('support-confirmation.html')
        return HttpResponse(json.dumps(dict(message=dict(success=True, html=rendered))))


def get_home_page(request):
    user = request.user
    if user.is_authenticated:
        current_database = get_user_databases(user)
        if current_database is None:
            return redirect('dashboard')
        return redirect('songs')
    return render(request, 'home_page.html')


def extra_syllables_context(request, context):
    database = context['current_database']
    user = request.user
    if database:
        if isinstance(database, Database):
            similarities = SimilarityIndex.objects.filter(Q(dm__database=database) | Q(ord__dm__database=database))
            cur_sim_val = ExtraAttrValue.objects\
                .filter(attr=settings.ATTRS.user.database_sim_attr, user=user, owner_id=database.id).first()
        else:
            similarities = SimilarityIndex.objects.filter(Q(dm__tmpdb=database) | Q(ord__dm__tmpdb=database))
            cur_sim_val = ExtraAttrValue.objects\
                .filter(attr=settings.ATTRS.user.tmpdb_sim_attr, user=user, owner_id=database.id).first()

        context['similarities'] = similarities

        cur_sim_id = None
        if cur_sim_val:
            cur_sim_id = int(cur_sim_val.value)

        sim_id = request.GET.get('similarity', None)
        if sim_id is None:
            if cur_sim_id is not None:
                sim_id = cur_sim_id
        else:
            sim_id = int(sim_id)
            if cur_sim_id is not None and cur_sim_id != sim_id:
                cur_sim_val.value = str(sim_id)
                cur_sim_val.save()

        if sim_id is None:
            current_similarity = similarities.first()
        else:
            current_similarity = SimilarityIndex.objects.filter(id=sim_id).first()
        context['current_similarity'] = current_similarity
    return context


def extra_view_ordination_context(request, context):
    database = context['current_database']
    viewas = context['viewas']

    if isinstance(database, Database):
        q = Q(dm__database=database)
        context['db_type'] = 'Database'
    else:
        q = Q(dm__tmpdb=database)
        context['db_type'] = 'Collection'

    ordinations = Ordination.objects.filter(q & (Q(task=None) | Q(task__stage=TaskProgressStage.COMPLETED)))
    ord_id = request.GET.get('ordination', None)
    if ord_id is None:
        current_ordination = ordinations.first()
    else:
        current_ordination = get_or_error(Ordination, dict(id=ord_id))
    context['current_ordination'] = current_ordination
    context['ordinations'] = ordinations

    if current_ordination:
        bytes_path = current_ordination.get_bytes_path()
        metadata_path = reverse('ordination-meta',
                                kwargs={'ord_id': current_ordination.id, 'viewas': viewas.username})

        context['metadata_path'] = metadata_path
        context['bytes_path'] = '/' + bytes_path
    return context


extra_context = {
    'syllables': extra_syllables_context,
    'view-ordination': extra_view_ordination_context
}


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

            extra_context_func = extra_context.get(self.__class__.page_name, None)
            if extra_context_func:
                extra_context_func(self.request, context)

            return context

        @can_have_exception
        def get(self, request, *args, **kwargs):
            return super(View, self).get(request, *args, **kwargs)

    return View.as_view()
