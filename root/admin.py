from django.apps import apps
from django.contrib import admin

from root.admin_utils import generate_admin_class

app = apps.get_app_config('root')

for model_name, model in app.models.items():
    model_admin_class = generate_admin_class(model)
    admin.site.register(model, model_admin_class)
