from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseServerError
from django.shortcuts import render
from django.urls import path

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


page_names = ['syllables', 'songs', 'sequence-mining', 'exemplars', 'view-ordination', 'dashboard', 'help']

for page_name in page_names:
    urlpatterns.append(
        path('{}/'.format(page_name), login_required(views.get_view(page_name)), name=page_name),
    )

urlpatterns += \
    [
        url(r'^admin/', admin.site.urls),
        url(r'^segmentation/(?P<file_id>[0-9]+)/$', login_required(views.SegmentationView.as_view()),
            name='segmentation'),
        url(r'^song-partition/$', login_required(views.SongPartitionView.as_view()), name='song-partition'),
        url(r'^extraction/feature/$', login_required(views.FeatureExtrationView.as_view()), name='feature-extraction'),
        url(r'^extraction/ordination/$', login_required(views.OrdinationExtrationView.as_view()),
            name='ordination-extraction'),
        url(r'^extraction/similarity/$', login_required(views.SimilarityExtrationView.as_view()),
            name='similarity-extraction'),
        url(r'^tsne/(?P<tensor_name>[0-9a-z]{32})/$', views.TensorvizView.as_view(), name='tsne'),
        url(r'^tsne/(?P<tensor_name>[0-9a-z]{32})/meta/$', tensorviz.get_metadata, name='tsne-meta'),
        path('ordination/meta/<int:ord_id>/<str:viewas>/', login_required(tensorviz.get_ordination_metadata),
             name='ordination-meta'),
        url(r'^contact-us/$', login_required(views.ContactUsView.as_view()), name='contact-us'),
        url(r'^$', login_required(views.get_home_page), name='home_page')
    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
