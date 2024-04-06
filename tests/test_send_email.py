import os
from unittest import TestCase

import django
from django.core.mail import EmailMultiAlternatives

from maintenance import get_config


class EmailTest(TestCase):
    def setUp(self):
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "koe.settings")
        envconf = get_config()
        default_config = envconf["email_config"]
        default_sender = envconf["from_email"]

        self.EMAIL_CONFIG = os.environ.get("EMAIL_CONFIG", default_config)
        self.FROM_EMAIL = os.environ.get("FROM_EMAIL", default_sender)
        self.TO_EMAIL = os.environ.get("TO_EMAIL", None)

        if (self.EMAIL_CONFIG != default_config and self.FROM_EMAIL == default_sender) or (
            self.EMAIL_CONFIG == default_config and self.FROM_EMAIL != default_sender
        ):
            raise Exception("Either provide both EMAIL_CONFIG and TO_EMAIL as environment variables or do neither")

        if self.TO_EMAIL is None:
            raise Exception("Please set environment variable TO_EMAIL before running this test")

        envconf["email_config"] = self.EMAIL_CONFIG
        django.setup()

        from django.conf import settings

        EMAIL_HOST = settings.EMAIL_HOST
        EMAIL_USER = settings.EMAIL_HOST_USER
        EMAIL_PASS = settings.EMAIL_HOST_PASSWORD
        EMAIL_PORT = settings.EMAIL_PORT
        EMAIL_USE_TLS = settings.EMAIL_USE_TLS
        EMAIL_USE_SSL = settings.EMAIL_USE_SSL

        print(
            "EMAIL_HOST = {}, EMAIL_USER = {}, EMAIL_PASS = {}, EMAIL_PORT = {}, EMAIL_USE_SSL={}, EMAIL_USE_TLS={}".format(
                EMAIL_HOST,
                EMAIL_USER,
                EMAIL_PASS,
                EMAIL_PORT,
                EMAIL_USE_SSL,
                EMAIL_USE_TLS,
            )
        )

    def test_send_email(self):
        plain_content = "Hello, this is a test email"

        email = EmailMultiAlternatives(
            "Hello",
            plain_content,
            self.FROM_EMAIL,
            [self.TO_EMAIL],
            headers={"From": "Koe <{}>".format(self.FROM_EMAIL)},
        )
        email.send()
