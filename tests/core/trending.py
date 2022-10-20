#!/usr/bin/env python
# coding=utf-8
import random

from django.utils import timezone
from django.conf import settings
from nose.plugins.attrib import attr
from rest_framework.test import APITestCase
from datetime import timedelta

from tests.factories import UserFactory, CommentFactory, LikeFactory, FollowFactory, ViewFactory, VideoFactory, HashtagFactory
from heartface.apps.core.tasks import popularity_score, hashtag_popularity_score, check_trending
from heartface.apps.core.models import Trending, TrendingProfile, TrendingHashtag
from nose_parameterized import parameterized
import sure


def insert_tag(ctext, tag):
    """
    Insert a hashtag at a random point
    within comment text
    """
    words = ctext.split()
    insert_point = random.randrange(len(words))
    return ' '.join(words[:insert_point] + [tag, ] + words[insert_point:])


@attr('slow')
class TrendingTestCase(APITestCase):

    @staticmethod
    def _create_profile_fixtures(users, t, count_params):
        exp_scores = {}
        producers = users[:len(count_params)]  # Users who create content
        consumers = users[len(count_params):]  # Users who only comment/like/view
        for n, user in enumerate(producers):
            comments_cnt, likes_cnt, followers_cnt, uploads_cnt, views_cnt, exp_score = count_params[n][:6]
            exp_scores[user.id] = exp_score
            # Use factory to create these model instances
            for n in range(followers_cnt):
                # Get a user who isn't already the follower
                follower = random.choice([usr for usr in consumers
                                          if usr not in user.followers.all()])
                FollowFactory.create(created=t, follower=follower, followed=user)
            videos = VideoFactory.create_batch(uploads_cnt, owner=user, published=t)
            # Distribute comments/likes/views over these videos
            for n in range(comments_cnt):
                video = random.choice(videos)
                author = random.choice(consumers)
                CommentFactory.create(created=t, author=author, video=video)
            for n in range(likes_cnt):
                video = random.choice(videos)
                liker = random.choice(consumers)
                # Get a user who isn't already a liker
                liker = random.choice([usr for usr in consumers
                                       if usr not in video.likes.all()])
                LikeFactory.create(created=t, user=liker, video=video)
            for n in range(views_cnt):
                video = random.choice(videos)
                # Get a viewer who hasn't already viewed this video
                viewer = random.choice([vwr for vwr in consumers
                                        if video.view_set.filter(user__id=vwr.id).count() == 0])
                ViewFactory.create(created=t, user=viewer, video=video)
        return exp_scores

    @parameterized.expand([
        # Each represents a given producer with following cnts
        # comments, likes, followers, uploads, views, exp_score
        ("user_batch1",
         [(10, 32, 39, 6, 44, 278),
          (6, 39, 18, 32, 47, 266),
          (20, 26, 41, 48, 13, 255),
          (26, 47, 13, 45, 4, 208),
          (44, 3, 46, 16, 12, 279),
          (9, 16, 6, 14, 17, 120),
          (30, 31, 4, 34, 23, 232),
          (31, 7, 44, 8, 30, 286),
          (11, 48, 32, 13, 14, 200),
          (34, 6, 39, 30, 49, 363)],
         )
    ])
    def test_popularity_score(self, _, count_params):
        """
        Usage:
        ./manage test tests.core.trending:TrendingTestCase.test_popularity_score_0_user_batch1
        """
        now = timezone.now()
        users = UserFactory.create_batch(100)  # Must be greater than len(count_params)
        exp_scores = self._create_profile_fixtures(users, now, count_params)

        t1 = now - timedelta(days=1) - timedelta(hours=12)
        exp_scores2 = self._create_profile_fixtures(users, t1, count_params)

        # Now run popularity_score and ensure the `exp_score` for each of
        # our Users matches the `computed_score`
        now = now + timedelta(seconds=100)
        ps_dict = popularity_score(now)
        for user_id in exp_scores:
            ps_dict[user_id].should.equal(exp_scores[user_id])

        # Yesterday's
        ps_dict2 = popularity_score(now - timedelta(days=1))
        for user_id in exp_scores2:
            ps_dict2[user_id].should.equal(exp_scores2[user_id])

    @staticmethod
    def _create_hashtag_fixtures(users, hashtags, t, count_params):
        exp_scores = {}
        # Create videos
        videos = []
        for n in range(100):
            vuser = random.choice(users)
            videos.append(VideoFactory.create(published=t, owner=vuser))
        # Create comments
        comments = []
        for n in range(100):
            author = random.choice(users)
            video = random.choice(videos)
            comments.append(CommentFactory.create(created=t, video=video, author=author))

        for n, htag in enumerate(hashtags):
            videos_cnt, comments_cnt, exp_score = count_params[n][-3:]
            exp_scores[htag.id] = exp_score

            # This hashtag tags `videos_cnt` videos
            for n in range(videos_cnt):
                # Tag a video we haven't tagged already
                video = random.choice([video for video in videos
                                       if video.hashtags.filter(name=htag.name).count() == 0])
                video.hashtags.add(htag)
                video.save()

            # This hashtag appears in `comments_cnt` comments
            for m in range(comments_cnt):
                # Add tag to comment text that it isn't already in
                comment = random.choice([comment for comment in comments
                                         if htag.name not in comment.text])
                comment.text = insert_tag(comment.text, '#'+htag.name)
                comment.save()

        return exp_scores

    @parameterized.expand([
        ("hashtag_batch1",
         # videos with tag, comments with tag, expected score
         [(10, 32, 42),
          (6, 39, 45),
          (20, 26, 46),
          (26, 47, 73),
          (44, 3, 47),
          (9, 16, 25),
          (30, 31, 61),
          (31, 7, 38),
          (11, 48, 59),
          (34, 6, 40)],
         )
    ])
    def test_hashtag_popularity_score(self, _, count_params):
        """
        Usage:
        ./manage test tests.core.trending:TrendingTestCase.test_hashtag_popularity_score_0_hashtag_batch1
        """
        now = timezone.now()
        users = UserFactory.create_batch(100)
        hashtags = HashtagFactory.create_batch(len(count_params))
        exp_scores = self._create_hashtag_fixtures(users, hashtags, now, count_params)

        t1 = now - timedelta(days=1) - timedelta(hours=12)
        exp_scores2 = self._create_hashtag_fixtures(users, hashtags, t1, count_params)

        # Now run hashtag_popularity_score and ensure the `exp_score` for each of
        # our Hashtags matches the `computed_score`
        now = now + timedelta(seconds=100)
        ps_dict = hashtag_popularity_score(now)
        for hashtag_id in exp_scores:
            ps_dict[hashtag_id].should.equal(exp_scores[hashtag_id])

        ps_dict2 = hashtag_popularity_score(now - timedelta(days=1))
        for hashtag_id in exp_scores2:
            ps_dict2[hashtag_id].should.equal(exp_scores2[hashtag_id])

    @parameterized.expand([
        ("hashtag_batch1",
         # videos with tag, comments with tag, expected score
         # counts for today
         [(6, 15, 21),
          (25, 16, 41),
          (13, 3, 16),
          (7, 43, 50),
          (6, 11, 17),
          (22, 20, 42),
          (19, 44, 63),
          (10, 2, 12),
          (0, 39, 39),
          (1, 1, 2)],
         # counts for yesterday
         [(28, 48, 76),
          (24, 49, 73),
          (22, 39, 61),
          (26, 41, 67),
          (42, 4, 46),
          (32, 17, 49),
          (47, 25, 72),
          (12, 21, 33),
          (40, 48, 88),
          (31, 28, 59)],
         # Trending scores for hashtags
         [-0.7236842105263158,
          -0.4383561643835616,
          -0.7377049180327869,
          -0.2537313432835821,
          -0.6304347826086957,
          -0.14285714285714285,
          -0.125,
          -0.6363636363636364,
          -0.5568181818181818,
          -0.9661016949152542]
         )
    ])
    def test_check_trending_tags(self, _, today_count_params, yest_count_params, exp_trending_scores):
        """
        Usage:
        ./manage test tests.core.trending:TrendingTestCase.test_check_trending_tags_0_hashtag_batch1
        """
        t = timezone.now()
        t1 = t - timedelta(days=1)

        # Fixtures
        tag_users = UserFactory.create_batch(100)
        hashtags = HashtagFactory.create_batch(len(today_count_params))
        exp_scores_t = self._create_hashtag_fixtures(tag_users, hashtags, t, today_count_params)
        exp_scores_t1 = self._create_hashtag_fixtures(tag_users, hashtags, t1, yest_count_params)

        len(exp_scores_t).should.equal(len(today_count_params))
        len(exp_scores_t1).should.equal(len(yest_count_params))

        # Pop score tests
        ps_dict = hashtag_popularity_score(t + timedelta(seconds=100))
        for hashtag_id in exp_scores_t:
            ps_dict[hashtag_id].should.equal(exp_scores_t[hashtag_id])
        ps_dict = hashtag_popularity_score(t1 + timedelta(seconds=100))
        for hashtag_id in exp_scores_t1:
            ps_dict[hashtag_id].should.equal(exp_scores_t1[hashtag_id])

        # Check trending tests
        check_trending()
        t = Trending.objects.latest('created')

        # Should just be one for today
        Trending.objects.filter(created__year=timezone.now().year, created__month=timezone.now().month, created__day=timezone.now().day).count().should.equal(1)

        trending_hashtags = TrendingHashtag.objects.filter(trending__id=t.id).order_by('-score')
        # Correct number
        len(trending_hashtags).should.equal(settings.TRENDING_LIMIT)

        # exp_trending_scores trending_profiles score and order
        exp_trending_scores = sorted(exp_trending_scores, reverse=True)
        for idx, trending_hashtag in enumerate(trending_hashtags):
            exp_score_2dp = '{0:.2f}'.format(exp_trending_scores[idx])
            exp_score_2dp.should.equal('{0:.2f}'.format(trending_hashtag.score))

    @parameterized.expand([
        ("prof_batch1",
         # comments, likes, followers, uploads, views, exp_score
         # counts for today
         [(45, 6, 29, 43, 40, 362),
          (23, 22, 47, 47, 7, 253),
          (32, 11, 18, 5, 48, 292),
          (21, 20, 0, 39, 7, 143),
          (33, 46, 7, 46, 38, 319),
          (4, 41, 40, 16, 36, 257),
          (18, 6, 28, 41, 42, 283),
          (41, 13, 31, 4, 19, 259),
          (28, 16, 1, 31, 14, 175),
          (33, 20, 45, 18, 18, 281)],
         # counts for yesterday
         [(26, 1, 35, 35, 41, 307),
          (15, 31, 25, 22, 37, 259),
          (8, 48, 37, 11, 1, 160),
          (45, 45, 33, 41, 32, 383),
          (15, 41, 5, 10, 45, 241),
          (24, 17, 10, 18, 39, 244),
          (13, 48, 44, 21, 10, 226),
          (39, 19, 46, 42, 3, 279),
          (6, 15, 0, 6, 40, 159),
          (13, 26, 38, 48, 21, 252)],
         # Trending scores for profiles
         [0.1791530944625407,
          -0.023166023166023165,
          0.825,
          -0.6266318537859008,
          0.3236514522821577,
          0.05327868852459016,
          0.252212389380531,
          -0.07168458781362007,
          0.10062893081761007,
          0.11507936507936507],
         )
    ])
    def test_check_trending_profs(self, _, today_count_params, yest_count_params, exp_trending_scores):
        """
        Usage:
        ./manage test tests.core.trending:TrendingTestCase.test_check_trending_profs_0_prof_batch1
        """
        t = timezone.now()
        t1 = t - timedelta(days=1)

        # prof fixtures
        prof_users = UserFactory.create_batch(100)
        exp_scores_t = self._create_profile_fixtures(prof_users, t, today_count_params)
        exp_scores_t1 = self._create_profile_fixtures(prof_users, t1, yest_count_params)

        len(exp_scores_t).should.equal(len(today_count_params))
        len(exp_scores_t1).should.equal(len(yest_count_params))

        # Pop score tests
        ps_dict = popularity_score(t + timedelta(seconds=100))
        for user_id in exp_scores_t:
            ps_dict[user_id].should.equal(exp_scores_t[user_id])
        ps_dict = popularity_score(t1 + timedelta(seconds=100))
        for user_id in exp_scores_t1:
            ps_dict[user_id].should.equal(exp_scores_t1[user_id])

        # Check trending tests
        check_trending()
        t = Trending.objects.latest('created')

        # Should just be one for today
        Trending.objects.filter(created__year=timezone.now().year, created__month=timezone.now().month, created__day=timezone.now().day).count().should.equal(1)

        trending_profiles = TrendingProfile.objects.filter(trending__id=t.id).order_by('-score')
        # Correct number of trending profiles
        len(trending_profiles).should.equal(settings.TRENDING_LIMIT)

        # exp_trending_scores trending_profiles score and order
        exp_trending_scores = sorted(exp_trending_scores, reverse=True)
        for idx, trending_profile in enumerate(trending_profiles):
            exp_score_2dp = '{0:.2f}'.format(exp_trending_scores[idx])
            exp_score_2dp.should.equal('{0:.2f}'.format(trending_profile.score))
