from django.utils import timezone
from django.contrib import auth
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.views.generic import FormView
from django.views.generic.edit import ProcessFormView

from root.forms import UserSignInForm, UserRegistrationForm, UserResetPasswordForm, UserForgetPasswordForm
from root.models import User, InvitationCode
from root.utils import forget_password_handler


def handle_redirect(request):
    """
    Redirect the user to the "next" address, e.g. localhost:8000/login?next=/ will redirect to localhost:8000/
    :param request:
    :return: a HttpResponseRedirect
    """
    next = request.GET.get('next', '/')
    return HttpResponseRedirect(next)


class RedirectIfAuthenticated(ProcessFormView):
    def get(self, request, *args, **kwargs):
        """
        Prevent user from logging in again if they already have
        :param request:
        :param args:
        :param kwargs:
        :return:
        """
        if request.user.is_authenticated:
            return HttpResponseRedirect('/')
        else:
            return super(RedirectIfAuthenticated, self).get(request, *args, **kwargs)


class UserSignInView(FormView, RedirectIfAuthenticated):
    """
    Handle user sign in.
    """

    form_class = UserSignInForm
    template_name = 'users/login.html'

    def form_valid(self, form):
        form_data = form.cleaned_data
        user = User.objects.filter(username__iexact=form_data['acc_or_email']).first()
        if user is None:
            user = User.objects.filter(email__iexact=form_data['acc_or_email']).first()
            if user is None:
                form.add_error('acc_or_email', 'Email/Account does not exist')
                context = self.get_context_data()
                context['form'] = form
                return self.render_to_response(context)

        now = timezone.now()
        if user.invitation_code and user.invitation_code.expiry <= now:
            user.is_active = False
            user.save()

        if not user.is_active:
            form.add_error('acc_or_email', 'Your account has expired. Should you wish to continue using this website, '
                                           'please contact us.')
            context = self.get_context_data()
            context['form'] = form
            return self.render_to_response(context)

        authenticated_user = auth.authenticate(self.request, username=user.username, password=form_data['password'])
        if authenticated_user is not None:
            auth.login(self.request, authenticated_user)
            return handle_redirect(self.request)
        else:
            form.add_error('password', 'Invalid password')
            context = self.get_context_data()
            context['form'] = form
            return self.render_to_response(context)


class UserRegistrationView(FormView, RedirectIfAuthenticated):
    """
    Handle user registration
    """

    form_class = UserRegistrationForm
    template_name = 'users/register.html'

    def form_valid(self, form):
        form_data = form.cleaned_data
        has_error = False
        now = timezone.now()

        code = form_data['code']
        email = form_data['email']
        password = form_data['password']
        re_password = form_data['re_password']
        username = form_data['username']
        last_name = form_data['last_name']
        first_name = form_data['first_name']

        invitation_code = InvitationCode.objects.filter(code=code, expiry__gte=now).first()

        if invitation_code is None:
            form.add_error('code', 'Invitation code doesn\'t exist or has expired')
            has_error = True
        duplicate_email = User.objects.filter(email__iexact=email).exists()
        duplicate_username = User.objects.filter(username__iexact=username).exists()

        if duplicate_email:
            form.add_error('email', 'A user with this email already exists.')
            has_error = True
        if duplicate_username:
            form.add_error('username', 'A user with this username already exists.')
            has_error = True
        if len(username) > 10:
            form.add_error('username', 'Username needs to be 10 or less characters.')
            has_error = True
        if len(password) < 8:
            form.add_error('password', 'Password needs to be at least 8 characters.')
            has_error = True
        if password != re_password:
            form.add_error('re_password', 'Retyped password unmatched')
            has_error = True

        if has_error:
            context = self.get_context_data()
            context['form'] = form
            return self.render_to_response(context)

        user = User.objects.create_user(username, email, password, invitation_code=invitation_code,
                                        first_name=first_name, last_name=last_name)
        user.save()

        authenticated_user = auth.authenticate(username=user.username, password=password)
        auth.login(self.request, authenticated_user)

        return handle_redirect(self.request)


class UserForgetPasswordView(FormView, RedirectIfAuthenticated):
    """
    Handle user registration
    """

    form_class = UserForgetPasswordForm
    template_name = 'users/forget-password.html'

    def form_valid(self, form):

        form_data = form.cleaned_data
        user = User.objects.filter(username__iexact=form_data['acc_or_email']).first()
        if user is None:
            user = User.objects.filter(email__iexact=form_data['acc_or_email']).first()
            if user is None:
                form.add_error('acc_or_email', 'Email/Account does not exist')
                context = self.get_context_data()
                context['form'] = form
                return self.render_to_response(context)

        # Send reset pw email
        forget_password_handler(user)
        message = 'We have sent you an email to reset your password at %s.' % (user.email,)
        return render(self.request, 'users/forgot-password-done.html', context={'message': message})


class UserResetPasswordView(FormView, RedirectIfAuthenticated):
    """
    This is subtab "security" in tab "profile"
    """

    form_class = UserResetPasswordForm
    template_name = 'users/reset-password.html'

    def form_valid(self, form):
        """
        Validate the password & new password.
        @TODO: Currently no password complexity is enforced.
        """
        data = form.cleaned_data
        user = self.request.user

        acc_or_email = str(data['acc_or_email'])
        oldpass = str(data['oldpass'])
        newpass = str(data['newpass'])
        retyped = str(data['retyped'])

        user = User.objects.filter(username__iexact=acc_or_email).first()
        if user is None:
            user = User.objects.filter(email__iexact=acc_or_email).first()
            if user is None:
                form.add_error('acc_or_email', 'Email/Account does not exist')
                context = self.get_context_data()
                context['form'] = form
                return self.render_to_response(context)

        no_errors = True

        if not user.check_password(oldpass):
            form.add_error('oldpass', 'Incorrect password')
            no_errors = False
        if len(newpass) < 8:
            form.add_error('newpass', 'Password needs to be at least 8 characters.')
            no_errors = False
        if newpass != retyped:
            form.add_error('retyped', 'Retyped password unmatched')
            no_errors = False

        if no_errors:
            user.set_password(newpass)
            user.save()
            authenticated_user = auth.authenticate(username=user.username, password=newpass)
            auth.login(self.request, authenticated_user)
            return handle_redirect(self.request)

        else:
            context = self.get_context_data()
            context['form'] = form
            return self.render_to_response(context)


def sign_out(request):
    """
    Log the user out and redirect to '/'
    :param request:
    :return:
    """
    auth.logout(request)
    response = HttpResponseRedirect('/')
    response.delete_cookie(key='user')
    return response
