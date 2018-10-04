import json
import os
from time import sleep
from logging import warning

import csv
import numpy as np
from django.conf import settings
from django.db.models import F
from scipy.cluster.hierarchy import linkage
from scipy.spatial.distance import squareform, pdist
from scipy.stats import zscore
from sklearn.decomposition import FastICA
from sklearn.decomposition import PCA
from sklearn.manifold import MDS
from sklearn.manifold import TSNE

from koe import binstorage
from koe.aggregator import aggregator_map
from koe.celery import app
from koe.features.feature_extract import feature_extractors
from koe.model_utils import natural_order
from koe.models import Feature, Aggregation, SimilarityIndex
from koe.models import Segment
from koe.models import Task, DataMatrix, Ordination
from koe.task import TaskRunner
from koe.ts_utils import bytes_to_ndarray, get_rawdata_from_binary
from koe.ts_utils import ndarray_to_bytes
from koe.utils import get_wav_info
from root.exceptions import CustomAssertionError
from root.utils import ensure_parent_folder_exists
from root.utils import wav_path, data_path, mkdirp

nfft = 512
noverlap = nfft * 3 // 4
win_length = nfft
stepsize = nfft - noverlap


# @profile
def extract_segment_feature_for_audio_file(wav_file_path, segs_info, feature):
    fs, length = get_wav_info(wav_file_path)

    duration_ms = length * 1000 / fs
    args = dict(nfft=nfft, noverlap=noverlap, wav_file_path=wav_file_path, fs=fs, start=0, end=None,
                win_length=win_length, center=False)

    extractor = feature_extractors[feature.name]
    tids = []
    fvals = []

    if feature.is_fixed_length:
        for tid, beg, end in segs_info:
            args['start'] = beg
            args['end'] = end
            feature_value = extractor(args)
            tids.append(tid)
            fvals.append(feature_value)
    else:
        args['start'] = 0
        args['end'] = None
        audio_file_feature_value = extractor(args)

        if feature.is_one_dimensional:
            feature_length = max(audio_file_feature_value.shape)
            audio_file_feature_value = audio_file_feature_value.reshape((1, feature_length))
        else:
            feature_length = audio_file_feature_value.shape[1]

        for tid, beg, end in segs_info:
            beg_idx = max(0, int(np.floor(beg * feature_length / duration_ms)))
            end_idx = min(feature_length, int(np.ceil(end * feature_length / duration_ms)))
            if end_idx == beg_idx:
                warning('Segment is too short - result might be not meaningful')
                end_idx = beg_idx + 1

            if audio_file_feature_value.ndim == 2:
                feature_value = audio_file_feature_value[:, beg_idx:end_idx]
            else:
                feature_value = audio_file_feature_value[beg_idx:end_idx]

            tids.append(tid)
            fvals.append(feature_value)

    return tids, fvals


# # @profile
def extract_segment_features_for_segments(task, sids, features, f2bs):
    segments = Segment.objects.filter(id__in=sids)
    tids = np.array(segments.values_list('tid', flat=True), dtype=np.int32)
    vals = list(segments.order_by('audio_file', 'start_time_ms')
                .values_list('audio_file__name', 'tid', 'start_time_ms', 'end_time_ms'))

    f2tid2fvals = {}
    f2af2segments = {}
    n_calculations = 0

    for feature in features:
        index_filename, value_filename = f2bs[feature]
        existing_tids = binstorage.retrieve_ids(index_filename)
        sorted_ids, sort_order = np.unique(existing_tids, return_index=True)

        non_existing_idx = np.where(np.logical_not(np.isin(tids, sorted_ids)))
        missing_tids = tids[non_existing_idx]

        af_to_segments = {}

        for name, tid, start, end in vals:
            if tid in missing_tids:
                if name not in af_to_segments:
                    af_to_segments[name] = []
                af_to_segments[name].append((tid, start, end))

        f2af2segments[feature] = af_to_segments
        n_calculations += len(af_to_segments)

    if n_calculations:
        task.start(limit=n_calculations)
        for feature, af_to_segments in f2af2segments.items():
            _tids = []
            _fvals = []
            for song_name, segs_info in af_to_segments.items():
                wav_file_path = wav_path(song_name)
                __tids, __fvals = extract_segment_feature_for_audio_file(wav_file_path, segs_info, feature)
                _tids += __tids
                _fvals += __fvals
                task.tick()
            f2tid2fvals[feature] = (_tids, _fvals)

    return tids, f2tid2fvals


# @profile
def aggregate_feature_values(ptask, sids, f2bs, fa2bs, features, aggregators):
    """
    Compress all feature sequences into fixed-length vectors
    :param sid_to_label:
    :param h5file:
    :param features:
    :return:
    """
    if features is None or len(features) == 0:
        raise Exception('must provide non-empty list of features')

    segment_info = Segment.objects\
        .filter(id__in=sids)\
        .annotate(duration=F('end_time_ms') - F('start_time_ms')).order_by('duration')

    attrs = segment_info.values_list('tid', 'duration', 'audio_file__fs')

    duration2segs = {}
    for tid, duration, fs in attrs:
        if duration not in duration2segs:
            segs = [[], []]
            duration2segs[duration] = segs
        else:
            segs = duration2segs[duration]
        segs[0].append(tid)
        segs[1].append(fs)

    args = dict(nfft=nfft, noverlap=noverlap, wav_file_path=None, start=None, end=None, win_length=win_length,
                center=False)

    n_calculations = 0

    jobs = {}
    for duration, (tids, fss) in duration2segs.items():
        tids = np.array(tids, dtype=np.int32)
        fss = np.array(fss, dtype=np.int32)

        jobs[duration] = {}

        for feature in features:
            f_idf, f_vlf = f2bs[feature]

            for aggregator in aggregators:
                fa_idf, fa_vlf = fa2bs[feature][aggregator]

                existing_tids = binstorage.retrieve_ids(fa_idf)
                sorted_ids, sort_order = np.unique(existing_tids, return_index=True)

                non_existing_idx = np.where(np.logical_not(np.isin(tids, sorted_ids)))
                _tids = tids[non_existing_idx]
                _fss = fss[non_existing_idx]

                n_calculations += len(_tids)

                jobs[duration][feature] = (_tids, _fss, f_idf, f_vlf)

    if not n_calculations:
        ptask.wrapping_up()
        return

    ptask.start(limit=n_calculations)
    result_by_ft = {}
    for duration, ftjobs in jobs.items():
        for feature, (_tids, _fss, f_idf, f_vlf) in ftjobs.items():
            if feature not in result_by_ft:
                result_by_tid = {}
                result_by_ft[feature] = result_by_tid
            else:
                result_by_tid = result_by_ft[feature]

            values = binstorage.retrieve(_tids, f_idf, f_vlf)

            for tid, fs, value in zip(_tids, _fss, values):
                args['fs'] = fs
                result_by_agg = {}
                result_by_tid[tid] = result_by_agg

                if not feature.is_fixed_length:
                    if value.ndim == 2:
                        nframes = value.shape[1]
                    else:
                        nframes = value.shape[0]

                    min_nsamples = nfft + (nframes - 1) * stepsize
                    args['nsamples'] = min_nsamples

                    for aggregator in aggregators:
                        if aggregator.is_chirpy():
                            aggregated = aggregator.process(value, args=args, feature=feature)
                        else:
                            aggregated = aggregator.process(value)

                        result_by_agg[aggregator] = aggregated
                        ptask.tick()

    ptask.wrapping_up()
    for feature in features:
        if feature.is_fixed_length:
            continue
        result_by_tid = result_by_ft[feature]
        agg2tids = {aggregator: ([], []) for aggregator in aggregators}

        for tid, result_by_agg in result_by_tid.items():
            for aggregator, val in result_by_agg.items():
                agg2tids[aggregator][0].append(tid)
                agg2tids[aggregator][1].append(val)

        for aggregator, (tids, vals) in agg2tids.items():
            tids = np.array(tids)
            fa_idf, fa_vlf = fa2bs[feature][aggregator]
            binstorage.store(tids, vals, fa_idf, fa_vlf)


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


def store_feature_values(ids, feature, values_arr):
    index_filename = data_path('binary/features', '{}.idx'.format(feature.name), for_url=False)
    value_filename = data_path('binary/features', '{}.val'.format(feature.name), for_url=False)

    ensure_parent_folder_exists(index_filename)
    binstorage.store(ids, values_arr, index_filename, value_filename)


def extract_rawdata(f2bs, fa2bs, ids, features, aggregators):
    rawdata = []
    col_inds = {}
    col_inds_start = 0

    for feature in features:
        if feature.is_fixed_length:
            index_filename, value_filename = f2bs[feature]
            rawdata_ = binstorage.retrieve(ids, index_filename, value_filename, flat=True)
            rawdata_stacked = np.stack(rawdata_)
            rawdata.append(rawdata_stacked)
            ncols = rawdata_stacked.shape[1]
            col_inds[feature.name] = (col_inds_start, col_inds_start + ncols)
            col_inds_start += ncols
        else:
            for aggregator in aggregators:
                index_filename, value_filename = fa2bs[feature][aggregator]
                rawdata_ = binstorage.retrieve(ids, index_filename, value_filename, flat=True)
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
# @profile
def extract_database_measurements(task_id):
    task = get_or_wait(task_id)
    runner = TaskRunner(task)
    try:
        runner.preparing()

        cls, dm_id = task.target.split(':')
        dm_id = int(dm_id)
        assert cls == DataMatrix.__name__
        dm = DataMatrix.objects.get(id=dm_id)

        if dm.database:
            segments = Segment.objects.filter(audio_file__database=dm.database)
            sids = segments.values_list('id', flat=True)
        else:
            sids = dm.tmpdb.ids

        features = Feature.objects.filter(id__in=dm.features_hash.split('-'))
        aggregations = Aggregation.objects.filter(id__in=dm.aggregations_hash.split('-'))
        aggregators = [aggregator_map[x.name] for x in aggregations]

        # feature to binstorage's files
        f2bs = {}
        # feature+aggregation to binstorage's files
        fa2bs = {}

        for feature in features:
            feature_name = feature.name
            index_filename = data_path('binary/features', '{}.idx'.format(feature_name), for_url=False)
            value_filename = data_path('binary/features', '{}.val'.format(feature_name), for_url=False)
            f2bs[feature] = (index_filename, value_filename)

            if feature not in fa2bs:
                fa2bs[feature] = {}

            for aggregator in aggregators:
                aggregator_name = aggregator.get_name()
                folder = os.path.join('binary', 'features', feature_name)
                mkdirp(os.path.join(settings.MEDIA_URL, folder)[1:])

                index_filename = data_path(folder, '{}.idx'.format(aggregator_name), for_url=False)
                value_filename = data_path(folder, '{}.val'.format(aggregator_name), for_url=False)
                fa2bs[feature][aggregator] = (index_filename, value_filename)

        tids, f2tid2fvals = extract_segment_features_for_segments(runner, sids, features, f2bs)

        for feature, (index_filename, value_filename) in f2bs.items():
            _tids, _fvals = f2tid2fvals.get(feature, (None, None))
            if _tids:
                _tids = np.array(_tids, dtype=np.int32)
                ensure_parent_folder_exists(index_filename)
                binstorage.store(_tids, _fvals, index_filename, value_filename)

        runner.wrapping_up()
        child_task = Task(user=task.user, parent=task)
        child_task.save()
        child_runner = TaskRunner(child_task)
        child_runner.preparing()

        aggregate_feature_values(child_runner, sids, f2bs, fa2bs, features, aggregators)
        child_runner.complete()

        full_sids_path = dm.get_sids_path()
        full_bytes_path = dm.get_bytes_path()
        full_cols_path = dm.get_cols_path()

        data, col_inds = extract_rawdata(f2bs, fa2bs, tids, features, aggregators)

        ndarray_to_bytes(data, full_bytes_path)
        ndarray_to_bytes(np.array(sids, dtype=np.int32), full_sids_path)

        with open(full_cols_path, 'w', encoding='utf-8') as f:
            json.dump(col_inds, f)

        dm.ndims = data.shape[1]
        dm.save()
        runner.complete()

    except Exception as e:
        runner.error(e)


def pca(data, ndims):
    dim_reduce_func = PCA(n_components=ndims)
    return dim_reduce_func.fit_transform(data)


def ica(data, ndims):
    dim_reduce_func = FastICA(n_components=ndims)
    return dim_reduce_func.fit_transform(data)


def tsne(data, ndims):
    assert 2 <= ndims <= 3, 'TSNE can only produce 2 or 3 dimensional result'
    pca_dims = min(50, data.shape[1])
    data = pca(data, pca_dims)

    tsne = TSNE(n_components=ndims, verbose=1, perplexity=10, n_iter=4000)
    tsne_results = tsne.fit_transform(data)

    return tsne_results


def mds(data, ndims):
    pca_dims = max(50, data.shape[1])
    data = pca(data, pca_dims)

    similarities = squareform(pdist(data, 'euclidean'))
    model = MDS(n_components=ndims, dissimilarity='precomputed', random_state=7, verbose=1, max_iter=1000)
    coordinate = model.fit_transform(similarities)
    return coordinate


methods = {'pca': pca, 'ica': pca, 'tsne': tsne, 'mds': mds}


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
        result = method(data, ndims)

        runner.wrapping_up()

        ord_sids_path = ord.get_sids_path()
        ord_bytes_path = ord.get_bytes_path()

        ndarray_to_bytes(result, ord_bytes_path)
        ndarray_to_bytes(sids, ord_sids_path)

        runner.complete()
    except Exception as e:
        runner.error(e)


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

        sids = bytes_to_ndarray(sids_path, np.int32)
        coordinates = get_rawdata_from_binary(source_bytes_path, len(sids))

        tree = linkage(coordinates, method='average')
        order = natural_order(tree)
        sorted_order = np.argsort(order).astype(np.int32)

        runner.wrapping_up()

        sim_sids_path = sim.get_sids_path()
        sim_bytes_path = sim.get_bytes_path()

        ndarray_to_bytes(sorted_order, sim_bytes_path)
        ndarray_to_bytes(sids, sim_sids_path)

        runner.complete()
    except Exception as e:
        runner.error(e)