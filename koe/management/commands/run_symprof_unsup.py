import os
import pickle

import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.stats import zscore

from koe.feature_utils import drop_useless_columns
from koe.management.abstract_commands.run_symprof import SymprofCommand, recursive_simprof
from koe.management.utils.matplotlib_utils import plot_dendrogram, show_highlighed_syllables
from koe.model_utils import get_or_error
from koe.models import DataMatrix
from koe.storage_utils import get_tids
from koe.ts_utils import bytes_to_ndarray, get_rawdata_from_binary
from koe.utils import mat2triu, triu2mat


def divide_clusters(
    global_distmat,
    original_cluster,
    max_cluster_size,
    sub_clusters,
    min_cluster_count=2,
):
    local_to_global_map = {ind: global_ind for ind, global_ind in enumerate(original_cluster)}

    local_distmat = global_distmat[original_cluster, :][:, original_cluster]
    local_disttriu = mat2triu(local_distmat)
    local_tree = linkage(local_disttriu, method="complete")
    local_heights = local_tree[:, 2]
    local_cluster_by_cutoff = cut_tree(local_tree, height=local_heights[-(min_cluster_count - 1)])
    num_clusters = np.max(local_cluster_by_cutoff) + 1

    for cluster_ind in range(num_clusters):
        sub_cluster = np.where(local_cluster_by_cutoff == cluster_ind)[0]
        sub_cluster_size = len(sub_cluster)

        print("sub_cluster_size = {}".format(sub_cluster_size))

        sub_cluster_global_ind = np.array([local_to_global_map[x] for x in sub_cluster])

        if sub_cluster_size > max_cluster_size:
            divide_clusters(global_distmat, sub_cluster_global_ind, max_cluster_size, sub_clusters)
        else:
            sub_clusters.append(sub_cluster_global_ind)


class Command(SymprofCommand):
    def visualise(self, dist_triu, cls_labels, syl_labels, clusters):
        import matplotlib.pyplot as plt

        pdf_name = "symprof-unsup-{}-{}-pca={}%-dendrogram.pdf".format(
            self.feature_grouper, self.max_deviation, self.pca_explained
        )
        pdf = PdfPages(pdf_name)
        tree = linkage(dist_triu, method="complete")
        plot_dendrogram(
            tree,
            "blah",
            syl_labels,
            clusters,
            pdf=pdf,
            fig=plt.figure(figsize=(18, 180)),
        )
        pdf.close()

        pdf_name = "symprof-unsup-{}-{}-pca={}%-syls.pdf".format(
            self.feature_grouper, self.max_deviation, self.pca_explained
        )
        pdf = PdfPages(pdf_name)

        for ind, cluster in enumerate(clusters):
            print("{}/{}".format(ind, len(clusters)))
            if len(cluster) == 1:
                continue
            highlighted_syl_names = syl_labels[cluster]
            highlighted_syls_name = "-".join(highlighted_syl_names)
            highlighted_syl_tids = self.tids[cluster]

            show_highlighed_syllables(highlighted_syls_name, highlighted_syl_tids, pdf=pdf)
        pdf.close()

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(self, *args, **kwargs)
        self.feature_grouper = None
        self.ord = None
        self.dm = None
        self.sids = None
        self.tids = None
        self.coordinates = None
        self.ord_coordinates = None

    def post_init(self, options):
        super(Command, self).post_init(options)

        dmid = options["dmid"]
        self.dm = get_or_error(DataMatrix, dict(id=dmid))

        sids_path = self.dm.get_sids_path()
        source_bytes_path = self.dm.get_bytes_path()

        self.sids = bytes_to_ndarray(sids_path, np.int32)
        self.tids = get_tids(self.sids)
        coordinates = get_rawdata_from_binary(source_bytes_path, len(self.sids))
        coordinates = drop_useless_columns(coordinates)
        coordinates = zscore(coordinates)
        coordinates[np.where(np.isinf(coordinates))] = 0
        coordinates[np.where(np.isnan(coordinates))] = 0
        self.coordinates = coordinates

    def get_class_measures_info(self, options):
        class_measures = self.coordinates
        syl_labels = []
        cls_labels = []
        syl_label_enum_arr = []
        classes_info = []
        for sind, sid in enumerate(self.sids):
            label = str(sind)
            syl_labels.append(label)
            cls_labels.append(label)
            syl_label_enum_arr.append(sind)
            classes_info.append([sind])
        nlabels = len(syl_labels)
        syl_labels = np.array(syl_labels)
        cls_labels = np.array(cls_labels)

        return class_measures, classes_info, nlabels, cls_labels, syl_labels

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            "--dm-id",
            action="store",
            dest="dmid",
            required=True,
            type=str,
            help="ID of the DM, if not provided the program will ask",
        )

    def perform_symprof(self, dist_triu, processed_measures, permuter):
        clusters_by_simprof_pkl_name = "symprof-unsup-{}-{}-pca={}%.pkl".format(
            self.feature_grouper, self.max_deviation, self.pca_explained
        )
        clusters_by_simprof_pkl_file = "/tmp/" + clusters_by_simprof_pkl_name

        clusters_by_cutoff_pkl_name = "cluster-unsup-{}-{}-pca={}%.pkl".format(
            self.feature_grouper, self.max_deviation, self.pca_explained
        )
        clusters_by_cutoff_pkl_file = "/tmp/" + clusters_by_cutoff_pkl_name

        if os.path.isfile(clusters_by_simprof_pkl_file):
            with open(clusters_by_simprof_pkl_file, "rb") as f:
                saved = pickle.load(f)
                clusters_by_symprof = saved["clusters_by_symprof"]
        else:
            nobs = processed_measures.shape[0]
            distmat = triu2mat(dist_triu)

            min_cluster_count = 10
            max_cluster_size = 1000

            if os.path.isfile(clusters_by_cutoff_pkl_file):
                with open(clusters_by_cutoff_pkl_file, "rb") as f:
                    saved = pickle.load(f)
                    sub_clusters = saved["sub_clusters"]
            else:
                original_cluster = np.arange(nobs)
                sub_clusters = []
                divide_clusters(
                    distmat,
                    original_cluster,
                    max_cluster_size,
                    sub_clusters,
                    min_cluster_count,
                )

                with open(clusters_by_cutoff_pkl_file, "wb") as f:
                    pickle.dump(dict(sub_clusters=sub_clusters), f)

            clusters_by_symprof = []
            x = 1
            for sub_cluster in sub_clusters:
                print("========================={}/{}========================".format(x, len(sub_clusters)))
                recursive_simprof(
                    processed_measures,
                    permuter,
                    sub_cluster,
                    clusters_by_symprof,
                    min_cluster_size=10,
                    max_deviation=self.max_deviation,
                    is_structural=self.structural_checker,
                )
                x += 1

            with open(clusters_by_simprof_pkl_file, "wb") as f:
                pickle.dump(dict(clusters_by_symprof=clusters_by_symprof), f)

        return clusters_by_symprof
