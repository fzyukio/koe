from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseServerError
from django.template import loader
from django.utils.deprecation import MiddlewareMixin

from root.exceptions import CustomAssertionError


class HandleBusinessExceptionMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if settings.DEBUG:
            return
        if isinstance(exception, CustomAssertionError):
            message = str(exception)
            messages.error(request, message)

            t = loader.get_template('errors/assertion-error.html')
            context = dict(request=request, message=message)
            return HttpResponseServerError(t.render(context=context))
