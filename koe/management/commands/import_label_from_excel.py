"""
Import syllables (not elements) from luscinia (after songs have been imported)
"""
import os
from logging import warning

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models.functions import Cast
from django.db.models.query import QuerySet
from django.forms import models
from openpyxl import load_workbook

from koe.models import Segment, AudioFile
from root.models import enum, ExtraAttr, ValueTypes, User, value_setter, ExtraAttrValue

ColumnName = enum(
    POPULATION='Population',
    SONG_NAME='Song Name',
    SYL_START='Syllable Start',
    SYL_END='Syllable End',
    FAMILY='Family',
    SUBFAMILY='Subfamily',
    LABEL='Label'
)

label_attr, _ = ExtraAttr.objects.get_or_create(klass=Segment.__name__, name='label', type=ValueTypes.SHORT_TEXT)
family_attr, _ = ExtraAttr.objects.get_or_create(klass=Segment.__name__, name='label_family',
                                                 type=ValueTypes.SHORT_TEXT)
subfamily_attr, _ = ExtraAttr.objects.get_or_create(klass=Segment.__name__, name='label_subfamily',
                                                    type=ValueTypes.SHORT_TEXT)
user = User.objects.get(username='wesley')


def bulk_set_attr(cls, objs_or_ids, attr, values, is_object=True):
    if is_object:
        objs = objs_or_ids
        if not hasattr(objs, '__iter__'):
            objs = [objs]

        if isinstance(objs, QuerySet):
            ids = objs.values_list('id', flat=True)
        else:
            ids = [obj.id for obj in objs]
    else:
        ids = objs_or_ids
        if not hasattr(ids, '__iter__'):
            ids = [ids]

    extra_attr = ExtraAttr.objects.get(klass=cls.__name__, name=attr)
    val2str = value_setter[extra_attr.type]

    if not hasattr(values, '__iter__'):
        values = [val2str(values)] * len(ids)

    else:
        for i in range(len(values)):
            values[i] = val2str(values[i])

    ids_2_values = {x: y for x, y in zip(ids, values)}

    existings = ExtraAttrValue.objects.filter(
        user=user, owner_id__in=ids, attr=extra_attr)
    existings_owner_ids = existings.values_list('owner_id', flat=True)
    nonexistings_owner_ids = [x for x in ids if x not in existings_owner_ids]

    with transaction.atomic():
        for obj, objid in zip(existings, existings_owner_ids):
            value = ids_2_values[objid]
            obj.value = value
            obj.save()

    newly_created = []

    for objid in nonexistings_owner_ids:
        value = ids_2_values[objid]
        newly_created.append(ExtraAttrValue(
            user=user, owner_id=objid, attr=extra_attr, value=value))

    ExtraAttrValue.objects.bulk_create(newly_created)


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--input',
            action='store',
            dest='infile',
            required=True,
            type=str,
            help='Full path to the xls/xlsx/xlsm... file',
        )

    def handle(self, infile, *args, **options):
        if not os.path.isfile(infile):
            raise Exception(
                '{} doesn\'t exist or is not a file'.format(infile))

        wb = load_workbook(filename=infile, read_only=True, data_only=True)
        ws = wb['Complete']

        col_idx = {cell.value: n for n, cell in enumerate(
            next(ws.rows)) if cell.value in ColumnName.values}
        if len(col_idx) != len(ColumnName.values):
            raise Exception('The excel file does not contain one or more of the mandatory columns: {}'
                            .format(ColumnName.values))

        rows = list(ws.rows)
        songs_2_syllable_labels = {}
        for idx in range(len(rows)):
            if idx == 0:
                continue
            row = rows[idx]
            excel_row_idx = idx + 1

            label = row[col_idx[ColumnName.LABEL]].value
            family = row[col_idx[ColumnName.FAMILY]].value
            subfamily = row[col_idx[ColumnName.SUBFAMILY]].value
            syl_start = row[col_idx[ColumnName.SYL_START]].value
            syl_end = row[col_idx[ColumnName.SYL_END]].value
            song_name = row[col_idx[ColumnName.SONG_NAME]].value.replace(' ', '').replace('$', '')
            has_error = False

            if not label:
                warning('At line {}, label is missing.'.format(excel_row_idx))
                has_error = True
            if not family:
                warning('At line {}, family is missing.'.format(excel_row_idx))
                has_error = True
            if not subfamily:
                warning('At line {}, subfamily is missing.'.format(excel_row_idx))
                has_error = True
            if not syl_start:
                warning('At line {}, syl_start is missing.'.format(excel_row_idx))
                has_error = True
            if not syl_end:
                warning('At line {}, syl_end is missing.'.format(excel_row_idx))
                has_error = True
            if not song_name:
                warning('At line {}, song_name is missing.'.format(excel_row_idx))
                has_error = True

            if song_name not in songs_2_syllable_labels:
                syllable_labels = {}
                songs_2_syllable_labels[song_name] = syllable_labels
            else:
                syllable_labels = songs_2_syllable_labels[song_name]

            if syl_start in syllable_labels:
                warning('Duplicate syllable start time = '.format(syl_start))
                has_error = True

            if has_error:
                continue

            syllable_labels[syl_start] = (
                syl_end, family, subfamily, label, excel_row_idx)

        song_names = list(songs_2_syllable_labels.keys())
        db_songs = list(AudioFile.objects.all().values_list('name', flat=True))

        songs_in_excel_not_db = [x for x in song_names if x not in db_songs]

        if songs_in_excel_not_db:
            warning('The following songs are found in Excel but not in database: \n{}'
                    .format('\n'.join(songs_in_excel_not_db)))

        segment_values_list = Segment.objects.filter(audio_file__name__in=song_names) \
            .annotate(strid=Cast('id', models.CharField())) \
            .values_list('strid', 'audio_file__name', 'start_time_ms', 'end_time_ms')

        songs_2_syllable_endpoints_db = {}
        for seg_id, song_name, syl_start, syl_end in segment_values_list:
            if song_name not in songs_2_syllable_endpoints_db:
                syllable_endpoints = {}
                songs_2_syllable_endpoints_db[song_name] = syllable_endpoints
            else:
                syllable_endpoints = songs_2_syllable_endpoints_db[song_name]
                syllable_endpoints[syl_start] = (syl_end, seg_id)

        seg_ids = []
        label_values = []
        family_values = []
        subfamily_values = []

        for song_name in songs_2_syllable_endpoints_db:
            syllable_endpoints = songs_2_syllable_endpoints_db[song_name]
            syllable_labels = songs_2_syllable_labels[song_name]

            syllable_start_end_db = [(x, y[0])
                                     for x, y in syllable_endpoints.items()]
            syllable_start_end_excel = [(x, y[0])
                                        for x, y in syllable_labels.items()]
            excel_row_idxs = [y[-1] for _, y in syllable_labels.items()]

            syls_in_excel_not_db = []
            for idx, (s, e) in enumerate(syllable_start_end_excel):
                if (s, e) not in syllable_start_end_db:
                    syls_in_excel_not_db.append((excel_row_idxs[idx], s, e))

            for syl_start, (syl_end, seg_id) in syllable_endpoints.items():
                if syl_start in syllable_labels:
                    syl_end, family, subfamily, label, excel_row_idx = syllable_labels[syl_start]

                    seg_ids.append(seg_id)
                    label_values.append(label)
                    family_values.append(family)
                    subfamily_values.append(subfamily)

        print('total_importable = {}'.format(len(seg_ids)))
        bulk_set_attr(Segment, seg_ids, 'label_family', family_values, False)
        bulk_set_attr(Segment, seg_ids, 'label', label_values, False)
        bulk_set_attr(Segment, seg_ids, 'label_subfamily',
                      subfamily_values, False)
