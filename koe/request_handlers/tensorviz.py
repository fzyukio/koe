import os

from django.http import HttpResponse
from django.template.loader import render_to_string

import numpy as np

from koe.model_utils import get_or_error
from koe.models import (
    Database,
    DatabaseAssignment,
    DataMatrix,
    DerivedTensorData,
    Ordination,
    Segment,
)
from koe.ts_utils import bytes_to_ndarray, extract_tensor_metadata, write_metadata
from root.exceptions import CustomAssertionError
from root.models import ExtraAttr, ExtraAttrValue, User
from root.views import can_have_exception


__all__ = [
    "get_annotators_and_presets",
    "get_data_matrix_config",
    "get_tensor_data_file_paths",
]


def _get_annotation_info(database, annotators):
    syls = Segment.objects.filter(audio_file__database=database)
    nsyls = syls.count()

    labelling_levels = ["label", "label_family", "label_subfamily"]
    labelling_attrs = ExtraAttr.objects.filter(klass=Segment.__name__, name__in=labelling_levels)

    annotation_info = {}

    for annotator in annotators:
        user_annotation = ExtraAttrValue.objects.filter(owner_id__in=syls, user=annotator)
        annotation_info[annotator] = {}

        for labelling_attr in labelling_attrs:
            user_annotation_this_level = user_annotation.filter(attr=labelling_attr)
            if nsyls == 0:
                user_annotation_complete_this_level = 100
            else:
                user_annotation_complete_this_level = user_annotation_this_level.count() / nsyls * 100

            annotation_info[annotator][labelling_attr.name] = user_annotation_complete_this_level
    return annotation_info


def _render_annotation_info(annotation_info, tensors):
    return render_to_string(
        "partials/annotator_dropdown_list_options.html",
        {"annotation_info": annotation_info, "tensors": tensors},
    )


def get_annotators_and_presets(request):
    database_id = get_or_error(request.POST, "database-id")
    database = get_or_error(Database, dict(id=database_id))

    annotators = [x.user for x in DatabaseAssignment.objects.filter(database=database_id)]
    annotation_info = _get_annotation_info(database, annotators)

    tensors = DerivedTensorData.objects.filter(database=database)

    annotation_rendered = _render_annotation_info(annotation_info, tensors)
    preset_rendered = render_to_string("partials/preset_dropdown_list_options.html", {"tensors": tensors})

    return dict(annotation=annotation_rendered, preset=preset_rendered, ntensors=len(tensors))


def get_data_matrix_config(request):
    dm_id = get_or_error(request.POST, "data-matrix-id")
    dm = get_or_error(DataMatrix, dict(id=dm_id))

    selections = dict(
        features=list(map(int, dm.features_hash.split("-"))),
        aggregations=list(map(int, dm.aggregations_hash.split("-"))),
        ndims=dm.ndims,
    )

    return dict(origin="request_database_access", success=True, warning=None, payload=selections)


def get_metadata(request, tensor_name):
    tensor = get_or_error(DerivedTensorData, dict(name=tensor_name))
    full_tensor = tensor.full_tensor

    full_sids_path = full_tensor.get_sids_path()
    sids = bytes_to_ndarray(full_sids_path, np.int32)

    metadata, headers = extract_tensor_metadata(sids, tensor.annotator)
    content = write_metadata(metadata, sids, headers)

    response = HttpResponse()
    response.write(content)
    response["Content-Type"] = "text/tsv"
    response["Content-Length"] = len(content)
    return response


@can_have_exception
def get_ordination_metadata(request, ord_id, viewas):
    ord = get_or_error(Ordination, dict(id=ord_id))

    sids_path = ord.get_sids_path()
    sids = bytes_to_ndarray(sids_path, np.int32)

    viewas = get_or_error(User, dict(username=viewas))

    try:
        metadata, headers = extract_tensor_metadata(sids, viewas)
    except KeyError as e:
        err_message = (
            "Syllable #{} has been deleted from the database since the creation of this ordination and "
            'thus renders it invalid. Please choose another one or rerun the datamatrix named "{}"'.format(
                str(e), ord.dm
            )
        )
        raise CustomAssertionError(err_message)

    content = write_metadata(metadata, sids, headers)

    response = HttpResponse()
    response.write(content)
    response["Content-Type"] = "text/tsv"
    response["Content-Length"] = len(content)
    return response


def get_tensor_data_file_paths(request):
    tensor_name = get_or_error(request.POST, "tensor-name")
    tensor = get_or_error(DerivedTensorData, dict(name=tensor_name))

    sids_path = tensor.full_tensor.get_sids_path()
    bytes_path = tensor.get_bytes_path()

    if not os.path.isfile(bytes_path):
        bytes_path = tensor.full_tensor.get_bytes_path()

    retval = {
        "bytes-path": bytes_path,
        "sids-path": sids_path,
        "database-name": tensor.database.name,
    }
    return dict(origin="request_database_access", success=True, warning=None, payload=retval)
