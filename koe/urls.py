from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required

from koe import views
from root import urls as root_urls
from root import views as root_views

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^version$', login_required(root_views.get_view('version')), name='version'),
    url(r'^help$', views.HelpView.as_view(), name='help'),
    url(r'^help-edit$', login_required(views.HelpEditView.as_view()), name='help-edit'),
    url(r'^$', login_required(views.IndexView.as_view()), name='index'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns += root_urls.urlpatterns
