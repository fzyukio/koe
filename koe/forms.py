from django import forms
from django.conf import settings

from koe.models import Database, Feature, Aggregation
from root.forms import ErrorMixin


class SongPartitionForm(ErrorMixin, forms.Form):
    track_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(
            attrs={
                'placeholder': 'Track\'s name'
            }
        )
    )

    date = forms.DateField(
        input_formats=settings.DATE_INPUT_FORMATS,
        required=False,
        widget=forms.DateInput(
            attrs={
                'placeholder': 'YYYY-MM-DD'
            }
        )
    )


class FeatureExtrationForm(ErrorMixin, forms.Form):
    database = forms.ModelChoiceField(
        to_field_name='id',
        queryset=Database.objects.all(),
    )

    # Must do this instead of an empty Select field - because it enforces value range checking
    # and the range of an empty field is none
    preset = forms.CharField(widget=forms.Select, required=False)

    # Same here
    annotator = forms.CharField(widget=forms.Select)

    features = forms.ModelMultipleChoiceField(
        to_field_name='id',
        queryset=Feature.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        error_messages={
            'required': 'At least one feature must be chosen'
        }
    )

    aggregations = forms.ModelMultipleChoiceField(
        to_field_name='id',
        queryset=Aggregation.objects.filter(enabled=True),
        widget=forms.CheckboxSelectMultiple(),
        error_messages={
            'required': 'At least one aggregation method must be chosen'
        }
    )

    dimreduce = forms.ChoiceField(
        choices=(
            ('pca', 'PCA'), ('ica', 'ICA'), ('tsne2', 'TSNE (2D)'), ('tsne3', 'TSNE (3D)'),
            ('none', 'No reduction')
        )
    )

    ndims = forms.IntegerField(
        required=False,
        min_value=3,
        max_value=50,
        widget=forms.NumberInput(attrs={
            'value': 50
        })
    )


class ContactUsForm(ErrorMixin, forms.Form):
    name = forms.CharField(
        required=True,
        max_length=100,
        error_messages={
            'required': 'Please let us know your name'
        },
        widget=forms.TextInput(attrs={'placeholder': 'Your name'})
    )

    email = forms.EmailField(
        required=True,
        max_length=100,
        error_messages={
            'required': 'This field is required'
        },
        widget=forms.TextInput(attrs={'placeholder': 'Your email'}),
    )

    message = forms.CharField(
        required=True,
        min_length=50,
        max_length=1000000,
        error_messages={
            'required': 'Please leave a message'
        },
        widget=forms.Textarea(
            attrs={
                'cols': 80,
                'rows': 10,
                "minlength": 50,
                "maxlength": 1000000
            }
        )
    )
