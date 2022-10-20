from django.core import management
from django.core.management.base import BaseCommand
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

from heartface.apps.core.search_indexes import SEARCH_INDEXES


class Command(BaseCommand):
    help = '''
        Rebuild Elasticsearch indexes
        
        run ./manage rebuild_indexes
    '''

    def handle(self, *args, **options):
        management.call_command('create_indexes', rebuild=True)
