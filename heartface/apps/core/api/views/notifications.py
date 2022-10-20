import logging

from django.http import Http404
from rest_framework import mixins
from rest_framework import viewsets
from rest_framework.pagination import CursorPagination

from heartface.apps.core.models import Notification, Device
from heartface.apps.core.api.serializers.notification import NotificationSerializer, DeviceSerializer
from heartface.apps.core.permissions import IsAuthenticatedAndEnabled

logger = logging.getLogger(__name__)


class TimestampCursorPagination(CursorPagination):
    ordering = '-timestamp'


class NotificationViewSet(viewsets.ModelViewSet):
    """
    Methods supported: GET, POST, PUT, PATCH, DELETE
    NOTE: this is a demo/test class and for this reason it allows creation and deletion
    retrieve:
        Get specific Notification instance
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/notifications/:id/
        URL parameters:
        - id*: The pk of the Notification object to be retrieved
        Expected status code: HTTP_200_OK
        Expected Response: The serialized Notification instance with pk=id

    list:
        List of Notification instances
        permissions: authenticated and enabled
        methods accepted: GET
        endpoint format: /api/v1/notifications/
        Request Body: N/A
        Expected status code: HTTP_200_OK
        Expected Response: A list of serialized Notification instances

    create:
        Create a new Notification instance
        permissions: authenticated and enabled
        methods accepted: POST
        endpoint format: /api/v1/notifications/
        Request Body:
        - type: Choice field, Type of notification
        - read: Boolean field
        Expected status code: HTTP_201_CREATED
        Expected Response: The serialized data of the newly created Notification instance

    delete:
        Delete specific Notification instance
        permissions: authenticated and enabled
        methods accepted: DELETE
        endpoint format: /api/v1/notifications/:id/
        URL parameters:
        - id*: The pk of the Notification object to be deleted
        Expected status code: HTTP_204_NO_CONTENT
        Expected Response: N/A

    partial_update:
        Update one or more fields of an existing Notification instance
        permissions: authenticated and enabled
        methods accepted: PATCH
        endpoint format: /api/v1/notifications/:id/
        URL parameters:
        - id*: The pk of the Notification object to be updated
        Request Body:
        - type: Choice field, Type of notification
        - read: Boolean field
        Expected status code: HTTP_200_OK
        Expected Response: The serialized data of updated Notification instance

    update:
        Update a Notification instance.
        permissions: authenticated and enabled
        methods accepted: PUT
        endpoint format: /api/v1/notifications/:id/
        URL parameters:
        - id*: The pk of the Notification object to be updated.
        Request Body:
        - type: Choice field, Type of notification
        - read: Boolean field
        Expected status code: HTTP_200_OK
        Expected Response: The serialized data of updated Notification instance
    """
    serializer_class = NotificationSerializer
    queryset = Notification.objects.all()
    permission_classes = (IsAuthenticatedAndEnabled,)
    pagination_class = TimestampCursorPagination

    def get_queryset(self):
        user = self.request.user
        return user.notifications.all()


class RegisterDeviceViewSet(mixins.CreateModelMixin, mixins.UpdateModelMixin, mixins.DestroyModelMixin,
                            viewsets.GenericViewSet):
    """
    Methods supported: POST, PUT, PATCH, DELETE

    create:
        Register a new Device
        permissions: authenticated and enabled
        methods accepted: POST
        endpoint format: /api/v1/notifications/register/
        Request Body:
        - type: Choice field, Type of Device. (android / ios)
        - player_id: Unique UUID value
        Expected status code: HTTP_201_CREATED
        Expected Response: The serialized data of the newly created Register Device with User instances

    delete:
        Delete an existing Device register instance
        permissions: authenticated and enabled
        methods accepted: DELETE
        endpoint format: /api/v1/notifications/register/:id/
        URL parameters:
        - id*: The pk of the Register Device object to be deleted
        Expected status code: HTTP_204_NO_CONTENT
        Expected Response: N/A

    partial_update:
        Update one or more fields of an existing Register device instance
        permissions: authenticated and enabled
        methods accepted: PATCH
        endpoint format: /api/v1/notifications/register/:id/
        URL parameters:
        - id*: The pk of the Register Device object to be updated
        Request Body:
        - type: Choice field, Type of Device. (android / ios)
        - player_id: Unique UUID value
        Expected status code: HTTP_200_OK
        Expected Response: The serialized data of updated Register Device instance

    update:
        Update a Register device instance     
        permissions: authenticated and enabled
        methods accepted: PUT
        endpoint format: /api/v1/notifications/register/:id/
        URL parameters:
        - id*: The pk of the Register Device object to be updated
        Request Body:
        - type: Choice field, Type of Device. (android / ios)
        - player_id: Unique UUID value
        Expected status code: HTTP_200_OK
        Expected Response: The serialized data of updated Register Device instance
    """
    serializer_class = DeviceSerializer
    queryset = Device.objects.all()
    permission_classes = (IsAuthenticatedAndEnabled,)

    def get_object(self):
        player_id = self.request.data['player_id']
        devices = Device.objects.filter(player_id=player_id)
        if devices and (devices[0].user == self.request.user or self.request.method == 'POST'):
            return devices[0]
        raise Http404

    def create(self, request, *args, **kwargs):
        # because we are doing POST to REST create is called
        # but we want give user possibility to change accouns on same devices
        try:
            device = self.get_object()
            # registering this as error as it is unusual activity in app and we must log such actions
            logger.error('Device %r already registered for %r, replacing it with %r', device, device.user, request.user)
            return super().update(request, *args, **kwargs)
        except Http404:
            return super().create(request, *args, **kwargs)

    def delete(self, request, *args, **kwargs):
        return self.destroy(request, *args, **kwargs)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    def perform_update(self, serializer):
        serializer.save(user=self.request.user)
