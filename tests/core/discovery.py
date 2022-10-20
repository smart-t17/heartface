#!/usr/bin/env python
# coding=utf-8
from urllib.parse import urljoin

from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from heartface.apps.core.models import View, Video

import sure

from tests.factories import UserFactory, VideoFactory, ProductFactory, HashtagFactory, CollectionFactory, \
  EditorialRecommendationFactory, User, HomepageContentFactory


class DiscoveryTestCase(APITestCase):

    def test_discovery_response(self):
        user = UserFactory()
        trending_user = UserFactory(is_staff=False, is_active=True)

        video = VideoFactory(owner=user, published=timezone.now(), recommended=True)
        collection = CollectionFactory()
        collection.videos.add(video)
        recommendation = EditorialRecommendationFactory(featured_video=video)

        hashtag = HashtagFactory()
        video.hashtags.add(hashtag)

        recommendation.featured_video = video
        recommendation.save()
        recommendation.collections.add(collection)

        self.client.force_login(user)
        response = self.client.get('/api/v1/discovery/')
        response.status_code.should.equal(status.HTTP_200_OK)

        response.data.get('featured').get('title').should.equal(video.title)
        response.data.get('hashtags')[0].get('name').should.equal(hashtag.name)
        response.data.get('collections')[0].get('id').should.equal(collection.id)
        response.data.get('collections')[0].get('name').should.equal(collection.name)
        response.data.get('collections')[0].get('cover_photo').should.equal(urljoin('http://testserver/', collection.cover_photo.url))

        trending_user.pk.should.be.within([u['id'] for u in response.data.get('trending')])

    def test_featuredvideo_can_be_null(self):
        user = UserFactory()

        video = VideoFactory(owner=user, published=timezone.now(), recommended=True)
        collection = CollectionFactory()
        collection.videos.add(video)

        hashtag = HashtagFactory()
        video.hashtags.add(hashtag)

        self.client.force_login(user)
        response = self.client.get('/api/v1/discovery/')
        response.status_code.should.equal(status.HTTP_200_OK)

        response.data['featured'].should.be(None)
        response.data.get('hashtags')[0].get('name').should.equal(hashtag.name)
        response.data.get('collections')[0].get('id').should.equal(collection.id)
        response.data.get('collections')[0].get('name').should.equal(collection.name)
        response.data.get('collections')[0].get('cover_photo').should.equal(urljoin('http://testserver/', collection.cover_photo.url))
