from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseServerError
from django.shortcuts import render

from koe import views
from koe.request_handlers import tensorviz
from root import urls as root_urls
from root import views as root_views

urlpatterns = [] + root_urls.urlpatterns


def handler500(request):
    """
    500 error handler which shows a dialog for user's feedback
    Ref: https://docs.sentry.io/clients/python/integrations/django/#message-references
    """
    return HttpResponseServerError(render(request, '500.html'))


urlpatterns += \
    [
        url(r'^admin/', admin.site.urls),
        url(r'^version/$', login_required(root_views.get_view('version')), name='version'),
        url(r'^syllables/$', login_required(views.SyllablesView.as_view()), name='syllables'),
        url(r'^syllables/(?P<from_user>[0-9a-zA-Z-_]+)/$$', login_required(views.SyllablesView.as_view()),
            name='syllables'),

        url(r'^songs/$', login_required(views.SongsView.as_view()), name='songs'),
        url(r'^songs/(?P<class>[0-9a-z-_]+)/$', login_required(views.SongsView.as_view()), name='songs'),
        url(r'^songs/(?P<class>[0-9a-z-_]+)/(?P<from_user>[0-9a-zA-Z-_]+)/$',
            login_required(views.SongsView.as_view()), name='songs'),

        url(r'^sequence-mining/$', login_required(views.SequenceMiningView.as_view()), name='sequence-mining'),
        url(r'^sequence-mining/(?P<class>[0-9a-z-_]+)/$', login_required(views.SequenceMiningView.as_view()),
            name='sequence-mining'),
        url(r'^sequence-mining/(?P<class>[0-9a-z-_]+)/(?P<from_user>[0-9a-zA-Z-_]+)/$',
            login_required(views.SequenceMiningView.as_view()), name='sequence-mining'),

        url(r'^segmentation/(?P<file_id>[0-9]+)/$', login_required(views.SegmentationView.as_view()),
            name='segmentation'),
        url(r'^exemplars/$', login_required(views.ExemplarsView.as_view()), name='exemplars'),
        url(r'^exemplars/(?P<class>[0-9a-z-_]+)/$', login_required(views.ExemplarsView.as_view()),
            name='exemplars'),
        url(r'^exemplars/(?P<class>[0-9a-z-_]+)/(?P<from_user>[0-9a-zA-Z-_]+)/$',
            login_required(views.ExemplarsView.as_view()), name='exemplars'),
        url(r'^song-partition/$', login_required(views.SongPartitionView.as_view()), name='song-partition'),
        url(r'^song-partition/(?P<track_id>[0-9]+)/$',
            login_required(views.SongPartitionView.as_view()),
            name='song-partition'),

        url(r'^feature-extraction/$', login_required(views.FeatureExtrationView.as_view()), name='feature-extraction'),
        url(r'^tsne/plotly/(?P<tensor_name>[0-9a-z]{32})/$', views.TsnePlotlyView.as_view(), name='tsne-plotly'),
        url(r'^tsne/(?P<tensor_name>[0-9a-z]{32})/$', views.TensorvizView.as_view(), name='tsne'),
        url(r'^tsne/(?P<tensor_name>[0-9a-z]{32})/meta/$', tensorviz.get_metadata, name='tsne-meta'),

        url(r'^$', views.HomePageView.as_view(), name='homepage'),
    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
