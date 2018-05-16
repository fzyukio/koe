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

    current_database_attr, _ = ExtraAttr.objects.get_or_create(
        klass=User.__name__, name='current-database', type=ValueTypes.SHORT_TEXT)
    current_similarity_attr, _ = ExtraAttr.objects.get_or_create(
        klass=User.__name__, name='current-similarity', type=ValueTypes.SHORT_TEXT)

    settings.ATTRS = DotMap(
        user=DotMap(current_database=current_database_attr, current_similarity=current_similarity_attr)
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
        is_importing_fixture = os.getenv('IMPORTING_FIXTURE', 'false') == 'true'

        if not is_importing_fixture:
            from root.views import register_app_modules, init_tables

            register_app_modules(self.name, 'request_handlers.history')
            register_app_modules(self.name, 'request_handlers.audio')
            register_app_modules(self.name, 'request_handlers.database')
            register_app_modules(self.name, 'models')
            register_app_modules(self.name, 'grid_getters')

            init_tables()
            get_builtin_attrs()
