from django.core.management import BaseCommand
import requests
from django.test import RequestFactory
from dotmap import DotMap

request_factory = RequestFactory()


class Command(BaseCommand):
    # def add_arguments(self, parser):
    #
    #   parser.add_argument(
    #     '--url',
    #     action='store',
    #     dest='save_to',
    #     required=True,
    #     help='File name to be saved. Name only. Files will be saved in saved_data/',
    #   )

    def handle(self, *args, **options):
        from koe.views import get_grid_content
        from koe.models import Herd

        herd = Herd.objects.first()
        r = DotMap(POST={'grid-type': 'report', 'herd': herd.id,
                         'toDate': '28/02/18', 'fromDate': '01/12/17', 'freq': 'daily'})

        for i in range(10):
            c = get_grid_content(r)
        # print(c.content)
