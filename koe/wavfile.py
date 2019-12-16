# wavfile.py (Enhanced)
# Date: 2017/01/11 Joseph Basquin
#
# URL: https://gist.github.com/josephernest/3f22c5ed5dabf1815f16efa8fa53d476
# Source: scipy/io/wavfile.py
#
# Added:
# * read: also returns bitrate, cue markers + cue marker labels (sorted), loops, pitch
#         See https://web.archive.org/web/20141226210234/http://www.sonicspot.com/guide/wavefiles.html#labl
# * read: 24 bit & 32 bit IEEE files support (inspired from wavio_weckesser.py from Warren Weckesser)
# * read: added normalized (default False) that returns everything as float in [-1, 1]
# * read: added forcestereo that returns a 2-dimensional array even if input is mono
#
# * write: can write cue markers, cue marker labels, loops, pitch
# * write: 24 bit support
# * write: can write from a float normalized in [-1, 1]
#
# * removed RIFX support (big-endian) (never seen one in 10+ years of audio production/audio programming),
#   only RIFF (little-endian) are supported
# * removed read(..., mmap)
#
#
# Test:
# ..\wav\____wavfile_demo.py


"""
Module to read / write wav files using numpy arrays

Functions
---------
`read`: Return the sample rate (in samples/sec) and data from a WAV file.

`write`: Write a numpy array as a WAV file.

"""
import struct
import warnings

import numpy


class WavFileWarning(UserWarning):
    pass


_ieee = False

SEEK_ABSOLUTE = 0
SEEK_RELATIVE = 1


# assumes file pointer is immediately
#  after the 'fmt ' id
def _read_fmt_chunk(fid):
    res = struct.unpack('<ihHIIHH', fid.read(20))
    size, comp, noc, rate, sbytes, ba, bits = res
    if comp != 1 or size > 16:
        if comp == 3:
            global _ieee
            _ieee = True
            warnings.warn("IEEE format not supported", WavFileWarning)
        else:
            warnings.warn("Unfamiliar format bytes", WavFileWarning)
        if size > 16:
            fid.read(size - 16)
    return size, comp, noc, rate, sbytes, ba, bits


def _skip_unknown_chunk(fid):
    data = fid.read(4)
    size = struct.unpack('<i', data)[0]
    if bool(size & 1):  # if odd number of bytes, move 1 byte further (data chunk is word-aligned)
        size += 1
    fid.seek(size, SEEK_RELATIVE)


def _read_riff_chunk(fid):
    str1 = fid.read(4)
    if str1 != b'RIFF':
        raise ValueError("Not a WAV file.")
    fsize = struct.unpack('<I', fid.read(4))[0] + 8
    str2 = fid.read(4)
    if (str2 != b'WAVE'):
        raise ValueError("Not a WAV file.")
    return fsize


def nearest_multiple(from_number, factor, max_val=None):
    """
    Return the nearest (but smaller) multiple of a factor from a given number
    E.g. nearest multiple of 7 from 20 is 14
    :param from_number:
    :param factor:
    :return:
    """
    if max_val and from_number > max_val:
        from_number = max_val

    residual = from_number % factor
    return from_number - residual


def read_wav_info(file):
    """
    Return info of a wav file
    :param file: a file object or path to a file
    :return:
    """
    if hasattr(file, 'read'):
        fid = file
    else:
        fid = open(file, 'rb')
    _read_riff_chunk(fid)

    # read the next chunk
    fid.read(4)
    size, comp, noc, rate, sbytes, ba, bits = _read_fmt_chunk(fid)
    if bits == 8 or bits == 24:
        dtype = 'u1'
        bytes = 1
    else:
        bytes = bits // 8
        dtype = '<i%d' % bytes

    if bits == 32 and _ieee:
        dtype = 'float32'

    fid.close()
    return size, comp, noc, rate, sbytes, ba, bits, bytes, dtype


def read_data(fid, data_cursor, fmt_info, data_size, beg_ms=0, end_ms=None, mono=False, normalised=True):
    bits = fmt_info['bits']
    ba = fmt_info['ba']
    rate = fmt_info['rate']
    noc = fmt_info['noc']

    if data_cursor:
        fid.seek(data_cursor, SEEK_ABSOLUTE)
    if bits == 8 or bits == 24:
        dtype = 'u1'
        bytes = 1
    else:
        bytes = bits // 8
        dtype = '<i%d' % bytes

    if bits == 32 and _ieee:
        dtype = 'float32'

    beg = int(beg_ms * rate * ba / 1000)

    # Important #2: beg must be at the beginning of a frame
    # e.g. for 16-bit audio (bytes = 2), beg must be divisible by 2
    #      for 24-bit audio (bytes = 1), beg must be divisible by 1
    #      for 32-bit audio (bytes = 4), beg must be divisible by 4
    # Furthermore, if there are more than one channel, beg must be divisible by
    # (bytes per frame * number of channels)
    byte_per_frame = bits // 8
    beg = nearest_multiple(beg, byte_per_frame * noc)
    fid.seek(beg, SEEK_RELATIVE)

    if end_ms is None:
        requested_end = data_size
    else:
        requested_end = int(end_ms * rate * ba / 1000)
    end = nearest_multiple(requested_end, byte_per_frame * noc, data_size)
    zero_pad = requested_end - end

    chunk_size = end - beg
    data = numpy.fromfile(fid, dtype=dtype, count=chunk_size // bytes)

    fid.close()

    if bits == 24:
        a = numpy.empty((len(data) // 3, 4), dtype='u1')
        a[:, :3] = data.reshape((-1, 3))
        a[:, 3:] = (a[:, 3 - 1:3] >> 7) * 255
        data = a.view('<i4').reshape(a.shape[:-1])

    if noc > 1:
        data = data.reshape(-1, noc)

        if mono:
            data = data[:, 0]

    if zero_pad:
        if len(data.shape) == 1:
            zeros = numpy.zeros((zero_pad,), dtype=data.dtype)
        else:
            zeros = numpy.zeros((zero_pad, data.shape[1]), dtype=data.dtype)
        data = numpy.concatenate((data, zeros), axis=0)

    if normalised:
        normfactor = 1.0 / (2 ** (bits - 1))
        data = numpy.ascontiguousarray(data, dtype=numpy.float32) * normfactor
    else:
        data = numpy.ascontiguousarray(data, dtype=data.dtype)

    return data


def read_segment(file, beg_ms=0, end_ms=None, mono=False, normalised=True, return_fs=False):
    """
    Read only the chunk of data between a segment (faster than reading a whole file then select the wanted segment)
    :param normalised: If true, return float32 array, otherwise return the raw ubyte array
    :param file: file name
    :param beg_ms: begin of the segment in milliseconds
    :param end_ms: end of the segment in milliseconds
    :return: a np array
    """
    if hasattr(file, 'read'):
        fid = file
    else:
        fid = open(file, 'rb')

    fsize = _read_riff_chunk(fid)
    rate = None

    fmt_info = dict()
    data_cursor = None
    data_size = None
    retval = None

    while fid.tell() < fsize:
        chunk_id = fid.read(4)
        if chunk_id == b'fmt ':
            _, comp, noc, rate, sbytes, ba, bits = _read_fmt_chunk(fid)
            fmt_info['rate'] = rate
            fmt_info['ba'] = ba
            fmt_info['bits'] = bits
            fmt_info['noc'] = noc
        elif chunk_id == b'data':
            data_size = struct.unpack('<i', fid.read(4))[0]
            if fmt_info is not None:
                retval = read_data(fid, None, fmt_info, data_size, beg_ms, end_ms, mono, normalised)
                break
            else:
                data_cursor = fid.tell()
                fid.seek(data_size, SEEK_RELATIVE)
        else:
            chunk_id = chunk_id.decode().rstrip('\0').encode()
            if len(chunk_id) > 0:
                _skip_unknown_chunk(fid)
            else:
                break

    assert rate is not None, 'Unable to read FMT block from file ' + fid.name
    assert data_size is not None, 'Unable to read DATA block from file ' + fid.name

    if retval is None:
        retval = read_data(fid, data_cursor, fmt_info, data_size, beg_ms, end_ms, mono, normalised)

    if return_fs:
        retval = (retval, rate)

    return retval


def get_wav_info(file, return_noc=False):
    """
    Return fs and length of an audio without readng the entire file
    :param return_noc: True to return number of channels
    :param file: a string or file pointer
    :return:
    """
    if hasattr(file, 'read'):
        fid = file
    else:
        fid = open(file, 'rb')

    fsize = _read_riff_chunk(fid)
    rate = 0
    size = 0
    noc = 0
    ba = 0

    while fid.tell() < fsize:
        chunk_id = fid.read(4)
        if chunk_id == b'fmt ':
            _, comp, noc, rate, sbytes, ba, bits = _read_fmt_chunk(fid)
        elif chunk_id == b'data':
            size = struct.unpack('<i', fid.read(4))[0]
            fid.seek(size, SEEK_RELATIVE)
        else:
            chunk_id = chunk_id.decode().rstrip('\0').encode()
            if len(chunk_id) > 0:
                _skip_unknown_chunk(fid)
            else:
                break

    assert rate != 0 and ba != 0 and noc != 0, 'Unable to read FMT block from file ' + fid.name
    assert size != 0, 'Unable to read DATA block from file ' + fid.name

    length = size // ba
    if return_noc:
        return rate, length, noc
    return rate, length


def _write(filename, rate, data, bitrate=None, markers=None, loops=None, pitch=None):
    """
    Write array bytes
    :param filename:
    :param rate: sampling rate
    :param data: a 3d array with shape: (number_of_samples, number_of_channels, byte_rate ) and dtype uint8
    :return: None
    """
    assert data.dtype == numpy.uint8
    shape = numpy.shape(data)
    assert len(shape) == 3
    assert shape[2] * 8 == bitrate

    fid = open(filename, 'wb')
    fid.write(b'RIFF')
    fid.write(b'\x00\x00\x00\x00')
    fid.write(b'WAVE')

    # fmt chunk
    fid.write(b'fmt ')
    if data.ndim == 1:
        noc = 1
    else:
        noc = data.shape[1]
    bits = data.dtype.itemsize * 8 if bitrate != 24 else 24
    sbytes = rate * (bits // 8) * noc
    ba = noc * (bits // 8)
    fid.write(struct.pack('<ihHIIHH', 16, 1, noc, rate, sbytes, ba, bits))

    fid.write(b'data')
    fid.write(struct.pack('<i', data.nbytes))
    import sys
    if data.dtype.byteorder == '>' or (data.dtype.byteorder == '=' and sys.byteorder == 'big'):
        data = data.byteswap()

    data.tofile(fid)
    # cue chunk
    if markers:  # != None and != []
        if isinstance(markers[0], dict):  # then we have [{'position': 100, 'label': 'marker1'}, ...]
            labels = [m['label'] for m in markers]
            markers = [m['position'] for m in markers]
        else:
            labels = ['' for m in markers]

        fid.write(b'cue ')
        size = 4 + len(markers) * 24
        fid.write(struct.pack('<ii', size, len(markers)))
        for i, c in enumerate(markers):
            s = struct.pack('<iiiiii', i + 1, c, 1635017060, 0, 0, c)  # 1635017060 is struct.unpack('<i',b'data')
            fid.write(s)

        lbls = ''
        for i, lbl in enumerate(labels):
            lbls += b'labl'
            label = lbl + ('\x00' if len(lbl) % 2 == 1 else '\x00\x00')
            size = len(lbl) + 1 + 4  # because \x00
            lbls += struct.pack('<ii', size, i + 1)
            lbls += label

        fid.write(b'LIST')
        size = len(lbls) + 4
        fid.write(struct.pack('<i', size))
        fid.write(
            b'adtl')  # https://web.archive.org/web/20141226210234/http://www.sonicspot.com/guide/wavefiles.html#list
        fid.write(lbls)

        # smpl chunk
    if loops or pitch:
        if not loops:
            loops = []
        if pitch:
            midiunitynote = 12 * numpy.log2(pitch * 1.0 / 440.0) + 69
            midipitchfraction = int((midiunitynote - int(midiunitynote)) * (2 ** 32 - 1))
            midiunitynote = int(midiunitynote)
            # print(midipitchfraction, midiunitynote)
        else:
            midiunitynote = 0
            midipitchfraction = 0
        fid.write(b'smpl')
        size = 36 + len(loops) * 24
        sampleperiod = int(1000000000.0 / rate)

        fid.write(
            struct.pack('<iiiiiIiiii', size, 0, 0, sampleperiod, midiunitynote, midipitchfraction, 0, 0, len(loops), 0))
        for i, loop in enumerate(loops):
            fid.write(struct.pack('<iiiiii', 0, 0, loop[0], loop[1], 0, 0))

    # Determine file size and place it in correct
    #  position at start of the file.
    size = fid.tell()
    fid.seek(4, SEEK_ABSOLUTE)
    fid.write(struct.pack('<i', size - 8))
    fid.close()


def write(filename, rate, data, bitrate=None, markers=None, loops=None, pitch=None, normalized=False):
    """
    Write a numpy array as a WAV file

    Parameters
    ----------
    filename : str
        The name of the file to write (will be over-written).
    rate : int
        The sample rate (in samples/sec).
    data : ndarray
        A 1-D or 2-D numpy array of integer data-type.

    Notes
    -----
    * Writes a simple uncompressed WAV file.
    * The bits-per-sample will be determined by the data-type.
    * To write multiple-channels, use a 2-D array of shape
      (Nsamples, Nchannels).

    """
    # normalization and 24-bit handling
    if bitrate == 24:  # special handling of 24 bit wav, because there is no numpy.int24...
        if normalized:
            data[data > 1.0] = 1.0
            data[data < -1.0] = -1.0
            a32 = numpy.asarray(data * (2 ** 23 - 1), dtype=numpy.int32)
        else:
            a32 = numpy.asarray(data, dtype=numpy.int32)
        if a32.ndim == 1:
            # Convert to a 2D array with a single column.
            a32.shape = a32.shape + (1,)

        # By shifting first 0 bits, then 8, then 16, the resulting output is 24 bit little-endian.
        a8 = (a32.reshape(a32.shape + (1,)) >> numpy.array([0, 8, 16])) & 255
        data = a8.astype(numpy.uint8)
    else:
        if normalized:  # default to 32 bit int
            data[data > 1.0] = 1.0
            data[data < -1.0] = -1.0
            data = numpy.asarray(data * (2 ** 31 - 1), dtype=numpy.int32)

    _write(filename, rate, data, bitrate, markers, loops, pitch)


def write_24b(filename, rate, data):
    """
    Shortcut to write 24 bit audio
    :param filename:
    :param rate:
    :param data:
    :return:
    """
    assert data.dtype == numpy.uint8
    shape = numpy.shape(data)
    assert len(shape) == 3
    assert shape[2] == 3

    _write(filename, rate, data, bitrate=24)
