from django.apps import apps
from django.core.management.base import BaseCommand
from django.contrib.sites.models import Site
from django.conf import settings

from elasticsearch import Elasticsearch
from heartface.apps.core.api.serializers.accounts import PublicUserSerializer
from heartface.apps.core.api.serializers.discovery import VideoSerializer, HashtagSerializer
from heartface.apps.core.api.serializers.products import ProductSerializer

from heartface.apps.core.search_indexes import SEARCH_INDEXES

from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from heartface.libs.utils import _req_ctx_with_request


class Command(BaseCommand):
    help = '''
        Create not existing Elasticsearch indexes

        run ./manage create_indexes
    '''

    def add_arguments(self, parser):
        parser.add_argument(
            '--rebuild',
            action='store_true',
            dest='rebuild',
            help='Rebuild all indexes (delete existing indexes)'
        )

    def handle(self, *args, **options):
        es = Elasticsearch(settings.ELASTIC_URL)

        if options['rebuild']:
            for index in es.indices.get_alias():
                es.indices.delete(index)

        serializer_map = {'User': PublicUserSerializer,
                          'Hashtag': HashtagSerializer,
                          'Video': VideoSerializer,
                          'Product': ProductSerializer}
        for index in SEARCH_INDEXES:
            if not es.indices.exists(index['index']):
                model_cls = serializer_map[index['model']]
                index['es_model'].init()
                for inst in apps.get_model('core', index['model']).objects.all().iterator():
                    obj = model_cls(inst, context=_req_ctx_with_request())
                    obj.es_save()
