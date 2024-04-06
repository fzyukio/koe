r"""
Run classifiers and export a)The confusion matrix and b)list of frequently misclassified instances
"""

import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def handle(self, *args, **options):
        files = os.listdir("csv/")
        syls = {}
        total = 0
        for f in files:
            if f.startswith("misclassified__tmi____"):
                f = "csv/{}".format(f)
                total += 1

                print(f)
                with open(f, "r") as _f:
                    lines = _f.readlines()
                    for line in lines[3:]:
                        parts = line.split(",")
                        id = parts[0]
                        label = parts[1]
                        count = int(parts[2])

                        if id in syls:
                            counts = syls[id][0]
                        else:
                            counts = []
                            syls[id] = (counts, label)

                        counts.append(count)

                with open("csv/misclassified__tmi.csv", "w") as f:
                    for id, (counts, label) in syls.items():
                        f.write("{},{},{}\n".format(id, label, sum(counts) / total))
