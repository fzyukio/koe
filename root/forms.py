from django import forms
from django.forms.utils import ErrorList
from django.utils.encoding import force_text
from django.utils.html import format_html_join


class ErrorMixin(forms.Form):
    """
    Primarily used to override error rendering
    """

    class SpanErrorList(ErrorList):
        def __unicode__(self):
            return self.as_spans()

        def as_spans(self):
            if not self:
                return ""
            return format_html_join(
                "",
                '<span class="error-label">{}</span>',
                ((force_text(e),) for e in self),
            )

    def __init__(self, *args, **kwargs):
        kwargs["error_class"] = ErrorMixin.SpanErrorList
        super(ErrorMixin, self).__init__(*args, **kwargs)


class UserSignInForm(ErrorMixin, forms.Form):
    acc_or_email = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Email address or username"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Password"}))


class UserRegistrationForm(ErrorMixin, forms.Form):
    username = forms.CharField(
        required=True,
        max_length=10,
        error_messages={"required": "This field is required"},
        widget=forms.TextInput(attrs={"placeholder": "Username, 10 characters or less"}),
    )

    first_name = forms.CharField(
        required=True,
        max_length=100,
        error_messages={"required": "This field is required"},
        widget=forms.TextInput(attrs={"placeholder": "First name"}),
    )

    last_name = forms.CharField(
        required=True,
        max_length=100,
        error_messages={"required": "This field is required"},
        widget=forms.TextInput(attrs={"placeholder": "Last name"}),
    )

    email = forms.EmailField(
        required=True,
        max_length=100,
        error_messages={"required": "This field is required"},
        widget=forms.TextInput(attrs={"placeholder": "Email"}),
    )

    password = forms.CharField(
        required=True,
        max_length=100,
        error_messages={"required": "This field is required"},
        widget=forms.PasswordInput(attrs={"placeholder": "Password, 8 characters or more"}),
    )

    re_password = forms.CharField(
        required=True,
        max_length=100,
        error_messages={"required": "This field is required"},
        widget=forms.PasswordInput(attrs={"placeholder": "Retype password"}),
    )


class UserForgetPasswordForm(ErrorMixin, forms.Form):
    acc_or_email = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Email address or username"}))


class UserResetPasswordForm(ErrorMixin, forms.Form):
    acc_or_email = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Email address or username"}))

    oldpass = forms.CharField(
        required=True,
        max_length=100,
        error_messages={"required": "This field is required"},
        widget=forms.PasswordInput(attrs={"placeholder": "Old password"}),
    )

    newpass = forms.CharField(
        required=True,
        max_length=100,
        error_messages={"required": "This field is required"},
        widget=forms.PasswordInput(attrs={"placeholder": "New password"}),
    )

    retyped = forms.CharField(
        required=True,
        max_length=100,
        error_messages={"required": "This field is required"},
        widget=forms.PasswordInput(attrs={"placeholder": "Retype new password"}),
    )
