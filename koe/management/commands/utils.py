import numpy
import psycopg2.extras

from koe import wavfile


def get_syllable_end_time(el_rows):
    """
    The reason for this is we can't rely on the last element to find where the syllable actually ends, despite they
    being sorted by starttime. The last element always start later than the element before it but it could be too short
    it finishes before the previous element finishes

    :param el_rows:
    :return:
    """
    end_time = -1
    for row in el_rows:
        el_end_time = row['starttime'] + row['timelength']
        if el_end_time > end_time:
            end_time = el_end_time
    return end_time


def get_dbconf(dbs):
    conns = {}

    for dbconf in dbs.split(','):
        abbr, dbname, port = dbconf.split(':')
        port = int(port)
        conn = psycopg2.connect(
            "dbname={} user=sa password='sa' host=localhost port={}".format(dbname, port))
        conn.set_client_encoding('LATIN1')
        conns[abbr] = conn

    return conns


def wav_2_mono(file):
    """
    Read a wav file and return fs and first channel's data stream.
    The data is normalised to be equivalent to Matlab's `audioread(...)` function
    :param file:
    :return: fs and signal
    """
    w = wavfile.read(file)
    if len(numpy.shape(w[1])) > 1:
        data = w[1][:, 0]
    else:
        data = w[1]
    fs = w[0]
    bitrate = w[2]
    normalization_factor = float(2 ** (bitrate - 1))
    sig = data / normalization_factor
    return fs, sig
