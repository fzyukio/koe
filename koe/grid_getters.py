import os

import numpy as np
from django.conf import settings
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.urls import reverse
from pycspade import cspade

from koe.model_utils import get_user_databases, get_or_error
from koe.models import AudioFile, Segment, DatabaseAssignment, DatabasePermission, Database, TemporaryDatabase,\
    SimilarityIndex
from koe.ts_utils import bytes_to_ndarray, get_rawdata_from_binary
from root.exceptions import CustomAssertionError
from root.models import ExtraAttr, ExtraAttrValue
from root.utils import history_path

__all__ = ['bulk_get_segment_info', 'bulk_get_exemplars', 'bulk_get_song_sequences', 'bulk_get_segments_for_audio',
           'bulk_get_history_entries', 'bulk_get_audio_file_for_raw_recording', 'bulk_get_song_sequence_associations',
           'bulk_get_database', 'bulk_get_database_assignment', 'bulk_get_concise_segment_info']


def bulk_get_concise_segment_info(segs, extras):
    database_id = extras.database
    user = extras.user
    current_database = get_or_error(Database, dict(id=database_id))
    rows = []
    ids = []
    if current_database is None:
        return ids, rows

    segs = segs.filter(audio_file__database=current_database.id)
    values = list(segs.values_list('id', 'tid', 'start_time_ms', 'end_time_ms', 'audio_file__name'))
    segids = [x[0] for x in values]

    label_attr = settings.ATTRS.segment.label
    family_attr = settings.ATTRS.segment.family
    subfamily_attr = settings.ATTRS.segment.subfamily

    labels = ExtraAttrValue.objects.filter(user__username=user, attr=label_attr, owner_id__in=segids)\
        .values_list('owner_id', 'value')
    families = ExtraAttrValue.objects.filter(user__username=user, attr=family_attr, owner_id__in=segids)\
        .values_list('owner_id', 'value')
    subfamilies = ExtraAttrValue.objects.filter(user__username=user, attr=subfamily_attr, owner_id__in=segids)\
        .values_list('owner_id', 'value')

    labels = {x: y for x, y in labels}
    families = {x: y for x, y in families}
    subfamilies = {x: y for x, y in subfamilies}

    for id, tid, start, end, song_name in values:
        ids.append(id)
        duration = end - start
        row = dict(id=id, start_time_ms=start, end_time_ms=end, duration=duration, song=song_name, spectrogram=tid)
        if id in labels:
            row['label'] = labels[id]
        if id in families:
            row['label_family'] = families[id]
        if id in subfamilies:
            row['label_subfamily'] = subfamilies[id]

        rows.append(row)

    return ids, rows


def bulk_get_segment_info(segs, extras):
    """
    Return rows contains Segments' information to display in SlickGrid
    :param segs: an array of segment object (or a QuerySet)
    :param extras: Must specify the user to get the correct ExtraAttrValue columns
    :return: [row]
    """
    viewas = extras.viewas
    holdout = extras.get('_holdout', 'false') == 'true'
    user = extras.user

    if 'database' in extras:
        database_id = extras.database
        current_database = get_or_error(Database, dict(id=database_id))
    else:
        database_id = extras.tmpdb
        current_database = get_or_error(TemporaryDatabase, dict(id=database_id))

    similarity_id = extras.similarity
    current_similarity = None
    if similarity_id:
        current_similarity = get_or_error(SimilarityIndex, dict(id=similarity_id))

    rows = []
    ids = []
    if current_database is None:
        return ids, rows

    if holdout:
        ids_holder = ExtraAttrValue.objects.filter(attr=settings.ATTRS.user.hold_ids_attr, owner_id=user.id,
                                                   user=user).first()

        if ids_holder is not None and ids_holder.value != '':
            ids = ids_holder.value.split(',')
            segs = segs.filter(id__in=ids)
    elif isinstance(current_database, TemporaryDatabase):
        ids = current_database.ids
        segs = segs.filter(id__in=ids)
    else:
        segs = segs.filter(audio_file__database=current_database.id)

    values = list(segs.values_list('id', 'tid', 'start_time_ms', 'end_time_ms',
                                   'audio_file__name',
                                   'audio_file__id',
                                   'audio_file__quality',
                                   'audio_file__track__name',
                                   'audio_file__track__date',
                                   'audio_file__individual__name',
                                   'audio_file__individual__gender',
                                   ))

    segids = [x[0] for x in values]
    song_ids = [x[5] for x in values]

    extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user__username=viewas, attr__klass=Segment.__name__, owner_id__in=segids) \
        .values_list('owner_id', 'attr__name', 'value')

    song_extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user__username=viewas, attr__klass=AudioFile.__name__, owner_id__in=song_ids) \
        .values_list('owner_id', 'attr__name', 'value')

    extra_attr_values_lookup = {}
    for id, attr, value in extra_attr_values_list:
        if id not in extra_attr_values_lookup:
            extra_attr_values_lookup[id] = {}
        extra_attr_dict = extra_attr_values_lookup[id]
        extra_attr_dict[attr] = value

    song_extra_attr_values_lookup = {}
    for id, attr, value in song_extra_attr_values_list:
        if id not in song_extra_attr_values_lookup:
            song_extra_attr_values_lookup[id] = {}
        extra_attr_dict = song_extra_attr_values_lookup[id]
        extra_attr_dict[attr] = value

    ids = np.array([x[0] for x in values], dtype=np.int32)

    if current_similarity is None:
        id2order = {}
    else:
        sim_sids_path = current_similarity.get_sids_path()
        sim_bytes_path = current_similarity.get_bytes_path()

        sim_sids = bytes_to_ndarray(sim_sids_path, np.int32).tolist()
        sim_order = np.squeeze(get_rawdata_from_binary(sim_bytes_path, len(sim_sids), np.int32)).tolist()
        id2order = dict(zip(sim_sids, sim_order))

    for id, tid, start, end, song_name, song_id, quality, track, date, individual, gender in values:
        sim_index = id2order.get(id, None)

        duration = end - start
        url = reverse('segmentation', kwargs={'file_id': song_id})
        url = '[{}]({})'.format(url, song_name)
        row = dict(id=id, start_time_ms=start, end_time_ms=end, duration=duration, song=url,
                   dtw_index=sim_index, song_track=track, song_individual=individual, song_gender=gender,
                   song_quality=quality, song_date=date, spectrogram=tid,)
        extra_attr_dict = extra_attr_values_lookup.get(id, {})
        song_extra_attr_dict = song_extra_attr_values_lookup.get(song_id, {})

        for attr in extra_attr_dict:
            row[attr] = extra_attr_dict[attr]

        for song_attr in song_extra_attr_dict:
            attr = 'song_{}'.format(song_attr)
            row[attr] = song_extra_attr_dict[song_attr]

        rows.append(row)

    return ids, rows


def bulk_get_exemplars(objs, extras):
    """
    Return rows containing n exemplars per class. Each row is one class. Class can be label, label_family,
    label_subfamily
    :param objs: a list of Segments
    :param extras: must contain key 'class', value can be one of 'label', 'label_family', 'label_subfamily'
    :return:
    """
    granularity = extras.granularity
    viewas = extras.viewas
    current_database = get_user_databases(extras.user)

    if isinstance(current_database, Database):
        if isinstance(objs, QuerySet):
            id2tid = {x: y for x, y in objs.filter(audio_file__database=current_database).values_list('id', 'tid')}
            ids = id2tid.keys()
        else:
            objs = [x for x in objs if x.audio_file.database == current_database]
            id2tid = {x.id: x.tid for x in objs}
            ids = id2tid.keys()
    else:
        ids = current_database.ids
        segs = Segment.objects.filter(id__in=ids)
        id2tid = {x: y for x, y in segs.values_list('id', 'tid')}

    values = ExtraAttrValue.objects.filter(attr__klass=Segment.__name__, attr__name=granularity, owner_id__in=ids,
                                           user__username=viewas) \
        .order_by(Lower('value'), 'owner_id').values_list('value', 'owner_id')

    class_to_exemplars = []
    current_class = ''
    current_exemplars_list = None
    current_exemplars_count = 0
    total_exemplars_count = 0

    for cls, owner_id in values:
        if cls:
            cls = cls.strip()
            if cls:
                if cls.lower() != current_class.lower():
                    class_to_exemplars.append((current_class, total_exemplars_count, current_exemplars_list))
                    current_exemplars_count = 0
                    current_class = cls
                    total_exemplars_count = 0
                    current_exemplars_list = [owner_id]
                else:
                    current_exemplars_list.append(owner_id)
                    current_exemplars_count += 1

                total_exemplars_count += 1

    class_to_exemplars.append((current_class, total_exemplars_count, current_exemplars_list))

    rows = []
    ids = []
    for cls, count, exemplar_ids in class_to_exemplars:
        if cls:
            exemplar_id2tid = [(x, id2tid[x]) for x in exemplar_ids]
            row = dict(id=cls, cls=cls, count=count, spectrograms=exemplar_id2tid)
            rows.append(row)
            ids.append(cls)

    return ids, rows


def get_sequence_info_empty_songs(empty_songs):
    rows = []
    ids = []

    if isinstance(empty_songs, QuerySet):
        values = empty_songs.values_list('name', 'id', 'quality', 'length', 'fs', 'track__name', 'track__date',
                                         'individual__name', 'individual__gender', 'individual__species__genus',
                                         'individual__species__species')
    else:
        values = []
        for x in empty_songs:
            track = x.track
            individual = x.individual
            species = individual.species if individual else None
            x_value = [x.name, x.id, x.quality, x.length, x.fs,
                       track.name if track else None,
                       track.date if track else None,
                       individual.name if individual else None,
                       individual.gender if individual else None,
                       species.genus if species else None,
                       species.species if species else None]
            values.append(x_value)

    for filename, song_id, quality, length, fs, track, date, indv, gender, genus, species in values:
        url = reverse('segmentation', kwargs={'file_id': song_id})
        url = '[{}]({})'.format(url, filename)
        duration_ms = round(length * 1000 / fs)
        genus = genus if genus else ''
        species = species if species else ''
        species_str = '{} {}'.format(genus, species)
        row = dict(id=song_id, filename=url, track=track, individual=indv, gender=gender,
                   quality=quality, date=date, duration=duration_ms, species=species_str)
        ids.append(song_id)
        rows.append(row)

    return ids, rows


def bulk_get_song_sequences(all_songs, extras):
    """
    For the song sequence page. For each song, send the sequence of syllables in order of appearance
    :param all_songs: a QuerySet list of AudioFile
    :param extras:
    :return:
    """
    granularity = extras.granularity
    current_database = get_user_databases(extras.user)
    permission = current_database.get_assigned_permission(extras.user)
    viewas = extras.viewas

    if permission < DatabasePermission.VIEW:
        raise CustomAssertionError('You don\'t have permission to view this database')

    extras.permission = permission

    if isinstance(current_database, Database):
        if isinstance(all_songs, QuerySet):
            all_songs = all_songs.filter(database=current_database)
            song_ids = all_songs.values_list('id', flat=True)
        else:
            all_songs = [x.id for x in all_songs if x.database == current_database]
            song_ids = all_songs
        segs = Segment.objects.filter(audio_file__in=all_songs).order_by('audio_file__name', 'start_time_ms')
    else:
        seg_ids = current_database.ids
        segs = Segment.objects.filter(id__in=seg_ids)
        song_ids = segs.values_list('audio_file').distinct()
        all_songs = AudioFile.objects.filter(id__in=song_ids)

    values = segs.values_list('id', 'tid', 'start_time_ms', 'end_time_ms',
                              'audio_file__name',
                              'audio_file__id',
                              'audio_file__quality',
                              'audio_file__length',
                              'audio_file__fs',
                              'audio_file__track__name',
                              'audio_file__track__date',
                              'audio_file__individual__name',
                              'audio_file__individual__gender',
                              'audio_file__individual__species__genus',
                              'audio_file__individual__species__species')
    seg_ids = segs.values_list('id', flat=True)

    label_attr = ExtraAttr.objects.get(klass=Segment.__name__, name=granularity)
    labels = ExtraAttrValue.objects.filter(attr=label_attr, owner_id__in=seg_ids, user__username=viewas) \
        .values_list('owner_id', 'value')

    seg_id_to_label = {x: y for x, y in labels}

    extra_attrs = ExtraAttr.objects.filter(klass=AudioFile.__name__)
    extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user__username=viewas, attr__in=extra_attrs, owner_id__in=song_ids) \
        .values_list('owner_id', 'attr__name', 'value')

    extra_attr_values_lookup = {}
    for id, attr, value in extra_attr_values_list:
        if id not in extra_attr_values_lookup:
            extra_attr_values_lookup[id] = {}
        extra_attr_dict = extra_attr_values_lookup[id]
        extra_attr_dict[attr] = value

    ids = []
    rows = []

    # Bagging song syllables by song name
    songs = {}

    for seg_id, tid, start, end, filename, song_id, quality, length, fs, track, date, indv, gender, genus, species\
            in values:
        if song_id not in songs:
            url = reverse('segmentation', kwargs={'file_id': song_id})
            url = '[{}]({})'.format(url, filename)
            duration_ms = round(length * 1000 / fs)
            genus = genus if genus else ''
            species = species if species else ''
            species_str = '{} {}'.format(genus, species)
            song_info = dict(filename=url, track=track, individual=indv, gender=gender,
                             quality=quality, date=date, duration=duration_ms, species=species_str)
            segs_info = []
            songs[song_id] = dict(song=song_info, segs=segs_info)
        else:
            segs_info = songs[song_id]['segs']

        label = seg_id_to_label.get(seg_id, '__NONE__')
        segs_info.append((tid, label, start, end))

    for song_id, info in songs.items():
        song_info = info['song']
        segs_info = info['segs']

        sequence_labels = []
        sequence_starts = []
        sequence_ends = []
        sequence_tids = []

        for tid, label, start, end in segs_info:
            sequence_labels.append(label)
            sequence_starts.append(start)
            sequence_ends.append(end)
            sequence_tids.append(tid)

        sequence_str = '-'.join('\"{}\"'.format(x) for x in sequence_labels)

        row = song_info
        row['id'] = song_id
        row['sequence'] = sequence_str
        row['sequence-labels'] = sequence_labels
        row['sequence-starts'] = sequence_starts
        row['sequence-ends'] = sequence_ends
        row['sequence-tids'] = sequence_tids

        extra_attr_dict = extra_attr_values_lookup.get(song_id, {})
        for attr in extra_attr_dict:
            row[attr] = extra_attr_dict[attr]

        ids.append(song_id)
        rows.append(row)

    # Now we have to deal with songs without any segmentation done
    empty_songs = all_songs.exclude(id__in=songs.keys())

    _ids, _rows = get_sequence_info_empty_songs(empty_songs)
    ids += _ids
    rows += _rows

    return ids, rows


def bulk_get_segments_for_audio(segs, extras):
    """
    For the segmentation page
    :param segs: a QuerySet of segments
    :param extras: must contain 'file_id', which is the ID of the audio
    :return: the usual stuff
    """
    file_id = extras.file_id
    viewas = extras.user

    if not isinstance(segs, QuerySet):
        segids = [x.id for x in segs]
        # segs = Segment.objects.filter(id=segids).filter(audio_file=file_id)
        values = [(x.id, x.start_time_ms, x.end_time_ms) for x in segs]
    else:
        segs = segs.filter(audio_file=file_id)
        values = segs.values_list('id', 'start_time_ms', 'end_time_ms')
        segids = [x[0] for x in values]
    ids = []
    rows = []

    extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user__username=viewas, attr__klass=Segment.__name__, owner_id__in=segids) \
        .values_list('owner_id', 'attr__name', 'value')

    extra_attr_values_lookup = {}
    for id, attr, value in extra_attr_values_list:
        if id not in extra_attr_values_lookup:
            extra_attr_values_lookup[id] = {}
        extra_attr_dict = extra_attr_values_lookup[id]
        extra_attr_dict[attr] = value

    for id, start, end in values:
        ids.append(id)
        duration = end - start
        row = dict(id=id, start=start, end=end, duration=duration)

        extra_attr_dict = extra_attr_values_lookup.get(id, {})

        for attr in extra_attr_dict:
            row[attr] = extra_attr_dict[attr]

        rows.append(row)

    return ids, rows


def has_import_permission(user_id, database_id):
    """
    Check if user has IMPORT permission on database
    :param user_id:
    :param database_id:
    :return:
    """
    return DatabaseAssignment.objects.filter(user=user_id, database=database_id,
                                             permission__gte=DatabasePermission.IMPORT_DATA).exists()


def bulk_get_history_entries(hes, extras):
    user = extras.user
    database = extras.database

    tz = extras.tz
    if isinstance(hes, QuerySet):
        values = hes.filter(database=database).values_list('id', 'filename', 'time', 'user__username', 'user__id',
                                                           'database', 'database__name', 'note', 'version', 'type')
    else:
        values = [(
            x.id, x.filename, x.time, x.user.username, x.user.id, x.database, x.database.name, x.note, x.version,
            x.type) for x in hes
        ]

    ids = []
    rows = []
    for id, filename, time, creator, creator_id, database_id, database_name, note, version, type in values:
        ids.append(id)
        tztime = time.astimezone(tz)

        user_is_creator = user.id == creator_id
        can_import = user_is_creator or has_import_permission(user.id, database_id)

        if can_import:
            url_path = history_path(filename, for_url=True)
            local_file_path = url_path[1:]
            if os.path.isfile(local_file_path):
                file_size = os.path.getsize(local_file_path) / 1024
                url = '[{}]({})'.format(url_path, filename)
            else:
                url = 'File is missing'
                file_size = 0
                can_import = False
        else:
            file_size = 0
            url = 'Insufficient permission to download'

        row = dict(id=id, url=url, creator=creator, time=tztime, size=file_size, database=database_name, note=note,
                   version=version, __can_import=can_import, __can_delete=user_is_creator, type=type)

        rows.append(row)

    return ids, rows


def bulk_get_song_sequence_associations(all_songs, extras):
    granularity = extras.granularity
    current_database = get_user_databases(extras.user)
    viewas = extras.viewas

    use_gap = extras.usegap
    maxgap = extras.maxgap if use_gap else 1
    mingap = extras.mingap if use_gap else -99999

    if isinstance(current_database, Database):
        if isinstance(all_songs, QuerySet):
            all_songs = all_songs.filter(database=current_database)
        else:
            all_songs = [x.id for x in all_songs if x.database == current_database]
        segs = Segment.objects.filter(audio_file__in=all_songs).order_by('audio_file__name', 'start_time_ms')
    else:
        segs = Segment.objects.filter(id__in=current_database.ids)

    if use_gap:
        values = segs.values_list('id', 'audio_file__id', 'start_time_ms', 'end_time_ms')
    else:
        values = segs.values_list('id', 'audio_file__id')

    seg_ids = segs.values_list('id', flat=True)

    label_attr = ExtraAttr.objects.get(klass=Segment.__name__, name=granularity)
    labels = ExtraAttrValue.objects.filter(attr=label_attr, owner_id__in=seg_ids, user__username=viewas) \
        .values_list('owner_id', 'value')

    seg_id_to_label = {x: y for x, y in labels}
    label_set = set(seg_id_to_label.values())
    labels2enums = {y: x + 1 for x, y in enumerate(label_set)}

    enums2labels = {x: y for y, x in labels2enums.items()}
    pseudo_end_id = len(label_set) + 1
    enums2labels[pseudo_end_id] = '__PSEUDO_END__'
    enums2labels[0] = '__PSEUDO_START__'

    seg_id_to_label_enum = {x: labels2enums[y] for x, y in seg_id_to_label.items()}

    # Bagging song syllables by song name
    songs = {}
    sequences = []
    sequence_ind = 1

    for value in values:
        seg_id = value[0]
        song_id = value[1]

        label2enum = seg_id_to_label_enum.get(seg_id, None)
        if use_gap:
            start = value[2]
            end = value[3]
            seg_info = (label2enum, start, end)
        else:
            seg_info = label2enum

        if song_id not in songs:
            segs_info = []
            songs[song_id] = segs_info
        else:
            segs_info = songs[song_id]

        segs_info.append(seg_info)

    for song_id, segs_info in songs.items():
        song_sequence = []
        has_unlabelled = False

        # This helps keep track of the current position of the syllable when the song is rid of syllable duration and
        # only gaps are retained.
        accum_gap = 10

        # This helps keep track of the gap between this current syllable and the previous one,
        # such that we can decide to merge two syllables if their gap is too small (could also be negative)
        gap = 0

        last_syl_end = None
        for ind, seg_info in enumerate(segs_info):
            if use_gap:
                label2enum, start, end = seg_info
                if last_syl_end is None:
                    gap = 0
                else:
                    gap = start - last_syl_end

                last_syl_end = end
                accum_gap += gap

                # If the gap is too small, merge this one with the previous one, which means the eid stays the same
                if ind > 0 and gap < mingap:
                    song_sequence[-1][2].append(label2enum)
                else:
                    eid = accum_gap
                    song_sequence.append([sequence_ind, eid, [label2enum]])
            else:
                label2enum = seg_info
                eid = ind + 1
                song_sequence.append([sequence_ind, eid, [label2enum]])

            if label2enum is None:
                has_unlabelled = True
                break

        pseudo_start = max(0, song_sequence[0][1] - 1)
        song_sequence.insert(0, [sequence_ind, pseudo_start, [0]])
        song_sequence.append([sequence_ind, eid + 1, [pseudo_end_id]])

        if not has_unlabelled:
            sequences += song_sequence
            sequence_ind += 1

    ids = []
    rows = []
    nsequences = sequence_ind - 1

    if nsequences == 0:
        return ids, rows

    support = max(int(nsequences * 0.01), 3)

    result = cspade(data=sequences, support=support, maxgap=maxgap)
    mined_objects = result['mined_objects']

    for idx, seq in enumerate(mined_objects):
        items = seq.items
        conf = -1 if seq.confidence is None else seq.confidence
        lift = -1 if seq.lift is None else seq.lift

        items_str = []
        for item in items:
            item_str = '{}' if len(item.elements) == 1 else '({})'
            labels = ' -&- '.join([enums2labels[element] for element in item.elements])
            item_str = item_str.format(labels)
            items_str.append(item_str)
        assocrule = ' => '.join(items_str)

        row = dict(id=idx, chainlength=len(items), transcount=seq.noccurs, accumoccurs=seq.accum_occurs,
                   confidence=conf, lift=lift, support=seq.noccurs / nsequences, assocrule=assocrule)

        rows.append(row)
        ids.append(idx)

    return ids, rows


def bulk_get_database(databases, extras):
    user = extras.user
    idx = []
    rows = []

    db_assignments = DatabaseAssignment.objects.filter(user=user)\
        .values_list('database__id', 'database__name', 'permission')

    for id, dbname, permission in db_assignments:
        idx.append(id)
        permission_str = DatabasePermission.get_name(permission)
        row = dict(id=id, name=dbname, permission=permission_str)
        rows.append(row)

    return idx, rows


def bulk_get_database_assignment(dbassignments, extras):
    database_id = extras.database
    idx = []
    rows = []

    if isinstance(dbassignments, QuerySet):
        db_assignments = dbassignments.filter(database=database_id).values_list('id', 'user__username', 'permission')
    else:
        db_assignments = [
            (x.id, x.user.username, x.permission) for x in dbassignments if x.database.id == database_id
        ]

    for id, username, permission in db_assignments:
        idx.append(id)
        row = dict(id=id, username=username, permission=permission)
        rows.append(row)

    return idx, rows


def bulk_set_database_assignment(*args, **kwargs):
    pass


def bulk_get_audio_file_for_raw_recording(audio_files, extras):
    return [], []
