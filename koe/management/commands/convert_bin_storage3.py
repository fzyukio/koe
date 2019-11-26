import os

from django.core.management.base import BaseCommand
from progress.bar import Bar

import koe.binstorage3 as bs3
from root.utils import mkdirp

OLD_FEATURE_FOLDER = 'user_data/binary/features3/'
NEW_FEATURE_FOLDER = 'user_data/binary/features3.new/'


def convert(olddir, newdir):
    ids, arrs = bs3.retrieve_raw(olddir)

    mkdirp(newdir)
    if not os.path.isfile(os.path.join(newdir, '.converted')):
        try:
            bs3.store(ids, arrs, newdir)
            with open(os.path.join(newdir, '.converted'), 'w') as f:
                f.write('done')
        except AssertionError:
            print('Error converting {}'.format(olddir))


class Command(BaseCommand):
    def handle(self, *args, **options):
        old_features_subdir = os.listdir(OLD_FEATURE_FOLDER)

        features = {}
        conversion_count = 0

        for item in old_features_subdir:
            if os.path.isdir(os.path.join(OLD_FEATURE_FOLDER, item)):
                features[item] = []
                conversion_count += 1

        for feature_name in features:
            feature_folder = OLD_FEATURE_FOLDER + feature_name
            aggegration_subdirs = os.listdir(feature_folder)
            for item in aggegration_subdirs:
                if os.path.isdir(os.path.join(feature_folder, item)):
                    features[feature_name].append(item)
                    conversion_count += 1

        bar = Bar('Converting...', max=conversion_count)

        for feature_name, aggreations in features.items():
            feature_folder = OLD_FEATURE_FOLDER + feature_name
            new_feature_folder = NEW_FEATURE_FOLDER + feature_name
            convert(feature_folder, new_feature_folder)
            bar.next()

            for aggreation in aggreations:
                aggreation_folder = OLD_FEATURE_FOLDER + feature_name + '/' + aggreation
                new_aggreation_folder = NEW_FEATURE_FOLDER + feature_name + '/' + aggreation
                convert(aggreation_folder, new_aggreation_folder)
                bar.next()

        bar.finish()
