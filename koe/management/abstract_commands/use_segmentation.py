"""
Convert audio file to spectrogram. Then use the trained segmentation encoder to detect syllables.
Then display the segmentation on a webpage
"""
import os
import pickle
from abc import abstractmethod

import numpy as np
import time
from PIL import Image
from django.core.management.base import BaseCommand
from progress.bar import Bar

from koe.management.commands.run_segmentation_rnn import extract_psd, good_audio_file_ids
from koe.model_utils import get_or_error
from koe.models import Database, AudioFile, Segment
from koe.spect_utils import extractors, psd2img
from root.utils import mkdirp

bad_groundtruth = [14413, 14358, 14408, 19398, 14480, 14463, 14531, 20067, 14484, 14529, 14530, 14017, 20033, 14478,
                   14486, 14016, 14511, 14372, 14438, 14118, 14528, 14019, 14116]


def generate_html(segmentation_results):
    segmentation_results_sorted = sorted(segmentation_results.items(), key=lambda item: (-item[1][-1], -item[1][1]))

    html_lines = ['''
<tr>
    <th>ID</th>
    <th>MAP</th>
    <th>F1</th>
    <th>Precision</th>
    <th>Recall</th>
    <th>Spect</th>
</tr>
    ''']
    for sid, (img_path, map, f1score, precision, recall) in segmentation_results_sorted:
        html_lines.append(
            '''
            <tr>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td>{}</td>
                <td><img src="{}"/></td>
            </tr>
            '''.format(sid, map, f1score, precision, recall, img_path)
        )

    html = '''
<table style="width:100%">
{}
</table>
    '''.format(''.join(html_lines))
    return html


def paint_segments(af_spect, correct_segments, auto_segments):
    top_bar = np.full((5, af_spect.shape[1], 3), 255, dtype=np.uint8)
    bottom_bar = np.full((5, af_spect.shape[1], 3), 255, dtype=np.uint8)
    for beg, end in correct_segments:
        top_bar[:, beg:end, :] = [255, 0, 0]

    for beg, end in auto_segments:
        bottom_bar[:, beg:end, :] = [0, 255, 0]
    af_spect = np.flip(af_spect, 0)
    af_spect = np.concatenate((bottom_bar, af_spect, top_bar), axis=0)
    return af_spect


number_label = 2


def calc_pr(positive, proposal, ground):
    """
    Calculate precision and recall
    :param positive: number of positive proposal
    :param proposal: number of all proposal
    :param ground: number of ground truth
    :return:
    """
    if proposal == 0:
        return 0, 0
    if ground == 0:
        return 0, 0
    return (1.0 * positive) / proposal, (1.0 * positive) / ground


def match(lst, ratio, ground):
    """
    Match proposal and ground truth
    :param lst: list of proposals(label, start, end, confidence, video_name)
    :param ratio: overlap ratio
    :param ground: list of ground truth(label, start, end, confidence, video_name)
    :return:    correspond_map: record matching ground truth for each proposal
                count_map: record how many proposals is each ground truth matched by
                index_map: index_list of each video for ground truth
    """
    def overlap(prop, ground):
        l_p, s_p, e_p = prop
        l_g, s_g, e_g = ground
        if int(l_p) != int(l_g):
            return 0
        return (min(e_p, e_g) - max(s_p, s_g)) / (max(e_p, e_g) - min(s_p, s_g))

    cos_map = [-1 for _ in range(len(lst))]
    count_map = [0 for _ in range(len(ground))]
    # generate index_map to speed up
    index_map = [[] for _ in range(number_label)]
    for x in range(len(ground)):
        index_map[1].append(x)

    for x in range(len(lst)):
        for y in index_map[int(lst[x][0])]:
            if overlap(lst[x], ground[y]) < ratio:
                continue
            if overlap(lst[x], ground[y]) < overlap(lst[x], ground[cos_map[x]]):
                continue
            cos_map[x] = y
        if cos_map[x] != -1:
            count_map[cos_map[x]] += 1
    positive = sum([(x > 0) for x in count_map])
    return cos_map, count_map, positive


def f1(lst, ratio, ground):
    """
    :param lst: list of proposals(label, start, end, confidence, video_name)
    :param ratio: overlap ratio
    :param ground: list of ground truth(label, start, end, confidence, video_name)
    :return:
    """
    ground = ground.tolist()
    for x in ground:
        x.insert(0, 1)

    cos_map, count_map, positive = match(lst, ratio, ground)
    precision, recall = calc_pr(positive, len(lst), len(ground))
    if (precision + recall) == 0:
        f1_score = 0
    else:
        f1_score = 2 * precision * recall / (precision + recall)
    return f1_score, precision, recall


def ap(lst, ratio, ground):
    """
    Interpolated Average Precision
    :param lst: list of proposals(label, start, end, confidence, video_name)
    :param ratio: overlap ratio
    :param ground: list of ground truth(label, start, end, confidence, video_name)
    :return: score = sigma(precision(recall) * delta(recall))
             Note that when overlap ratio < 0.5, one ground truth will correspond to many proposals
             In that case, only one positive proposal is counted
    """
    for x in lst:
        x.insert(0, 1)

    ground = ground.tolist()
    for x in ground:
        x.insert(0, 1)

    # lst.sort(key=lambda x: x[3])  # sorted by confidence
    cos_map, count_map, positive = match(lst, ratio, ground)
    score = 0
    number_proposal = len(lst)
    number_ground = len(ground)
    old_precision, old_recall = calc_pr(positive, number_proposal, number_ground)

    for x in range(len(lst)):
        number_proposal -= 1
        if cos_map[x] == -1:
            continue
        count_map[cos_map[x]] -= 1
        if count_map[cos_map[x]] == 0:
            positive -= 1

        precision, recall = calc_pr(positive, number_proposal, number_ground)
        if precision > old_precision:
            old_precision = precision
        score += old_precision * (old_recall - recall)
        old_recall = recall
    return score


def showcase_segmentation(variables, segmenter):
    tmp_dir = variables['tmp_dir']
    extractor = variables['extractor']
    is_log_psd = variables['is_log_psd']
    database_name = variables['database_name']
    normalise = variables['normalise']

    database = get_or_error(Database, dict(name__iexact=database_name))
    audio_files = AudioFile.objects.filter(database=database).filter(id=19413)

    segmentation_results = {}
    segmentation_extra = {}
    bar = Bar('Extracting spectrogram and show segmentation...', max=len(audio_files))
    for audio_file in audio_files:
        af_id = audio_file.id
        if af_id in bad_groundtruth or af_id in good_audio_file_ids:
            continue
        af_psd = extract_psd(extractor, audio_file, normalise)
        _, duration_frames = af_psd.shape

        af_duration_ms = int(audio_file.length / audio_file.fs * 1000)

        correct_segments = Segment.objects.filter(audio_file=audio_file).values_list('start_time_ms', 'end_time_ms')
        correct_segments = np.array(list(correct_segments)) / af_duration_ms * duration_frames
        correct_segments = correct_segments.astype(np.int32)

        start = time.time()
        auto_segments, extra = segmenter.get_segment(af_psd, audio_file)
        end = time.time()

        af_spect = psd2img(af_psd, islog=is_log_psd)

        if extra is not None:
            segmenter.paint_extra(af_spect, extra)

        af_spect = np.flipud(af_spect)
        af_spect = paint_segments(af_spect, correct_segments, auto_segments)

        theta = 0.5
        score_mAP = ap(auto_segments, theta, correct_segments)
        score_f1, precision, recall = f1(auto_segments, theta, correct_segments)

        img_filename = '{}.png'.format(af_id)
        img_path = os.path.join(tmp_dir, img_filename)

        img = Image.fromarray(af_spect)
        img.save(img_path, format='PNG')

        segmentation_results[af_id] = (img_filename, score_mAP, score_f1, precision, recall)
        segmentation_extra[af_id] = (img_filename, score_mAP, score_f1, precision, recall, correct_segments,
                                     auto_segments, end - start)
        bar.next()

    html = generate_html(segmentation_results)
    with open(os.path.join(tmp_dir, 'index.html'), 'w') as f:
        f.write(html)
    with open(os.path.join(tmp_dir, 'results.pkl'), 'wb') as f:
        pickle.dump(segmentation_results, f)
    with open(os.path.join(tmp_dir, 'extra_results.pkl'), 'wb') as f:
        pickle.dump(segmentation_extra, f)
    bar.finish()


class Segmenter(object):
    class Meta:
        abstract = True

    @abstractmethod
    def get_segment(self, spectrogram, audio_file):
        pass

    def paint_extra(self, af_spect, extra):
        pass


class UseSegmenter(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--database-name', action='store', dest='database_name', required=True, type=str)
        parser.add_argument('--tmp-dir', action='store', dest='tmp_dir', default='/tmp', type=str)

    @abstractmethod
    def create_segmenter(self, variables) -> Segmenter:
        pass

    @abstractmethod
    def create_variables(self, options) -> dict:
        pass

    @abstractmethod
    def close(self):
        pass

    def handle(self, *args, **options):
        database_name = options['database_name']
        tmp_dir = options['tmp_dir']

        variables = self.create_variables(options)

        format = variables['format']
        extractor = extractors[format]

        if not os.path.isdir(tmp_dir):
            mkdirp(tmp_dir)

        variables['tmp_dir'] = tmp_dir
        variables['extractor'] = extractor
        variables['is_log_psd'] = format.startswith('log_')
        variables['database_name'] = database_name

        segmenter = self.create_segmenter(variables)

        showcase_segmentation(variables, segmenter)
