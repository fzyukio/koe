import numpy as np

from django.apps import AppConfig


class KoeConfig(AppConfig):
    name = 'koe'

    def ready(self):
        from root.views import register_app_modules, init_tables
        register_app_modules(self.name, 'views')
        register_app_modules(self.name, 'models')
        register_app_modules(self.name, 'grid_getters')

        init_tables()
