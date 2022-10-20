#!/usr/bin/env python
# coding=utf-8

from django.conf import settings

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from elasticsearch import Elasticsearch, RequestsHttpConnection
from elasticsearch_dsl import Q
from rest_framework_elasticsearch import es_views, es_filters

from heartface.apps.core.search_indexes import UserIndex, HashtagIndex, VideoIndex, ProductIndex


class SearchFilter(es_filters.ElasticSearchFilter):
    search_param = 'q'


class PrefixSearchFilter(es_filters.ElasticSearchFilter):
    search_param = 'q'

    def get_es_query(self, s_query, s_fields, **kwargs):
        """
        Do a phrase prefix search to support search-as-you-type, i.e.
        the query "Peter Sm" would expand to "Peter Sm*", which would match
        accross `s_fields`
        """
        return Q("multi_match", query=s_query, fields=s_fields, type="phrase_prefix")


prefix_filter_backends = (
    es_filters.ElasticFieldsFilter,
    PrefixSearchFilter
)

filter_backends = (
    es_filters.ElasticFieldsFilter,
    SearchFilter
)


class UserSearchView(es_views.ListElasticAPIView):
    es_client = Elasticsearch(hosts=[settings.ELASTIC_URL], connection_class=RequestsHttpConnection)
    es_model = UserIndex
    es_filter_backends = filter_backends
    # These fields will be searchable with q multimatch and need 75% match by default
    # ./get 'v1/search/?topic=users&q=whatever.com'
    es_search_fields = ('username', 'full_name', 'email', 'description')

    @classmethod
    def as_view(cls, prefix_only, **initkwargs):
        if prefix_only:
            cls.es_filter_backends = prefix_filter_backends
        return super().as_view(**initkwargs)


class HashtagSearchView(es_views.ListElasticAPIView):
    es_client = Elasticsearch(hosts=[settings.ELASTIC_URL], connection_class=RequestsHttpConnection)
    es_model = HashtagIndex
    es_filter_backends = filter_backends
    es_search_fields = ('name', )

    @classmethod
    def as_view(cls, prefix_only, **initkwargs):
        if prefix_only:
            cls.es_filter_backends = prefix_filter_backends
        return super().as_view(**initkwargs)


class VideoSearchView(es_views.ListElasticAPIView):
    es_client = Elasticsearch(hosts=[settings.ELASTIC_URL], connection_class=RequestsHttpConnection)
    es_model = VideoIndex
    es_filter_backends = filter_backends
    es_search_fields = ('title', 'owner.username', 'owner.full_name', 'products.name',
                        'products.supplier_info.link')

    @classmethod
    def as_view(cls, prefix_only, **initkwargs):
        if prefix_only:
            cls.es_filter_backends = prefix_filter_backends
        return super().as_view(**initkwargs)


class ProductSearchView(es_views.ListElasticAPIView):
    es_client = Elasticsearch(hosts=[settings.ELASTIC_URL], connection_class=RequestsHttpConnection)
    es_model = ProductIndex
    es_filter_backends = filter_backends
    # ./get 'v1/search/?topic=products&q=...'
    # TODO: we need to see the rest framework elastic bug so can begin to
    # properly use field filters and range filters instead of just q across multi
    # es_search_fields = ('name', 'style_code', 'supplier_info.link')
    # Temp just search on name
    es_search_fields = ('name', )

    @classmethod
    def as_view(cls, prefix_only, **initkwargs):
        if prefix_only:
            cls.es_filter_backends = prefix_filter_backends
        return super().as_view(**initkwargs)


SEARCH_VIEWS = {
    'users': UserSearchView,
    'hashtags': HashtagSearchView,
    'videos': VideoSearchView,
    'products': ProductSearchView
}


def search_views(topic, prefix_only):
    return SEARCH_VIEWS[topic].as_view(prefix_only)


class SearchAPIView(APIView):
    """
    Search API for users, hashtags, videos, products
    methods accepted: GET
    permissions: any
    endpoint format: /api/v1/search/
    for users: /api/v1/search/?topic=users
    for hashtags: /api/v1/search/?topic=hashtags
    for videos: /api/v1/search/?topic=videos
    for products: /api/v1/search/?topic=products
    Note: for search-as-you-type: add '&prefix_only=1'
    Request Body: N/A
    Expected status code: HTTP_200_OK
    Expected Response: A list of serialized search results related to topic
    """
    def get(self, request, *args, **kwargs):
        topic = request.GET.get('topic')
        # This will use the phrase_prefix filter rather than regular search
        # to achieve search-as-you-type functionality
        prefix_only = True if request.GET.get('prefix_only') else False

        if not topic or topic not in SEARCH_VIEWS.keys():
            return Response(status=status.HTTP_404_NOT_FOUND, data={'detail': 'Please specify a valid topic'})
        return search_views(topic, prefix_only)(self.request._request, *args, **kwargs)
