from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import re_path, include

from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls
from wagtail.core import urls as wagtail_urls

from koe import views
from root import urls as root_urls
from root import views as root_views

urlpatterns = [] + root_urls.urlpatterns

urlpatterns += [
    url(r'^admin/', admin.site.urls),
    url(r'^version$', login_required(root_views.get_view('version')), name='version'),
    url(r'^label$', login_required(views.IndexView.as_view()), name='index'),
    re_path(r'^cms/', include(wagtailadmin_urls)),
    re_path(r'^documents/', include(wagtaildocs_urls)),
    re_path(r'', include(wagtail_urls))
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

