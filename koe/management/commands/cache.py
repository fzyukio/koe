from django.core.cache import cache
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument(
            "--pattern",
            action="store",
            dest="pattern",
            default="*",
            help="Search pattern",
        )

        parser.add_argument(
            "--action",
            action="store",
            type=str,
            default="list",
            dest="action",
            help="can be clear, show, count, list",
        )

    def handle(self, pattern, action, *args, **options):
        keys = cache.keys(pattern)
        if action == "count":
            print("Found {} keys for pattern {}".format(len(keys), pattern))
        elif action == "list":
            print("Found {} keys for pattern {}: ".format(len(keys), pattern))
            for key in keys:
                print(key)
        elif action == "show":
            for key in keys:
                value = cache.get(key)

                print("Key: {}".format(key))
                print("Value: {}".format(value))

        elif action == "clear":
            cache.delete_pattern(pattern)
        else:
            print("What do you mean '{}'?".format(action))
