#!/usr/bin/env python
# coding=utf-8

# https://stackoverflow.com/questions/31483282/django-rest-framework-combining-routers-from-different-apps
from django.conf.urls import url
from django.urls import include
from rest_framework.routers import SimpleRouter, DefaultRouter

from heartface.apps.core.api.views.feed import *
from heartface.apps.core.api.views.search import SearchAPIView
from heartface.apps.core.api.views.discovery import DiscoveryView, CollectionRetrieveView, HomepageContentView
from heartface.apps.core.api.views.products import ProductViewSet, OrdersViewSet, SupplierProductViewSet, \
    SupplierViewSet, MissingProductViewSet
from heartface.apps.core.api.views.notifications import NotificationViewSet, RegisterDeviceViewSet
from heartface.apps.core.api.views.accounts import UserViewSet, FollowerView, \
    FollowingView, FollowingIDView, LikedVideosIDView, UsernameAvailableView

# router = SimpleRouter()
router = DefaultRouter()
router.register('users', UserViewSet)
router.register('notifications/register', RegisterDeviceViewSet)
router.register('notifications', NotificationViewSet)
router.register('videos', VideoViewSet)
router.register('products', ProductViewSet)
router.register('supplier-products', SupplierProductViewSet)
router.register('supplier', SupplierViewSet)
router.register('hashtags', HashtagViewSet)
router.register('videos/(?P<id>\w+)/comments', CommentViewSet)
router.register('users/(?P<id>\w+)/videos', UserVideosViewSet)
router.register('orders', OrdersViewSet)
router.register('missing-products', MissingProductViewSet)

urlpatterns = [
    url('', include(router.urls)),
    url(r'^followers/$', FollowerView.as_view()),
    url(r'^following/$', FollowingView.as_view()),
    url(r'^users/me/following/ids/$', FollowingIDView.as_view()),
    url(r'^users/me/likes/ids/$', LikedVideosIDView.as_view()),
    url(r'^users/usernames/(?P<username>\w+)/$', UsernameAvailableView.as_view()),
    url(r'^discovery/$', DiscoveryView.as_view()),
    url(r'^homepagecontent/$', HomepageContentView.as_view()),
    url(r'^feed/$', FeedView.as_view()),
    url(r'^recommended/follows/$', RecommendedFollowsListView.as_view()),
    url(r'^recommended/$', RecommendedVideosListView.as_view()),
    url(r'^users/(?P<user_id>\w+)/likes/$', LikedVideosListView.as_view()),
    url(r'^collections/(?P<pk>\w+)/$', CollectionRetrieveView.as_view()),
    url(r'^search/$', SearchAPIView.as_view()),
    url(r'^payments/', include('djstripe.urls', namespace="djstripe")),
]
