"""
Import syllables (not elements) from luscinia (after songs have been imported)
"""

import psycopg2.extras
from openpyxl import load_workbook
import argparse

COLUMN_NAMES = ['Individual name', 'Corrected to']

parser = argparse.ArgumentParser(description='Process some integers.')

parser.add_argument(
    '--db',
    action='store',
    dest='db',
    required=True,
    type=str,
    help='Database name',
)

parser.add_argument(
    '--port',
    action='store',
    dest='port',
    required=True,
    type=str,
    help='Port',
)

parser.add_argument(
    '--host',
    action='store',
    dest='host',
    required=True,
    type=str,
    help='Host',
)

parser.add_argument(
    '--xls',
    action='store',
    dest='xls',
    required=True,
    type=str,
    help='Full path to the xls/xlsx/xlsm... file',
)

args = parser.parse_args()
port = args.port
db = args.db
host = args.host
xls = args.xls

conn = None

wb = load_workbook(filename=xls, read_only=True, data_only=True)
ws = wb['Labels']

try:
    port = int(port)
    conn = psycopg2.connect(
        "dbname={} user=sa password='sa' host={} port={}".format(db, host, port))
    conn.set_client_encoding('LATIN1')

    cur = conn.cursor()
    cur.execute('select id, name from individual')
    songs = cur.fetchall()
    song_id_to_name = {}
    song_name_to_id = {}
    for song in songs:
        id = song[0]
        name = song[1]
        song_id_to_name[id] = name
        song_name_to_id[name] = id

    new_name_to_id = {}
    id_to_new_name = {}

    rows = list(ws.rows)
    for idx in range(len(rows)):
        if idx == 0:
            continue
        row = rows[idx]
        original_name = row[0].value
        corrected_name = row[1].value

        if corrected_name:
            try:
                new_name_to_id[corrected_name] = song_name_to_id[original_name]
                id_to_new_name[song_name_to_id[original_name]] = corrected_name
            except KeyError:
                pass

    for idx in range(len(rows)):
        if idx == 0:
            continue
        row = rows[idx]
        original_name = row[0].value
        corrected_name = row[1].value

        if corrected_name:
            try:
                id = song_name_to_id[original_name]
                check_corrected_name = id_to_new_name[id]

                assert corrected_name == check_corrected_name
            except KeyError:
                pass

    for idx in range(len(rows)):
        if idx == 0:
            continue
        row = rows[idx]
        original_name = row[0].value
        corrected_name = row[1].value

        if corrected_name:
            try:
                id = song_name_to_id[original_name]
                cur.execute('update individual set name=\'%s\' where id=%i' % (
                    corrected_name, id))
                conn.commit()
            except KeyError:
                pass
    wb.close()

finally:
    if conn is not None:
        conn.close()
