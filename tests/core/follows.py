#!/usr/bin/env python
# coding=utf-8
from rest_framework import status
from rest_framework.test import APITestCase
import sure

from tests.factories import UserFactory


class FollowersAPITestCase(APITestCase):
    def test_followers_returned_correctly(self):
        u1 = UserFactory()
        u2 = UserFactory()
        u3 = UserFactory()

        u2.follow(u1)
        self.client.force_login(u3)
        response = self.client.get('/api/v1/users/%s/followers/' % u1.id)

        response.status_code.should.equal(status.HTTP_200_OK)
        user1_follower_ids = set(u1.followers.values_list('pk', flat=True))

        response.data.should.have.length_of(len(user1_follower_ids))
        response_follower_ids = set(u['id'] for u in response.data)
        response_follower_ids.should.equal(user1_follower_ids)


    def test_followers_returned_correctly_for_current_user(self):
        u1 = UserFactory()
        u2 = UserFactory()
        u3 = UserFactory()

        u2.follow(u1)

        self.client.force_login(u1)
        response = self.client.get('/api/v1/followers/')

        response.status_code.should.equal(status.HTTP_200_OK)
        user1_follower_ids = set(u1.followers.values_list('pk', flat=True))
        # response.data.should.have.length_of(len(user1_follower_ids))
        # response_follower_ids = set(u['id'] for u in response.data)
        # response_follower_ids.should.equal(user1_follower_ids)


    def test_follow_user(self):
      followed = UserFactory()
      follower = UserFactory()
      follower_2 = UserFactory()

      follower_2.follow(followed)

      self.client.force_login(follower)
      response = self.client.post('/api/v1/users/%s/followers/' % followed.id)
      response.status_code.should.equal(status.HTTP_201_CREATED)

      followed.followers.count().should.equal(2)
      followed.followers.filter(pk=follower.pk).exists().should.be(True)


    def test_unfollow_user(self):
        followed = UserFactory()
        follower = UserFactory()
        follower_2 = UserFactory()

        follower.follow(followed)
        follower_2.follow(followed)

        self.client.force_login(follower)
        response = self.client.delete('/api/v1/users/%s/followers/' % followed.id)

        response.status_code.should.equal(status.HTTP_200_OK)

        followed.followers.count().should.equal(1)
        followed.followers.filter(pk=follower.pk).exists().should.be(False)
