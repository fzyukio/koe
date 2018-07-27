import os

import numpy as np
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.urls import reverse
from pycspade import cspade

from koe.model_utils import get_user_databases, get_current_similarity
from koe.models import AudioFile, Segment, DatabaseAssignment, DatabasePermission
from root.models import ExtraAttr, ExtraAttrValue
from root.utils import spect_mask_path, spect_fft_path, history_path

__all__ = ['bulk_get_segment_info', 'bulk_get_exemplars', 'bulk_get_song_sequences', 'bulk_get_segments_for_audio',
           'bulk_get_history_entries', 'bulk_get_audio_file_for_raw_recording', 'bulk_get_song_sequence_associations']


def bulk_get_segment_info(segs, extras):
    """
    Return rows contains Segments' information to display in SlickGrid
    :param segs: an array of segment object (or a QuerySet)
    :param extras: Must specify the user to get the correct ExtraAttrValue columns
    :return: [row]
    """
    databases, current_database = get_user_databases(extras.user)
    from_user = extras.from_user
    similarities, current_similarity = get_current_similarity(extras.user, current_database)

    rows = []
    ids = []
    if current_database is None:
        return ids, rows

    segs = segs.filter(audio_file__database=current_database.id)
    values = list(segs.values_list('id', 'start_time_ms', 'end_time_ms', 'mean_ff', 'min_ff', 'max_ff',
                                   'audio_file__name',
                                   'audio_file__id',
                                   'audio_file__quality',
                                   'audio_file__track__name',
                                   'audio_file__track__date',
                                   'audio_file__individual__name',
                                   'audio_file__individual__gender',
                                   'audio_file__individual__species__genus',
                                   'audio_file__individual__species__species'
                                   ))

    segids = [x[0] for x in values]
    song_ids = [x[7] for x in values]

    extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user__username=from_user, attr__klass=Segment.__name__, owner_id__in=segids) \
        .values_list('owner_id', 'attr__name', 'value')

    song_extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user__username=from_user, attr__klass=AudioFile.__name__, owner_id__in=song_ids) \
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

    ids = [x[0] for x in values]

    nrows = len(values)
    if current_similarity is None:
        indices = [0] * nrows
    else:
        sorted_ids = current_similarity.ids
        try:
            sorted_order = current_similarity.order
            indices = sorted_order[np.searchsorted(sorted_ids, ids)].tolist()
        except IndexError as e:
            # This happens when the referenced IDs no longer exist - most likely because the
            # segmentation changed

            indices = [0] * nrows

    for i in range(nrows):
        id, start, end, mean_ff, min_ff, max_ff, song_name, song_id, quality, track, date, individual, gender, genus, \
            species = values[i]

        index = indices[i]
        mask_img = spect_mask_path(id, for_url=True)

        if not os.path.isfile(mask_img[1:]):
            mask_img = ''

        spect_img = spect_fft_path(id, 'syllable', for_url=True)
        duration = end - start
        species_str = '{} {}'.format(genus, species)
        url = reverse('segmentation', kwargs={'file_id': song_id})
        url = '[{}]({})'.format(url, song_name)
        row = dict(id=id, start_time_ms=start, end_time_ms=end, duration=duration, song=url, signal_mask=mask_img,
                   dtw_index=index, song_track=track, song_individual=individual, song_gender=gender,
                   song_quality=quality, song_date=date, mean_ff=mean_ff, min_ff=min_ff, max_ff=max_ff,
                   spectrogram=spect_img, species=species_str)
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
    cls = extras.cls
    from_user = extras.from_user
    _, current_database = get_user_databases(extras.user)

    if isinstance(objs, QuerySet):
        ids = objs.filter(audio_file__database=current_database).values_list('id', flat=True)
    else:
        ids = [x.id for x in objs if x.audio_file.database == current_database]

    values = ExtraAttrValue.objects.filter(attr__klass=Segment.__name__, attr__name=cls, owner_id__in=ids,
                                           user__username=from_user) \
        .order_by(Lower('value'), 'owner_id').values_list('value', 'owner_id')

    class_to_exemplars = []
    current_class = ''
    current_exemplars_list = None
    current_exemplars_count = 0
    total_exemplars_count = 0

    from koe.jsons import num_exemplars

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
                elif current_exemplars_count < num_exemplars:
                    current_exemplars_list.append(owner_id)
                    current_exemplars_count += 1

                total_exemplars_count += 1

    class_to_exemplars.append((current_class, total_exemplars_count, current_exemplars_list))

    rows = []
    ids = []
    for cls, count, exemplars in class_to_exemplars:
        if cls:
            row = dict(id=cls, cls=cls, count=count)
            for i in range(num_exemplars):
                if i < len(exemplars):
                    mask_img = spect_mask_path(exemplars[i], for_url=True)
                    spect_img = spect_fft_path(exemplars[i], 'syllable', for_url=True)
                else:
                    mask_img = ''
                    spect_img = ''

                if not os.path.isfile(mask_img[1:]):
                    mask_img = ''

                row['exemplar{}_mask'.format(i + 1)] = mask_img
                row['exemplar{}_spect'.format(i + 1)] = spect_img

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
        species_str = '{} {}'.format(genus, species)
        row = dict(id=song_id, filename=filename, url=url, track=track, individual=indv, gender=gender,
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
    cls = extras.cls
    _, current_database = get_user_databases(extras.user)
    from_user = extras.from_user

    if isinstance(all_songs, QuerySet):
        all_songs = all_songs.filter(database=current_database)
        song_ids = all_songs.values_list('id', flat=True)
    else:
        all_songs = [x.id for x in all_songs if x.database == current_database]
        song_ids = all_songs

    segs = Segment.objects.filter(audio_file__in=all_songs) \
        .order_by('audio_file__name', 'start_time_ms')
    values = segs.values_list('id', 'start_time_ms', 'end_time_ms',
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

    label_attr = ExtraAttr.objects.get(klass=Segment.__name__, name=cls)
    labels = ExtraAttrValue.objects.filter(attr=label_attr, owner_id__in=seg_ids, user__username=from_user) \
        .values_list('owner_id', 'value')

    seg_id_to_label = {x: y for x, y in labels}

    extra_attrs = ExtraAttr.objects.filter(klass=AudioFile.__name__)
    extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user__username=from_user, attr__in=extra_attrs, owner_id__in=song_ids) \
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

    for seg_id, start, end, filename, song_id, quality, length, fs, track, date, indv, gender, genus, species in values:
        if song_id not in songs:
            url = reverse('segmentation', kwargs={'file_id': song_id})
            url = '[{}]({})'.format(url, filename)
            duration_ms = round(length * 1000 / fs)
            species_str = '{} {}'.format(genus, species)
            song_info = dict(filename=filename, url=url, track=track, individual=indv, gender=gender,
                             quality=quality, date=date, duration=duration_ms, species=species_str)
            segs_info = []
            songs[song_id] = dict(song=song_info, segs=segs_info)
        else:
            segs_info = songs[song_id]['segs']

        label = seg_id_to_label.get(seg_id, '__NONE__')
        segs_info.append((seg_id, label, start, end))

    for song_id, info in songs.items():
        song_info = info['song']
        segs_info = info['segs']

        sequence_labels = []
        sequence_starts = []
        sequence_ends = []
        sequence_masks = []

        for seg_id, label, start, end in segs_info:
            sequence_labels.append(label)
            sequence_starts.append(start)
            sequence_ends.append(end)
            mask_img = spect_mask_path(seg_id, for_url=True)
            sequence_masks.append(mask_img)

        sequence_str = '-'.join('\"{}\"'.format(x) for x in sequence_labels)

        row = song_info
        row['id'] = song_id
        row['sequence'] = sequence_str
        row['sequence-labels'] = sequence_labels
        row['sequence-starts'] = sequence_starts
        row['sequence-ends'] = sequence_ends
        row['sequence-imgs'] = sequence_masks

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
    from_user = extras.user
    segs = segs.filter(audio_file=file_id)
    values = segs.values_list('id', 'start_time_ms', 'end_time_ms', 'mean_ff', 'min_ff', 'max_ff',)
    ids = []
    rows = []

    segids = [x[0] for x in values]

    extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user__username=from_user, attr__klass=Segment.__name__, owner_id__in=segids) \
        .values_list('owner_id', 'attr__name', 'value')

    extra_attr_values_lookup = {}
    for id, attr, value in extra_attr_values_list:
        if id not in extra_attr_values_lookup:
            extra_attr_values_lookup[id] = {}
        extra_attr_dict = extra_attr_values_lookup[id]
        extra_attr_dict[attr] = value

    for id, start, end, mean_ff, min_ff, max_ff in values:
        ids.append(id)
        duration = end - start
        row = dict(id=id, start=start, end=end, duration=duration, mean_ff=mean_ff, min_ff=min_ff, max_ff=max_ff)

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

    tz = extras.tz
    values = hes.values_list('id', 'filename', 'time', 'user__username', 'user__id', 'database',
                             'database__name', 'note', 'version', 'type')

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
        else:
            file_size = 0
            url = 'Insufficient permission to download'

        row = dict(id=id, url=url, creator=creator, time=tztime, size=file_size, database=database_name, note=note,
                   version=version, __can_import=can_import, __can_delete=user_is_creator, type=type)

        rows.append(row)

    return ids, rows


def bulk_get_song_sequence_associations(all_songs, extras):
    cls = extras.cls
    _, current_database = get_user_databases(extras.user)
    from_user = extras.from_user

    if isinstance(all_songs, QuerySet):
        all_songs = all_songs.filter(database=current_database)
    else:
        all_songs = [x.id for x in all_songs if x.database == current_database]

    segs = Segment.objects.filter(audio_file__in=all_songs) \
        .order_by('audio_file__name', 'start_time_ms')

    values = segs.values_list('id', 'audio_file__id')

    seg_ids = segs.values_list('id', flat=True)

    label_attr = ExtraAttr.objects.get(klass=Segment.__name__, name=cls)
    labels = ExtraAttrValue.objects.filter(attr=label_attr, owner_id__in=seg_ids, user__username=from_user) \
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
        # else:
        #     print('Skip song {} due to having unlabelled data'.format(song_id))

    ids = []
    rows = []

    if len(sequences) == 0:
        return ids, rows

    result = cspade(data=sequences, support=20, maxgap=1)
    mined_objects = result['mined_objects']
    nseqs = result['nsequences']

    for idx, mined_object in enumerate(mined_objects):
        items = mined_object.items
        if len(items) == 1:
            continue
        conf = -1 if mined_object.confidence is None else mined_object.confidence
        lift = -1 if mined_object.lift is None else mined_object.lift
        assocrule = '->'.join([enums2labels[item.elements[0]] for item in items])

        row = dict(id=idx, chainlength=len(items), transcount=mined_object.noccurs, confidence=conf, lift=lift,
                   support=mined_object.noccurs / nseqs, assocrule=assocrule)

        rows.append(row)
        ids.append(idx)

    return ids, rows


def bulk_get_audio_file_for_raw_recording(audio_files, extras):
    return [], []
