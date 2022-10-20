#!/usr/bin/env python
# coding=utf-8
from typing import List

from django.conf import settings
from django.db import transaction
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APITestCase


from heartface.apps.core.models import Video, View, ReportedVideo
from tests.factories import UserFactory, VideoFactory, ProductFactory, HashtagFactory, LikeFactory, \
    SupplierProductFactory

import sure

class VideoTestCase(APITestCase):
    def test_like_own_video(self):
        video = VideoFactory()

        self.client.force_login(video.owner)
        response = self.client.post('/api/v1/videos/%s/like/' % video.id)
        response.status_code.should.equal(status.HTTP_201_CREATED)
        video.likes.first().should.equal(video.owner)

    def test_view_video(self):
        video = VideoFactory()
        user = UserFactory()

        self.client.force_login(user)
        original_view_count = video.view_count # For comparison

        # Run in a transaction to make sure it works this way as well, because we'll have to run in a transaction for
        #  the test below
        with transaction.atomic():
            response = self.client.post('/api/v1/videos/%s/views/' % video.id)
            response.status_code.should.equal(status.HTTP_201_CREATED)

        # Check video.view_count did increment
        video.refresh_from_db()
        video.view_count.should.equal(original_view_count + 1)

        # Check View instance for this video and user exists
        View.objects.filter(user=user, video=video).count().should.be(1)

        # Wrap in a transaction because there will be an exception inside the view (and it doesn't seem to roll back
        #  automatically when running it from a test)
        with transaction.atomic():
            # If same user views a second time, check still only one View instance
            response = self.client.post('/api/v1/videos/%s/views/' % video.id)
            response.status_code.should.equal(status.HTTP_200_OK)

        View.objects.filter(user=user, video=video).count().should.be(1)
        # And view_count hasn't been updated a second time
        video.refresh_from_db()
        video.view_count.should.equal(original_view_count + 1)

        # Check response if video invalid
        non_existent_video_id = 86524953124545  # Some big random number
        Video.objects.filter(pk=non_existent_video_id).exists().should.be(False) # Precondition, just in case
        self.client.force_login(user)
        response = self.client.post('/api/v1/videos/%s/views/' % non_existent_video_id)
        response.status_code.should.equal(status.HTTP_404_NOT_FOUND)

    def test_double_like_video(self):
        video = VideoFactory()
        user = UserFactory()

        self.client.force_login(user)
        response = self.client.post('/api/v1/videos/%s/like/' % video.id)
        response.status_code.should.equal(status.HTTP_201_CREATED)
        video.likes.first().should.equal(user)
        video.likes.count().should.equal(1)

        response = self.client.post('/api/v1/videos/%s/like/' % video.id)
        response.status_code.should.equal(status.HTTP_201_CREATED)
        video.likes.first().should.equal(user)
        video.likes.count().should.equal(1)

    def test_like_other_users_video(self):
        video = VideoFactory()
        user = UserFactory()

        self.client.force_login(user)
        response = self.client.post('/api/v1/videos/%s/like/' % video.id)
        response.status_code.should.equal(status.HTTP_201_CREATED)
        video.likes.first().should.equal(user)

    def test_unlike_video(self):
        user = UserFactory()
        video = VideoFactory()
        LikeFactory(video=video, user=user)

        self.client.force_login(user)
        respone = self.client.delete('/api/v1/videos/%s/like/' % video.id)
        respone.status_code.should.equal(status.HTTP_200_OK)
        video.likes.count().should.equal(0)

    def test_get_videos_guest_mode(self):
        video = VideoFactory()
        response = self.client.get('/api/v1/videos/')

        videos = response.data.get('results')[0]
        response.status_code.should.equal(status.HTTP_200_OK)
        videos.get('title').should.equal(video.title)
        videos.get('owner').get('id').should.equal(video.owner.id)

    def test_guest_cant_update_videos(self):
        video = VideoFactory()
        response = self.client.patch('/api/v1/videos/%s/' % video.id, {'title': 'change_video_title'})
        response.status_code.should.equal(status.HTTP_401_UNAUTHORIZED)

    def test_user_cant_update_other_video(self):
        consumer = UserFactory()
        producer = UserFactory()
        video = VideoFactory()

        self.client.force_login(consumer)
        response = self.client.patch('/api/v1/videos/%s/' % video.id, {'title': 'change_title_for_another_video'})

        response.status_code.should.equal(status.HTTP_403_FORBIDDEN)

    def test_user_cant_delete_other_users_video(self):
        consumer = UserFactory()
        producer = UserFactory()
        video = VideoFactory()

        self.client.force_login(consumer)
        response = self.client.delete('/api/v1/videos/%s/' % video.id)

        response.status_code.should.equal(status.HTTP_403_FORBIDDEN)

    def test_user_can_update_own_video(self):
        consumer = UserFactory()
        video = VideoFactory(owner=consumer)
        new_title = 'change title for own video'

        self.client.force_login(consumer)
        response = self.client.patch('/api/v1/videos/%s/' % video.id, {'title': new_title})

        response.status_code.should.equal(status.HTTP_200_OK)
        response.data['title'].should.equal(new_title)
        video.refresh_from_db()
        video.title.should.equal(new_title)


    def test_filter_by_hashtag(self):
        def tag(tag, videos: List[Video]):
            for v in videos:
                v.hashtags.add(tag)

        hashtag1 = HashtagFactory()
        hashtag2 = HashtagFactory()

        videos1 = [VideoFactory() for i in range(5)]
        videos2 = [VideoFactory() for i in range(5)]
        videos3 = [VideoFactory() for i in range(5)]

        tag(hashtag1, videos1)
        tag(hashtag1, videos3)
        tag(hashtag2, videos2)
        tag(hashtag2, videos3)

        self.client.force_login(UserFactory())

        response = self.client.get('/api/v1/videos/?hashtag=%s' % hashtag1.name)
        response.status_code.should.equal(status.HTTP_200_OK)

        response_videos = response.data['results']

        tagged_video_ids = set(v.pk for v in (videos1 + videos3))
        response_videos.should.have.length_of(tagged_video_ids)

        response_video_ids = set(v['id'] for v in response_videos)

        response_video_ids.should.equal(tagged_video_ids)

    @parameterized.expand([
        ('no-extenstion-filename',), ('some-video.mp4',), ('some-otherf-ormat.mov',), ('non-video-ext-.jpg',)
    ])
    def test_cdn_url_extension(self, file_name):
        video = VideoFactory(videofile=file_name)

        video.videofile_cdn_url.should.match('\.%s$' % settings.CDN_VIDEO_EXTENSION)

    def test_video_has_likes_list_even_if_no_likes(self):
        video = VideoFactory()

        self.client.login(user=UserFactory())
        response = self.client.get('/api/v1/videos/%s/' % video.id)

        response.status_code.should.equal(status.HTTP_200_OK)
        response.data.should.have.key('likes')
        response.data['likes'].should.equal([])


# TODO: move it to the right module & class/TestCase
class VideoProductTaggingTestCase(APITestCase):
    def test_tag_video_with_product(self):
        user = UserFactory()
        video = VideoFactory(owner=user)

        ProductFactory()
        ProductFactory()

        product = ProductFactory()

        self.client.force_login(user)
        response = self.client.post('/api/v1/videos/%s/products/' % video.pk, {'id': product.pk})

        response.status_code.should.equal(status.HTTP_201_CREATED)

        list(video.products.all()).should.equal([product])

    def test_untag_video_with_product(self):
        user = UserFactory()
        video = VideoFactory(owner=user)

        ProductFactory()
        ProductFactory()

        product = ProductFactory()

        self.client.force_login(user)
        response = self.client.delete('/api/v1/videos/%s/products/' % video.pk, {'id': product.pk})

        response.status_code.should.equal(status.HTTP_200_OK)
