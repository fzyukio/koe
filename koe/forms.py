from django import forms

from root.forms import ErrorMixin


class HelpEditForm(ErrorMixin, forms.Form):
    content = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'placeholder': 'Markdown code'
            }
        )
    )
