from django.apps import AppConfig
from django.db.utils import OperationalError


class KoeConfig(AppConfig):
    name = 'koe'

    def ready(self):
        try:
            from root.views import register_app_modules, init_tables

            register_app_modules(self.name, 'views')
            register_app_modules(self.name, 'models')
            register_app_modules(self.name, 'grid_getters')

            init_tables()
        except OperationalError:
            # This error occurs when loadata runs and the database is empty
            # which is not really a problem, so we ignore
            pass
