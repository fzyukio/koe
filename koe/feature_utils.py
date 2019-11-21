import json
import os
from time import sleep

import csv
import numpy as np
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform, pdist
from scipy.stats import zscore
from sklearn.decomposition import FastICA
from sklearn.decomposition import PCA
from sklearn.manifold import MDS
from sklearn.manifold import TSNE

from koe import binstorage3 as bs
from koe.aggregator import aggregator_map
from koe.celery_init import app
from koe.features.feature_extract import feature_extractors
from koe.model_utils import natural_order
from koe.models import Feature, Aggregation, SimilarityIndex, AudioFile
from koe.models import Segment
from koe.models import Task, DataMatrix, Ordination
from koe.storage_utils import get_storage_loc_template
from koe.task import TaskRunner
from koe.ts_utils import bytes_to_ndarray, get_rawdata_from_binary
from koe.ts_utils import ndarray_to_bytes
from koe.utils import wav_path
from koe.wavfile import get_wav_info
from root.exceptions import CustomAssertionError
from root.utils import mkdirp

nfft = 512
noverlap = nfft * 3 // 4
win_length = nfft
stepsize = nfft - noverlap


@profile  # noqa F821
def extract_segment_feature_for_audio_file(wav_file_path, segs_info, feature, **kwargs):
    fs, length = get_wav_info(wav_file_path)

    args = dict(nfft=nfft, noverlap=noverlap, wav_file_path=wav_file_path, fs=fs, start=0, end=None,
                win_length=win_length, center=False, order=44)

    for v, k in kwargs.items():
        args[v] = k

    extractor = feature_extractors[feature.name]
    tids = []
    fvals = []

    for tid, beg, end in segs_info:
        args['start'] = beg
        args['end'] = end
        feature_value = extractor(args)
        tids.append(tid)
        fvals.append(feature_value)

    return tids, fvals


@profile  # noqa F821
def extract_segment_features_for_segments(runner, sids, features, force=False):
    segments = Segment.objects.filter(id__in=sids)
    tids = np.array(segments.values_list('tid', flat=True), dtype=np.int32)

    if len(tids) == 0:
        return

    tid_min = tids.min()
    tid_max = tids.max()

    storage_loc_template = get_storage_loc_template()

    f2af2segments = {}
    n_calculations = 0

    for feature in features:
        storage_loc = storage_loc_template.format(feature.name)
        mkdirp(storage_loc)

        if force:
            tids_target = tids
        else:
            existing_tids = bs.retrieve_ids(storage_loc, (tid_min, tid_max))
            sorted_ids, sort_order = np.unique(existing_tids, return_index=True)

            non_existing_idx = np.where(np.logical_not(np.isin(tids, sorted_ids)))
            missing_tids = tids[non_existing_idx]
            tids_target = missing_tids

        af_to_segments = {}

        vl = segments.filter(tid__in=tids_target).order_by('audio_file', 'start_time_ms')\
                     .values_list('tid', 'audio_file', 'start_time_ms', 'end_time_ms')

        if len(vl):
            for tid, afid, start_time_ms, end_time_ms in vl:
                if afid not in af_to_segments:
                    af_to_segments[afid] = []
                af_to_segments[afid].append((tid, start_time_ms, end_time_ms))

            f2af2segments[feature] = af_to_segments
            n_calculations += len(tids_target)

    if n_calculations:
        runner.start(limit=n_calculations)
        for ind, (feature, af_to_segments) in enumerate(f2af2segments.items()):
            _tids = []
            _fvals = []
            storage_loc = storage_loc_template.format(feature.name)

            afids = list(af_to_segments.keys())
            af_lookup = {x.id: x for x in AudioFile.objects.filter(id__in=afids)}
            for afid, segs_info in af_to_segments.items():
                af = af_lookup[afid]
                wav_file_path = wav_path(af)
                try:
                    __tids, __fvals = extract_segment_feature_for_audio_file(wav_file_path, segs_info, feature)
                except Exception as e:
                    raise Exception('Error extracting [{}] for file {}. Error message: {}'
                                    .format(feature.name, af.name, str(e)))
                #
                _tids += __tids
                _fvals += __fvals

                if len(_tids) >= 100:
                    bs.store(_tids, _fvals, storage_loc)
                    runner.tick(len(_tids))
                    _tids = []
                    _fvals = []

            if len(_tids):
                bs.store(_tids, _fvals, storage_loc)
                runner.tick(len(_tids))


def get_batches(items, batch_size=100):
    nitems = len(items)
    batches = []
    batch_start = 0
    while True:
        batch_end = min(nitems, batch_start + batch_size)
        batches.append(items[batch_start:batch_end])
        if batch_end >= nitems:
            break
        batch_start = batch_end
    return batches


# @profile
def aggregate_feature_values(runner, tids, features, aggregators, force=False):
    """
    Compress all feature sequences into fixed-length vectors
    :param sid_to_label:
    :param h5file:
    :param features:
    :return:
    """
    if features is None or len(features) == 0:
        raise Exception('must provide non-empty list of features')

    storage_loc_template = get_storage_loc_template()

    if len(tids) == 0:
        runner.wrapping_up()
        return

    tid_min = tids.min()
    tid_max = tids.max()

    n_calculations = 0
    jobss = []

    for feature in features:
        if feature.is_fixed_length:
            continue

        jobs = []
        storage_loc = storage_loc_template.format(feature.name)
        fa_storage_loc_template = os.path.join(storage_loc, '{}')

        if force:
            combined_tids = tids
        else:
            combined_tids = []

        for aggregator in aggregators:
            fa_storage_loc = fa_storage_loc_template.format(aggregator.name)
            mkdirp(fa_storage_loc)

            if force:
                tids_target = tids
            else:
                existing_tids = bs.retrieve_ids(fa_storage_loc, (tid_min, tid_max))
                sorted_ids, sort_order = np.unique(existing_tids, return_index=True)

                non_existing_idx = np.where(np.logical_not(np.isin(tids, sorted_ids)))
                missing_tids = tids[non_existing_idx]
                tids_target = np.array(sorted(missing_tids))
                n_tids_target = len(tids_target)
                if n_tids_target:
                    combined_tids.append(tids_target)

            if n_tids_target:
                n_calculations += n_tids_target
                jobs.append((tids_target, aggregator, fa_storage_loc))

        if len(combined_tids):
            combined_tids = np.unique(np.concatenate(combined_tids).astype(np.int32))
            jobss.append((combined_tids, storage_loc, jobs))

    if not n_calculations:
        return

    runner.start(limit=n_calculations)

    for combined_tids, storage_loc, jobs in jobss:
        batches = get_batches(combined_tids, batch_size=100)
        for batch_tids in batches:
            batch_size = len(batch_tids)
            batch_arrs = bs.retrieve(batch_tids, storage_loc)
            for tids_target, aggregator, fa_storage_loc in jobs:
                aggregateds = []
                aggregated_ids = []
                target_batch_ind = np.searchsorted(batch_tids, tids_target)
                batch_id_within_range = np.where(target_batch_ind < batch_size)
                target_batch_ind = target_batch_ind[batch_id_within_range]
                tids_within_range = tids_target[batch_id_within_range]

                for batch_ind, tid in zip(target_batch_ind, tids_within_range):
                    if batch_ind == 0 and batch_tids[0] != tid:
                        continue
                    aggregated_ids.append(tid)
                    arr = batch_arrs[batch_ind]
                    aggregated = aggregator.process(arr)
                    aggregateds.append(aggregated)

                if len(aggregated_ids):
                    aggregated_ids = np.array(aggregated_ids)
                    bs.store(aggregated_ids, aggregateds, fa_storage_loc)
                    runner.tick(len(aggregated_ids))


def get_segment_ids_and_labels(csv_file):
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')
        supplied_fields = reader.fieldnames

        # The first field is always id, the second field is always the primary label type
        primary_label_level = supplied_fields[1]

        return {int(row['id']): row[primary_label_level] for row in reader}


def extract_tids_fvals(tid2fvals, features):
    tids = np.array(list(tid2fvals.keys()))
    tids.sort()

    vals_per_feature = [[] for feature in features]
    for tid in tids:
        fvals = tid2fvals[tid]
        for idx, val in enumerate(fvals):
            vals_per_feature[idx].append(val)

    f2vals = {x: y for x, y in zip(features, vals_per_feature)}
    return tids, f2vals


def extract_rawdata(ids, features, aggregators):
    storage_loc_template = get_storage_loc_template()

    rawdata = []
    col_inds = {}
    col_inds_start = 0

    for feature in features:
        storage_loc = storage_loc_template.format(feature.name)
        if feature.is_fixed_length:
            rawdata_ = bs.retrieve(ids, storage_loc, flat=True)
            rawdata_stacked = np.stack(rawdata_)
            rawdata.append(rawdata_stacked)
            ncols = rawdata_stacked.shape[1]
            col_inds[feature.name] = (col_inds_start, col_inds_start + ncols)
            col_inds_start += ncols
        else:
            fa_storage_loc_template = os.path.join(storage_loc, '{}')
            for aggregator in aggregators:
                fa_storage_loc = fa_storage_loc_template.format(aggregator.name)
                rawdata_ = bs.retrieve(ids, fa_storage_loc, flat=True)
                rawdata_stacked = np.stack(rawdata_)
                rawdata.append(rawdata_stacked)
                ncols = rawdata_stacked.shape[1]
                col_inds['{}_{}'.format(feature.name, aggregator.name)] = (col_inds_start, col_inds_start + ncols)
                col_inds_start += ncols
    rawdata = np.concatenate(rawdata, axis=1)

    return rawdata, col_inds


def get_or_wait(task_id):
    task = Task.objects.filter(id=task_id).first()
    sleeps = 0
    max_sleeps = 10
    while task is None and sleeps < max_sleeps:
        sleep(0.5)
        sleeps += 1
        task = Task.objects.filter(id=task_id).first()

    if task is None:
        raise CustomAssertionError('Unable to get task #{} from database'.format(task_id))

    return task


@app.task(bind=False)
def extract_database_measurements(arg=None, force=False):
    if isinstance(arg, int):
        task = get_or_wait(arg)
    else:
        task = arg
    runner = TaskRunner(task)
    try:
        runner.preparing()

        if isinstance(task, Task):
            cls, dm_id = task.target.split(':')
            dm_id = int(dm_id)
            assert cls == DataMatrix.__name__
            dm = DataMatrix.objects.get(id=dm_id)

            if dm.database:
                segments = Segment.objects.filter(audio_file__database=dm.database)
                sids = segments.values_list('id', flat=True)
            else:
                sids = dm.tmpdb.ids
            features_hash = dm.features_hash
            aggregations_hash = dm.aggregations_hash
        else:
            sids = task.sids
            features_hash = task.features_hash
            aggregations_hash = task.aggregations_hash

        if len(sids) == 0:
            raise Exception('Measurement cannot be extracted because your database doesn\'t contain any segments.')

        segments = Segment.objects.filter(id__in=sids)
        tids = np.array(segments.values_list('tid', flat=True), dtype=np.int32)

        features = Feature.objects.filter(id__in=features_hash.split('-'))
        aggregations = Aggregation.objects.filter(id__in=aggregations_hash.split('-'))
        aggregators = [aggregator_map[x.name] for x in aggregations]

        extract_segment_features_for_segments(runner, sids, features, force=force)

        runner.wrapping_up()
        child_task = task.__class__(user=task.user, parent=task)
        child_task.save()
        child_runner = TaskRunner(child_task)
        child_runner.preparing()

        aggregate_feature_values(child_runner, tids, features, aggregators, force=force)
        child_runner.complete()

        if isinstance(task, Task):
            full_sids_path = dm.get_sids_path()
            full_bytes_path = dm.get_bytes_path()
            full_cols_path = dm.get_cols_path()

            data, col_inds = extract_rawdata(tids, features, aggregators)

            ndarray_to_bytes(data, full_bytes_path)
            ndarray_to_bytes(np.array(sids, dtype=np.int32), full_sids_path)

            with open(full_cols_path, 'w', encoding='utf-8') as f:
                json.dump(col_inds, f)

            dm.ndims = data.shape[1]
            dm.save()
        runner.complete()

    except Exception as e:
        runner.error(e)


def pca(data, ndims, **kwargs):
    params = dict(n_components=ndims)
    params.update(kwargs)
    kwargs['n_components'] = ndims
    dim_reduce_func = PCA(**params)
    return dim_reduce_func.fit_transform(data)


def ica(data, ndims, **kwargs):
    params = dict(n_components=ndims)
    params.update(kwargs)
    dim_reduce_func = FastICA(**params)
    return dim_reduce_func.fit_transform(data)


def pca_optimal(data, max_ndims, min_explained, min_ndims=2):
    """
    Incrementally increase the dimensions of PCA until sum explained reached a threshold
    :param data: 2D ndarray
    :param max_ndims: maximum number of dimensions to try. Return when reached even if explained threshold hasn't.
    :param min_explained: The minimum explained threshold. Might not reached.
    :return: sum explained and the PCA result.
    """
    for ndim in range(min_ndims, max_ndims):
        dim_reduce_func = PCA(n_components=ndim)
        retval = dim_reduce_func.fit_transform(data)
        explained = np.sum(dim_reduce_func.explained_variance_ratio_)
        if explained >= min_explained:
            break
    return explained, retval


def tsne(data, ndims, **kwargs):
    assert 2 <= ndims <= 3, 'TSNE can only produce 2 or 3 dimensional result'
    pca_dims = min(50, data.shape[1], data.shape[0])
    if pca_dims < data.shape[1]:
        data = pca(data, pca_dims)

    params = dict(n_components=ndims, verbose=1, perplexity=10, n_iter=4000)
    params.update(kwargs)
    tsne = TSNE(**params)
    tsne_results = tsne.fit_transform(data)

    return tsne_results


def mds(data, ndims, **kwargs):
    pca_dims = max(50, data.shape[1])
    data = pca(data, pca_dims)

    params = dict(n_components=ndims, dissimilarity='precomputed', random_state=7, verbose=1, max_iter=1000)
    params.update(kwargs)
    similarities = squareform(pdist(data, 'euclidean'))
    model = MDS(**params)
    coordinate = model.fit_transform(similarities)
    return coordinate


methods = {'pca': pca, 'ica': pca, 'tsne': tsne}


@app.task(bind=False)
def construct_ordination(task_id):
    task = get_or_wait(task_id)
    runner = TaskRunner(task)
    try:
        runner.preparing()

        cls, ord_id = task.target.split(':')
        ord_id = int(ord_id)
        assert cls == Ordination.__name__
        ord = Ordination.objects.get(id=ord_id)

        dm = ord.dm
        method_name = ord.method
        ndims = ord.ndims
        param_kwargs = Ordination.params_to_kwargs(ord.params)

        assert dm.task is None or dm.task.is_completed()
        assert method_name in methods.keys(), 'Unknown method {}'.format(method_name)
        assert 2 <= ndims <= 3, 'Only support 2 or 3 dimensional ordination'

        runner.start()
        dm_sids_path = dm.get_sids_path()
        dm_bytes_path = dm.get_bytes_path()

        sids = bytes_to_ndarray(dm_sids_path, np.int32)
        dm_data = get_rawdata_from_binary(dm_bytes_path, len(sids))

        data = zscore(dm_data)
        data[np.where(np.isnan(data))] = 0
        data[np.where(np.isinf(data))] = 0

        method = methods[method_name]
        result = method(data, ndims, **param_kwargs)

        runner.wrapping_up()

        ord_sids_path = ord.get_sids_path()
        ord_bytes_path = ord.get_bytes_path()

        ndarray_to_bytes(result, ord_bytes_path)
        ndarray_to_bytes(sids, ord_sids_path)

        runner.complete()
    except Exception as e:
        runner.error(e)


def _calculate_similarity(sids_path, source_bytes_path, return_tree=False):
    sids = bytes_to_ndarray(sids_path, np.int32)
    coordinates = get_rawdata_from_binary(source_bytes_path, len(sids))

    tree = linkage(coordinates, method='average')
    order = natural_order(tree)
    sorted_order = np.argsort(order).astype(np.int32)
    if return_tree:
        return sids, sorted_order, tree
    return sids, sorted_order


@app.task(bind=False)
def calculate_similarity(task_id):
    task = get_or_wait(task_id)
    runner = TaskRunner(task)
    try:
        runner.preparing()

        cls, sim_id = task.target.split(':')
        sim_id = int(sim_id)
        assert cls == SimilarityIndex.__name__
        sim = SimilarityIndex.objects.get(id=sim_id)

        dm = sim.dm
        ord = sim.ord

        assert dm.task is None or dm.task.is_completed()
        assert ord is None or ord.task is None or ord.task.is_completed()

        if ord:
            sids_path = ord.get_sids_path()
            source_bytes_path = ord.get_bytes_path()
        else:
            sids_path = dm.get_sids_path()
            source_bytes_path = dm.get_bytes_path()

        runner.start()

        sids, sorted_order = _calculate_similarity(sids_path, source_bytes_path)

        runner.wrapping_up()

        sim_sids_path = sim.get_sids_path()
        sim_bytes_path = sim.get_bytes_path()

        ndarray_to_bytes(sorted_order, sim_bytes_path)
        ndarray_to_bytes(sids, sim_sids_path)

        runner.complete()
    except Exception as e:
        runner.error(e)


def drop_useless_columns(mat):
    colmin = np.min(mat, axis=0)
    colmax = np.max(mat, axis=0)

    useful_col_ind = np.where(np.logical_not(np.isclose(colmin, colmax, atol=1e-04)))[0]
    mat = mat[:, useful_col_ind]
    return mat


def aggregate_class_features(syl_label_enum_arr, nlabels, ftvalues, method=np.mean):
    classes_info = [[] for _ in range(nlabels)]
    for sidx, enum_label in enumerate(syl_label_enum_arr):
        classes_info[enum_label].append(sidx)

    n_features = ftvalues.shape[1]
    class_measures = np.zeros((nlabels, n_features))
    for class_idx in range(nlabels):
        this_class_ids = classes_info[class_idx]
        this_class_ftv = ftvalues[this_class_ids]
        class_measures[class_idx, :] = method(this_class_ftv, axis=0)

    return class_measures, classes_info
