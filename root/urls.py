import django_js_reverse.views
from django.conf import settings
from django.conf.urls import url
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth.decorators import login_required

from root import views, userviews

urlpatterns = [
    url(r'^admin/', admin.site.urls),
    url(r'^jsreverse/$', django_js_reverse.views.urls_js, name='js_reverse'),
    url(r'^fetch-data/(?P<type>[0-9a-z-]+)/$', login_required(views.fetch_data), name='fetch-data'),
    url(r'^send-data/(?P<type>[0-9a-z-]+)/$', login_required(views.send_data), name='send-data'),
    url(r'^fetch-data/(?P<module>[0-9a-z-]+)/(?P<type>[0-9a-z-]+)/$', login_required(views.fetch_data),
        name='fetch-data'),
    url(r'^send-data/(?P<module>[0-9a-z-]+)/(?P<type>[0-9a-z-]+)/$', login_required(views.send_data),
        name='send-data'),
    url(r'^login$', userviews.UserSignInView.as_view(), name='login'),
    url(r'^register$', userviews.UserRegistrationView.as_view(), name='register'),
    url(r'^reset', userviews.UserResetPasswordView.as_view(), name='reset-password'),
    url(r'^forget', userviews.UserForgetPasswordView.as_view(), name='forget-password'),
    url(r'^logout$', userviews.sign_out, name='logout'),
    url(r'^some-view', views.get_view('some-view'), name='some-view'),
    url(r'^$', login_required(views.IndexView.as_view()), name='index'),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
