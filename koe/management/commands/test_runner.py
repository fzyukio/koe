r"""
Run this to generate a CSV file that has two columns: id and label.
ID=ids of the segments, label=Label given to that segment

e.g:

- python manage.py segment_select --database-name=bellbirds --owner=superuser --csv-file=/tmp/bellbirds.csv \
                                  --startswith=LBI --label-level=label_family --labels-to-ignore="Click;Stutter"
  --> Find segments of Bellbirds database, where the files start with LBI and family labels made by superuser, ignore
      all segments that are labelled 'Click' or 'Stutter', save to file /tmp/bellbirds.csv
"""

from django.core.management.base import BaseCommand

from koe.task import ConsoleTaskRunner


class Command(BaseCommand):
    def handle(self, *args, **options):
        runner = ConsoleTaskRunner(prefix='Testing')
        limit = 100
        runner.start(limit=limit)
        per = 2
        for i in range(limit // per):
            runner.tick(per)

        runner.complete()
