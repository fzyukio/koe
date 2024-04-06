from django import forms
from django.conf import settings

from koe.models import Aggregation, Feature
from root.forms import ErrorMixin


cached = {}


class SongPartitionForm(ErrorMixin, forms.Form):
    track_id = forms.CharField(required=False, widget=forms.HiddenInput())

    name = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"placeholder": "Track's name"}))

    date = forms.DateField(
        input_formats=settings.DATE_INPUT_FORMATS,
        required=True,
        widget=forms.DateInput(attrs={"placeholder": "YYYY-MM-DD"}),
    )


class FeatureExtrationForm(ErrorMixin, forms.Form):
    # Must do this instead of an empty Select field - because it enforces value range checking
    # and the range of an empty field is none
    data_matrix = forms.CharField(widget=forms.Select, required=False)

    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={"placeholder": "Give it a name that is easy to remember"}),
    )

    features = forms.ModelMultipleChoiceField(
        to_field_name="id",
        queryset=Feature.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        error_messages={"required": "At least one feature must be chosen"},
    )

    aggregations = forms.ModelMultipleChoiceField(
        to_field_name="id",
        queryset=Aggregation.objects.all(),
        widget=forms.CheckboxSelectMultiple(),
        error_messages={"required": "At least one aggregation method must be chosen"},
    )

    def __init__(self, *args, **kwargs):
        super(FeatureExtrationForm, self).__init__(*args, **kwargs)
        if "feature_choices" in cached:
            feature_choices = cached["feature_choices"]
        else:
            from koe.features.feature_extract import features

            feature_choices = Feature.objects.filter(id__in=[x.id for x in features])
            cached["feature_choices"] = feature_choices
        self.fields["features"].queryset = feature_choices

        if "aggregation_choices" in cached:
            aggregation_choices = cached["aggregation_choices"]
        else:
            aggregation_choices = Aggregation.objects.filter(enabled=True)
            cached["aggregation_choices"] = aggregation_choices
        self.fields["aggregations"].queryset = aggregation_choices


class OrdinationExtractionForm(ErrorMixin, forms.Form):
    data_matrix = forms.CharField(widget=forms.Select, required=True)

    ordination = forms.CharField(widget=forms.Select, required=False)

    method = forms.ChoiceField(
        required=True,
        choices=(
            ("pca", "Principal Component Analysis"),
            ("ica", "Independent Component Analysis"),
            ("tsne", "t-SNE (with PCA preprocessing)"),
        ),
    )

    ndims = forms.IntegerField(
        required=True,
        min_value=2,
        max_value=3,
        widget=forms.NumberInput(attrs={"value": 2}),
    )

    params = forms.CharField(required=False)


class SimilarityExtractionForm(ErrorMixin, forms.Form):
    data_matrix = forms.CharField(widget=forms.Select, required=False)
    ordination = forms.CharField(widget=forms.Select, required=False)


class ContactUsForm(ErrorMixin, forms.Form):
    name = forms.CharField(
        required=True,
        max_length=100,
        error_messages={"required": "Please let us know your name"},
        widget=forms.TextInput(attrs={"placeholder": "Your name"}),
    )

    email = forms.EmailField(
        required=True,
        max_length=100,
        error_messages={"required": "This field is required"},
        widget=forms.TextInput(attrs={"placeholder": "Your email"}),
    )

    message = forms.CharField(
        required=True,
        min_length=50,
        max_length=1000000,
        error_messages={"required": "Please leave a message"},
        widget=forms.Textarea(attrs={"cols": 80, "rows": 10, "minlength": 50, "maxlength": 1000000}),
    )
