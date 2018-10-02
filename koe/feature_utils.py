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
def extract_segment_features_for_audio_file(wav_file_path, segs_info, features, tid2fvals):
    fs, length = get_wav_info(wav_file_path)

    duration_ms = length * 1000 / fs
    args = dict(nfft=nfft, noverlap=noverlap, wav_file_path=wav_file_path, fs=fs, start=0, end=None,
                win_length=win_length, center=False)

    def add_feature_value(tid, val):
        if tid not in tid2fvals:
            fvals = []
            tid2fvals[tid] = fvals
        else:
            fvals = tid2fvals[tid]

        fvals.append(val)

    for fidx, feature in enumerate(features):
        extractor = feature_extractors[feature.name]

        if feature.is_fixed_length:
            for tid, beg, end in segs_info:
                args['start'] = beg
                args['end'] = end
                feature_value = extractor(args)
                add_feature_value(tid, feature_value)
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

                add_feature_value(tid, feature_value)


def extract_segment_features_for_segments(task, sids, features):
    segments = Segment.objects.filter(id__in=sids)

    vals = segments.order_by('audio_file', 'start_time_ms')\
        .values_list('audio_file__name', 'tid', 'start_time_ms', 'end_time_ms')
    af_to_segments = {}

    for name, tid, start, end in vals:
        if name not in af_to_segments:
            af_to_segments[name] = []
        af_to_segments[name].append((tid, start, end))

    num_audio_files = len(af_to_segments)
    update_steps = max(1, num_audio_files // 100)

    tid2fvals = {}
    step_idx = 0
    task.start(max=len(af_to_segments))
    for song_name, segs_info in af_to_segments.items():
        wav_file_path = wav_path(song_name)
        extract_segment_features_for_audio_file(wav_file_path, segs_info, features, tid2fvals)
        step_idx += 1
        if step_idx % update_steps == 0:
            task.tick()

    return tid2fvals


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

    n_calculations = sum([0 if f.is_fixed_length else len(aggregators) for f in features]) * len(sids)
    ptask.start(max=n_calculations)
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

    all_tids = []
    all_aggregated_values = {}

    for duration, (tids, fss) in duration2segs.items():
        all_tids += tids

        tids = np.array(tids, dtype=np.int32)

        for feature in features:
            if feature not in all_aggregated_values:
                all_aggregated_values_this = {}
                all_aggregated_values[feature] = all_aggregated_values_this
            else:
                all_aggregated_values_this = all_aggregated_values[feature]

            f_idf, f_vlf = f2bs[feature]
            values = binstorage.retrieve(tids, f_idf, f_vlf)

            # aggregated_values = {}

            for tid, fs, value in zip(tids, fss, values):
                args['fs'] = fs

                if not feature.is_fixed_length:
                    if value.ndim == 2:
                        nframes = value.shape[1]
                    else:
                        nframes = value.shape[0]

                    min_nsamples = nfft + (nframes - 1) * stepsize
                    args['nsamples'] = min_nsamples

                    for aggregator in aggregators:
                        if aggregator not in all_aggregated_values_this:
                            all_aggregated_values_this[aggregator] = []

                        if aggregator.is_chirpy():
                            aggregated = aggregator.process(value, args=args, feature=feature)
                        else:
                            aggregated = aggregator.process(value)

                        all_aggregated_values_this[aggregator].append(aggregated)
                        ptask.tick()

    ptask.wrapping_up()
    all_tids = np.array(all_tids, dtype=np.int32)
    for feature in features:
        if feature.is_fixed_length:
            continue
        for aggregator in aggregators:
            fa_idf, fa_vlf = fa2bs[feature][aggregator]
            binstorage.store(all_tids, all_aggregated_values[feature][aggregator], fa_idf, fa_vlf)


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

        tid2fvals = extract_segment_features_for_segments(runner, sids, features)
        tids, f2vals = extract_tids_fvals(tid2fvals, features)

        runner.wrapping_up()
        child_task = Task(user=task.user, parent=task)
        child_task.save()
        child_runner = TaskRunner(child_task)
        child_runner.preparing()

        # feature to binstorage's files
        f2bs = {}
        # feature+aggregation to binstorage's files
        fa2bs = {}

        for feature in features:
            feature_name = feature.name
            index_filename = data_path('binary/features', '{}.idx'.format(feature_name), for_url=False)
            value_filename = data_path('binary/features', '{}.val'.format(feature_name), for_url=False)
            f2bs[feature] = (index_filename, value_filename)

            values_arr = f2vals[feature]
            ensure_parent_folder_exists(index_filename)
            binstorage.store(tids, values_arr, index_filename, value_filename)

            if feature not in fa2bs:
                fa2bs[feature] = {}

            for aggregator in aggregators:
                aggregator_name = aggregator.get_name()
                folder = os.path.join('binary', 'features', feature_name)
                mkdirp(os.path.join(settings.MEDIA_URL, folder)[1:])

                index_filename = data_path(folder, '{}.idx'.format(aggregator_name), for_url=False)
                value_filename = data_path(folder, '{}.val'.format(aggregator_name), for_url=False)
                fa2bs[feature][aggregator] = (index_filename, value_filename)

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
    pca_dims = max(50, data.shape[1])
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

        assert dm.task.is_completed()
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

        assert dm.task.is_completed()
        assert ord is None or ord.task.is_completed()

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
        sorted_order = np.argsort(order)

        runner.wrapping_up()

        sim_sids_path = sim.get_sids_path()
        sim_bytes_path = sim.get_bytes_path()

        ndarray_to_bytes(sorted_order, sim_bytes_path)
        ndarray_to_bytes(sids, sim_sids_path)

        runner.complete()
    except Exception as e:
        runner.error(e)
