import json
import zipfile

from progress.bar import Bar

from koe.utils import wav_path


def read_variables(save_to):
    with zipfile.ZipFile(save_to, 'r', zipfile.ZIP_BZIP2, False) as zip_file:
        content = zip_file.read('variables')
        content = str(content, "utf-8")
        variables = json.loads(content)
    return variables


def spect_from_seg(seg, extractor):
    af = seg.audio_file
    wav_file_path = wav_path(af)
    fs = af.fs
    start = seg.start_time_ms
    end = seg.end_time_ms
    database = af.database
    return extractor(wav_file_path, fs=fs, start=start, end=end, nfft=database.nfft, noverlap=database.noverlap)


def encode_syllables(variables, encoder, session, segs, kernel_only):
    num_segs = len(segs)
    batch_size = 200
    extractor = variables['extractor']
    denormalised = variables['denormalised']
    global_max = variables.get('global_max', None)
    global_min = variables.get('global_min', None)
    global_range = global_max - global_min

    num_batches = num_segs // batch_size
    if num_segs / batch_size > num_batches:
        num_batches += 1

    seg_idx = -1
    encoding_result = {}

    bar = Bar('', max=num_segs)

    for batch_idx in range(num_batches):
        if batch_idx == num_batches - 1:
            batch_size = num_segs - (batch_size * batch_idx)

        bar.message = 'Batch #{}/#{} batch size {}'.format(batch_idx, num_batches, batch_size)

        lengths = []
        batch_segs = []
        spects = []
        for idx in range(batch_size):
            seg_idx += 1
            seg = segs[seg_idx]
            batch_segs.append(seg)
            spect = spect_from_seg(seg, extractor)
            if denormalised:
                spect = (spect - global_min) / global_range

            dims, length = spect.shape
            lengths.append(length)
            spects.append(spect.T)
            bar.next()
        encoded = encoder.encode(spects, session=session, kernel_only=kernel_only)

        for encod, seg, length in zip(encoded, batch_segs, lengths):
            encoding_result[seg.id] = encod

        bar.finish()
    return encoding_result
