#!/usr/bin/env python
# coding=utf-8
from heartface.apps.core.apps import stripe
from django.conf import settings
from django.db.models.signals import post_save
from heartface.libs.utils import sendgrid_send_notification
from django.db.models import Exists, OuterRef
from django.dispatch import receiver
from django.templatetags.static import static
from djstripe.models import Customer
from rest_framework import status
from rest_framework import viewsets, mixins
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
from rest_framework.views import APIView
from rest_framework.decorators import detail_route
from rest_framework.settings import api_settings

from allauth.account.utils import send_email_confirmation
from allauth.account.models import EmailAddress
from heartface.apps.core.models import User, Video, Follow, Notification
from heartface.apps.core.permissions import SelfOrReadOnly, IsAuthenticatedAndEnabled, IsAuthenticatedAndMaybeDisabled
from heartface.apps.core.api.serializers.accounts import *
from heartface.libs import notifications


class UserViewSet(mixins.CreateModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):

    """
    Methods supported: GET, POST, PUT, PATCH, DELETE
    retrieve:
        Get specific User instance
        permissions: any
        methods accepted: GET
        endpoint format: /api/v1/users/:id/
        URL parameters:
        - id*: The pk of the User object to be retrieved
        Request Body: N/A
        Expected status code: HTTP_200_OK
        Expected Response: Serialized User instance with pk=id

    destroy:
        Delete specific User instance
        permissions: authenticated and enabled or owner
        methods accepted: DELETE
        endpoint format: /api/v1/users/:id/
        URL parameters:
        - id*: The pk of the User object to be deleted
        Request Body: N/A
        Expected status code: HTTP_204_NO_CONTENT
        Expected Response: Empty data

    create:
        Create a new User instance
        permissions: authenticated and enabled
        methods accepted: POST
        endpoint format: /api/v1/users/
        URL parameters: N/A
        Request Body:
        - password*: Char field
        - email*: A unique and valid email id
        - username*: Char field of max length 30
        - full_name*: Char field of max length 60
        - description: Text field
        - gender*: Choice field (options: male, female, others)
        - address*: Char field of max length 255
        - phone*: Char field of max length 255
        Expected status code: HTTP_201_CREATED
        Expected Response: The serialized data of the newly created User instance

    partial_update:
        Update one or more fields of an existing User instance
        permissions: authenticated, enabled and owner
        methods accepted: PATCH
        endpoint format: /api/v1/users/:id/
        URL parameters:
        - id: The pk of the User object to be updated
        Request Body:
        - password*: Char field
        - email*: A unique and valid email id
        - username*: Char field of max length 30
        - full_name*: Char field of max length 60
        - description: Text field
        - gender*: Choice field (options: male, female, others)
        - address*: Char field of max length 255
        - phone*: Char field of max length 255
        Expected status code: HTTP_200_OK
        Expected Response: The serialized data of the updated instance

    update:
        Update an existing User instance
        permissions: authenticated, enabled and owner
        methods accepted: PUT
        endpoint format: /api/v1/users/:id/
        URL parameters:
        - id: The pk of the User object to be updated
        Request Body:
        - password*: Char field
        - email*: A unique and valid email id
        - username*: Char field of max length 30
        - full_name*: Char field of max length 60
        - description: Text field
        - gender*: Choice field (options: male, female, others)
        - address*: Char field of max length 255
        - phone*: Char field of max length 255
        Expected status code: HTTP_200_OK
        Expected Response: The serialized data of the updated instance
    """
    # /users/me/ refers to the current user
    SELF_LOOKUP_VALUE = 'me'
    permission_classes = (IsAuthenticatedAndEnabled, SelfOrReadOnly)
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def initialize_request(self, request, *args, **kwargs):
        """
        'Rewrite' /users/me/ urls to /users/x/ where x is the user id of the current logged in user. We can't do it
        in dispatch, unfortunately, where it would make the most sense, because authentication happens only after we
        call the inherited dispatch method.
        """
        drf_request = super().initialize_request(request, *args, **kwargs)

        # NOTE: this is somewhat fragile as it assumes that self.kwargs has already been populated. (We have to work
        #  with that instead of kwargs because kwargs is just a copy, a different instance.)
        if self.lookup_field in self.kwargs and self.kwargs[self.lookup_field] == self.SELF_LOOKUP_VALUE:
            self.kwargs[self.lookup_field] = str(drf_request.user.id)

        return drf_request

    @detail_route(methods=['POST'], permission_classes=(IsAuthenticatedAndMaybeDisabled, SelfOrReadOnly))
    def resend_email(self, request, pk=None):
        """
        Send email to User with pk=id
        permissions: authenticated, but may be disabled or enabled
        methods accepted: POST
        endpoint format: /api/v1/users/:id/resend_email/
        URL parameters:
        - id*: The pk of the User object
        Request Body: N/A
        Expected status code: HTTP_202_ACCEPTED or HTTP_409_CONFLICT or HTTP_403_FORBIDDEN
        Expected Response: Empty data
        """
        user = self.get_object()
        if not EmailAddress.objects.filter(user=user, email=user.email,
                                           verified=True).exists():
            send_email_confirmation(request, user)
            return Response(status=status.HTTP_202_ACCEPTED, data={})
        return Response(status=status.HTTP_409_CONFLICT, data={})

    @detail_route(methods=['GET'], permission_classes=())
    def following(self, request, pk=None):
        """
        Return list of users following by the logged in user
        permissions: any
        methods accepted: GET
        endpoint format: /api/v1/users/{id}/following/
        URL parameters:
        - id*:  A unique integer value to identify user.
        Request Body: N/A
        Expected status code: HTTP_200_OK
        Expected Response: A list of serialized User instances that the User with pk=id is following
        """
        user = self.get_object()
        following_qs = user.following.filter(disabled=False)
        if request.user.is_authenticated:
            # Annotate with `is_followed`. True if the request user is following the specific user in the QuerySet
            following_qs = following_qs.annotate(is_followed=Exists(Follow.objects.filter(followed=OuterRef('pk'),
                                                                                          follower=request.user)))
        return Response(PublicUserSerializer(following_qs, many=True, context={'request': request}).data)

    @detail_route(methods=['GET'])
    def stripe_key(self, request, pk=None):
        """
        Create stripe key with customer as logged in user for user with id
        permissions: any
        methods accepted: POST
        endpoint format: /api/v1/users/:id/stripe_key/
        URL parameters:
        - id*:  A unique integer value to identify user.
        Request Body: N/A
        Expected status code: HTTP_200_OK
        Expected Response: The Stripe key (EphemeralKey) instance
        """
        customer = Customer.objects.get_or_create(subscriber=self.request.user)
        key = stripe.EphemeralKey.create(customer=customer[0].stripe_id, api_version="2017-05-25")
        return Response(status=status.HTTP_200_OK, data=key)

    @detail_route(methods=['GET', 'POST', 'DELETE'], permission_classes=(IsAuthenticatedAndEnabled,))
    def followers(self, request, pk=None):
        """
        Api to follow, unfollow a user and list all followers
        methods accepted: GET, POST, DELETE
        endpoint format: /api/v1/users/:id/followers/
        URL parameters:
        - id*:  A unique integer value to identify user

        retrieve:
            permissions: any
            Expected status code: HTTP_200_OK
            Expected Response: The serialized list of followers of user
        create:
            Add request.user as follower of user with pk=id
            permissions: authenticated and enabled
            Request Body: N/A
            Expected status code: HTTP_201_CREATED or HTTP_400_BAD_REQUEST
            Expected Response: The serialized user instance with request.user as follower of user with pk=id
        destroy:
            Removes request.user from followers of user with pk=id
            permissions: authenticated and enabled
            Expected status code: HTTP_204_NO_CONTENT or HTTP_200_OK
            Expected Response: Empty data
        """
        user = self.get_object()
        current_user = self.request.user

        # import ipdb;
        # ipdb.set_trace()
        if request.method == 'POST':
            if user != current_user:
                user.add_follower(current_user)
                notifications.send(Notification.TYPES.new_follower, current_user, user)
                # Send the notification using template if user hasnt
                # unsubscribed to follow notifications
                if hasattr(current_user, 'photo') and current_user.photo:
                    photo_url = current_user.photo.url
                else:
                    photo_url = static(settings.DEFAULT_USER_AVATAR)
                photo_absolute_url = request.build_absolute_uri(photo_url)
                dynamic_template_data = {"subject": "User {} has followed you".format(current_user.full_name),
                                         "photo": photo_absolute_url,
                                         "followed_name": user.full_name,
                                         "follower_name": current_user.full_name}
                sendgrid_send_notification(user.email, settings.SENDGRID_FOLLOW_TEMPLATE_ID,
                                           dynamic_template_data, settings.SENDGRID_FOLLOW_UNSUB_GROUP_ID)
                return Response(status=status.HTTP_201_CREATED, data={})

            return Response(status=status.HTTP_400_BAD_REQUEST, data={'detail': "You can't follow yourself."})
        elif request.method == 'DELETE':
            self.get_object().remove_follower(current_user)
            return Response(status=status.HTTP_200_OK, data={})

        return Response(PublicUserSerializer(user.followers.all(), many=True, context={'request': request}).data)

    @detail_route(methods=['POST'], permission_classes=(IsAuthenticatedAndMaybeDisabled, SelfOrReadOnly))
    def enabled(self, request, pk=None):
        """
        Api to enable a User with pk=id
        permissions: authenticated, but may be disabled or enabled
        methods accepted: POST
        endpoint format: /api/v1/users/:id/enabled/
        URL parameters:
        - id*:  A unique integer value to identify user
        Request Body: N/A
        Expected status code: HTTP_201_CREATED
        Expected Response: The serialized data of enabled User instance
        """
        user = self.get_object()
        user.disabled = False
        user.save()
        return Response(status=status.HTTP_200_OK, data={})

    def perform_update(self, serializer):
        old_email = serializer.instance.email
        super().perform_create(serializer)
        if 'email' in serializer.validated_data and serializer.validated_data['email'] != old_email:
            if not serializer.instance.emailaddress_set.filter(email=serializer.validated_data['email'], verified=True).exists():
                self.request.user.refresh_from_db()
                send_email_confirmation(self.request, self.request.user)

    @receiver(post_save, sender=User, dispatch_uid="create_customer")
    def create_customer(sender, instance, **kwargs):
        Customer.get_or_create(subscriber=instance)

    def get_serializer_class(self):
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field
        if lookup_url_kwarg in self.kwargs and self.get_object() == self.request.user:
            return self.serializer_class
        else:
            return PublicUserSerializer

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action == 'retrieve' or (self.action == 'followers' and self.request.method in permissions.SAFE_METHODS):
            permission_classes = []
        else:
            permission_classes = self.permission_classes
        return [permission() for permission in permission_classes]


class FollowerView(ListAPIView):
    """
    Get all followers of Logged in user.
    permissions: authenticated and enabled
    methods accepted: GET
    endpoint format: /api/v1/followers/
    Expected status code: HTTP_200_OK
    Expected Response: A List of serialized User instances that the request.user is followed by and who are enabled
    """
    serializer_class = PublicUserSerializer
    permission_classes = (IsAuthenticatedAndEnabled,)

    def get_queryset(self):
        return self.request.user.followers.filter(disabled=False)


class FollowingView(ListAPIView):
    """
    Get all users followed by Logged in user.
    permissions: authenticated and enabled
    methods accepted: GET
    endpoint format: /api/v1/following/
    Expected status code: HTTP_200_OK
    Expected Response: A list of serialized User instances that the request.user is following and who are enabled
    """
    serializer_class = PublicUserSerializer
    permission_classes = (IsAuthenticatedAndEnabled,)

    def get_queryset(self):
        return self.request.user.following.filter(disabled=False)


class FollowingIDView(ListAPIView):
    """
    Return IDs of all users that user with id `user_id` is following.
    permissions: authenticated and enabled
    methods accepted: GET
    endpoint format: /api/v1/users/me/following/ids/
    Expected status code: HTTP_200_OK
    Expected Response: A List of id's of all user's that the logged in user is following.
    N.B Can paginate with limit and offset with ?limit=<limit>&offset=<offset>
    """
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    page_size = 300
    permission_classes = (IsAuthenticatedAndEnabled, SelfOrReadOnly)
    serializer_class = GenericIDSerializer.for_model(User)

    def get_queryset(self):
        return User.objects.filter(followers=self.request.user).exclude(disabled=True).values('id')


class LikedVideosIDView(ListAPIView):
    """
    Return IDs of all videos that user has liked
    permissions: authenticated and enabled
    methods accepted: GET
    endpoint format: /api/v1/users/me/likes/ids/
    Expected status code: HTTP_200_OK
    Expected Response: A List of id's of Video instances that the user has liked
    N.B Can paginate with limit and offset with ?limit=<limit>&offset=<offset>
    """
    pagination_class = api_settings.DEFAULT_PAGINATION_CLASS
    page_size = 300
    permission_classes = (IsAuthenticatedAndEnabled, SelfOrReadOnly)
    serializer_class = GenericIDSerializer.for_model(Video)

    def get_queryset(self):
        return Video.objects.filter(like__user=self.request.user).exclude(owner__disabled=True).values('id')


class UsernameAvailableView(APIView):

    permission_classes = []

    def get(self, request, username):
        """
        Checks if a username is available
        permissions: any
        methods accepted: GET
        endpoint format: /api/v1/users/
        URL parameters:
        - username*:  String value `username` to identify user.
        Expected status code: HTTP_200_OK or HTTP_404_NOT_FOUND
        Expected Response:  if the username is exists 200 response with empty data, else if already
                            taken 404 not found with empty data
        """
        if User.objects.filter(username=username).exists():
            return Response(status=status.HTTP_200_OK, data={})
        return Response(status=status.HTTP_404_NOT_FOUND, data={})
