from django import forms
from django.conf import settings

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
