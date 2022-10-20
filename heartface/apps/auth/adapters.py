from datetime import datetime
import json
import requests
import dateutil.parser
from rest_framework.reverse import reverse
from allauth.account.adapter import DefaultAccountAdapter
from allauth.account.models import EmailAddress
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.utils import user_field
from django.conf import settings


from ..core.models import User


class NoSocialEmailException(Exception):
    pass


class DuplicateSocialEmailException(Exception):
    pass


class MissingUsernameException(Exception):
    pass


class UsernameTakenException(Exception):
    pass


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        """
        Check if we have a local email already for this and also that the social
        site provided an email
        """
        # Ignore existing social accounts, just do this stuff for new ones
        if sociallogin.is_existing:
            return

        # some social logins don't have an email address, e.g. facebook accounts
        # with mobile numbers only
        if 'email' not in sociallogin.account.extra_data:
            raise NoSocialEmailException('Email was not provided by social site.')

        # check if given email address already exists.
        email = sociallogin.account.extra_data['email'].lower()
        if EmailAddress.objects.filter(email__iexact=email).exists():
            raise DuplicateSocialEmailException('The email %s already exists in our database. Please use it to login' % email)

        if not sociallogin.is_existing:
            if 'username' in request.POST:
                username = request.POST['username']
            else:
                post_data = json.loads(request.body.decode('utf-8'))
                username = post_data.get('username')

            if not username:
                raise MissingUsernameException()

            if User.objects.filter(username=username):
                raise UsernameTakenException()
            sociallogin.user.username = username

            if 'picture' in sociallogin.account.extra_data:
                try:
                    photo_url = sociallogin.account.extra_data['picture']['data']['url']
                    photo_filename = '%s.jpg' % email

                    with requests.get(photo_url, stream=True) as r:
                        sociallogin.user.photo.save(photo_filename, r.raw)
                except KeyError:
                    pass

            if 'birthday' in sociallogin.account.extra_data:
                # Bad idea to store age, but it require changes in app
                # Format seems to be in %m/%d/%Y format (cf Tuan bug) use
                # dateutil to make more robust
                birthday = dateutil.parser.parse(sociallogin.account.extra_data['birthday'])
                sociallogin.user.birthday = birthday

            if 'gender' in sociallogin.account.extra_data and \
                    sociallogin.account.extra_data['gender'] in User.GENDER:
                sociallogin.user.gender = sociallogin.account.extra_data['gender']
            else:
                sociallogin.user.gender = 'other'


class AccountAdapter(DefaultAccountAdapter):
    def is_email_verified(self, request, email):
        if request.path == reverse('fb_login'):
            # always set email as confirmed when user login using Facebook OAuth
            return True
        return super().is_email_verified(request, email)

    def get_email_confirmation_redirect_url(self, request):
        return reverse('account_confirm_email_redirect')

    def render_mail(self, template_prefix, email, context):
        msg = super().render_mail(template_prefix, email, context)
        # If signup email comes from the hello address
        if 'signup' in template_prefix:
            msg.from_email = settings.DEFAULT_CONFIRMATION_FROM_EMAIL
        return msg

    def save_user(self, request, user, form, commit=True):
        user = super(AccountAdapter, self).save_user(request, user, form, commit=commit)
        data = form.cleaned_data
        full_name = data.get('full_name')
        if full_name:
            user_field(user, 'full_name', full_name)
        if commit:
            user.save()
        return user
