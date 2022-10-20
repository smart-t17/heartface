import os
import random
import math

from logging import getLogger

import uuid
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError
from django.db.models import QuerySet, F
from django.utils import timezone
from django.templatetags.static import static

from collections import namedtuple
from itertools import chain
from typing import List

from rest_framework import mixins
from rest_framework import status
from rest_framework import viewsets
from rest_framework.decorators import detail_route, list_route
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.generics import get_object_or_404, ListAPIView
from rest_framework.pagination import CursorPagination
from rest_framework.parsers import MultiPartParser, FileUploadParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.settings import api_settings
from rest_framework.views import APIView

from heartface.apps.core.api.pagination import PaginationMixin

from heartface.apps.core.api.serializers.discovery import *
from heartface.apps.core.api.serializers.feed import FollowSerializer
from heartface.apps.core.api.serializers.products import VideoProductTagRequestSerializer
from heartface.apps.core.models import Comment, Like, User, Product, View, Notification
from heartface.apps.core.models import Follow, DefaultFollowRecommendation
from heartface.apps.core.permissions import IsAuthenticatedAndEnabled, IsOwnerOrReadOnly
from heartface.apps.core.tasks import upload_video
from heartface.libs import notifications
from heartface.libs.utils import sendgrid_send_notification

log = getLogger(__name__)

FeedSerializationInfo = namedtuple('FeedSerializationInfo', ['serializer_class', 'type_name'])


class MergingQuerySetAdapter(object):
    """
    An adapter class providing the necessary interface methods of QuerySet required by CursorPagination to work. It
    merges the results from the provided list of querysets. It's not a generic class, just an adapter and its logic
    is tied to the feed.
    """
    def __init__(self, query_sets: List[QuerySet], sort_key: str):
        self.query_sets = query_sets
        self.reverse = sort_key.startswith('-')
        self.sort_key = sort_key[1:] if self.reverse else sort_key
        self._orig_sort_key = sort_key

    def filter(self, *args, **kwargs):
        return MergingQuerySetAdapter([q.filter(*args, **kwargs) for q in self.query_sets], self._orig_sort_key)

    def order_by(self, *args, **kwargs):
        # print('** New MergingQuerySetAdapter [order_by=%s]' % args)
        return MergingQuerySetAdapter(self.query_sets, *args)

    def __getitem__(self, key):
        """
        This is where the merging/magic happens.
        """
        # We're disregarding the start of the slice (the offset) here, because we don't know which queriset it belongs to
        #  (if it belongs to one and not caused by a collision between multiple ones). We'll apply it later.
        results = list(chain.from_iterable(q[:key.stop] for q in self.query_sets))
        # print('** Sorint by [key=%s, reverse=%s]' % (self.sort_key, self.reverse))
        return list(sorted(results, key=lambda o: getattr(o, self.sort_key), reverse=self.reverse)[key])


class RecommendedFollowsListView(ListAPIView):
    """
    List of  Recommended follower instances
    permissions: authenticated and enabled
    methods accepted: GET
    endpoint format: /api/v1/recommended/follows/
    Request Body: N/A
    Expected status code: HTTP_200_OK
    Expected Response: A list of serialized Recommended follower instances

    """
    permission_classes = (IsAuthenticatedAndEnabled,)
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    serializer_class = PublicUserSerializer

    def get_queryset(self):
        # Get most recent DefaultFollowRecommendation list
        dfr = DefaultFollowRecommendation.objects.latest('created')
        # Users in list ordered by rank
        return dfr.users.order_by('follow_rank_users__rank')


class FeedView(PaginationMixin, APIView):
    """
    Get all Video feeds of the user's followed by Logged in user
    permissions: authenticated and enabled
    methods accepted: GET
    endpoint format: /api/v1/feed/
    Request Body: N/A
    Expected status code: HTTP_200_OK
    Expected Response: A list of serialized Video feed instances of user's followed by Logged in user.
    """
    pagination_class = CursorPagination
    permission_classes = (IsAuthenticatedAndEnabled,)
    # NOTE: this doesn't really work and will be replaced with 'created' by cursor pagination. (Using a non-field
    #  doesn't work, because CursorPagination will have to use a field for filtering as well.)
    sort_key = '-feed_order'
    # sort_key = '-created'

    serialization_info = {
        Video: FeedSerializationInfo(VideoSerializer, 'video'),
        Like: FeedSerializationInfo(LikeSerializer, 'like'),
        Comment: FeedSerializationInfo(CommentSerializer, 'comment'),
        Follow: FeedSerializationInfo(FollowSerializer, 'follow')
    }

    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(MergingQuerySetAdapter(self.get_query_set_list(), self.sort_key)) or []

        data = []

        for item in page:
            info = self.serialization_info[type(item)]
            data.append({'type': info.type_name, 'content': info.serializer_class(item, context={'request': request}).data})

        return self.get_paginated_response(data)

    def get_query_set_list(self):
        following = self.request.user.following.filter(disabled=False)
        return [
            # NOTE: using different fields for ordering doesn't really work while using (an unmodified) CursorPagination.
            Video.objects.filter(
                owner__in=following, owner__disabled=False, published__isnull=False, cdn_available__isnull=False)
            .prefetch_related('owner').with_liked_and_following(self.request.user)\
            .order_by('-published', '-created'),
            Like.objects.filter(user__in=following).order_by('-created'),
            Comment.objects.filter(author__in=following).order_by('-created'),
            # We show in the feed if a user we follow starts following someone (if someone starts following us, that goes
            #  into the notifications)
            Follow.objects.filter(follower__in=following).exclude(follower=self.request.user).order_by('-created')
        ]


class VideoViewSet(viewsets.ModelViewSet):
    """
    Methods supported: GET, POST, PUT, PATCH, DELETE
    retrieve:
        Get specific Video instance
        permissions: authenticated and enabled or owner
        methods accepted: GET
        Method: GET
        endpoint format: /api/v1/videos/:id/
        URL parameters:
        - id*: The pk of the Video object to be retrieved
        Expected status code: HTTP_200_OK
        Expected Response: The serialized Video instance with pk=id

    list:
        List of Video instances
        permissions: authenticated and enabled or owner
        methods accepted: GET
        Method: GET
        endpoint format: /api/v1/videos/
        Request Body: N/A
        Expected status code: HTTP_200_OK
        Expected Response: A list of serialized Video instances

    create:
        Create a new Video instance
        permissions: authenticated and enabled
        methods accepted: POST
        endpoint format: /api/v1/videos/
        Request Body:
        - title: CharField of max_length 255
        - description: Text field
        - view_count: Positive integer field
        - publish*: Boolean field
        - published: Datetime string
        Expected status code: HTTP_201_CREATED
        Expected Response: The serialized data of the newly created Video instance

    delete:
        Delete specific Video instance
        permissions: owner
        methods accepted: DELETE
        endpoint format: /api/v1/videos/:id/
        URL parameters:
        - id*: The pk of the Video object to be deleted
        Expected status code: HTTP_204_NO_CONTENT
        Expected Response: N/A

    partial_update:
        Update one or more fields of an existing Video instance
        permissions: owner
        methods accepted: PATCH
        endpoint format: /api/v1/videos/:id/
        URL parameters:
        - id*: The pk of the Video object to be updated
        Request Body:
        - title: CharField of max_length 255
        - description: Text field
        - view_count: Positive integer field
        - publish*: Boolean field
        - published: Datetime string
        Expected status code: HTTP_200_OK
        Expected Response: The serialized data of updated Video instance

    update:
        Update a Video instance
        permissions: owner
        methods accepted: PUT
        endpoint format: /api/v1/videos/:id/
        URL parameters:
        - id*: The pk of the Video object to be updated
        Request Body:
        - title: CharField of max_length 255
        - description: Text field
        - view_count: Positive integer field
        - publish*: Boolean field
        - published: Datetime string
        Expected status code: HTTP_200_OK
        Expected Response: The serialized data of updated Video instance
    """
    queryset = Video.objects.all()
    serializer_class = VideoSerializer
    permission_classes = (IsOwnerOrReadOnly, )

    def get_queryset(self):
        if not self.request.user.is_anonymous:
            return Video.objects.filter(owner__disabled=False).with_liked_and_following(self.request.user).order_by('-published', '-created')
        return Video.objects.filter(owner__disabled=False).order_by('-published', '-created')

    def filter_queryset(self, queryset: QuerySet):
        hashtag = self.request.query_params.get('hashtag', None)

        return queryset.filter(hashtags__name=hashtag) if hashtag else queryset

    @detail_route(methods=['POST'], permission_classes=[AllowAny])
    def report(self, request, pk=None):
        """
        Api to report a video
        permissions: any
        methods accepted: POST
        endpoint format: /api/v1/videos/:id/report/
        URL parameters:
        - id*: The pk of the Video object
        Request Body:
        - title: CharField of max_length 255
        - description: Text field
        - view_count: Positive integer field
        - publish*: Boolean field
        - published: Datetime string
        Expected status code: HTTP_201_CREATED
        Expected Response: Empty data
        """
        video = self.get_object()

        if video is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        user = None if isinstance(request.user, AnonymousUser) else request.user
        try:
            if user is None:
                # for anonymous users create a new entry every time
                ReportedVideo.objects.create(video=video)
                created = True
            else:
                # for registered users allow only single report per video
                created = ReportedVideo.objects.get_or_create(video=video, reporting_user=user)[1]
        except (ValidationError, IntegrityError):
            # Something went wrong - log exception and return 500.
            log.error('Unable to submit report for video: %s', pk, exc_info=True)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # if new report return 201 CREATED, otherwise 200
        if created:
            return Response(data={}, status=status.HTTP_201_CREATED)
        return Response(data={}, status=status.HTTP_200_OK)

    @detail_route(methods=['POST', ], permission_classes=[AllowAny])
    def views(self, request, pk=None):
        """
        Create Views to Video, Views count
        permissions: authenticated and enabled
        methods accepted: POST
        endpoint format: /api/v1/videos/:id/views/
        URL parameters:
        - id*: The pk of the Video object
        Expected status code: HTTP_201_CREATED
        Expected Response: Empty data
        """
        user = request.user
        video = self.get_object()
        if request.method == 'POST':
            user = None if isinstance(request.user, AnonymousUser) else request.user
            try:
                if user is None:
                    # For anon user, just create the view as new entry
                    View.objects.create(video=video)
                    created = True
                else:
                    created = View.objects.get_or_create(video=video, user=user)[1]
                # Possibly now not needed:
            except (ValidationError, IntegrityError):
                # Something went wrong - log exception and return 500.
                log.error('Unable to submit view for video: %s', pk, exc_info=True)
                return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            if created:
                Video.objects.filter(pk=video.pk).update(view_count=F('view_count')+1)
                return Response(data={}, status=status.HTTP_201_CREATED)
            return Response(data={}, status=status.HTTP_200_OK)

    @detail_route(methods=['POST', 'DELETE'], permission_classes=[IsAuthenticatedAndEnabled])
    def like(self, request, pk=None):
        """
        API to Like / Dislike Videos
        permissions: authenticated and enabled
        endpoint format: /api/v1/videos/:id/like/
        URL parameters:
        - id*: The pk of the Video object

        create:
            methods accepted: POST
            Expected status code: HTTP_201_CREATED
            Expected Response: Empty data

        delete:
            methods accepted: DELETE
            Expected status code: HTTP_204_NO_CONTENT
            Expected Response: Empty data
        """
        user = request.user
        video = self.get_object()
        if request.method == 'POST':
            # Note that in recent Djangos get_or_create handles integrity error
            # and should not be race condn prob
            like, created = Like.objects.get_or_create(video=video, user=user)
            if created and user != video.owner:
                # Notify if not like of own video
                notifications.send(Notification.TYPES.new_like, self.request.user, video.owner, video_id=video.pk)
                # Check if video.owner has unsubscribed from sendgrid like
                # notifications and send email if not
                if hasattr(user, 'photo') and user.photo:
                    photo_url = user.photo.url
                else:
                    photo_url = static(settings.DEFAULT_USER_AVATAR)
                photo_absolute_url = request.build_absolute_uri(photo_url)
                dynamic_template_data = {"subject": "User {} has liked your video {}".format(user.full_name, video.title),
                                         "photo": photo_absolute_url,
                                         "video_cover": video.cover_picture_cdn_url if video.cdn_available else '',
                                         "liked_name": video.owner.full_name,
                                         "liker_name": user.full_name,
                                         "video_title": video.title}
                sendgrid_send_notification(video.owner.email, settings.SENDGRID_VIDEO_LIKES_TEMPLATE_ID,
                                           dynamic_template_data, settings.SENDGRID_VIDEO_LIKE_UNSUB_GROUP_ID)
            return Response(data={}, status=status.HTTP_201_CREATED)

        if request.method == 'DELETE':
            try:
                like = Like.objects.get(video=video, user=user)
                like.delete()
                return Response(data={}, status=status.HTTP_200_OK)
            except Like.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)

    @detail_route(methods=['PUT'], parser_classes=[MultiPartParser, FileUploadParser], url_path='upload',
                  url_name='update-upload')
    def update_upload(self, request, pk=None):
        """
        Update a video instance
        permissions: owner
        methods accepted: PUT
        endpoint format: /api/v1/videos/:id/upload/
        URL parameters:
        - id*: The pk of the Video object
        Request Body:
        - title: CharField of max_length 255
        - description: Text field
        - view_count: Positive integer field
        - publish*: Boolean field
        - published: Datetime string
        Expected status code: HTTP_200_OK
        Expected Response: Empty data
        """
        video = self.get_object()
        video.videofile = request.data.get('file') or request.data.get('files')[0]
        video.cdn_available = timezone.now()
        video.save()
        if video.published is not None:
            # Only upload if video was published earlier
            upload_video.delay(video.pk)

        return Response(status=status.HTTP_200_OK)

    @list_route(methods=['GET'], url_path='pushr-status')
    def pushr_status(self, request):
        """
        Pushr CDN will ping this hook with the query parameters of filename and status
        as soon as we have up uploaded a video to them that has begun transcoding
        every N minutes.

        In the event of a transcoding error they would also add the query parameter
        error with a description of what went wrong.

        This endpoint is for pushr use only
        """
        errors = []
        filename = request.GET.get('filename')
        status = request.GET.get('status')
        error = request.GET.get('error')

        if not filename:
            errors.append('missing ?filename parameter in URL')
        if not status and not error:
            errors.append('missing ?status or ?error parameters in URL')

        if errors:
            log.error("Pushr got wrong request: %s", errors)
            return Response(status=400, content_type='application/json', data={'errors': errors})

        filename = filename[0]
        if error:
            status = 'error'
            description = error[0]
        else:
            description = ''
            status = status[0]

        try:
            # 'videos/%s' % filename because in db we store them relative to Upload
            video = Video.objects.get(videofile='videos/%s' % filename)
        except Video.DoesNotExist:
            log.error("Unable to find video for file %s", filename)
            return Response(status=404, data={})

        video.cdn_status.create(status=status, description=description, filename=filename)

        return Response(status=200, data={})

    @list_route(methods=['POST'])
    def upload(self, request):
        """
        Create a video instance by uploading a new video file
        permissions: owner
        methods accepted: POST
        endpoint format: /upload/
        Request Body:
        - title: CharField of max_length 255
        - description: Text field
        - view_count: Positive integer field
        - publish*: Boolean field
        - published: Datetime string
        Expected status code: HTTP_201_CREATED
        Expected Response: The serialized data of created Video instance
        """

        filename = request.data['file.path']
        file_ext = os.path.splitext(request.data['file.name'])[1]

        # add video.pk and created timestamp to make video filename unique on CDN
        # add extension to file to be aware what type of file was uploaded
        new_filename = '%s%s' % (uuid.uuid4(), file_ext)
        new_filename = os.path.join(settings.MEDIA_ROOT, 'videos', new_filename)
        os.rename(filename, new_filename)

        path = os.path.relpath(new_filename, settings.MEDIA_ROOT)
        video = Video.objects.create(owner=request.user, videofile=path)
        return Response(self.get_serializer(video).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        # should be removed after WEB-32 is merged
        video = serializer.save()
        if 'publish' in serializer.validated_data:
            Video.publish(video)

    @detail_route(methods=['POST'])
    def publish(self, request):
        """
        Publish a video instance
        permissions: owner
        methods accepted: POST
        URL parameters:
        - id*: The pk of the Video object
        endpoint format: /api/v1/videos/:id/publish/
        Request Body:
        - title: CharField of max_length 255
        - description: Text field
        - view_count: Positive integer field
        - publish*: Boolean field
        - published: Datetime string
        Expected status code: HTTP_201_CREATED
        Expected Response: Empty data
        """
        Video.publish(self.get_object())

    @list_route(permission_classes=[IsAuthenticatedAndEnabled])
    def pending(self, request):
        """Return videos which aren't uploaded to CDN yet by current user"""
        videos = Video.objects.filter(published__isnull=False, cdn_available__isnull=True, owner=request.user) \
            .order_by('-published')
        return Response(self.get_serializer(videos, many=True).data)

    @detail_route(methods=['POST', 'DELETE'], permission_classes=[IsAuthenticatedAndEnabled])
    def products(self, request, pk=None):
        """
        API to Add / Remove a product from a video
        endpoint format: /api/v1/videos/:id/products/
        permissions: authenticated and enabled
        URL parameters:
        - id*: The pk of the Video object

        create:
            methods accepted: POST
            Expected status code: HTTP_201_CREATED
            Expected Response: The serialized Product instance tagged to Video

        delete:
            methods accepted: DELETE
            Expected status code: HTTP_204_NO_CONTENT
            Expected Response: Empty data
        """
        if request.method in ['POST', 'DELETE']:
            serializer = VideoProductTagRequestSerializer(data=request.data)

            if not serializer.is_valid():
                raise ValidationError(serializer.errors)

            try:
                product = Product.objects.get(pk=serializer.validated_data['id'])
            except Product.DoesNotExist:
                raise NotFound(detail="Product with id %s does not exist." % serializer.validated_data['id'])

            video = self.get_object()

            if request.method == 'POST':
                video.products.add(product)
                if product.status == Product.STATUSES.scraped:
                    product.status = Product.STATUSES.queued
                    product.save()
                return Response(ProductSerializer(product, context=self.get_serializer_context()).data, status=status.HTTP_201_CREATED)
            else:
                video.products.remove(product)
                return Response(status=status.HTTP_200_OK)


class BaseListVideoView(ListAPIView):
    permission_classes = ()
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    serializer_class = VideoSerializer


class LikedVideosListView(BaseListVideoView):
    """
    Get Video instances that user with id `user_id` has liked
    permissions: any
    methods accepted: GET
    endpoint format: /api/v1/users/:user_id/likes/
    URL parameters:
    - user_id*: A unique integer value to identify user
    Expected status code: HTTP_200_OK
    Expected Response: A list of serialized Video instances that user with id `user_id` has liked
    """
    def get_queryset(self):
        """
        Videos that user with id `user_id` has liked
        """
        user_id = self.kwargs['user_id']
        if user_id == 'me':
            user_id = self.request.user.id
        return Video.objects.filter(like__user__id=user_id, owner__disabled=False)


class RecommendedVideosListView(BaseListVideoView):
    """
    Get list of recommended Video instances
    permissions: any
    methods accepted: GET
    endpoint format: /api/v1/recommended/
    Request Body: N/A
    Expected status code: HTTP_200_OK
    Expected Response: A list of serialized recommended Video instances
    """
    def get_queryset(self):
        """
        Videos that user with id `user_id` has liked
        """
        # Make sure whatever that the videos are published, cdn available with active owner
        base_qs = Video.objects.filter(owner__disabled=False, published__isnull=False, cdn_available__isnull=False)

        videos = []  # Final set to return
        VIDEO_SET_SIZE = 5  # How many videos should be in final set

        # Get unseen admin recommended videos as first preference
        recommended_videos = base_qs.filter(recommended=True).exclude(view__user=self.request.user)
        sample_size = min(VIDEO_SET_SIZE, len(recommended_videos))
        videos = random.sample(list(recommended_videos), sample_size)
        missing_count = VIDEO_SET_SIZE - len(videos)

        if missing_count > 0:
            # Need to augment videos set from other sources
            unseen_videos = list(base_qs.exclude(pk__in=recommended_videos)\
                                 .exclude(view__user=self.request.user).order_by('-view_count'))
            # Get top 10%, 10-20%, 20-30% videos from user unseen
            top_10_pc_cutoff = math.ceil(0.1 * len(unseen_videos))
            top_20_pc_cutoff = math.ceil(0.2 * len(unseen_videos))
            top_30_pc_cutoff = math.ceil(0.3 * len(unseen_videos))
            top_10_pc_videos = unseen_videos[:top_10_pc_cutoff]
            top_20_pc_videos = unseen_videos[top_10_pc_cutoff: top_20_pc_cutoff]
            top_30_pc_videos = unseen_videos[top_20_pc_cutoff: top_30_pc_cutoff]
            # Try to take `missing_count` random videos from top 10
            sample_size = min(missing_count, len(top_10_pc_videos))
            videos.extend(random.sample(top_10_pc_videos, sample_size))
            # Update missing count
            missing_count = VIDEO_SET_SIZE - len(videos)
            if missing_count > 0:
                # Try to take `missing_count` videos from top 20
                sample_size = min(missing_count, len(top_20_pc_videos))
                videos.extend(random.sample(top_20_pc_videos, sample_size))
                missing_count = VIDEO_SET_SIZE - len(videos)
                if missing_count > 0:
                    # Try to take `missing_count` videos from top 30
                    sample_size = min(missing_count, len(top_30_pc_videos))
                    videos.extend(random.sample(top_30_pc_videos, sample_size))

        # If still missing some, just augment with random already seen rec vids
        missing_count = VIDEO_SET_SIZE - len(videos)
        if missing_count > 0:
            extra_recommended_videos = recommended_videos.exclude(pk__in=[video.pk for video in videos])
            sample_size = min(missing_count, len(extra_recommended_videos))
            videos.extend(random.sample(list(extra_recommended_videos), sample_size))


        # Convert these back to queryset
        qs = Video.objects.filter(pk__in=[video.id for video in videos])
        if not self.request.user.is_anonymous:
            qs = qs.with_liked_and_following(self.request.user)
        return qs.order_by('-view_count')


class HashtagViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    API to handle Hashtags
    endpoint format: /api/v1/hashtags/
    permissions: authenticated and enabled

    create:
        Create a new Hashtag instance
        methods accepted: POST
        Request Body:
        - name*: CharField of max_length 100.
        Expected status code: HTTP_201_CREATED
        Expected Response: The serialized data of the newly created Hashtag instance

    retrieve:
        Get a specific Hashtag instance.
        methods accepted: GET
        endpoint format: /api/v1/hashtags/:id/
        URL parameters:
        - id*: The pk of the Hashtag object to be retrieved
        Expected status code: HTTP_200_OK
        Expected Response: The serialized Hashtag instance with pk=id
    """
    queryset = Hashtag.objects.all()
    serializer_class = HashtagSerializer
    permission_classes = (IsAuthenticatedAndEnabled,)


class CommentViewSet(mixins.CreateModelMixin, mixins.ListModelMixin, mixins.RetrieveModelMixin,
                     viewsets.GenericViewSet):
    """
    API to handle Comments on Video.
    permissions: authenticated and enabled
    endpoint format: /api/v1/videos/:id/comments/

    create:
        Add a new comment to video
        methods accepted: POST
        Request Body:
        - text*: Text field to add comment.
        Expected status code: HTTP_201_CREATED
        Expected Response: The serialized data of created Comment instance

    retrieve:
        Get a comment on video
        methods accepted: GET
        endpoint format: /api/v1/videos/:id/comments/:id/
        URL parameters:
        - id*: The pk of the Comment object to be retrieved
        Expected status code: HTTP_200_OK
        Expected Response: The serialized Comment instance with pk=id
    """
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = (IsAuthenticatedAndEnabled,)
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS

    def get_queryset(self):
        return Comment.objects.filter(video__id=self.kwargs['id'])

    def perform_create(self, serializer):
        video = get_object_or_404(Video, pk=self.kwargs['id'])
        comment = serializer.save(author=self.request.user, video=video)
        if self.request.user != video.owner:
            # Only notify if the comment not on own video
            notifications.send(Notification.TYPES.new_comment, self.request.user,
                               video.owner, video_id=video.pk)
            # Check if video.owner has unsubscribed from sendgrid comment notifications
            # and send email if not
            user = self.request.user
            if hasattr(user, 'photo') and user.photo:
                photo_url = user.photo.url
            else:
                photo_url = static(settings.DEFAULT_USER_AVATAR)
            photo_absolute_url = self.request.build_absolute_uri(photo_url)
            dynamic_template_data = {"subject": "User {} has commented on your video {}".format(user.full_name, video.title),
                                     "photo": photo_absolute_url,
                                     "video_cover": video.cover_picture_cdn_url if video.cdn_available else '',
                                     "comment_text": comment.text,
                                     "commented_name": video.owner.full_name,
                                     "commentor_name": user.full_name,
                                     "video_title": video.title}
            sendgrid_send_notification(video.owner.email, settings.SENDGRID_VIDEO_COMMENT_TEMPLATE_ID,
                                       dynamic_template_data, settings.SENDGRID_VIDEO_COMMENT_UNSUB_GROUP_ID)


class UserVideosViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Get videos that user with id `user_id` uploaded
    permissions: any
    methods accepted: GET
    endpoint format: /api/v1/users/:id/videos/
    URL parameters:
    - id*: The pk of the User object
    Expected status code: HTTP_200_OK
    Expected Response: A list of serialized Video instances that user with id `user_id` uploaded
    """
    queryset = Video.objects.all()
    serializer_class = VideoSerializer
    permission_classes = ()

    def get_queryset(self):
        if User.objects.filter(pk=self.kwargs['id']).exists():
            return Video.objects.filter(owner__id=self.kwargs['id'], owner__disabled=False,
                                        published__isnull=False, cdn_available__isnull=False).order_by('-published', '-created')
        else:
            raise NotFound(detail='User not found')
