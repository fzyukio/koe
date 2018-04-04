import os

from django.apps import AppConfig


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

            register_app_modules(self.name, 'views')
            register_app_modules(self.name, 'models')
            register_app_modules(self.name, 'grid_getters')

            init_tables()
