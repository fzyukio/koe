import datetime
import os
import random
import string
import threading
import time

import errno
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.urls import reverse

from_email = settings.FROM_EMAIL
sender_name = 'Koe <{}>'.format(from_email)
siteurl = settings.SITE_URL_BARE


def datetime2timestamp(date, format=None):
    if format is not None:
        date = datetime.datetime.strptime(date, format)
    return time.mktime(date.timetuple())


def password_generator(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


class SendEmailThread(threading.Thread):
    def __init__(self, subject, template, to, context, to_override=None, **kwargs):
        self.subject = subject
        self.template = template
        self.to = [to_override] if to_override else to  # allow overriding the "to" email field for testing
        self.context = context

        super(SendEmailThread, self).__init__(**kwargs)

    def run(self):
        html = get_template('emails/' + self.template + '.html')
        plain = get_template('emails/' + self.template + '.txt')

        html_content = html.render(self.context)
        plain_content = plain.render(self.context)

        email = EmailMultiAlternatives(self.subject, plain_content, from_email, self.to, headers={'From': sender_name})
        email.attach_alternative(html_content, 'text/html')
        email.send()


def forget_password_handler(user):
    subject = 'Reset your password'
    template = 'forget-password'
    reset_link = "{}{}".format(siteurl, reverse('reset-password'))

    password = password_generator(8)

    user.set_password(password)
    user.save()

    context = {'user': user, 'password': password, 'resetlink': reset_link}
    send_email_thread = SendEmailThread(subject, template, [user.email], context)
    send_email_thread.start()


def data_path(prefix, fullname, ext=None, for_url=False):
    filename, _ext = os.path.splitext(fullname)
    _ext = _ext[1:]
    if ext is None:
        ext = _ext
    slashed_url = os.path.join(settings.MEDIA_URL, prefix, '{}.{}'.format(filename, ext))
    unslashed_url = slashed_url[1:]
    absolute_url = os.path.join(settings.BASE_DIR, unslashed_url)
    if for_url:
        return slashed_url
    return absolute_url


def pickle_path(fullname, subdir=None, for_url=False):
    folder = 'pickle'
    if subdir:
        folder = os.path.join(folder, subdir)
    return data_path(folder, fullname, 'pkl', for_url)


def wav_path(fullname, for_url=False):
    return data_path('audio/wav', fullname, 'wav', for_url)


def audio_path(fullname, ext, for_url=False):
    return data_path('audio/' + ext, fullname, ext, for_url)


def history_path(fullname, for_url=False):
    return data_path('history', fullname, 'zip', for_url)


def spect_fft_path(fullname, subdir=None, for_url=False):
    folder = 'spect/fft'
    if subdir:
        folder = os.path.join(folder, subdir)
    return data_path(folder, fullname, 'png', for_url)


def spect_mask_path(fullname, subdir=None, for_url=False):
    folder = 'spect/mask'
    if subdir:
        folder = os.path.join(folder, subdir)
    return data_path(folder, fullname, 'png', for_url)


def ensure_empty_file_exists(file_path):
    if not os.path.exists(os.path.dirname(file_path)):
        try:
            os.makedirs(os.path.dirname(file_path))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise
    if os.path.isfile(file_path):
        os.remove(file_path)
    with open(file_path, "w") as f:
        f.close()


def ensure_parent_folder_exists(file_path):
    parent_dir = os.path.dirname(file_path)
    if not os.path.exists(parent_dir):
        try:
            os.makedirs(parent_dir)
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:
                raise


class CustomAssertionError(Exception):
    """
    To throw when an expected error occurs because of user's fault.
    """

    pass
