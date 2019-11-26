import os

from django.core.management.base import BaseCommand
from progress.bar import Bar

import koe.binstorage as bs1
import koe.binstorage3 as bs3
from root.utils import mkdirp

OLD_FEATURE_FOLDER = 'user_data/binary/features/'
NEW_FEATURE_FOLDER = 'user_data/binary/features3/'


def convert(olddir, newdir):
    old_index_file = olddir + '.idx'
    old_value_file = olddir + '.val'

    ids = bs1.retrieve_ids(old_index_file)
    arrs = bs1.retrieve(ids, old_index_file, old_value_file)

    mkdirp(newdir)
    if not os.path.isfile(os.path.join(newdir, '.converted')):
        try:
            bs3.store(ids, arrs, newdir)
            with open(os.path.join(newdir, '.converted'), 'w') as f:
                f.write('done')
        except AssertionError:
            print('Error converting {}'.format(olddir))
    # else:
    #     print('Skip {}'.format(olddir))


class Command(BaseCommand):
    def handle(self, *args, **options):
        old_features_subdir = os.listdir(OLD_FEATURE_FOLDER)

        features = {}
        conversion_count = 0

        for item in old_features_subdir:
            if item.endswith('.idx'):
                name = item[:-4]
            elif item.endswith('.val'):
                name = item[:-4]
            else:
                name = item
            if name not in features:
                features[name] = []
                conversion_count += 1

        for feature_name in features:
            feature_folder = OLD_FEATURE_FOLDER + feature_name
            if os.path.isdir(feature_folder):
                aggegration_subdirs = os.listdir(feature_folder)
                for item in aggegration_subdirs:
                    if item.endswith('.idx'):
                        features[feature_name].append(item[:-4])
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
