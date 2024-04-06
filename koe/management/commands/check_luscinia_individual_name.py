"""
Import syllables (not elements) from luscinia (after songs have been imported)
"""

from django.core.management.base import BaseCommand

import openpyxl
import psycopg2.extras
from progress.bar import Bar


COLUMN_NAMES = ["Individual name", "Corrected to"]


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--db",
            action="store",
            dest="db",
            required=True,
            type=str,
            help="Database name",
        )

        parser.add_argument(
            "--port",
            action="store",
            dest="port",
            required=True,
            type=str,
            help="Port",
        )

        parser.add_argument(
            "--host",
            action="store",
            dest="host",
            required=True,
            type=str,
            help="Host",
        )

    def handle(self, db, port, host, *args, **options):
        conn = None
        wb = openpyxl.Workbook()
        ws = wb.create_sheet("Labels", 0)
        ws.append(COLUMN_NAMES)
        try:
            port = int(port)
            conn = psycopg2.connect("dbname={} user=sa password='sa' host={} port={}".format(db, host, port))
            conn.set_client_encoding("LATIN1")

            cur = conn.cursor()

            cur.execute("select name from individual")
            names = cur.fetchall()
            nnames = len(names)
            bar = Bar("Checking file...", max=nnames)
            for idx, name in enumerate(names):
                bar.next()
                ws.append([name[0], ""])
            bar.finish()

            wb.save("Individual_pattern_check.xlsx")

        finally:
            if conn is not None:
                conn.close()
