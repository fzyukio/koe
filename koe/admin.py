from django.contrib import admin
from django.apps import apps

app = apps.get_app_config('koe')

for model_name, model in app.models.items():
    admin.site.register(model)
