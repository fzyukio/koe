import os

import numpy as np
from django.conf import settings
from django.db.models.functions import Lower
from django.db.models.query import QuerySet
from django.urls import reverse

from koe.model_utils import get_currents
from koe.models import AudioFile, Segment, Database
from root.models import ExtraAttr, ExtraAttrValue
from root.utils import spect_mask_path, spect_fft_path, audio_path, history_path

__all__ = ['bulk_get_segment_info', 'bulk_get_exemplars', 'bulk_get_song_sequences', 'bulk_get_segments_for_audio',
           'bulk_get_history_entries']


def bulk_get_segment_info(segs, extras):
    """
    Return rows contains Segments' information to display in SlickGrid
    :param segs: an array of segment object (or a QuerySet)
    :param extras: Must specify the user to get the correct ExtraAttrValue columns
    :return: [row]
    """
    user = extras.user
    similarities, current_similarity, databases, current_database = get_currents(user)

    rows = []

    if isinstance(segs, QuerySet):
        segs = segs.filter(segmentation__audio_file__database=current_database.id)
        values = list(segs.values_list('id', 'start_time_ms', 'end_time_ms', 'mean_ff', 'min_ff', 'max_ff',
                                       'segmentation__audio_file__name',
                                       'segmentation__audio_file__id',
                                       'segmentation__audio_file__quality',
                                       'segmentation__audio_file__track__name',
                                       'segmentation__audio_file__track__date',
                                       'segmentation__audio_file__individual__name',
                                       'segmentation__audio_file__individual__gender',
                                       'segmentation__audio_file__individual__species__genus',
                                       'segmentation__audio_file__individual__species__species'
                                       ))
    else:
        values = [(x.id, x.start_time_ms, x.end_time_ms, x.mean_ff, x.min_ff, x.max_ff,
                   x.segmentation.audio_file.name,
                   x.segmentation.audio_file.id,
                   x.segmentation.audio_file.quality,
                   x.segmentation.audio_file.track.name,
                   x.segmentation.audio_file.track.date,
                   x.segmentation.audio_file.individual.name,
                   x.segmentation.audio_file.individual.gender,
                   x.segmentation.audio_file.individual.species.genus,
                   x.segmentation.audio_file.individual.species.species) for x in segs
                  if x.segmentation.audio_file.database == current_database]

    segids = [str(x[0]) for x in values]
    extra_attrs = ExtraAttr.objects.filter(klass=Segment.__name__)
    extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user=user, attr__in=extra_attrs, owner_id__in=segids) \
        .values_list('owner_id', 'attr__name', 'value')

    song_ids = list(set([x[4] for x in values]))
    song_extra_attrs = ExtraAttr.objects.filter(klass=AudioFile.__name__)
    song_extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user=user, attr__in=song_extra_attrs, owner_id__in=song_ids) \
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
        sorted_order = current_similarity.order
        indices = sorted_order[np.searchsorted(sorted_ids, ids)].tolist()

    ids = []
    for i in range(nrows):
        id, start, end, mean_ff, min_ff, max_ff, song_name, song_id, quality, track, date, individual, gender, genus, \
            species = values[i]
        ids.append(id)

        index = indices[i]
        mask_img = spect_mask_path(str(id), for_url=True)

        if not os.path.isfile(mask_img[1:]):
            mask_img = ''

        spect_img = spect_fft_path(str(id), 'syllable', for_url=True)
        duration = end - start
        species_str = '{} {}'.format(genus, species)
        url = reverse('segmentation', kwargs={'file_id': song_id})
        url = '[{}]({})'.format(url, song_name)
        row = dict(id=id, start_time_ms=start, end_time_ms=end, duration=duration, song=url, signal_mask=mask_img,
                   dtw_index=index, song_track=track, song_individual=individual, song_gender=gender,
                   song_quality=quality, song_date=date, mean_ff=mean_ff, min_ff=min_ff, max_ff=max_ff,
                   spectrogram=spect_img, species=species_str)
        extra_attr_dict = extra_attr_values_lookup.get(str(id), {})
        song_extra_attr_dict = song_extra_attr_values_lookup.get(str(song_id), {})

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
    user = extras.user
    _, _, _, current_database = get_currents(user)

    if isinstance(objs, QuerySet):
        ids = objs.filter(segmentation__audio_file__database=current_database).values_list('id', flat=True)
    else:
        ids = [x.id for x in objs if x.segmentation.audio_file.database == current_database]

    values = ExtraAttrValue.objects.filter(attr__klass=Segment.__name__, attr__name=cls, owner_id__in=ids, user=user) \
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


def _get_sequence_info_empty_songs(empty_songs):
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
        row['song-url'] = audio_path(filename, settings.AUDIO_COMPRESSED_FORMAT, for_url=True)

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
    user = extras.user
    _, _, _, current_database = get_currents(user)

    if isinstance(all_songs, QuerySet):
        all_songs = all_songs.filter(database=current_database)
        song_ids = all_songs.values_list('id', flat=True)
    else:
        all_songs = [x.id for x in all_songs if x.database == current_database]
        song_ids = all_songs

    segs = Segment.objects.filter(segmentation__audio_file__in=all_songs, segmentation__source='user') \
        .order_by('segmentation__audio_file__name', 'start_time_ms')
    values = segs.values_list('id', 'start_time_ms', 'end_time_ms',
                              'segmentation__audio_file__name',
                              'segmentation__audio_file__id',
                              'segmentation__audio_file__quality',
                              'segmentation__audio_file__length',
                              'segmentation__audio_file__fs',
                              'segmentation__audio_file__track__name',
                              'segmentation__audio_file__track__date',
                              'segmentation__audio_file__individual__name',
                              'segmentation__audio_file__individual__gender',
                              'segmentation__audio_file__individual__species__genus',
                              'segmentation__audio_file__individual__species__species')
    seg_ids = segs.values_list('id', flat=True)

    label_attr = ExtraAttr.objects.get(klass=Segment.__name__, name=cls)
    labels = ExtraAttrValue.objects.filter(attr=label_attr, owner_id__in=seg_ids, user=user) \
        .values_list('owner_id', 'value')

    seg_id_to_label = {int(x): y for x, y in labels}

    extra_attrs = ExtraAttr.objects.filter(klass=AudioFile.__name__)
    extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user=user, attr__in=extra_attrs, owner_id__in=song_ids) \
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
            mask_img = spect_mask_path(str(seg_id), for_url=True)
            sequence_masks.append(mask_img)

        sequence_str = '-'.join('\"{}\"'.format(x) for x in sequence_labels)

        song_url = audio_path(song_info['filename'], settings.AUDIO_COMPRESSED_FORMAT, for_url=True)

        row = song_info
        row['id'] = song_id
        row['sequence'] = sequence_str
        row['sequence-labels'] = sequence_labels
        row['sequence-starts'] = sequence_starts
        row['sequence-ends'] = sequence_ends
        row['sequence-imgs'] = sequence_masks
        row['song-url'] = song_url

        extra_attr_dict = extra_attr_values_lookup.get(str(song_id), {})
        for attr in extra_attr_dict:
            row[attr] = extra_attr_dict[attr]

        ids.append(song_id)
        rows.append(row)

    # Now we have to deal with songs without any segmentation done
    empty_songs = all_songs.exclude(id__in=songs.keys())

    _ids, _rows = _get_sequence_info_empty_songs(empty_songs)
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
    segs = segs.filter(segmentation__audio_file=file_id)
    values = segs.values_list('id', 'start_time_ms', 'end_time_ms')
    ids = []
    rows = []
    for id, start, end in values:
        ids.append(id)
        rows.append(dict(id=id, start=start, end=end))

    return ids, rows


def bulk_get_history_entries(hes, extras):
    tz = extras.tz
    if isinstance(hes, QuerySet):
        values = list(hes.values_list('id', 'filename', 'time', 'user__username', 'user__id'))
    else:
        values = list([(x.id, x.filename, x.time, x.user.username, x.user.id) for x in hes])

    ids = list([x[0] for x in values])
    users = list([x[-1] for x in values])

    extra_attr_values = ExtraAttrValue.objects \
        .filter(owner_id__in=ids, user__id__in=users, attr__in=settings.ATTRS.history.values()) \
        .values_list('owner_id', 'attr__name', 'value')

    database_map = {x[0]: x[1] for x in Database.objects.all().values_list('id', 'name')}

    extra_attr_values_lookup = {}
    for id, attr, value in extra_attr_values:
        if id not in extra_attr_values_lookup:
            extra_attr_values_lookup[id] = {}
        extra_attr_dict = extra_attr_values_lookup[id]

        if attr == 'database':
            extra_attr_dict[attr] = database_map[value]
        else:
            extra_attr_dict[attr] = value

    rows = []
    for id, filename, time, username, userid in values:
        ids.append(id)
        tztime = time.astimezone(tz)

        url_path = history_path(filename, for_url=True)
        local_file_path = url_path[1:]
        if os.path.isfile(local_file_path):
            file_size = os.path.getsize(local_file_path) / 1024
            url = '[{}]({})'.format(url_path, filename)
        else:
            url = 'File is missing'
            file_size = 0

        row = dict(id=id, url=url, creator=username, time=tztime, size=file_size)

        extra_attr_dict = extra_attr_values_lookup.get(str(id), {})

        for attr in extra_attr_dict:
            row[attr] = extra_attr_dict[attr]

        rows.append(row)
    return ids, rows
