import numpy as np
from django.db.models.functions import Lower
from django.db.models.query import QuerySet

from koe.model_utils import get_currents
from koe.models import AudioFile, Segment
from root.models import ExtraAttr, ExtraAttrValue
from root.utils import spect_mask_path, spect_fft_path


__all__ = ['bulk_get_segment_info', 'bulk_get_exemplars']


def bulk_get_segment_info(segs, extras):
    """
    Return rows contains Segments' information to display in SlickGrid
    :param segs: an array of segment object (or a QuerySet)
    :param extras: Must specify the user to get the correct ExtraAttrValue columns
    :return: [row]
    """
    user = extras['user']
    similarities, current_similarity, databases, current_database = get_currents(user)

    rows = []

    if isinstance(segs, QuerySet):
        segs = segs.filter(segmentation__audio_file__database=current_database.id)
        attr_values_list = list(segs.values_list('id', 'start_time_ms', 'end_time_ms', 'mean_ff', 'min_ff', 'max_ff',
                                                 'segmentation__audio_file__name',
                                                 'segmentation__audio_file__id',
                                                 'segmentation__audio_file__quality',
                                                 'segmentation__audio_file__track__name',
                                                 'segmentation__audio_file__track__date',
                                                 'segmentation__audio_file__individual__name',
                                                 'segmentation__audio_file__individual__gender'))
    else:
        attr_values_list = [(x.id,
                             x.start_time_ms,
                             x.end_time_ms,
                             x.mean_ff,
                             x.segmentation.audio_file.name,
                             x.segmentation.audio_file.id,
                             x.segmentation.audio_file.quality,
                             x.segmentation.audio_file.track.name,
                             x.segmentation.audio_file.track.date,
                             x.segmentation.audio_file.individual.name,
                             x.segmentation.audio_file.individual.gender) for x in segs
                            if x.segmentation.audio_file.database == current_database]

    segids = [str(x[0]) for x in attr_values_list]
    extra_attrs = ExtraAttr.objects.filter(klass=Segment.__name__)
    extra_attr_values_list = ExtraAttrValue.objects \
        .filter(user=user, attr__in=extra_attrs, owner_id__in=segids) \
        .values_list('owner_id', 'attr__name', 'value')

    song_ids = list(set([x[4] for x in attr_values_list]))
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

    ids = [x[0] for x in attr_values_list]

    nrows = len(attr_values_list)
    if current_similarity is None:
        indices = [0] * nrows
    else:
        sorted_ids = current_similarity.ids
        sorted_order = current_similarity.order
        indices = sorted_order[np.searchsorted(sorted_ids, ids)].tolist()

    ids = []
    for i in range(nrows):
        id, start, end, mean_ff, min_ff, max_ff, song, song_id, quality, track, date, individual, gender = attr_values_list[i]
        ids.append(id)

        index = indices[i]
        mask_img = spect_mask_path(str(id), for_url=True)
        spect_img = spect_fft_path(str(id), 'syllable', for_url=True)
        duration = end - start
        row = dict(id=id, start_time_ms=start, end_time_ms=end, duration=duration, song=song, signal_mask=mask_img,
                   dtw_index=index, song_track=track, song_individual=individual, song_gender=gender,
                   song_quality=quality, song_date=date, mean_ff=mean_ff, min_ff=min_ff, max_ff=max_ff,
                   spectrogram=spect_img)
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
    cls = extras['cls']
    user = extras['user']
    _, _, _, current_database = get_currents(user)

    if isinstance(objs, QuerySet):
        ids = objs.filter(segmentation__audio_file__database=current_database.id).values_list('id', flat=True)
    else:
        ids = [x.id for x in objs if x.segmentation.audio_file.database == current_database]

    values = ExtraAttrValue.objects.filter(attr__klass=Segment.__name__, attr__name=cls, owner_id__in=ids, user=user)\
        .order_by(Lower('value')).values_list('value', 'owner_id')

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
                row['exemplar{}_mask'.format(i + 1)] = mask_img
                row['exemplar{}_spect'.format(i + 1)] = spect_img

            rows.append(row)
            ids.append(cls)

    return ids, rows

