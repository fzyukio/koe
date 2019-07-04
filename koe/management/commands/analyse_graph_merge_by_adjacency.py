"""
Start with all syllables belonging to one class, then split them by distance until each syllable is one class.
At each step, produce sequences, construct a graph and extract features from the graph
"""
import pickle

import numpy as np
from scipy.cluster.hierarchy import linkage

from koe.cluster_analysis_utils import SimpleNameMerger, NameMerger,\
    get_clustering_based_on_user_annotation
from koe.management.abstract_commands.analyse_graph_merge import AnalyseGraphMergeCommand
from koe.management.utils.prompt_utils import prompt_for_object
from koe.model_utils import get_or_error, natural_order
from koe.models import Database
from koe.sequence_utils import calc_class_ajacency, calc_class_dist_by_adjacency
from koe.storage_utils import get_sids_tids
from koe.utils import mat2triu
from root.models import User


def get_database(dbid):
    if dbid is None:
        dbs = Database.objects.all()
        prompt_for_db = 'Choose from one of the following databases: (Press Ctrl + C to exit)'
        db = prompt_for_object(prompt_for_db, dbs)
    else:
        db = get_or_error(Database, dict(id=dbid))
    return db


class Command(AnalyseGraphMergeCommand):
    def prepare_data_for_analysis(self, pkl_filename, options):
        label_level = options['label_level']
        dbid = options['dbid']
        annotator_name = options['annotator_name']

        database = get_database(dbid)

        sids, tids = get_sids_tids(database)
        annotator = get_or_error(User, dict(username__iexact=annotator_name))
        unique_labels, enum_labels = get_clustering_based_on_user_annotation(annotator, label_level, sids)
        nlabels = len(unique_labels)

        adjacency_mat, classes_info = calc_class_ajacency(database, label_level, annotator_name, enum_labels, nlabels)
        distmat = calc_class_dist_by_adjacency(adjacency_mat)

        dist_triu = mat2triu(distmat)

        tree = linkage(dist_triu, method='average')
        order = natural_order(tree)
        sorted_order = np.argsort(order).astype(np.int32)

        saved_dict = dict(tree=tree, sorted_order=sorted_order, distmat=distmat, dbid=database.id,
                          sids=sids, unique_labels=unique_labels, classes_info=classes_info)

        with open(pkl_filename, 'wb') as f:
            pickle.dump(saved_dict, f)

        return saved_dict

    def get_name_merger_class(self, options) -> NameMerger:
        return SimpleNameMerger

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('--db-id', action='store', dest='dbid', required=False, type=str,
                            help='Name of the DM, if not provided the program will ask', )
        parser.add_argument('--annotator', action='store', dest='annotator_name', required=True, type=str,
                            help='Name of the person who owns this database, case insensitive', )
        parser.add_argument('--label-level', action='store', dest='label_level', default='label', type=str,
                            help='Level of labelling to use', )
