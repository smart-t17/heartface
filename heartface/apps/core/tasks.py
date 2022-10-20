#!/usr/bin/env python
# coding=utf-8

# from __future__ import absolute_import

import ftplib
import logging
import os
import operator
import re

import requests
from celery import shared_task
from celery.decorators import periodic_task
from celery.schedules import crontab

from django.conf import settings
from django.utils import timezone
from django.db.models import Count
from django.db import IntegrityError
from collections import defaultdict, namedtuple
from rest_framework import status

import subprocess
import boto3

from heartface.apps.core.models import Video, GlacierFile, Trending, TrendingProfile, TrendingHashtag, Hashtag
from heartface.apps.core.models import User, Comment, View, Like, Order, TaskRun, Product, Video
from heartface.libs import notifications
from heartface.libs.utils import _req_ctx_with_request

from python_skimlinks.python_skimlinks import Client as SkimClient

logger = logging.getLogger(__name__)


# Weighting for popularity score components
Weight = namedtuple('Weight', 'views likes followers comments uploads hashtag_videos hashtag_comments')
weight = Weight(3, 1, 2, 3, 1, 1, 1)


def update_score(ps_dict, qs, weight):
    """
    Update the popularity score dictionary, ps_dict.

    qs is a queryset annotated with 'cnt', which is for example
    the number of comments received or likes received etc
    """
    for item in qs:
        ps_dict[item['id']] += weight * item['cnt']


def popularity_score(t):
    """
    Instead of looping of Users, which
    hits the db with user_number*5 queries
    we can run 5 queries

    Return a dictionary of ps indexed by User pk
    """

    # Record ps for users in dictionary indexed by User pk
    ps_dict = defaultdict(int)

    t1 = t - settings.TRENDING_WINDOW_SIZE

    # Comments
    comments_qs = User.objects.filter(videos__comments__in=Comment.objects.filter(created__lt=t,
                                                                                  created__gte=t1)) \
        .annotate(cnt=Count('videos__comments')).values('id', 'cnt')
    update_score(ps_dict, comments_qs, weight.comments)

    # Likes
    likes_qs = User.objects.filter(videos__like__in=Like.objects.filter(created__lt=t,
                                                                        created__gte=t1)) \
        .annotate(cnt=Count('videos__likes')).values('id', 'cnt')
    update_score(ps_dict, likes_qs, weight.likes)

    # Views
    views_qs = User.objects.filter(videos__view__in=View.objects.filter(created__lt=t, created__gte=t1)) \
        .annotate(cnt=Count('videos__view')).values('id', 'cnt')
    update_score(ps_dict, views_qs, weight.views)

    # Followers
    followers_qs = User.objects.filter(followed__created__lt=t, followed__created__gte=t1) \
        .annotate(cnt=Count('followed')).values('id', 'cnt')
    update_score(ps_dict, followers_qs, weight.followers)

    # Videos uploaded
    uploaded_qs = User.objects.filter(videos__published__lt=t, videos__published__gte=t1) \
        .annotate(cnt=Count('videos')).values('id', 'cnt')
    update_score(ps_dict, uploaded_qs, weight.uploads)

    return ps_dict


def hashtag_popularity_score(t):
    """
    Hashtag usage means the number of videos created that are tagged with the
    given hashtag plus the number of comments created containing the given
    hashtag during the examined time window
    """
    # Record ps for hashtag in dictionary indexed by hashtag pk
    ps_dict = defaultdict(int)

    t1 = t - settings.TRENDING_WINDOW_SIZE

    # Videos with hashtag
    videos_qs = Hashtag.objects.filter(videos__in=Video.objects.filter(
        published__lt=t, published__gte=t1, cdn_available__isnull=False)) \
        .annotate(cnt=Count('videos')).values('id', 'cnt')
    update_score(ps_dict, videos_qs, weight.hashtag_videos)

    # Comments that contain the hashtag
    hashtag_pttn = "(?:^|\s)[＃#]{1}(\w+)"
    hashtag_re = re.compile(hashtag_pttn, re.UNICODE)
    comments = Comment.objects.filter(created__lt=t, created__gte=t1).filter(text__regex=hashtag_pttn) \
        .values('id', 'text')
    hashtag_count = defaultdict(int)
    for comment in comments:
        hashtags = hashtag_re.findall(comment['text'])
        for hashtag in hashtags:
            hashtag_count[hashtag] += 1
    hashtag_qs = Hashtag.objects.filter(name__in=hashtag_count.keys()).values('id', 'name')
    # Need a list of items with hashtag (id, cnt) for update_score
    items = []
    items = [{'id': i['id'], 'cnt': hashtag_count.get(i['name'], 0)} for i in hashtag_qs]
    # Update score
    update_score(ps_dict, items, weight.hashtag_comments)

    return ps_dict


@shared_task
def check_trending():
    # Get popularity score dictionaries (indexed by user id)
    ps_dict = popularity_score(timezone.now())
    ps_dict_t1 = popularity_score(timezone.now() - settings.TRENDING_WINDOW_SIZE)

    t = Trending.objects.create()  # auto_now_add
    threshold = settings.TRENDING_THRESHOLD
    trending_scores = {}
    for u_id in ps_dict.keys():
        ts_t_numerator = ps_dict[u_id] - ps_dict_t1.get(u_id, 0)
        ts_t_denom = max(ps_dict_t1.get(u_id, 0), threshold)
        trending_scores[u_id] = ts_t_numerator/ts_t_denom

    # Create TrendingProfile instances for top TRENDING_LIMIT scores
    sorted_trending_scores = sorted(trending_scores.items(),  key=operator.itemgetter(1), reverse=True)
    for u_id, score in sorted_trending_scores[: settings.TRENDING_LIMIT]:
        TrendingProfile.objects.create(user_id=u_id, trending=t, score=score)

    # Hashtags
    # Get popularity score dictionaries (indexed by user id)
    hashtag_ps_dict = hashtag_popularity_score(timezone.now())
    hashtag_ps_dict_t1 = hashtag_popularity_score(timezone.now() - settings.TRENDING_WINDOW_SIZE)
    hashtag_trending_scores = {}
    for h_id in hashtag_ps_dict.keys():
        ts_t_numerator = hashtag_ps_dict[h_id] - hashtag_ps_dict_t1.get(h_id, 0)
        ts_t_denom = max(hashtag_ps_dict_t1.get(h_id, 0), threshold)
        hashtag_trending_scores[h_id] = ts_t_numerator/ts_t_denom

    sorted_trending_scores = sorted(hashtag_trending_scores.items(),  key=operator.itemgetter(1), reverse=True)
    for h_id, score in sorted_trending_scores[: settings.TRENDING_LIMIT]:
        TrendingHashtag.objects.create(hashtag_id=h_id, trending=t, score=score)


@shared_task(name='upload_video_glacier', max_retries=100)
def upload_video_glacier(video_id):

    client = boto3.client(
        'glacier',
        region_name=settings.AWS_REGION_NAME,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

    video = Video.objects.get(pk=video_id)

    if not os.path.exists(video.videofile.path):
        glacier_files = GlacierFile.objects.filter(video=video)
        if glacier_files:
            glacier_file = glacier_files[0]
            # duplicate task upload task - video already has been uploaded? Log error just in case.
            logger.error("Video file '%s' not found on filesystem. Glacier object id for id: %s",
                         video.videofile.path, glacier_file.id)
        else:
            # No file on filesystem and no assosiated GlacierFile record. File was deleted before upload?
            logger.error("Video file '%s' not found on filesystem. No glacier object associated.",
                         video.videofile.path)
        return None

    # Do not import glacier_upload as a module as it is under GPL license
    output = subprocess.check_output([
        'glacier_upload',
        '-v', settings.AWS_GLACIER_VAULT_NAME,
        '-f', video.videofile.path,
        '-d', video.description,
        '-r', settings.AWS_REGION_NAME,
    ], env={
        'AWS_ACCESS_KEY_ID': settings.AWS_ACCESS_KEY_ID,
        'AWS_SECRET_ACCESS_KEY': settings.AWS_SECRET_ACCESS_KEY,
    })

    for line in output.split('\n'):
        if line.startswith('Archive ID: '):
            archive_id = line[12:]
            break
    else:
        raise Exception('Failed upload, output: %s' % output)

    try:
        GlacierFile.objects.create(video=video, archive_id=archive_id, size=video.videofile.size)
    except IntegrityError:
        # we can hit IntegrityError when this Video object has already GlacierFile
        # which means that file already uploaded by another task.
        # Report as error
        glacier_file = GlacierFile.objects.get(video=video)
        logger.error("Already exists in archive, id: {id} created: {created} size {size} archive_id: {archive_id}".format(
            id=glacier_file.id,
            created=glacier_file.created,
            size=glacier_file.size,
            archive_id=glacier_file.archive_id,
        ))

        # delete just uploaded file
        client.delete_archive(
            vaultName=settings.AWS_GLACIER_VAULT_NAME,
            archiveId=archive_id,
        )
    else:
        # Upload successful. Remove file from filesystem as we have backup copy in glacier.
        os.unlink(video.videofile.path)


@shared_task(max_retries=3)
def upload_video(video_id):
    try:
        video = Video.objects.get(id=video_id)
    except Video.DoesNotExist:
        logger.error('Upload of non-existent video requested. Video.id = %s', video_id)
        return

    if not os.path.exists(video.videofile.path):
        logger.error('Videofile %s for Video %r is absent, unable to upload', video.videofile.path, video)
        return

    try:
        logger.debug('Uploading video [id=%s]', video_id)

        session = ftplib.FTP(settings.CDN_FTP, settings.CDN_USERNAME, settings.CDN_PASSWORD)
        session.cwd(settings.CDN_VIDEO_UPLOAD_PATH)

        video_filename = os.path.basename(video.videofile.name)

        with open(video.videofile.path, 'rb') as f:
            session.storbinary('STOR {}'.format(video_filename), f)

        logger.debug('Uploaded video [id=%s]', video_id)

        session.quit()
    except Exception as e:
        return upload_video.retry(countdown=60, exc=e)

    check_for_video_exists_in_cdn.delay(video_id=video_id)


@shared_task(max_retries=30)
def check_for_video_exists_in_cdn(video_id):
    filters = dict(published__isnull=False, cdn_available__isnull=True, pk=video_id)
    try:
        video = Video.objects.get(**filters)
    except Video.DoesNotExist:
        return

    cdn_urls = [video.videofile_cdn_url, video.cover_picture_cdn_url]
    logger.debug('Check video ready on CDN. [id=%s, url1=%s, url2=%s]', video.pk, *cdn_urls)
    if all(requests.head(url).status_code == status.HTTP_200_OK for url in cdn_urls):
        if Video.objects.filter(**filters).update(cdn_available=timezone.now()):
            # Backup should be done only once, that's why doing filter(...).update(...)
            logger.debug('Published video [id=%s]', video.pk)
            upload_video_glacier.delay(video_id=video.pk)
    else:
        # check again in 60 seconds if some videos marked as not available on cdn
        return check_for_video_exists_in_cdn.retry(countdown=60)


@shared_task
def cleanup_unpublished_vids():
    for video in Video.objects.filter(
            published__isnull=True, created__lte=(timezone.now() - settings.UNPUBLISHED_VIDEO_RETAIN_WINDOW)):
        logger.debug('Deleting video %s and associated file' % video.pk)
        videofile = video.videofile
        video.delete()  # Delete instance
        if videofile is not None:
            videofile.delete(save=False)  # Delete file itself (respect storage)


@shared_task(name='send_notification', bind=True, max_retries=30)
def send_notification(self, notification_type, current_user_username, user_id, video_id=None, retry_count=1):
    if not notifications._send_sync_impl(notification_type, current_user_username, user_id, video_id=video_id):
        raise self.retry(args=(notification_type, current_user_username, user_id),
                         kwargs={'retry_count': retry_count + 1, 'video_id': video_id}, countdown=pow(1.5, retry_count//5))


def _get_commissions(updated_since=None):
    """
    Use the search_commissions endpoint to get
    commissions updated since `updated_since` (paging over)

    N.B. if we do this on-demand in the future we can also filter
    commissions by `custom_id`, which should contain the `xcust` data we
    set on the affil link.

        cli.search_comissions(custom_id='order_id:114')

    assuming `xcust=order_id:114` set on affil link.
    """
    has_next = True  # Is there another page of data
    query_params = {'offset': 0, 'limit': 30}  # Limit is default 30
    if updated_since:
        # Only get commissions updated since this date, format 'Y-m-d-dd H:M'
        query_params.update({'updated_since': updated_since})
    # Init the client
    cli = SkimClient(settings.SKIMLINKS_ACCT_ID, settings.SKIMLINKS_ACCT_TYPE,
                     settings.SKIMLINKS_PRIV_KEY)
    comms = []
    while has_next:
        resp = cli.search_commissions(**query_params)
        comms.extend(resp.get('commissions', []))
        # Next page
        has_next = resp['pagination'].get('has_next', False)
        if has_next:
            query_params['offset'] += resp['pagination'].get('limit')
    return comms


@shared_task(name="update_es_record")
def update_es_record_task(instance_pk, model_name):
    # Avoid circ imports on serializers
    from heartface.apps.core.api.serializers.discovery import VideoSerializer
    from heartface.apps.core.api.serializers.accounts import PublicUserSerializer
    from heartface.apps.core.api.serializers.discovery import HashtagSerializer
    from heartface.apps.core.api.serializers.products import ProductSerializer
    from heartface.apps.core.models import Hashtag, Product, Video, User
    MODEL_MAP = {"User": {"serializer": PublicUserSerializer, "model": User},
                 "Hashtag": {"serializer": HashtagSerializer, "model": Hashtag},
                 "Video": {"serializer": VideoSerializer, "model": Video},
                 "Product": {"serializer": ProductSerializer, "model": Product}}
    # Get instance from db
    try:
        instance = MODEL_MAP[model_name]["model"].objects.get(pk=instance_pk)
    except MODEL_MAP[model_name]["model"].DoesNotExist:
        logger.error('Could not find %s instance with pk %s for ES update', model_name, instance_pk)
        return False
    obj = MODEL_MAP[model_name]["serializer"](instance, context=_req_ctx_with_request())
    obj.es_save()
    logger.info('Updated ES record with id {} (model {})'.format(instance_pk, model_name))


@shared_task(name="save_scraped_product")
def save_scraped_product(item):
    logger.debug(item)
    stockx_id = item.pop('stockx_id')
    Product.objects.update_or_create(stockx_id=stockx_id,
                                     defaults=item)
    return True


@shared_task(name="delete_es_record")
def delete_es_record_task(instance_pk, serializer_name):
    # Avoid circ imports on serializers
    from heartface.apps.core.api.serializers.discovery import VideoSerializer
    from heartface.apps.core.api.serializers.accounts import PublicUserSerializer
    from heartface.apps.core.api.serializers.discovery import HashtagSerializer
    from heartface.apps.core.api.serializers.products import ProductSerializer
    SERIALIZER_MAP = {"PublicUserSerializer": PublicUserSerializer,
                      "HashtagSerializer": HashtagSerializer,
                      "VideoSerializer": VideoSerializer,
                      "ProductSerializer": ProductSerializer}

    data = {"id": instance_pk}
    obj = SERIALIZER_MAP[serializer_name](data=data, context=_req_ctx_with_request())
    # We use es_delete with data kwarg, which bypasses es_instance, since we
    # don't have an instance here (cel cant serialize etc)
    obj.es_delete(data=data, ignore=404)
    logger.info('Deleted ES record with id {} (serializer {})'.format(instance_pk, serializer_name))


@shared_task
def stockx_crawler_update_product():
    """
    Run stockx crawler everyday to update products within the last 7 days
    """
    from crawlers.spiders.stockx import StockxSpider
    from scrapy.crawler import CrawlerProcess
    from scrapy.utils.project import get_project_settings

    process = CrawlerProcess(get_project_settings())

    process.crawl(StockxSpider)
    process.start()

    # because twisted reactors aren't restartable and the only solution is to kill worker process
    # https://twistedmatrix.com/trac/ticket/9154
    # http://docs.celeryproject.org/en/latest/userguide/workers.html#restarting-the-worker
    os.kill(os.getpid(), 1)
