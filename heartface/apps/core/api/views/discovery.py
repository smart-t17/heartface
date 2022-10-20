#!/usr/bin/env python
# coding=utf-8

from rest_framework import status
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import detail_route, list_route
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.generics import RetrieveAPIView
from rest_framework.settings import api_settings

from heartface.apps.core.models import *
from heartface.apps.core.permissions import IsAuthenticatedAndEnabled
from heartface.apps.core.api.serializers.discovery import *

import math
import random


class CollectionRetrieveView(RetrieveAPIView):
    """
    Get a Collection instance with pk=id
    permissions: authenticated and enabled
    methods accepted: GET
    endpoint format: /api/v1/collections/:id/
    URL parameters:
    - id*: A unique integer value identifying this collection.

    Expected status code: HTTP_200_OK
    Expected Response: The serialized Collection instance with pk=id.
    """
    permission_classes = (IsAuthenticatedAndEnabled,)
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    serializer_class = CollectionVideoSerializer
    queryset = Collection.objects.all()


class DiscoveryView(APIView):
    """
    Get trending hashtags, Users, Collections and Recommended Videos.
    permissions: any
    methods accepted: GET
    endpoint format: /api/v1/discovery/
    Request Body: N/A
    Expected status code: HTTP_200_OK
    Expected Response: The serialized featured Video (if editorial recommendation),
    the list of serialized Collections, top 5 trending Hashtags, top 5 trending Users

    """
    permission_classes = ()

    def get(self, request):
        recommended = EditorialRecommendation.objects.last()
        video = recommended.featured_video if recommended and not recommended.featured_video.owner.disabled else None
        collections = Collection.objects.all()
        trending = None
        try:
            trending = Trending.objects.latest('created')
            tags = trending.hashtags.filter()[:5]
            users = trending.profiles.filter(is_active=True, disabled=False). \
                        exclude(is_staff=True, pk=request.user.pk)[:5]
        except Trending.DoesNotExist:
            pass
        if trending is None or len(tags) == 0 or len(users) == 0:
            # Fallback
            tags = Hashtag.objects.filter()[:5]
            users = User.objects.filter(is_active=True, disabled=False). \
                        exclude(is_staff=True, pk=request.user.pk)[:5]

        data = {
            'featured': VideoSerializer(video, context={'request': request}).data if video else None,
            'collections': CollectionSerializer(collections, many=True, context={'request': request}).data,
            'hashtags': HashtagSerializer(tags, many=True).data,
            'trending': PublicUserSerializer(users, many=True, context={'request': request}).data
        }

        return Response(data)


class HomepageContentView(APIView):
    """
    Get featured videos and profiles.
    permissions: any
    methods accepted: GET
    endpoint format: /api/v1/homepagecontent/
    Request Body: N/A
    Expected status code: HTTP_200_OK
    Expected Response: The serialized Video instances and User instances that will
    be featured on the home page
    """
    permission_classes = ()

    def get(self, request):
        # Return a valid structure even if there is no data.

        data = {
            'featured_videos': [],
            'featured_profiles': []
        }

        try:
            content = HomepageContent.objects.latest('created')
            data['featured_videos'] = VideoSerializer(content.videos.filter()[:5], many=True,
                                                      context={'request': request}).data
            data['featured_profiles'] = PublicUserSerializer(content.profiles.filter()[:5], many=True,
                                                             context={'request': request}).data
        except HomepageContent.DoesNotExist:
            pass

        return Response(data)
