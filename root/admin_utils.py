from django.contrib import admin
from django.db.models import ManyToManyField, CharField, TextField
from django.db.models.fields.reverse_related import ForeignObjectRel


def generate_admin_class(model):
    displayable_fields = []
    searchable_fields = []
    for field in model._meta.get_fields():
        if not isinstance(field, (ManyToManyField, ForeignObjectRel)) and field.name != 'password':
            displayable_fields.append(field.name)
            if isinstance(field, (CharField, TextField)):
                searchable_fields.append(field.name)

    model_admin_class = type(
        "{}Admin".format(model.__name__),
        (admin.ModelAdmin,),
        {
            'list_display': displayable_fields,
            'search_fields': searchable_fields
        }
    )

    return model_admin_class
