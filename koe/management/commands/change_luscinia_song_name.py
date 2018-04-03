"""
Import syllables (not elements) from luscinia (after songs have been imported)
"""
import os
import re
from logging import warning

import psycopg2.extras
from openpyxl import load_workbook
import argparse

name_regex = re.compile(
    '(\w{3})_(\d{4})_(\d{2})_(\d{2})_([\w\d]+)_(\d+)_(\w+)\.(B|EX|VG|G|OK)(\..*)?\.wav')

COLUMN_NAMES = ['Song name', 'Problem', 'Recommend name']

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
    type=int,
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

parser.add_argument(
    '--folder',
    action='store',
    dest='folder',
    required=True,
    type=str,
    help='Path to the root folder where the song wavs are stored',
)

args = parser.parse_args()
port = args.port
xls = args.xls
db = args.db
host = args.host
folder = args.folder

conn = None

wb = load_workbook(filename=xls, read_only=True, data_only=True)
ws = wb['Labels']

try:
    port = int(port)
    conn = psycopg2.connect(
        "dbname={} user=sa password='sa' host={} port={}".format(db, host, port))
    conn.set_client_encoding('LATIN1')

    cur = conn.cursor()
    cur.execute(
        'select s.id, s.name, w.filename, w.id from songdata s join wavs w on w.songid=s.id')
    songs = cur.fetchall()
    song_id_to_name = {}
    song_name_to_id = {}
    filename_to_old_name = {}
    old_or_new_name_to_filename = {}

    wav_id_to_filename = {}
    filename_to_wav_id = {}

    for song in songs:
        id = song[0]
        name = song[1]
        filename = song[2]
        wav_id = song[3]

        song_id_to_name[id] = name
        song_name_to_id[name] = id
        wav_id_to_filename[wav_id] = filename
        filename_to_wav_id[filename.lower()] = wav_id

        filename_to_old_name[filename.lower()] = name
        old_or_new_name_to_filename[name] = filename

    new_name_to_id = {}
    id_to_new_name = {}
    old_name_to_new_name = {}

    rows = list(ws.rows)
    for idx in range(len(rows)):
        if idx == 0:
            continue
        row = rows[idx]
        original_name = row[0].value
        corrected_name = row[2].value

        matches = name_regex.match(corrected_name)
        if matches is None:
            warning('Corrected name at row {} is still incorrect: {}'.format(
                idx, corrected_name))
            continue

        old_name_to_new_name[original_name] = corrected_name

        try:
            new_name_to_id[corrected_name] = song_name_to_id[original_name]
            id_to_new_name[song_name_to_id[original_name]] = corrected_name
        except KeyError as e:
            pass

    for idx in range(len(rows)):
        if idx == 0:
            continue
        row = rows[idx]
        original_name = row[0].value
        corrected_name = row[2].value

        try:
            id = song_name_to_id[original_name]
            check_corrected_name = id_to_new_name[id]

            assert corrected_name == check_corrected_name
        except KeyError as e:
            pass

    """
    for idx in range(len(rows)):
        if idx == 0:
            continue
        row = rows[idx]
        original_name = row[0].value
        corrected_name = row[2].value

        try:
            id = song_name_to_id[original_name]
            print('update songdata set name=\'%s\' where id=%i' % (corrected_name, id))
            cur.execute('update songdata set name=\'%s\' where id=%i' % (corrected_name, id))
            conn.commit()
        except KeyError as e:
            pass

    for idx in range(len(rows)):
        if idx == 0:
            continue
        row = rows[idx]
        original_name = row[0].value
        corrected_name = row[2].value

        try:
            if original_name in old_or_new_name_to_filename:
                filename = old_or_new_name_to_filename[original_name]
            else:
                filename = old_or_new_name_to_filename[corrected_name]
            wav_id = filename_to_wav_id[filename.lower()]
            print('update wavs set filename=\'%s\' where id=%i' % (corrected_name, wav_id))
            cur.execute('update wavs set filename=\'%s\' where id=%i' % (corrected_name, wav_id))
            conn.commit()
        except KeyError as e:
            warning('{} or {} not found'.format(original_name, corrected_name))
            pass
    """

    for path, subdirs, files in os.walk(folder):
        for name in files:
            if name.lower() in filename_to_old_name:
                old_name = filename_to_old_name[name.lower()]
                if old_name in old_name_to_new_name:
                    new_name = old_name_to_new_name[old_name]

                    original_file_name = os.path.join(path, name)
                    new_file_name = os.path.join(path, new_name)
                    print('Change {} to {}'.format(
                        original_file_name, new_file_name))
                    os.renames(original_file_name, new_file_name)
                else:
                    matches = name_regex.match(name)
                    if matches is None:
                        warning('File name {} in {} have non-conforming name pattern, '
                                'but there is no correction in the Excel sheet '.format(name, path))
            else:
                # warning('File name {} in {} have does not exist in the database'.format(name, path))
                pass

    files = []

    for path, subdirs, files in os.walk(folder):
        for name in files:
            files.append(name.lower())

    for new_name in old_name_to_new_name.values():
        if new_name.lower() not in files:
            warning('File {} exists in the database but not on disk'.format(new_name))

    wb.close()

finally:
    if conn is not None:
        conn.close()
