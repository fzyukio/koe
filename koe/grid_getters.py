import numpy as np

from django.db.models.query import QuerySet

from koe.models import AudioFile, Segment, Coordinate
from root.models import ExtraAttr, ExtraAttrValue
from root.utils import spect_mask_path, spect_fft_path


__all__ = ['bulk_get_segment_info']


def bulk_get_segment_info(segs, extras):
    """
    Return rows contains Segments' information to display in SlickGrid
    :param segs: an array of segment object (or a QuerySet)
    :param extras: Must specify the user to get the correct ExtraAttrValue columns
    :return: [row]
    """
    user = extras['user']
    rows = []
    if isinstance(segs, QuerySet):
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
                             x.segmentation.audio_file.individual.gender) for x in segs]

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

    similarity = extras['similarity']
    similarity = Coordinate.objects.filter(id=similarity).first()

    nrows = len(attr_values_list)
    if similarity is None:
        indices = [0] * nrows
    else:
        sorted_ids = similarity.ids
        sorted_order = similarity.order
        indices = sorted_order[np.searchsorted(sorted_ids, ids)].tolist()

    for i in range(nrows):
        id, start, end, mean_ff, min_ff, max_ff, song, song_id, quality, track, date, individual, gender = attr_values_list[i]
        index = indices[i]
        mask_img = spect_mask_path(str(id))
        spect_img = spect_fft_path(str(id), 'syllable')
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

    return rows
