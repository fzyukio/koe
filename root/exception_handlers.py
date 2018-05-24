from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseBadRequest
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin

from root.exceptions import CustomAssertionError


class HandleBusinessExceptionMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if settings.DEBUG:
            return
        if isinstance(exception, CustomAssertionError):
            message = str(exception)
            messages.error(request, message)

            context = dict(message=message, status_code=400)
            return HttpResponseBadRequest(render(request, 'errors/assertion-error.html', context=context))
