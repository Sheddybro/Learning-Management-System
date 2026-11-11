from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.exceptions import ImmediateHttpResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.urls import reverse


class CustomAccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter that prevents automatic user creation.
    Users must be created manually through the regular registration process.
    """

    def pre_social_login(self, request, sociallogin):
        """
        Called before social login. We prevent automatic signup here.
        """
        # For Google OAuth, we don't want automatic signup
        # Users must already have an account and link Google manually
        if sociallogin.is_existing:
            # User already exists, proceed with login
            return

        # New user trying to sign up with Google - redirect to registration
        messages.warning(
            request,
            _("Account creation via Google is not allowed. Please register manually first, "
              "then link your Google account in your profile settings.")
        )
        raise ImmediateHttpResponse(redirect(reverse('users:login')))


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for Google account linking and sign-in.
    - If user is authenticated and linking account: validate and link
    - If user is not authenticated: check if Google account is linked to an existing user
    """

    def pre_social_login(self, request, sociallogin):
        """
        Called before social login. Handles both account linking and sign-in.
        """
        if request.user.is_authenticated:
            # User is authenticated - this is account linking
            return self._handle_account_linking(request, sociallogin)
        else:
            # User is not authenticated - this is sign-in attempt
            return self._handle_social_login(request, sociallogin)

    def _handle_account_linking(self, request, sociallogin):
        """
        Handle account linking for authenticated users.
        """
        # Check if this Google account is already linked to another user
        existing_social_account = sociallogin.account.__class__.objects.filter(
            uid=sociallogin.account.uid,
            provider=sociallogin.account.provider
        ).exclude(user=request.user).first()

        if existing_social_account:
            messages.error(
                request,
                _("This Google account is already linked to another user.")
            )
            raise ImmediateHttpResponse(redirect(reverse('users:profile')))

        # Check if the Google email matches the current user's email
        google_email = sociallogin.account.extra_data.get('email', '').lower().strip()
        user_email = request.user.email.lower().strip()

        if google_email and google_email != user_email:
            messages.error(
                request,
                _("Google account email ({}) does not match your account email ({}). "
                  "Please use the same email address.").format(google_email, user_email)
            )
            raise ImmediateHttpResponse(redirect(reverse('users:profile')))

    def _handle_social_login(self, request, sociallogin):
        """
        Handle social login for non-authenticated users.
        Only allow login if Google account is already linked to an existing user.
        """
        # Check if this Google account is linked to any existing user
        existing_social_account = sociallogin.account.__class__.objects.filter(
            uid=sociallogin.account.uid,
            provider=sociallogin.account.provider
        ).first()

        if not existing_social_account:
            # Google account not linked to any user - redirect to login
            messages.warning(
                request,
                _("This Google account is not linked to any user account. "
                  "Please log in with your email and password first, then link your Google account.")
            )
            raise ImmediateHttpResponse(redirect(reverse('users:login')))

        # Google account is linked - proceed with login but ensure it's the same user
        linked_user = existing_social_account.user

        # Double-check email match as security measure
        google_email = sociallogin.account.extra_data.get('email', '').lower().strip()
        user_email = linked_user.email.lower().strip()

        if google_email and user_email and google_email != user_email:
            messages.error(
                request,
                _("Account configuration error. Please contact support.")
            )
            raise ImmediateHttpResponse(redirect(reverse('users:login')))

        # Everything checks out - proceed with login
        sociallogin.connect(request, linked_user)

    def save_user(self, request, sociallogin, form=None):
        """
        This should never be called in our setup since we don't allow signup.
        But override to be safe.
        """
        return None

    def populate_user(self, request, sociallogin, data):
        """
        This should never be called in our setup since we don't allow signup.
        But override to be safe.
        """
        return None
