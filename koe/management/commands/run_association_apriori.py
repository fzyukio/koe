r"""
Run classifiers and export a)The confusion matrix and b)list of frequently misclassified instances
"""
from django.core.management.base import BaseCommand

from koe.models import Segment
from root.models import ExtraAttr, ExtraAttrValue

from pycspade import cspade


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            '--database-name',
            action='store',
            dest='database_name',
            required=True,
            type=str,
            help='E.g Bellbird, Whale, ..., case insensitive',
        )

        parser.add_argument(
            '--owner',
            action='store',
            dest='username',
            default='superuser',
            type=str,
            help='Name of the person who owns this database, case insensitive',
        )

        parser.add_argument(
            '--label-level',
            action='store',
            dest='label_level',
            default='label',
            type=str,
            help='Level of labelling to use',
        )

    def handle(self, database_name, username, label_level, *args, **options):
        segs = Segment.objects.filter(audio_file__database__name=database_name) \
            .order_by('audio_file__name', 'start_time_ms')

        values = segs.values_list('id', 'audio_file__id')

        seg_ids = segs.values_list('id', flat=True)

        label_attr = ExtraAttr.objects.get(klass=Segment.__name__, name=label_level)
        labels = ExtraAttrValue.objects.filter(attr=label_attr, owner_id__in=seg_ids, user__username=username) \
            .values_list('owner_id', 'value')

        seg_id_to_label = {x: y for x, y in labels}
        label_set = set(seg_id_to_label.values())
        labels2enums = {y: x + 1 for x, y in enumerate(label_set)}
        enums2labels = {x: y for y, x in labels2enums.items()}
        seg_id_to_label_enum = {x: labels2enums[y] for x, y in seg_id_to_label.items()}

        # Bagging song syllables by song name
        songs = {}
        sequences = []
        sequence_ind = 1

        for seg_id, song_id in values:
            if song_id not in songs:
                segs_info = []
                songs[song_id] = segs_info
            else:
                segs_info = songs[song_id]

            label2enum = seg_id_to_label_enum.get(seg_id, None)

            segs_info.append(label2enum)

        for song_id, segs_info in songs.items():
            sequence_labels = []
            song_sequence = []

            has_unlabelled = False
            for ind, label2enum in enumerate(segs_info):
                sequence_labels.append(label2enum)
                song_sequence.append((sequence_ind, ind + 1, (label2enum,)))
                if label2enum is None:
                    has_unlabelled = True
                    break
            if not has_unlabelled:
                sequences += song_sequence
                sequence_ind += 1
            else:
                print('Skip song {} due to having unlabelled data'.format(song_id))

        result = cspade(data=sequences, support=20, maxgap=1)
        mined_objects = result['mined_objects']
        nseqs = result['nsequences']
        mined_objects.sort(key=lambda x: x.noccurs, reverse=True)

        print('{0:>9s} {1:>9s} {2:>9s} {3:>9s} {4:>80s}'.format('Occurs', 'Support', 'Confid', 'Lift', 'Sequence'))
        for mined_object in mined_objects:
            items = mined_object.items
            conf = 'N/A'
            lift = 'N/A'
            if mined_object.confidence:
                conf = '{:0.7f}'.format(mined_object.confidence)
            if mined_object.lift:
                lift = '{:0.7f}'.format(mined_object.lift)

            print('{0:>9d} {1:>0.7f} {2:>9s} {3:>9s} {4:>80s} '.format(
                mined_object.noccurs, mined_object.noccurs / nseqs, conf, lift,
                '->'.join([enums2labels[item.elements[0]] for item in items])))
