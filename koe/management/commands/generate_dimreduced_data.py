"""
Run tsne with different numbers of dimensions, svm and export result
"""
import os
import numpy as np
import pickle
from django.core.management.base import BaseCommand
from scipy.stats import zscore
from sklearn.manifold import MDS

from koe.management.commands.extract_features import run_clustering
from koe.model_utils import get_or_error
from koe.models import Segment, Feature, Aggregation, Database, FullTensorData, AudioFile
from koe.ts_utils import bytes_to_ndarray, get_rawdata_from_binary

from sklearn.decomposition import PCA
from scipy.spatial.distance import squareform, pdist


def get_sids_tids(database, population_name):
    """
    Get ids and tids from all syllables in this database
    :param database:
    :return: sids, tids. sorted by sids
    """
    audio_files = AudioFile.objects.filter(database=database)
    audio_files = [x for x in audio_files if x.name.startswith(population_name)]
    segments = Segment.objects.filter(audio_file__in=audio_files)
    segments_info = segments.values_list('id', 'tid')

    tids = []
    sids = []
    for sid, tid in segments_info:
        tids.append(tid)
        sids.append(sid)
    tids = np.array(tids, dtype=np.int32)
    sids = np.array(sids, dtype=np.int32)
    sids_sort_order = np.argsort(sids)
    sids = sids[sids_sort_order]
    tids = tids[sids_sort_order]

    return sids, tids


def cherrypick_tensor_data(full_data, full_sids, sids):
    sorted_ids, sort_order = np.unique(full_sids, return_index=True)

    non_existing_idx = np.where(np.logical_not(np.isin(sids, sorted_ids)))
    non_existing_ids = sids[non_existing_idx]

    if len(non_existing_ids) > 0:
        err_msg = 'These IDs don\'t exist: {}'.format(','.join(list(map(str, non_existing_ids))))
        raise ValueError(err_msg)

    lookup_ids_rows = np.searchsorted(sorted_ids, sids)
    return full_data[lookup_ids_rows, :]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )
        parser.add_argument('--population', action='store', dest='population_name', required=True, type=str,
                            help='Name of the person who labels this dataset, case insensitive', )
        parser.add_argument('--type', action='store', dest='type', required=True, type=str,
                            help='MDS or TSNE', )
        parser.add_argument('--normalised', dest='normalised', action='store_true', default=False)

    def handle(self, database_name, population_name, type, normalised, *args, **kwargs):
        database = get_or_error(Database, dict(name__iexact=database_name))
        assert type in ['tsne', 'mds', 'mdspca']

        features = Feature.objects.all().order_by('id')
        aggregations = Aggregation.objects.all().order_by('id')

        features_hash = '-'.join(list(map(str, features.values_list('id', flat=True))))
        aggregations_hash = '-'.join(list(map(str, aggregations.values_list('id', flat=True))))

        full_tensor = FullTensorData.objects.filter(database=database, features_hash=features_hash,
                                                    aggregations_hash=aggregations_hash).first()

        if full_tensor is None:
            raise Exception('Full feature matrix not found. Need to create FullTensor first.')

        full_sids_path = full_tensor.get_sids_path()
        full_bytes_path = full_tensor.get_bytes_path()

        full_sids = bytes_to_ndarray(full_sids_path, np.int32)
        full_data = get_rawdata_from_binary(full_bytes_path, len(full_sids))

        sids, tids = get_sids_tids(database, population_name)

        normalised_str = 'normed' if normalised else 'raw'
        file_name = '{}_{}_{}_{}.pkl'.format(database_name, population_name, type, normalised_str)
        if os.path.isfile(file_name):
            with open(file_name, 'rb') as f:
                saved = pickle.load(f)
                coordinate = saved['coordinate']
                stress = saved['stress']
        else:
            population_data = cherrypick_tensor_data(full_data, full_sids, sids).astype(np.float64)

            if normalised:
                population_data = zscore(population_data)

            population_data[np.where(np.isnan(population_data))] = 0
            population_data[np.where(np.isinf(population_data))] = 0

            if type.startswith('mds'):
                if type == 'mdspca':
                    dim_reduce_func = PCA(n_components=50)
                    population_data = dim_reduce_func.fit_transform(population_data, y=None)
                    if hasattr(dim_reduce_func, 'explained_variance_ratio_'):
                        print('Cumulative explained variation for {} principal components: {}'
                              .format(50, np.sum(dim_reduce_func.explained_variance_ratio_)))

                similarities = squareform(pdist(population_data, 'euclidean'))

                model = MDS(n_components=3, dissimilarity='precomputed', random_state=7, verbose=1, max_iter=1000)
                coordinate = model.fit_transform(similarities)
                stress = model.stress_
            else:
                coordinate = run_clustering(population_data, PCA, 50)
                stress = None

        with open(file_name, 'wb') as f:
            pickle.dump(dict(coordinate=coordinate, stress=stress, sids=sids, tids=tids), f,
                        protocol=pickle.HIGHEST_PROTOCOL)
