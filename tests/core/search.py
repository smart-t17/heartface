#!/usr/bin/env python
# coding=utf-8
import json
import pickle
import re
import time
from collections import OrderedDict

from django.utils.crypto import get_random_string
from elasticsearch_dsl import connections
from nose.plugins.attrib import attr
from parameterized import parameterized
from rest_framework import status
from rest_framework.test import APITestCase

import sure
from rest_framework.utils.encoders import JSONEncoder

from heartface.apps.core.api.serializers.discovery import VideoSerializer
from heartface.apps.core.tasks import update_es_record_task
from heartface.libs.utils import _req_ctx_with_request
from tests.factories import UserFactory, VideoFactory, ProductFactory, HashtagFactory

from heartface.apps.core.models import Video
from heartface.apps.core.search_indexes import VideoIndex


# NOTE: Needs ElasticSearch running
# NOTE: this is broken. The test is stateful (will update ES) and thus the API can't be guaranteed to return the expected
#  results. Possible ways to fix it:
#  - make it a smoke test (only check returned data structure)
#  - generate random/unique values for the fields that we'll use as test terms
#  - somehow clean up after running the test (e.g. delete models). This is still error prone.
from tests.utils import pp


@attr('broken')
class SearchTestCase(APITestCase):
    @parameterized.expand([
        (VideoFactory, 'title', 'videos'),
        (UserFactory, 'username', 'users'),
        (HashtagFactory, 'name', 'hashtags'),
        # NOTE: The test may fail for the following two, as the test will only check for the presence of the search term
        #  in the specified model field (and product is indexed by two fields)
        (ProductFactory, 'name', 'products'),
        (ProductFactory, 'description', 'products')
    ])
    def test_search(self, factory, model_field, topic):
        els = connections.get_connection()

        instances = [factory() for i in range(10)]
        search_term = getattr(instances[0], model_field).split(' ')[0].lower()

        # (Kind of) wait for indexing to finish (or force it to happen now)
        print(els.indices.refresh())
        # time.sleep(5)

        response = self.client.get('/api/v1/search/?q=%s&topic=%s' % (search_term, topic))
        response.status_code.should.equal(status.HTTP_200_OK)

        # Print some debug info to help indentify problems
        print("""Term: %s
        Field: %s
        Data: %s
        Response: %s
        """ % (search_term, model_field, ['%s: %s' % (i.pk, getattr(i, model_field)) for i in instances], response.data)
              )

        response.data.should.contain('results')
        response.data.get('results').should_not.be.empty

        response.data.get('results')[0].get(model_field).lower().should.contain(search_term)
        result_ids = [d.get('pk') for d in response.data.get('results')]
        result_ids.should.contain(instances[0].pk)

    # def test_search_title_video(self):
    #   for i in range(10):
    #     VideoFactory(owner=UserFactory(), published=timezone.now())
    #
    #   videos = Video.objects.all()
    #   title = videos.first().title.split(' ')[0]
    #
    #   response = self.client.get('/api/v1/search/?q=%s&topic=%s' % (title.lower(), 'videos'))
    #   response.status_code.should.equal(status.HTTP_200_OK)
    #   print(response.data)
    #   if response.data.get('results'):
    #     response.data.get('results')[0].get('title').should.contain(title)

URL_TO_FIX_RX = re.compile('https?://(testserver)/.*')

def _normalize(serialized):
    if isinstance(serialized, OrderedDict):
        return _normalize(dict(serialized))
    if isinstance(serialized, (list, tuple)):
        return [_normalize(o) for o in serialized]
    if isinstance(serialized, str) and URL_TO_FIX_RX.match(serialized):
        return serialized.replace('testserver', 'localhost')

    return serialized


class SearchResultFormatTestCase(APITestCase):
    # This isn't very nice for a unit test (or, but we need to reach out to ElasticSearch as it can cause surprises.
    def test_video_matches_api_format(self):
        es = connections.get_connection()

        # As we can't start with a clean state of ES nor can we reliably roll back the changes made by the tests,
        # we use random unique values for the the object fields to avoid collisions.
        # TODO: we could actually run the rebuild_indexes task with the non-test db to clean things up... (Maybe on test
        #   startup
        video = VideoFactory(title=get_random_string(length=16))

        # manually call update task so that it happens sync (and also, if a celery worker is running, it probably uses
        # a different database and not the test_* one.
        # TODO: check if the task was laucned by the signal
        update_es_record_task(video.pk, 'Video')

        es.indices.refresh()
        self.client.force_login(UserFactory())

        response = self.client.get('/api/v1/search/?q=%s&topic=videos' % video.title)
        response.status_code.should.equal(status.HTTP_200_OK)

        es_result = response.data['results'][0]
        # json.dumps(es_result).should.equal(json.dumps(VideoSerializer(video, context=_req_ctx_with_request()).data, cls=JSONEncoder))
        serialized = _normalize(VideoSerializer(video, context=_req_ctx_with_request()).data)
        es_result.should.equal(serialized)
