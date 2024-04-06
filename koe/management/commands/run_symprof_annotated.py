import os

from django.conf import settings

import numpy as np
from matplotlib.backends.backend_pdf import PdfPages
from scipy.cluster.hierarchy import linkage
from scipy.stats import zscore

from koe.cluster_analysis_utils import get_syllable_labels
from koe.feature_utils import aggregate_class_features, drop_useless_columns
from koe.management.abstract_commands.run_symprof import SymprofCommand, recursive_simprof
from koe.management.utils.matplotlib_utils import (
    plot_dendrogram,
    scatter_plot_with_highlighted_clusters,
    show_highlighed_cls_syllables,
)
from koe.model_utils import get_or_error
from koe.models import DataMatrix, Ordination
from koe.storage_utils import get_tids
from koe.ts_utils import bytes_to_ndarray, get_rawdata_from_binary
from root.models import User


class Command(SymprofCommand):
    def visualise(self, dist_triu, cls_labels, syl_labels, clusters):
        if self.ord is not None:
            ord_bytes_path = os.path.join(settings.BASE_DIR, self.ord.get_bytes_path())
            self.ord_coordinates = get_rawdata_from_binary(ord_bytes_path, len(self.sids))

        pdf_name = "symprof-annotated-{}-{}-{}-pca={}%.pdf".format(
            self.feature_grouper,
            self.max_deviation,
            self.class_aggregation,
            self.pca_explained,
        )
        pdf = PdfPages(pdf_name)
        tree = linkage(dist_triu, method="complete")
        plot_dendrogram(tree, "blah", cls_labels, clusters, pdf=pdf)

        for cluster in clusters:
            highlighted_cls_names = cls_labels[np.array(cluster)]
            if len(highlighted_cls_names) == 1:
                continue

            if self.ord is not None:
                scatter_plot_with_highlighted_clusters(
                    highlighted_cls_names,
                    syl_labels,
                    self.sids,
                    self.ord_coordinates,
                    pdf=pdf,
                )
            show_highlighed_cls_syllables(highlighted_cls_names, syl_labels, self.tids, pdf=pdf)
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
        self.class_aggregation = None

    def post_init(self, options):
        super(Command, self).post_init(options)

        dmid = options["dmid"]
        ordid = options["ordid"]
        self.class_aggregation = options["class_aggregation"]

        if (dmid is None) == (ordid is None):
            raise Exception("Either but not both --dm-id and --ord-id should be given")

        if dmid:
            self.dm = get_or_error(DataMatrix, dict(id=dmid))
            self.ord = None
        else:
            self.ord = get_or_error(Ordination, dict(id=ordid))
            self.dm = self.ord.dm

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
        annotator_name = options["annotator_name"]
        label_level = options["label_level"]

        annotator = get_or_error(User, dict(username__iexact=annotator_name))
        syl_labels = get_syllable_labels(annotator, label_level, self.sids)
        cls_labels, syl_label_enum_arr = np.unique(syl_labels, return_inverse=True)

        nlabels = len(cls_labels)
        class_measures, classes_info = aggregate_class_features(
            syl_label_enum_arr, nlabels, self.coordinates, method=np.mean
        )
        return class_measures, classes_info, nlabels, cls_labels, syl_labels

    def perform_symprof(self, dist_triu, processed_measures, permuter):
        nclasses, nfeatures = processed_measures.shape
        inital_inds = np.arange(nclasses)
        clusters = []
        recursive_simprof(
            processed_measures,
            permuter,
            inital_inds,
            clusters,
            max_deviation=self.max_deviation,
            is_structural=self.structural_checker,
        )

        return clusters

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)
        parser.add_argument(
            "--dm-id",
            action="store",
            dest="dmid",
            required=False,
            type=str,
            help="ID of the DM, if not provided the program will ask",
        )
        parser.add_argument(
            "--ord-id",
            action="store",
            dest="ordid",
            required=False,
            type=str,
            help="ID of the ordination, if given, the ordination plot will be rendered",
        )
        parser.add_argument(
            "--annotator",
            action="store",
            dest="annotator_name",
            required=True,
            type=str,
            help="Name of the person who owns this database, case insensitive",
        )
        parser.add_argument(
            "--label-level",
            action="store",
            dest="label_level",
            default="label",
            type=str,
            help="Level of labelling to use",
        )
        parser.add_argument(
            "--class-aggregation",
            action="store",
            dest="class_aggregation",
            default="mean",
            type=str,
        )
