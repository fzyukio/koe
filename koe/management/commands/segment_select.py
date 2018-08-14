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

from koe.models import *
from root.models import ExtraAttrValue
from collections import Counter


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )

        parser.add_argument('--startswith', action='store', dest='startswith', required=False, type=str, )

        parser.add_argument('--owner', action='store', dest='username', default='superuser', type=str,
                            help='Name of the person who owns this database, case insensitive', )

        parser.add_argument('--label-level', action='store', dest='label_level', default='label', type=str,
                            help='Level of labelling to use', )

        parser.add_argument('--min-occur', action='store', dest='min_occur', default=2, type=int,
                            help='Ignore syllable classes that have less than this number of instances', )

        parser.add_argument('--labels-to-ignore', action='store', dest='labels_to_ignore', default='', type=str,
                            help='labels to be ignored, case insensitive', )

        parser.add_argument('--csv-file', action='store', dest='csv_file', required=True, type=str, )

    def handle(self, *args, **options):
        database_name = options['database_name']
        username = options['username']
        primary_label_level = options['label_level']
        csv_file = options['csv_file']
        startswith = options['startswith']
        labels_to_ignore = options['labels_to_ignore']
        min_occur = options['min_occur']
        labels_to_ignore = labels_to_ignore.split(';')
        labels_to_ignore = [x.lower() for x in labels_to_ignore]

        segments = Segment.objects.filter(audio_file__database__name__iexact=database_name)

        if startswith:
            segments = segments.filter(audio_file__name__istartswith=startswith)

        segment_ids = segments.values_list('id', flat=True)

        segment_to_primary_label = {
            x: y.lower() for x, y in
            ExtraAttrValue.objects
                .filter(attr__name=primary_label_level, owner_id__in=segment_ids, user__username__iexact=username)
                .values_list('owner_id', 'value')
            if y.lower() not in labels_to_ignore
        }

        occurs = Counter(segment_to_primary_label.values())

        segment_to_labels = {}
        for segid, primary_label in segment_to_primary_label.items():
            if occurs[primary_label] >= min_occur:
                segment_to_labels[segid] = [primary_label]

        other_labels = [x for x in ['label_family', 'label_subfamily', 'label'] if x != primary_label_level]
        for other_label in other_labels:
            segment_to_label = {
                x: y.lower() for x, y in
                ExtraAttrValue.objects
                    .filter(attr__name=other_label, owner_id__in=segment_ids, user__username__iexact=username)
                    .values_list('owner_id', 'value')
            }
            for segid, labels in segment_to_labels.items():
                label = segment_to_label.get(segid, '')
                labels.append(label)

        segment_to_gender = {x: y.lower() for x, y in segments.values_list('id', 'audio_file__individual__gender')}
        for segid, labels in segment_to_labels.items():
            gender = segment_to_gender.get(segid, '')
            labels.append(gender)

        with open(csv_file, 'w', encoding='utf-8') as f:
            f.write('id\t{}\t{}\tGender\n'.format(primary_label_level, '\t'.join(other_labels)))
            for sid, labels in segment_to_labels.items():
                f.write('{}\t{}\n'.format(sid, '\t'.join(labels)))
