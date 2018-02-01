import psycopg2.extras
from dotmap import DotMap


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
        conn = psycopg2.connect("dbname={} user=sa password='sa' host=localhost port={}".format(dbname, port))
        conn.set_client_encoding('LATIN1')
        conns[abbr] = conn

    return conns
