import pickle

from django.core.management import BaseCommand
from django.db.models import Case, When

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_pdf import PdfPages

from koe.models import AudioFile


class Command(BaseCommand):
    def handle(self, *args, **options):
        pkls = {
            "2": "/tmp/showcase-rnn-w2/",
            "3": "/tmp/showcase-rnn-w3/",
            "4": "/tmp/showcase-rnn-w4/",
            "5": "/tmp/showcase-rnn-w5/",
            "6": "/tmp/showcase-rnn-w6/",
            "7": "/tmp/showcase-rnn-w7/",
            "8": "/tmp/showcase-rnn-w8/",
            "9": "/tmp/showcase-rnn-w9/",
            "10": "/tmp/showcase/",
            # '2': '/tmp/showcase-mlp-w2/',
            # '3': '/tmp/showcase-mlp-w3/',
            # '4': '/tmp/showcase-mlp-w4/',
            # '5': '/tmp/showcase-mlp-w5/',
            # '6': '/tmp/showcase-mlp-w6/',
            # '7': '/tmp/showcase-mlp-w7/',
            # '8': '/tmp/showcase-mlp-w8/',
            # '9': '/tmp/showcase-mlp-w9/',
            # '10': '/tmp/showcase-mlp/',
            # 'mlp': '/tmp/showcase-mlp/',
            # 'rnn': '/tmp/showcase/',
            # 'hma': '/tmp/showcase-harma/',
            # 'lsk': '/tmp/showcase-lasseck/',
            # 'l+h': '/tmp/showcase-lasseck-harma/'
        }

        columns = [
            "MAP",
            "F1",
            "Precision",
            "Recall",
            "Elapsed",
            "Correct segs",
            "Auto segs",
            "Duration",
        ]
        # columns_to_use = ['F1', 'Precision', 'Recall']

        result_by_type = {c: {t: [] for t in pkls.keys()} for c in columns}
        result_by_type["Song duration"] = {t: [] for t in pkls.keys()}

        for name, tmpdir in pkls.items():
            result_file = tmpdir + "extra_results.pkl"
            with open(result_file, "rb") as f:
                result = pickle.load(f)
                af_ids = []
                for af_id, (
                    img_filename,
                    score_mAP,
                    score_f1,
                    precision,
                    recall,
                    correct_segments,
                    auto_segments,
                    elapsed,
                ) in result.items():
                    af_ids.append(af_id)
                    result_by_type["MAP"][name].append(score_mAP)
                    result_by_type["F1"][name].append(score_f1)
                    result_by_type["Precision"][name].append(precision)
                    result_by_type["Recall"][name].append(recall)
                    result_by_type["Elapsed"][name].append(elapsed)

                preserved = Case(*[When(id=id, then=pos) for pos, id in enumerate(af_ids)])
                af_vl = AudioFile.objects.filter(id__in=af_ids).order_by(preserved).values_list("length", "fs")
                result_by_type["Duration"][name] = [x / y for x, y in af_vl]

        def ps_to_sigs(ps):
            retval = []
            for p in ps:
                if np.isnan(p):
                    retval.append("-")
                elif p < 0.05:
                    retval.append("*")
                else:
                    retval.append(" ")
            return retval

        # for t, result in result_by_type.items():
        #     data = np.array(list(result_by_type[t].values())).transpose()
        #     columns = list(result_by_type[t].keys())
        #
        #     win_lens = list(pkls.keys())
        #     p_mat = np.zeros((len(win_lens), len(win_lens)))
        #     for i in range(len(win_lens)):
        #         wx = win_lens[i]
        #         wx_rs = result_by_type[t][wx]
        #         for j in range(len(win_lens)):
        #             if i == j:
        #                 p_mat[i,i] = np.nan
        #             else:
        #                 wy = win_lens[j]
        #                 wy_rs = result_by_type[t][wy]
        #
        #                 _, p = stats.ttest_ind(wx_rs, wy_rs)
        #
        #                 p_mat[i, j] = p_mat[j, i] = p
        #
        #     p_mat_sig = [ps_to_sigs(x) for x in p_mat]
        #     print('t-test for type ' + t)
        #     print(',' + ','.join(win_lens))
        #     for wl, x in zip(win_lens, p_mat_sig):
        #         print(wl + ',' + ','.join(x))
        #
        # for t, result in result_by_type.items():
        #     pdf_file = '/Users/yfukuzaw/workspace/latexprojects/mythesis/figures/segmentation_result_plot_{}.pdf'\
        #                .format(t)
        #     pdf = PdfPages()
        #     data = np.array(list(result_by_type[t].values())).transpose()
        #     columns = list(result_by_type[t].keys())
        #
        #     # mlp = result_by_type[t]['mlp']
        #     # rnn = result_by_type[t]['rnn']
        #
        #     # _, p = stats.ttest_ind(mlp, rnn)
        #
        #     fig = plt.figure(figsize=(4, 4), frameon=False)
        #     plt.boxplot(data, labels=columns, showfliers=False, notch=True)
        #
        #     ax = plt.gca()
        #     ax.set_ylabel(t + ' score')
        #     ax.set_xlabel('Method')
        #     # ax.set_xlabel('t-test(mlp, rnn) = {}'.format(p))
        #
        #     pdf.savefig(fig)
        #     plt.close()
        #     pdf.close()

        elapsed_data = result_by_type["Elapsed"]
        duration_data = result_by_type["Duration"]

        pdf = PdfPages(
            "/Users/yfukuzaw/workspace/latexprojects/mythesis/figures/segmentation_result_plot_rnn_elapsed.pdf"
        )
        time_elapsed = np.array(list(elapsed_data.values())).transpose()
        song_durations = np.array(list(duration_data.values())).transpose()
        columns = list(elapsed_data.keys())
        mean_elapsed = time_elapsed * 1000 / song_durations
        mean_elapsed[np.where(np.isinf(mean_elapsed))] = 0
        mean_elapsed = mean_elapsed.mean(axis=0)

        # mlp = result_by_type[t]['mlp']
        # rnn = result_by_type[t]['rnn']

        # _, p = stats.ttest_ind(mlp, rnn)

        fig = plt.figure(figsize=(4, 4), frameon=False)
        y_pos = np.arange(len(columns))
        plt.bar(y_pos, mean_elapsed, align="center", alpha=1, color="k")
        plt.xticks(y_pos, columns)
        plt.subplots_adjust(left=0.15, right=1, top=0.95, bottom=0.1)

        ax = plt.gca()

        for i, v in enumerate(mean_elapsed):
            ax.text(i - 0.5, v + 2, "{:.1f}".format(v), color="k")

        # ax.set_ylabel('Speed (elapsed seconds per audio file second)')
        ax.set_xlabel("Method")

        ax.spines["right"].set_visible(False)
        ax.spines["top"].set_visible(False)
        # ax.set_xlabel('t-test(mlp, rnn) = {}'.format(p))

        pdf.savefig(fig)
        # plt.show()
        plt.close()
        pdf.close()

        print("Done")

        # x = "day"
        # y = "total_bill"
        # hue = "smoker"
        # sns.set(style="whitegrid")
        # df = sns.load_dataset("tips")
        # ax = sns.boxplot(data=df, x=x, y=y)
        # add_stat_annotation(ax, data=df, x=x, y=y, hue=hue,
        #                     box_pairs=[(("Thur", "No"), ("Fri", "No")),
        #                                  (("Sat", "Yes"), ("Sat", "No")),
        #                                  (("Sun", "No"), ("Thur", "Yes"))
        #                                 ],
        #                     test='t-test_ind', text_format='full', loc='inside', verbose=2)
        # plt.legend(loc='upper left', bbox_to_anchor=(1.03, 1))
        # plt.show()
        #
        #
        #
        # import numpy as np
        # from koe.models import *
        # from root.models import *
        #
        # from koe.management.commands.use_segmentation_lasseck import LasseckSegmenter
        # from koe.management.commands.use_segmentation_harma import HarmaSegmenter
        #
        # from koe.management.commands.run_segmentation_rnn import extract_psd
        #
        # from koe.spect_utils import extractors, psd2img
        #
        # af_id = 13227
        # audio_file = AudioFile.objects.get(pk=af_id)
        # extractor = extractors['log_spect']
        # normalise = False
        # is_log_psd = True
        #
        # segmenter = HarmaSegmenter()
        #
        #
        # af_psd = extract_psd(extractor, audio_file, normalise)
        # _, duration_frames = af_psd.shape
        #
        # af_duration_ms = int(audio_file.length / audio_file.fs * 1000)
        #
        # correct_segments = Segment.objects.filter(audio_file=audio_file).values_list('start_time_ms', 'end_time_ms')
        # correct_segments = np.array(list(correct_segments)) / af_duration_ms * duration_frames
        # correct_segments = correct_segments.astype(np.int32)
        #
        # auto_segments, extra = segmenter.get_segment(af_psd, audio_file)
        #
        # af_spect = psd2img(af_psd, islog=is_log_psd, cm='grayflipped')
        # af_spect = np.flipud(af_spect)
        #
        # min_freq = 500
        # num_bins, nframes = af_psd.shape
        # niqst_fs = audio_file.fs / 2
        #
        # lo_bin = int(min_freq * num_bins / niqst_fs)
        #
        # peak_over_time = np.max(af_psd[lo_bin:, :], 0)
        # max_peak = np.max(peak_over_time)
        #
        # import matplotlib.pyplot as plt
        # from matplotlib.backends.backend_pdf import PdfPages
        #
        # pdf = PdfPages('peak_over_time.pdf')
        #
        # fig = plt.figure(figsize=(10, 4))
        # plt.plot(peak_over_time)
        # pdf.savefig(fig)
        # # plt.close()
        #
        #
        # fig = plt.figure(figsize=(10, 6))
        # plt.imshow(af_spect, extent=[0, 1, 0, 1])
        # pdf.savefig(fig)
        # # plt.close()
        #
        # pdf.close()
