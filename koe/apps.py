import os

from django.apps import AppConfig
from django.conf import settings
from dotmap import DotMap


def get_builtin_attrs():
    """
    Query and store some built-in ExtraAttr in settings

    :return: None
    """
    from root.models import ExtraAttr, ValueTypes, User
    from koe.models import AudioFile, Segment, Database

    goc = ExtraAttr.objects.get_or_create

    current_database_attr, _ = goc(klass=User.__name__, name='current-database', type=ValueTypes.SHORT_TEXT)
    hold_ids_attr, _ = goc(klass=User.__name__, name='hold-ids', type=ValueTypes.SHORT_TEXT)
    database_sim_attr, _ = goc(klass=User.__name__, name='database-similarity', type=ValueTypes.SHORT_TEXT)
    tmpdb_sim_attr, _ = goc(klass=User.__name__, name='tmpdb-similarity', type=ValueTypes.SHORT_TEXT)

    song_note_attr, _ = goc(klass=AudioFile.__name__, name='note', type=ValueTypes.LONG_TEXT)
    type_attr, _ = goc(klass=AudioFile.__name__, name='type', type=ValueTypes.SHORT_TEXT)
    label_attr, _ = goc(klass=Segment.__name__, name='label', type=ValueTypes.SHORT_TEXT)
    family_attr, _ = goc(klass=Segment.__name__, name='label_family', type=ValueTypes.SHORT_TEXT)
    subfamily_attr, _ = goc(klass=Segment.__name__, name='label_subfamily', type=ValueTypes.SHORT_TEXT)
    seg_note_attr, _ = goc(klass=Segment.__name__, name='note', type=ValueTypes.SHORT_TEXT)
    db_cm_attr, _ = goc(klass=Database.__name__, name='cm', type=ValueTypes.SHORT_TEXT)
    db_zoom_attr, _ = goc(klass=Database.__name__, name='zoom', type=ValueTypes.SHORT_TEXT)

    settings.ATTRS = DotMap(
        user=DotMap(current_database=current_database_attr, database_sim_attr=database_sim_attr,
                    tmpdb_sim_attr=tmpdb_sim_attr, hold_ids_attr=hold_ids_attr),
        database=DotMap(cm=db_cm_attr, zoom=db_zoom_attr),
        audio_file=DotMap(note=song_note_attr, type=type_attr),
        segment=DotMap(note=seg_note_attr, label=label_attr, family=family_attr, subfamily=subfamily_attr),
    )


class KoeConfig(AppConfig):
    name = 'koe'

    def ready(self):
        """
        Register app specific's views, request handlers and classes to the root app

        Note
        ---
        The app should only load when it runs as a server, not when the fixtures are being loaded,
        otherwise we end up with database problem.
        If the fixtures are loaded by the migrate.sh script (which they should be)
        then that script will set an environment variable IMPORTING_FIXTURE to "true"
        before it runs and to "false" when it finishes

        :return: None
        """
        run_main = os.environ.get('RUN_MAIN', None) == 'true'
        run_command = os.environ.get('RUN_COMMAND', None) == 'true'
        run_celery = getattr(settings, 'IS_CELERY', False)

        in_production = not settings.DEBUG
        if in_production or run_main or run_command or run_celery:
            is_importing_fixture = os.getenv('IMPORTING_FIXTURE', 'false') == 'true'

            if not is_importing_fixture:
                from root.models import User
                from root.views import register_app_modules, init_tables
                from koe.aggregator import init as init_aggregators
                from koe.features.feature_extract import init as init_features

                is_database_empty = User.objects.all().count() == 0

                if not is_database_empty:
                    register_app_modules(self.name, 'request_handlers.history')
                    register_app_modules(self.name, 'request_handlers.audio')
                    register_app_modules(self.name, 'request_handlers.database')
                    register_app_modules(self.name, 'request_handlers.tensorviz')
                    register_app_modules(self.name, 'request_handlers.preferences')
                    register_app_modules(self.name, 'request_handlers.templates')
                    register_app_modules(self.name, 'request_handlers.features')
                    register_app_modules(self.name, 'models')
                    register_app_modules('root', 'models')
                    register_app_modules(self.name, 'grid_getters')

                    init_tables()
                    get_builtin_attrs()
                    init_aggregators()
                    init_features()

                import koe.signals  # noqa: F401  Must include this for the signals to work
