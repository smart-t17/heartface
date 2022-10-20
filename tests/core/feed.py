#!/usr/bin/env python
# coding=utf-8
import json
import os
from collections import namedtuple
from itertools import product
from urllib.parse import urljoin

import datetime
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from rest_framework import status
from rest_framework.reverse import reverse
from rest_framework.test import APITestCase

import sure

from heartface.apps.core.models import User, ReportedVideo
from tests.factories import UserFactory, VideoFactory, ProductFactory, HashtagFactory, CommentFactory, FollowFactory, \
  LikeFactory, DefaultFollowRecommendationFactory
from tests.utils import Clock, pp


class FeedTestCase(APITestCase):

    def setUp(self):
        self.clock = Clock(-datetime.timedelta(minutes=10))

    # Further tests TBD:
    #  - test if the correct events show up in the feed (all the needed events and only the needed ones)

    def test_video_with_product_and_hashtag(self):
        consumer = UserFactory()
        producer = UserFactory()
        product = ProductFactory()
        hashtag = HashtagFactory()

        self._tick(FollowFactory(follower=consumer, followed=producer))
        # producer.followers.add(consumer)

        video = VideoFactory(owner=producer, published=self.clock.tick())
        video.products.add(product)
        video.hashtags.add(hashtag)

        self.client.force_login(consumer)
        response = self.client.get('/api/v1/feed/')
        response.status_code.should.equal(status.HTTP_200_OK)
        # print(video.videofile.url, ps(response))

        result = response.data.get('results')[0]

        result.get('type').should.equal('video')
        content = result.get('content')
        # Since the Video was published it will be the CDN url that gets
        # serialized. The extension of which is defined by
        # settings.CDN_VIDEO_EXTENSION
        cdn_filename = "%s.%s" % (os.path.splitext(os.path.basename(video.videofile.name))[0],
                                  settings.CDN_VIDEO_EXTENSION)
        content.get('videofile').should.match('https?://.*%s' % cdn_filename)
        content.get('title').should.equal(video.title)
        content.get('view_count').should.equal(video.view_count)

        products = content.get('products')[0]
        products.get('name').should.equal(product.name)
        products.get('description').should.equal(product.description)
        # products.get('link').should.equal(product.link)

        hashtags = content.get('hashtags')[0]
        hashtags.get('name').should.equal(hashtag.name)

        # Links are returned as rest_framework.relations.Hyperlink (and not str) which breaks sure, so we're using assertEquals instead
        owner = content.get('owner')
        owner['id'].should.equal(producer.id)
        owner['full_name'].should.equal(producer.full_name)

    def test_feed_pagination(self):
        consumer = UserFactory()
        producer = UserFactory()
        FollowFactory(follower=consumer, followed=producer)

        for i in range(20):
            product = ProductFactory()
            hashtag = HashtagFactory()

            video = VideoFactory(owner=producer)
            video.products.add(product)
            video.hashtags.add(hashtag)

        # video.comments.add(CommentFactory(video=video))
        # video.comments.add(CommentFactory(video=video))
        CommentFactory(video=video)
        CommentFactory(video=video)

        self.client.force_login(consumer)
        response = self.client.get('/api/v1/feed/')

        response.status_code.should.equal(status.HTTP_200_OK)
        response.data.get('next').should.match('http://testserver/api/v1/feed/\?.*')
        self._check_item_ordering(response.data['results'])

        # pp(response)
        first_page_data = response.data

        response.data.get('next').should_not.be.none

        response = self.client.get(response.data.get('next'))
        response.status_code.should.equal(status.HTTP_200_OK)
        self._check_item_ordering(response.data['results'])

        response.data.get('results').should_not.be.empty
        response.data.get('previous').should.match('http://testserver/api/v1/feed/\?.*')

        # print(response.data.get('previous'))
        response = self.client.get(response.data.get('previous'))
        response.status_code.should.equal(status.HTTP_200_OK)
        # pp(response)

        self._check_item_ordering(response.data['results'])
        response.data.get('results').should.equal(first_page_data.get('results'))

        # TODO: test for no overlap and no missing items between pages (i.e. test that all data is returned and returned
        #  only once

    def test_feed_ordering_mixed_events(self):
        consumer = UserFactory()
        producer = UserFactory()
        user = UserFactory()

        # tick(FollowFactory(follower=consumer, followed=producer))
        self._tick(FollowFactory(follower=consumer, followed=producer))

        events = []
        v = VideoFactory(owner=producer, published=self.clock.tick())
        events.append(v)

        events.append(self._tick(CommentFactory(author=user, video=v)))

        events.append(self._tick(CommentFactory(author=producer, video=v)))

        events.append(self._tick(FollowFactory(followed=consumer, follower=producer)))

        events.append(VideoFactory(owner=producer, published=self.clock.tick()))

        v = VideoFactory(owner=consumer, published=self.clock.tick())
        events.append(self._tick(LikeFactory(user=producer, video=v)))

        # Unpublished video should not appear in feed
        self._tick(VideoFactory(owner=producer, published=None))

        self.client.force_login(consumer)
        response = self.client.get('/api/v1/feed/')

        response.status_code.should.equal(status.HTTP_200_OK)
        # pp(response)
        self._check_item_ordering(response.data['results'])

    def _check_item_ordering(self, items):
        timestamps = [e['content']['timestamp'] for e in items]
        all(t1 >= t2 for t1, t2 in zip(timestamps[:-1], timestamps[1:])).should.be.true

    def _tick(self, instance):
        instance.created = self.clock.tick()
        instance.save()

        return instance


class CommentTestCase(APITestCase):
    def test_comment_response(self):
        user = UserFactory()

        video = VideoFactory(owner=user, published=timezone.now(), recommended=True)
        comment = CommentFactory(author=user, video=video)

        self.client.force_login(user)
        response = self.client.get('/api/v1/videos/%s/comments/' % video.id)

        response.status_code.should.equal(status.HTTP_200_OK)

        comments = response.data.get('results')[0]
        comments.get('id').should.equal(comment.id)
        comments.get('author').get('id').should.equal(user.id)


class ReportVideoTestCase(APITestCase):
    def test_report_video_anonymous(self):
        # init variables
        video = VideoFactory()

        response = self.client.post('/api/v1/videos/%s/report/' % video.id)
        response.status_code.should.equal(status.HTTP_201_CREATED)

        ReportedVideo.objects.filter(video=video).count().should.be(1)
        ReportedVideo.objects.get(video=video).reporting_user.should.be(None)

        # validate that we can handle more than 1 anonymous user
        response = self.client.post('/api/v1/videos/%s/report/' % video.id)
        response.status_code.should.equal(status.HTTP_201_CREATED)
        ReportedVideo.objects.filter(video=video).count().should.be(2)

    def test_report_video_registered(self):
        # init variables, login user
        user, video = UserFactory(), VideoFactory()
        self.client.force_login(user)

        response = self.client.post('/api/v1/videos/%s/report/' % video.id)
        response.status_code.should.equal(status.HTTP_201_CREATED)
        ReportedVideo.objects.filter(reporting_user=user, video=video).count().should.be(1)

        # If same user reports same video, still should just be one ReportedVideo instance
        response = self.client.post('/api/v1/videos/%s/report/' % video.id)
        response.status_code.should.equal(status.HTTP_200_OK)
        ReportedVideo.objects.filter(reporting_user=user, video=video).count().should.be(1)


class WithLikesFollowingVideoTestCase(APITestCase):
    def test_recommended_videos(self):
        """
        ./manage test --keepdb --nologcapture tests.core.feed:WithLikesFollowingVideoTestCase.test_recommended_videos
        """
        Params = namedtuple('params', ['owner', 'recommended', 'liked'])

        # Users
        followed_user = UserFactory()
        unfollowed_user = UserFactory()
        request_user = UserFactory()
        FollowFactory(follower=request_user, followed=followed_user)

        # Create 8 videos altogether, all combinations of followed, recommended and liked
        all_params = [Params(o, r, l) for o, r, l in product([followed_user, unfollowed_user], [True, False], [True, False])]
        videos = {}
        for params in all_params:
            video = VideoFactory(owner=params.owner, recommended=params.recommended)
            if params.liked:
                LikeFactory(video=video, user=request_user)
            videos[video.pk] = params

        self.client.force_login(request_user)
        response = self.client.get('/api/v1/recommended/')
        response.status_code.should.equal(status.HTTP_200_OK)

        results = response.data.get('results')
        results.should.have.length_of(5)

        for result in results:
            params = videos[result['id']]
            result['owner']['following'].should.equal(params.owner.id == followed_user.id)
            result['liked'].should.equal(params.liked)

    def test_videos(self):
        """
        ./manage test --keepdb --nologcapture tests.core.feed:WithLikesFollowingVideoTestCase.test_videos
        """
        owner = UserFactory()
        other_user = UserFactory()
        request_user = UserFactory()
        liked_video = VideoFactory(owner=owner, published=timezone.now(), recommended=True)
        other_video = VideoFactory(owner=owner, published=timezone.now(), recommended=True)
        unloved_video = VideoFactory(owner=other_user, published=timezone.now(), recommended=True)

        # Make request_user follow owner (labels opposite to expectatations)
        FollowFactory(follower=request_user, followed=owner)
        LikeFactory(video=liked_video, user=request_user)

        self.client.force_login(request_user)
        response = self.client.get('/api/v1/videos/')
        response.status_code.should.equal(status.HTTP_200_OK)

        videos = response.data.get('results')
        videos.should.have.length_of(3)

        # Test we have the liked video and it is followed and liked
        liked_video_res = list(filter(lambda d: d['id'] == liked_video.id, videos))
        liked_video_res.should.have.length_of(1)
        liked_video_res[0]['owner']['following'].should.be(True)
        liked_video_res[0]['liked'].should.be(True)

        # Test the other video is followed but not liked
        other_video_res = list(filter(lambda d: d['id'] == other_video.id, videos))
        other_video_res.should.have.length_of(1)
        other_video_res[0]['owner']['following'].should.be(True)
        other_video_res[0]['liked'].should.be(False)

        # Test the unloved video is neither followed nor liked
        unloved_video_res = list(filter(lambda d: d['id'] == unloved_video.id, videos))
        unloved_video_res.should.have.length_of(1)
        unloved_video_res[0]['owner']['following'].should.be(False)
        unloved_video_res[0]['liked'].should.be(False)

    def test_feed(self):
        """
        ./manage test --keepdb --nologcapture tests.core.feed:WithLikesFollowingVideoTestCase.test_feed
        """
        owner = UserFactory()
        request_user = UserFactory()
        other_user = UserFactory()
        liked_video = VideoFactory(owner=owner, published=timezone.now(), recommended=True)
        other_video = VideoFactory(owner=owner, published=timezone.now(), recommended=True)

        # Make request_user follow owner
        FollowFactory(follower=request_user, followed=owner)
        # The feed of request_user should show when a user we follow (owner) starts to follow other_user
        # is followed by other_user
        FollowFactory(followed=other_user, follower=owner)
        # The feed of request user should not show when a user we follow (owner) is being followed by other users
        FollowFactory(followed=owner, follower=UserFactory())
        LikeFactory(video=liked_video, user=request_user)

        self.client.force_login(request_user)
        response = self.client.get('/api/v1/feed/')
        response.status_code.should.equal(status.HTTP_200_OK)

        resp_results = response.data.get('results')
        videos = list(filter(lambda d: d['type'] == 'video',  resp_results))
        videos.should.have.length_of(2)

        # Test we have the liked video and it is followed and liked
        liked_video_res = list(filter(lambda d: d['content']['id'] == liked_video.id, videos))
        liked_video_res.should.have.length_of(1)
        liked_video_res[0]['content']['owner']['following'].should.be(True)
        liked_video_res[0]['content']['liked'].should.be(True)

        # Test the other video is followed but not liked
        other_video_res = list(filter(lambda d: d['content']['id'] == other_video.id, videos))
        other_video_res.should.have.length_of(1)
        other_video_res[0]['content']['owner']['following'].should.be(True)
        other_video_res[0]['content']['liked'].should.be(False)

        # Follows in the feed
        follows = list(filter(lambda d: d['type'] == 'follow',  resp_results))
        follows.should.have.length_of(1)
        follows[0]['content']['follower']['id'].should.equal(owner.pk)
        # import ipdb;
        # ipdb.set_trace()


class UserVideosTestCase(APITestCase):
    def test_get_user_videos(self):
        user = UserFactory()
        other_owner = UserFactory()
        video = VideoFactory(owner=user, published=timezone.now(), recommended=True)
        VideoFactory(owner=other_owner, published=timezone.now(), recommended=True)

        self.client.force_login(user)
        response = self.client.get('/api/v1/users/%s/videos/' % user.id)
        response.status_code.should.equal(status.HTTP_200_OK)

        user_videos = response.data.get('results')

        for user_video in user_videos:
            user_video.get('id').should.equal(video.id)
            user_video.get('owner').get('id').should.equal(user.id)

    def test_unpublished_videos_filtered(self):
        user = UserFactory()
        VideoFactory(owner=user, published=None)
        published_video = VideoFactory(owner=user, published=timezone.now())

        self.client.force_login(user)
        response = self.client.get('/api/v1/users/%s/videos/' % user.id)
        response.status_code.should.equal(status.HTTP_200_OK)
        user_videos = response.data.get('results')

        len(user_videos).should.equal(1)
        user_videos[0].get('id').should.equal(published_video.id)

    def test_get_videos_of_nonexistent_user(self):
        user = UserFactory()

        non_existent_user_id = 911928345  # Some big random number
        User.objects.filter(pk=non_existent_user_id).exists().should.be(False)  # Precondition, just in case

        self.client.force_login(user)
        response = self.client.get('/api/v1/users/%s/videos/' % non_existent_user_id)

        response.status_code.should.equal(status.HTTP_404_NOT_FOUND)


class RecommendedFollowTestCase(APITestCase):
    def test_recommended_follow(self):
        dfr = DefaultFollowRecommendationFactory()
        request_user = UserFactory()
        u1 = UserFactory()
        u2 = UserFactory()
        u3 = UserFactory()
        dfr.add_user(u3, 3)
        dfr.add_user(u1, 1)
        dfr.add_user(u2, 2)

        self.client.force_login(request_user)
        response = self.client.get('/api/v1/recommended/follows/')
        response.status_code.should.equal(status.HTTP_200_OK)

        rec_users = response.data.get('results')
        rec_users.should.have.length_of(3)

        # First user
        rec_users[0]['username'].should.equal(u1.username)
        rec_users[1]['username'].should.equal(u2.username)
        rec_users[2]['username'].should.equal(u3.username)
