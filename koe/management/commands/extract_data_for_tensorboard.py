"""
Run tsne with different numbers of dimensions, svm and export result
"""
import os

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand
from dotmap import DotMap
from scipy.io import loadmat

from koe.management.commands.run_ndim_tsne_svm import reduce_funcs
from koe.models import Segment
from koe.ts_utils import load_config, get_safe_tensors_name, ndarray_to_bytes, write_config, write_metadata
from root.models import ExtraAttrValue
from root.utils import ensure_parent_folder_exists


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--matfile', action='store', dest='matfile', required=True, type=str,
                            help='Name of the .mat file that stores extracted feature values for Matlab', )

        parser.add_argument('--annotator', action='store', dest='username', default='superuser', type=str,
                            help='Name of the person who labels this dataset, case insensitive', )

        parser.add_argument('--config', action='store', dest='config_name', type=str, required=True,
                            help='Name of the tensorboard configuration - if exists the tensors will be appended')

        parser.add_argument('--tensors', action='store', dest='tensors_name', type=str, required=True,
                            help='Name of the tensorboard\'s tensors data - if exists a numeric appendix will be '
                                 'appended')

        parser.add_argument('--reduce-type', action='store', dest='reduce_type', default='pca', type=str)

    def handle(self, matfile, username, config_name, tensors_name, reduce_type, *args, **options):
        assert reduce_type in reduce_funcs.keys(), 'Unknown function: {}'.format(reduce_type)
        reduce_func = reduce_funcs[reduce_type]

        saved = DotMap(loadmat(matfile))
        sids = saved.sids.ravel()
        rawdata = saved.get('rawdata', saved.dataset).astype(np.float32)

        sids_sort_order = np.argsort(sids)
        sids = sids[sids_sort_order]
        rawdata = rawdata[sids_sort_order]

        dim_reduce_func = reduce_func(n_components=50)
        reduced = dim_reduce_func.fit_transform(rawdata)

        data = reduced
        metadata = {sid: [str(sid)] for sid in sids}

        label_levels = ['label']
        headers = ['id'] + label_levels + ['gender']

        for i in range(len(label_levels)):
            label_level = label_levels[i]
            segment_to_label = \
                {x: y.lower() for x, y in
                 ExtraAttrValue.objects
                     .filter(attr__name=label_level, attr__klass=Segment.__name__, owner_id__in=sids,
                             user__username__iexact=username)
                     .order_by('owner_id')
                     .values_list('owner_id', 'value')
                 }

            for sid in sids:
                metadata[sid].append(segment_to_label.get(sid, ''))

        sid_to_gender = \
            {x: y.lower() for x, y in
             Segment.objects.filter(id__in=sids).order_by('id')
                 .values_list('id', 'audio_file__individual__gender')
             }

        for sid in sids:
            metadata[sid].append(sid_to_gender.get(sid, ''))

        config_file = os.path.join(settings.MEDIA_URL, 'oss_data', '{}.json'.format(config_name))
        config_file = config_file[1:]
        config = load_config(config_file)

        safe_tensors_name = get_safe_tensors_name(config, tensors_name)
        rawdata_path = os.path.join(settings.MEDIA_URL, 'oss_data', config_name, '{}.bytes'.format(safe_tensors_name))
        metadata_path = os.path.join(settings.MEDIA_URL, 'oss_data', config_name, '{}.tsv'.format(safe_tensors_name))

        rawdata_relative_path = rawdata_path[1:]
        metadata_relative_path = metadata_path[1:]

        ensure_parent_folder_exists(config_file)
        ensure_parent_folder_exists(rawdata_relative_path)
        ensure_parent_folder_exists(metadata_relative_path)

        ndarray_to_bytes(data, rawdata_relative_path)
        write_metadata(metadata, sids, headers, metadata_relative_path)

        # Always write config last - to make sure it's not missing anything
        write_config(config, config_file, safe_tensors_name, data.shape, rawdata_path, metadata_path)