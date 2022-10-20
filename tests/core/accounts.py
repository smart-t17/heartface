#!/usr/bin/env python
# coding=utf-8
import re
from django.conf import settings
from django.templatetags.static import static
from django.core import mail
from rest_framework import status
from rest_framework.test import APITestCase
import sure

from heartface.apps.core.models import Follow
from tests.factories import UserFactory, VideoFactory, CommentFactory, FollowFactory, LikeFactory
from allauth.account.models import EmailAddress


class DisabledUserTestCase(APITestCase):
    """
    Test if disabled user can re-enable account, can't do
    various things, videos from this user are hidden, likes/comments
    are anonimized.
    """
    def test_disabled_user_can_reenable(self):
        disabled_user = UserFactory.create(disabled=True)

        disabled_user.disabled.should.equal(True)

        self.client.force_login(disabled_user)

        response = self.client.post('/api/v1/users/%s/enabled/' % disabled_user.pk)
        response.status_code.should.equal(status.HTTP_200_OK)

        disabled_user.refresh_from_db()
        disabled_user.disabled.should.equal(False)

    def test_other_user_cannot_reenable(self):

        disabled_user = UserFactory.create(disabled=True)
        other = UserFactory()

        disabled_user.disabled.should.equal(True)

        self.client.force_login(other)

        response = self.client.post('/api/v1/users/%s/enabled/' % disabled_user.pk)
        response.status_code.should.equal(status.HTTP_403_FORBIDDEN)

        disabled_user.refresh_from_db()
        disabled_user.disabled.should.equal(True)

    def test_disabled_user_videos_hidden(self):

        disabled_user = UserFactory.create(disabled=True)
        enabled_user = UserFactory()
        request_user = UserFactory()

        VideoFactory(owner=disabled_user)
        VideoFactory(owner=enabled_user)

        disabled_user.disabled.should.equal(True)

        self.client.force_login(request_user)

        response = self.client.get('/api/v1/videos/')
        response.status_code.should.equal(status.HTTP_200_OK)

        results = response.data.get('results')
        results.should.have.length_of(1)
        results[0]['owner']['id'].should.equal(enabled_user.id)

    def test_disabled_user_videos_hidden_from_recommended(self):

        disabled_user = UserFactory.create(disabled=True)
        enabled_user = UserFactory()
        request_user = UserFactory()

        VideoFactory(owner=disabled_user, recommended=True)
        VideoFactory(owner=enabled_user, recommended=True)

        disabled_user.disabled.should.equal(True)

        self.client.force_login(request_user)

        response = self.client.get('/api/v1/recommended/')
        response.status_code.should.equal(status.HTTP_200_OK)

        results = response.data.get('results')
        results.should.have.length_of(1)
        results[0]['owner']['id'].should.equal(enabled_user.id)

    def test_disabled_users_hidden_from_discovery(self):

        disabled_user = UserFactory.create(disabled=True)
        enabled_user = UserFactory()
        request_user = UserFactory()

        disabled_user.disabled.should.equal(True)

        self.client.force_login(request_user)

        response = self.client.get('/api/v1/discovery/')
        response.status_code.should.equal(status.HTTP_200_OK)

        trending = response.data.get('trending')
        trending.should.have.length_of(2)
        for trending in trending:
            trending['id'].should.be.within([enabled_user.id, request_user.id])

    def test_disabled_users_and_feed(self):

        disabled_user = UserFactory.create(disabled=True)
        enabled_user = UserFactory()
        request_user = UserFactory()

        disabled_user.disabled.should.equal(True)

        dis_vid = VideoFactory(owner=disabled_user, recommended=True)
        en_vid = VideoFactory(owner=enabled_user, recommended=True)

        # Feed only shows content from users that we follow
        FollowFactory(follower=request_user, followed=enabled_user)
        en_comm = CommentFactory(author=enabled_user)
        dis_comm = CommentFactory(author=disabled_user)
        en_like = LikeFactory(user=enabled_user)
        dis_like = LikeFactory(user=disabled_user)

        self.client.force_login(request_user)

        response = self.client.get('/api/v1/feed/')
        response.status_code.should.equal(status.HTTP_200_OK)
        results = response.data.get('results')

        # Videos of disabled hidden
        videos = [res for res in results if res['type'] == 'video']
        videos.should.have.length_of(1)
        videos[0]['content']['owner']['id'].should.equal(enabled_user.id)

        # Likes of disabled anonimized
        likes = [res for res in results if res['type'] == 'like']
        likes.should.have.length_of(1)
        likes[0]['content']['user']['id'].should.equal(enabled_user.id)

        # Comments of disabled anonimized
        comments = [res for res in results if res['type'] == 'comment']
        comments.should.have.length_of(1)
        comments[0]['content']['author']['id'].should.equal(enabled_user.id)

    def test_disabled_comments_are_anon(self):
        disabled_user = UserFactory.create(disabled=True)
        request_user = UserFactory()

        disabled_user.disabled.should.equal(True)
        v = VideoFactory()
        c = CommentFactory(video=v, author=disabled_user)

        self.client.force_login(request_user)

        response = self.client.get('/api/v1/videos/%i/comments/' % v.pk)
        response.status_code.should.equal(status.HTTP_200_OK)

        results = response.data.get('results')
        results.should.have.length_of(1)
        c_res = results[0]
        c_res['id'].should.equal(c.pk)
        c_res['author']['full_name'].should.equal('Disabled User')
        c_res['author']['username'].should.equal('disabled_user')
        c_res['author']['email'].should.equal('disabled@disabled.com')
        c_res['author']['description'].should.equal('')
        c_res['author']['address'].should.equal('')
        c_res['author']['phone'].should.equal('')
        c_res['author']['photo'].should.equal(static(settings.DISABLED_USER_AVATAR))
        c_res['author']['age'].should.equal(None)


class UsersMeTestCase(APITestCase):
    """
    Test if the /users/me/ shorthand works
    """
    def test_users_me_returns_self(self):
        users = [UserFactory() for i in range(5)]
        me = users[3]

        self.client.force_login(me)

        response = self.client.get('/api/v1/users/me/')
        response.status_code.should.equal(status.HTTP_200_OK)
        response.data['id'].should.equal(me.id)

        response = self.client.patch('/api/v1/users/me/', {'full_name': 'test_full_name'})
        response.status_code.should.equal(status.HTTP_200_OK)
        response.data['full_name'].should.equal('test_full_name')

    def test_user_cant_edit_other_profile(self):
        users = [UserFactory() for i in range(5)]
        me = users[3]
        not_me = users[2]

        self.client.force_login(me)
        response = self.client.patch('/api/v1/users/%s/' % not_me.id, {'full_name': 'change_name_for_another_user'})
        response.status_code.should.equal(status.HTTP_403_FORBIDDEN)


class UsernameAvailableTestCase(APITestCase):
    def test_username_available(self):
        UserFactory(username='abcdefg')
        request_user = UserFactory(username='zyxwvu')
        self.client.force_login(request_user)

        # 200 when username exists already
        response = self.client.get('/api/v1/users/usernames/abcdefg/')
        response.status_code.should.equal(status.HTTP_200_OK)

        # 404 when username does not exist
        response = self.client.get('/api/v1/users/usernames/doesnotexist1234/')
        response.status_code.should.equal(status.HTTP_404_NOT_FOUND)


class ResendEmailTestCase(APITestCase):
    def test_resend_email(self):
        request_user = UserFactory()
        self.client.force_login(request_user)

        # 202 when not verified already
        response = self.client.post('/api/v1/users/me/resend_email/')
        response.status_code.should.equal(status.HTTP_202_ACCEPTED)
        mail.outbox.should.have.length_of(1)
        mail.outbox[0].subject.should.contain('Confirm Your E-mail Address')
        mail.outbox[0].to.should.contain(request_user.email)

        # Simulate user clicking the confirm link
        matches = re.findall(r'\/rest-auth\/account-confirm-email\/[-:\w]+\/$', mail.outbox[0].body, re.MULTILINE)
        matches.should.have.length_of(1)
        url = matches[0]
        response = self.client.get(url)
        response.status_code.should.equal(status.HTTP_302_FOUND)
        EmailAddress.objects.get(email=request_user).verified.should.be(True)

        # 409 if they try resend confirm email again
        response = self.client.post('/api/v1/users/me/resend_email/')
        response.status_code.should.equal(status.HTTP_409_CONFLICT)
        mail.outbox.should.have.length_of(1)


class FollowingLikeIDTestCase(APITestCase):
    def test_get_own_following_ids(self):
        user = UserFactory()

        following = UserFactory.create_batch(5)
        UserFactory.create_batch(10)

        for u in following:
            FollowFactory(follower=user, followed = u)

        self.client.force_login(user)
        response = self.client.get('/api/v1/users/me/following/ids/')

        response.status_code.should.equal(status.HTTP_200_OK)
        data = response.data
        data['count'].should.equal(len(following))
        response_ids = set(d['id'] for d in data['results'])
        response_ids.should.equal(set(u.pk for u in following))

    def test_get_own_like_ids(self):
        user = UserFactory()

        liked_videos = VideoFactory.create_batch(8)
        VideoFactory.create_batch(6)

        for v in liked_videos:
            LikeFactory(video=v,user=user)

        self.client.force_login(user)
        response = self.client.get('/api/v1/users/me/likes/ids/')

        response.status_code.should.equal(status.HTTP_200_OK)
        data = response.data
        data['count'].should.equal(len(liked_videos))

        response_ids = set(d['id'] for d in data['results'])
        response_ids.should.equal(set(v.pk for v in liked_videos))

class UserGuestTestCase(APITestCase):
    def test_guest_can_retrive_user(self):
        u = UserFactory(username='abcdefg')

        response = self.client.get('/api/v1/users/%s/' % u.id)
        response.status_code.should.equal(status.HTTP_200_OK)

    def test_guest_can_get_user_followers(self):
        u = UserFactory(username='abcdefg')

        response = self.client.get('/api/v1/users/%s/followers/' % u.id)
        response.status_code.should.equal(status.HTTP_200_OK)

    def test_guest_can_get_user_followering(self):
        u = UserFactory(username='abcdefg')

        response = self.client.get('/api/v1/users/%s/following/' % u.id)
        response.status_code.should.equal(status.HTTP_200_OK)

    def test_guest_cannot_follow_user(self):
        u = UserFactory(username='abcdefg')

        response = self.client.post('/api/v1/users/%s/followers/' % u.id)
        response.status_code.should.equal(status.HTTP_401_UNAUTHORIZED)

    def test_guest_cannot_unfollow_user(self):
        u = UserFactory(username='abcdefg')

        response = self.client.delete('/api/v1/users/%s/followers/' % u.id)
        response.status_code.should.equal(status.HTTP_401_UNAUTHORIZED)


class UserSerializationTestCase(APITestCase):
    SENSITIVE_FIELDS = ['email', 'age', 'gender', 'email_verified', 'can_charge', 'disabled']

    def test_self_sees_all_fields(self):
        u = UserFactory(username='abcdefg')
        self.client.force_login(u)
        response = self.client.get('/api/v1/users/%s/' % u.id)
        response.status_code.should.equal(status.HTTP_200_OK)
        for field in self.SENSITIVE_FIELDS:
            response.json().should.contain(field)

    def test_other_doesnt_see_all_fields(self):
        u = UserFactory(username='abcdefg')
        other = UserFactory(username='efghijk')
        self.client.force_login(other)
        response = self.client.get('/api/v1/users/%s/' % u.id)
        response.status_code.should.equal(status.HTTP_200_OK)
        for field in self.SENSITIVE_FIELDS:
            response.json().shouldnt.contain(field)
