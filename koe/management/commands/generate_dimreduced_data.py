"""
Run tsne with different numbers of dimensions, svm and export result
"""
import os
import pickle

import numpy as np
import time
from django.core.management.base import BaseCommand
from scipy.spatial.distance import squareform, pdist
from scipy.stats import zscore
from sklearn.decomposition import PCA
from sklearn.manifold import MDS
from sklearn.manifold import TSNE

from koe.management.commands.extract_data_for_tensorboard import get_sids_tids
from koe.model_utils import get_or_error
from koe.models import Feature, Aggregation, Database, FullTensorData
from koe.ts_utils import bytes_to_ndarray, get_rawdata_from_binary, cherrypick_tensor_data_by_sids


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database', action='store', dest='database_name', required=True, type=str,
                            help='E.g Bellbird, Whale, ..., case insensitive', )
        parser.add_argument('--population', action='store', dest='population_name', required=True, type=str,
                            help='Name of the person who labels this dataset, case insensitive', )
        parser.add_argument('--type', action='store', dest='type', required=True, type=str,
                            help='MDS or TSNE', )
        parser.add_argument('--perplexity', action='store', dest='perplexity', default=10, type=int,
                            help='Only used for TSNE', )
        parser.add_argument('--normalised', dest='normalised', action='store_true', default=False)

    def handle(self, database_name, population_name, type, perplexity, normalised, *args, **kwargs):
        database = get_or_error(Database, dict(name__iexact=database_name))
        assert type in ['tsne2', 'tsne3', 'mds', 'mdspca']

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
        if type.startswith('tsne'):
            file_name = '{}_{}_{}_{}_{}.pkl'.format(database_name, population_name, type, perplexity, normalised_str)
        else:
            file_name = '{}_{}_{}_{}.pkl'.format(database_name, population_name, type, normalised_str)
        if os.path.isfile(file_name):
            with open(file_name, 'rb') as f:
                saved = pickle.load(f)
                coordinate = saved['coordinate']
                stress = saved['stress']
        else:
            population_data = cherrypick_tensor_data_by_sids(full_data, full_sids, sids).astype(np.float64)

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
                ntsne_dims = int(type[4:])
                dim_reduce_func = PCA(n_components=50)
                population_data = dim_reduce_func.fit_transform(population_data, y=None)

                print('Cumulative explained variation: {}'
                      .format(np.sum(dim_reduce_func.explained_variance_ratio_)))

                time_start = time.time()
                tsne = TSNE(n_components=ntsne_dims, verbose=1, perplexity=perplexity, n_iter=4000)
                coordinate = tsne.fit_transform(population_data)
                print('t-SNE done! Time elapsed: {} seconds'.format(time.time() - time_start))
                stress = None

        with open(file_name, 'wb') as f:
            pickle.dump(dict(coordinate=coordinate, stress=stress, sids=sids, tids=tids), f,
                        protocol=pickle.HIGHEST_PROTOCOL)
