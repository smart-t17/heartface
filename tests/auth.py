#!/usr/bin/env python
# coding=utf-8
import re
import sys
from code import InteractiveConsole
from collections import namedtuple

from django.conf import settings
from django.core import mail
from nose.plugins.attrib import attr
from oauthlib.oauth2 import MobileApplicationClient
from parameterized import parameterized
from requests_oauthlib import OAuth2Session
from requests_oauthlib.compliance_fixes import facebook_compliance_fix
from rest_framework import status
from rest_framework.test import APITestCase
from allauth.account.models import EmailAddress

from heartface.apps.core.models import User
from tests.factories import ProductFactory, UserFactory
from tests.utils import pp

TEST_USER_FB_ID = '100023844096907'
TEST_USER_FB_EMAIL = 'ydaukvovzz_1514976705@tfbnw.net'
TEST_USER_FB_PW = 'zzXKLz1F'

FacebookAuthStrategy = namedtuple('FacebookAuthStrategy', ['create_client', 'parse_response'])

FBCodeStrategy = FacebookAuthStrategy(
    lambda client_id: None,
    lambda fb, resp: fb._client.parse_request_uri_response(resp, state=fb._state)['code']
)

FBTokenStrategy = FacebookAuthStrategy(
    lambda client_id: MobileApplicationClient(client_id=client_id),
    lambda fb, resp: fb.token_from_fragment(resp)['access_token']
)


def _authorize_with_facebook(strategy, email, password):
    client_id = settings.SOCIAL_APPS['facebook']['client_id']
    authorization_base_url = 'https://www.facebook.com/dialog/oauth'
    redirect_uri = 'http://heartface.atleta.hu/api'  # Should match Site URL
    facebook = OAuth2Session(client_id, redirect_uri=redirect_uri, client=strategy.create_client(client_id))
    facebook = facebook_compliance_fix(facebook)

    # Redirect user to Facebook for authorization
    authorization_url, state = facebook.authorization_url(authorization_base_url)
    print('Use the below credentials to log in to FB:\n  email: %s\n  password: %s' % (email, password), file=sys.stderr)
    print('Please go here and authorize,', authorization_url, file=sys.stderr)

    # Get the authorization verifier code from the callback url
    redirect_response = InteractiveConsole.raw_input('Paste the full redirect URL here:')
    # Fetch the access token
    # return facebook.fetch_token(token_url, client_secret=client_secret,
    #                             authorization_response=redirect_response)['access_token']
    return strategy.parse_response(facebook, redirect_response)


def _get_facebook_auth_code(email=settings.FACEBOOK_TEST_USER['email'],
                            password=settings.FACEBOOK_TEST_USER['password']):
    """
    Get an auth code from facebook.
    """
    return _authorize_with_facebook(FBCodeStrategy, email=email, password=password)


def _get_facebook_token(email=settings.FACEBOOK_TEST_USER['email'], password=settings.FACEBOOK_TEST_USER['password']):
    return _authorize_with_facebook(FBTokenStrategy, email=email, password=password)


class FacebookLoginTestCase(APITestCase):
    @attr('interactive')
    def test_facebook_signup_with_token(self):
        print(ProductFactory())
        # print(User.objects.first().email)
        # placeholder-migrations@dummy.user.no
        User.objects.exclude(email="placeholder-migrations@dummy.user.no").count().should.equal(0)
        # Create Existing User w/ same email as facebook email
        response = self.client.post('/rest-auth/facebook/', data={'access_token': _get_facebook_token()})
        response.status_code.should.equal(status.HTTP_200_OK)
        response.json().should.have.key('key')
        response.json()['key'].should_not.be.empty
        User.objects.exclude(email="placeholder-migrations@dummy.user.no").count().should.equal(1)
        EmailAddress.objects.get(email=settings.FACEBOOK_TEST_USER['email']).verified.should.equal(True)

    @attr('interactive')
    def test_facebook_signup_existing_email_with_token(self):
        User.objects.exclude(email="placeholder-migrations@dummy.user.no").count().should.equal(0)
        # Create Existing User w/ same email as facebook test-user email (prob
        # goes in settings per environment)
        u = User.objects.create(username="test", email=settings.FACEBOOK_TEST_USER['email'])
        EmailAddress.objects.create(user=u, email=settings.FACEBOOK_TEST_USER['email'])
        response = self.client.post('/rest-auth/facebook/', data={'access_token': _get_facebook_token()})
        response.status_code.should.equal(status.HTTP_400_BAD_REQUEST)
        print(response.json())
        response.json()['non_field_errors'][0].should.contain('already have that email')
        User.objects.exclude(email="placeholder-migrations@dummy.user.no").count().should.equal(1)

    # authentication with code isn't supported for now
    # def test_facebook_login_code(self):
    #     response = self.client.post('/rest-auth/facebook/', data={'code': _get_facebook_auth_code()})
    #     print(response.json())
    #     response.status_code.should.equal(status.HTTP_200_OK)

    @attr('interactive')
    def test_facebook_login_with_token(self):
        User.objects.exclude(email="placeholder-migrations@dummy.user.no").count().should.equal(0)
        response = self.client.post('/rest-auth/facebook/', data={'access_token': _get_facebook_token()})
        response.status_code.should.equal(status.HTTP_200_OK)
        response.json().should.have.key('key')
        response.json()['key'].should_not.be.empty
        User.objects.exclude(email="placeholder-migrations@dummy.user.no").count().should.equal(1)


class PasswordLoginTestCase(APITestCase):
    def test_login_with_username_and_password(self):
        u = UserFactory(password='pass')

        response = self.client.post('/rest-auth/login/', data={'username': u.username, 'password': 'pass'})
        response.status_code.should.equal(status.HTTP_200_OK)
        response.data.should.have.key('key')
        response.data['key'].should.not_be.empty


class RegisterTestCase(APITestCase):
    def test_register(self):
        system_users = list(User.objects.values_list('id', flat=True))
        username = 'abcdefg'
        email = 'abcdefg@mail.com'
        full_name = 'John Doe'
        response = self.client.post('/rest-auth/registration/', data={
            'username': username,
            'email': email,
            'password1': 'password12',
            'password2': 'password12',
            'full_name': full_name

        })

        response.status_code.should.equal(status.HTTP_201_CREATED)

        # TODO: check user creation
        new_users = User.objects.all().exclude(pk__in=system_users)
        new_users.count().should.equal(1)
        new_user = new_users.first()

        new_user.email.should.equal(email)
        new_user.username.should.equal(username)
        new_user.full_name.should.equal(full_name)

        # Check email was sent
        mail.outbox.should.have.length_of(1)
        mail.outbox[0].subject.should_not.be.empty
        mail.outbox[0].body.should.contain(username)
        mail.outbox[0].body.should.match(r'.*https?://\S*rest-auth/account-confirm-email/.*', re.MULTILINE)

        # Extract the exact confirm email URL
        matches = re.findall(r'\/rest-auth\/account-confirm-email\/[-:\w]+\/$', mail.outbox[0].body, re.MULTILINE)
        matches.should.have.length_of(1)
        url = matches[0]

        # Simulate user clicking the confirm link
        response = self.client.get(url)
        # response.status_code.should.equal(status.HTTP_200_OK)
        response.status_code.should.equal(status.HTTP_302_FOUND)

        # Simulate user posting the confirm form
        response = self.client.post(url)
        response.status_code.should.equal(status.HTTP_302_FOUND)

        # Check the email is now verified and we are redirect to correct place
        EmailAddress.objects.get(email=email).verified.should.be(True)
        response['Location'].should.equal('/rest-auth/account-confirm-email-redirect/')

    @parameterized.expand([
        [{'full_name': 'Whoever Yop'}], [{'birthday': '1970-01-01'}], [{'gender': 'male'}]
    ])
    def test_no_email_verification_on_non_email_update(self, update):
        user = UserFactory()
        self.client.force_login(user)
        reponse = self.client.patch('/api/v1/users/me/', update)
        reponse.status_code.should.equal(status.HTTP_200_OK)

        mail.outbox.should.have.length_of(0)

    def test_no_email_verification_on_updating_with_current_address(self):
        user = UserFactory()
        self.client.force_login(user)
        reponse = self.client.patch('/api/v1/users/me/', {'email': user.email})
        reponse.status_code.should.equal(status.HTTP_200_OK)

        mail.outbox.should.have.length_of(0)

    def test_no_email_verification_on_updating_with_verified_address(self):
        NEW_EMAIL = 'new.email@for.verification.test.com'
        user = UserFactory()
        EmailAddress.objects.create(user=user, email=NEW_EMAIL, verified=True)

        self.client.force_login(user)
        reponse = self.client.patch('/api/v1/users/me/', {'email': NEW_EMAIL})
        reponse.status_code.should.equal(status.HTTP_200_OK)

        mail.outbox.should.have.length_of(0)

    def test_verification_sent_on_updating_email(self):
        NEW_EMAIL = 'new.email@for.verification.test.com'
        user = UserFactory()
        self.client.force_login(user)
        reponse = self.client.patch('/api/v1/users/me/', {'email': NEW_EMAIL})
        reponse.status_code.should.equal(status.HTTP_200_OK)

        mail.outbox.should.have.length_of(1)
        mail.outbox[0].recipients().should.equal([NEW_EMAIL])

    @parameterized.expand([
        [{'email': 'user@host.domain.no'}], [{'username': 'johndoe'}]
    ])
    def test_no_duplicate_email_or_username(self, params):
        UserFactory(**params)
        data = {
            'username': 'abcdefg',
            'email': 'abcdefg@gmail.com',
            'password1': 'password12',
            'password2': 'password12',

        }

        data.update(params)

        # Registering with an existing user should fail
        response = self.client.post('/rest-auth/registration/', data=data)
        response.status_code.should.equal(status.HTTP_400_BAD_REQUEST)


class PasswordResetTestCase(APITestCase):
    def test_reset(self):
        user = UserFactory()
        response = self.client.post('/rest-auth/password/reset/', data={
            'email': user.email,
        })

        response.status_code.should.equal(status.HTTP_200_OK)

        # Check email was sent
        mail.outbox.should.have.length_of(1)
        mail.outbox[0].subject.should.contain('Password Reset E-mail')
        mail.outbox[0].recipients().should.equal([user.email])
