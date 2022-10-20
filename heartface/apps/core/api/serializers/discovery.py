#!/usr/bin/env python
# coding=utf-8
from urllib.parse import urljoin


from django.core.paginator import Paginator
from django.conf import settings
from rest_framework import serializers
from rest_framework.fields import ReadOnlyField, DateTimeField

from heartface.apps.core.api.serializers.accounts import PublicUserSerializer
from heartface.apps.core.api.serializers.products import ProductSerializer
from heartface.apps.core.models import Hashtag, Video, Collection, ReportedVideo, Comment, Like

from .accounts import CustomElasticModelSerializer
from heartface.apps.core.search_indexes import HashtagIndex, VideoIndex


class HashtagSerializer(CustomElasticModelSerializer):
    class Meta:
        es_model = HashtagIndex
        model = Hashtag
        fields = ['name']


# class VideoSerializer(serializers.HyperlinkedModelSerializer):
class VideoSerializer(CustomElasticModelSerializer):
    hashtags = HashtagSerializer(many=True, read_only=True)
    products = ProductSerializer(many=True, read_only=True)
    owner = PublicUserSerializer(read_only=True)
    # NOTE: we would want this to be published, not created but at the moment is doesn't work with our pagination code
    # timestamp = DateTimeField(source='published', read_only=True)
    timestamp = DateTimeField(source='created', read_only=True)
    videofile = serializers.SerializerMethodField(method_name='get_videofile_url')
    cover_picture = serializers.SerializerMethodField(method_name='get_cover_picture_url')
    publish = serializers.BooleanField(write_only=True)

    # If the request.user in some view has liked this video
    liked = serializers.BooleanField(required=False, read_only=True)

    class Meta:
        model = Video
        es_model = VideoIndex
        fields = [
            'id',
            'url',
            'title',
            'description',
            'view_count',
            'videofile',
            'cover_picture',
            'owner',
            'likes',
            'products',
            'hashtags',
            'publish',
            'published',
            'timestamp',
            'liked'
        ]

    def to_representation(self, obj):
        """
        If request.user is following the video owner
        Set `is_followed` on obj.owner so PublicUserSerializer will render it
        Use `annotate` or `with_liked_and_following` in the View to add `follwing_owner` to Videos in queryset.
        """
        if hasattr(obj, 'following_owner'):
            obj.owner.is_followed = obj.following_owner
        return super().to_representation(obj)

    def get_videofile_url(self, obj: Video):
        if obj.published:
            return obj.videofile_cdn_url
        else:
            url = obj.videofile.url
            request = self.context.get('request', None)
            if request is not None:
                return request.build_absolute_uri(url)
            return url

    def get_cover_picture_url(self, obj: Video):
        if obj.published:
            return obj.cover_picture_cdn_url
        else:
            # We don't generate a cover picture locally
            return None
            # request = self.context.get('request', None)
            # return request.build_absolute_uri(obj.cover_picture) if request is not None else obj.cover_picture


class CollectionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Collection
        fields = [
            'id',
            'name',
            'cover_photo',
        ]


class CollectionVideoSerializer(serializers.ModelSerializer):
    videos = VideoSerializer(read_only=True, many=True)

    class Meta:
        model = Collection
        fields = [
            'id',
            'name',
            'cover_photo',
            'videos',
        ]


class ReportedVideoSerializer(serializers.HyperlinkedModelSerializer):
    video = VideoSerializer(read_only=True)

    class Meta:
        model = ReportedVideo
        fields = [
            'video',
            'reviewed'
        ]


class CommentSerializer(serializers.HyperlinkedModelSerializer):
    video = VideoSerializer(read_only=True, allow_null=False)
    author = PublicUserSerializer(read_only=True)
    timestamp = DateTimeField(source='created', read_only=True)

    class Meta:
        model = Comment
        fields = [
            'id',
            'video',
            'author',
            'text',
            'created',
            'timestamp'
        ]

        read_only_fields = ['created']


class LikeSerializer(serializers.HyperlinkedModelSerializer):
    video = VideoSerializer(read_only=True, allow_null=False)
    user = PublicUserSerializer(read_only=True)
    timestamp = DateTimeField(source='created', read_only=True)

    class Meta:
        model = Like
        fields = [
            'id',
            'user',
            'video',
            'created',
            'timestamp'
        ]


class PaginatedSerializer():
    def __init__(self, res, request, num):

        paginator = Paginator(res, num)
        page = request.POST.get('page', 1)
        try:
            p_res = paginator.page(page)
            res = res[num*(page-1):num]
        except Exception:
            pass
        count = paginator.count
        previous = None if not p_res.has_previous() else p_res.previous_page_number()
        next = None if not p_res.has_next() else p_res.next_page_number()

        self.data = {'count': count, 'previous': previous, 'next': next, 'results': res}
