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
        url(r'^syllables/$', login_required(views.get_view('syllables')), name='syllables'),
        url(r'^songs/$', login_required(views.get_view('songs')), name='songs'),
        url(r'^sequence-mining/$', login_required(views.get_view('sequence-mining')), name='sequence-mining'),
        url(r'^segmentation/(?P<file_id>[0-9]+)/$', login_required(views.SegmentationView.as_view()),
            name='segmentation'),
        url(r'^exemplars/$', login_required(views.get_view('exemplars')), name='exemplars'),
        url(r'^song-partition/$', login_required(views.SongPartitionView.as_view()), name='song-partition'),
        url(r'^feature-extraction/$', login_required(views.FeatureExtrationView.as_view()), name='feature-extraction'),
        url(r'^tsne/plotly/(?P<tensor_name>[0-9a-z]{32})/$', views.TsnePlotlyView.as_view(), name='tsne-plotly'),
        url(r'^tsne/(?P<tensor_name>[0-9a-z]{32})/$', views.TensorvizView.as_view(), name='tsne'),
        url(r'^tsne/(?P<tensor_name>[0-9a-z]{32})/meta/$', tensorviz.get_metadata, name='tsne-meta'),
        url(r'^dashboard/$', login_required(views.get_view('dashboard')), name='dashboard'),
        url(r'^help/$', login_required(views.get_view('help')), name='help'),
        url(r'^contact-us/$', login_required(views.ContactUsView.as_view()), name='contact-us'),
        url(r'^$', login_required(views.get_home_page), name='home_page')

    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
