"""
Start with all syllables belonging to one class, then split them by distance until each syllable is one class.
At each step, produce sequences, construct a graph and extract features from the graph
"""
import os
import pickle
from abc import abstractmethod

import numpy as np
from django.core.management.base import BaseCommand
from progress.bar import Bar
from scipy.cluster.hierarchy import cut_tree

from koe.cluster_analysis_utils import merge_labels, NameMerger
from koe.graph_utils import resolve_meas, extract_graph_feature
from koe.management.utils.parser_utils import read_cluster_range
from koe.models import AudioFile, Database


class AnalyseGraphMergeCommand(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--profile', action='store', dest='profile', required=True, type=str)
        parser.add_argument('--niter', action='store', dest='niter', required=False, type=int)
        parser.add_argument('--nrand', action='store', dest='nrand', required=False, type=int)
        parser.add_argument('--measurements', action='store', dest='measurements', required=True)
        parser.add_argument('--cluster-range', action='store', dest='cluster_range', default='0:-1')

    @abstractmethod
    def prepare_data_for_analysis(self, pkl_filename, options):
        pass

    @abstractmethod
    def get_name_merger_class(self, options) -> NameMerger:
        pass

    def handle(self, *args, **options):
        profile = options['profile']
        niter = options['niter']
        nrand = options['nrand']
        measurements_str = options['measurements']
        cluster_range = options['cluster_range']

        tsv_filename = profile + '.tsv'
        pkl_filename = profile + '.pkl'

        name_merger_class = self.get_name_merger_class(options)

        measurements_order, measurements_output = resolve_meas(measurements_str)
        extra_args = dict(niter=niter, nrand=nrand)

        if not os.path.isfile(pkl_filename):
            saved_dict = self.prepare_data_for_analysis(pkl_filename, options)
        else:
            with open(pkl_filename, 'rb') as f:
                saved_dict = pickle.load(f)

        tree = saved_dict['tree']
        sids = saved_dict['sids']
        unique_labels = saved_dict['unique_labels']
        classes_info = saved_dict['classes_info']
        database = Database.objects.get(id=saved_dict['dbid'])
        songs = AudioFile.objects.filter(database=database)

        enum2label = {enum: label for enum, label in enumerate(unique_labels)}

        heights = tree[:, 2]
        clusters = cut_tree(tree, height=heights)
        clusters_sizes = np.max(clusters, axis=0)

        min_cluster_size, max_cluster_size = read_cluster_range(cluster_range, clusters_sizes)
        suitable_cluster_inds = np.where(np.logical_and(min_cluster_size < clusters_sizes,
                                                        clusters_sizes < max_cluster_size))[0]

        suitable_clusters = clusters[:, suitable_cluster_inds]
        cutoffs = heights[suitable_cluster_inds]

        n_suitable_clusters = len(suitable_cluster_inds)

        total_run = n_suitable_clusters
        bar = Bar('Running...', max=total_run, suffix='%(percent).1f%% - %(eta)ds')

        with open(tsv_filename, 'w') as f:
            f.write('Cutoff\tNum clusters\t' + '\t'.join(measurements_output) + '\n')

        for i in range(n_suitable_clusters):
            name_merger = name_merger_class()
            merge_func = name_merger.merge

            cutoff = cutoffs[i]
            clustering = suitable_clusters[:, i]
            ncluster = np.max(clustering) + 1
            sid_to_cluster, merged_enum2label = merge_labels(clustering, classes_info, sids, enum2label, merge_func)

            measurements_values = extract_graph_feature(songs, sid_to_cluster, merged_enum2label, measurements_order,
                                                        **extra_args)

            with open(tsv_filename, 'a') as f:
                extractable_values = [measurements_values[x] for x in measurements_output]
                extractable_values_as_string = '\t'.join(map(str, extractable_values))
                f.write('{}\t{}\t'.format(cutoff, ncluster) + extractable_values_as_string + '\n')
            bar.next()
        bar.finish()
