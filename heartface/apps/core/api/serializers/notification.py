#!/usr/bin/env python
# coding=utf-8
from rest_framework import serializers

from heartface.apps.core.api.serializers.accounts import PublicUserSerializer
from heartface.apps.core.api.serializers.discovery import VideoSerializer
from heartface.apps.core.models import Notification, User, Device

from .fields import HumanChoiceField


class NotificationSerializer(serializers.ModelSerializer):
    sender = PublicUserSerializer(read_only=True)
    video = VideoSerializer(read_only=True)

    class Meta:
        model = Notification
        fields = ['sender', 'video',
                  'type',
                  'message', 'read', 'timestamp', 'id', 'url']
        read_only_fields = ['notification_type', 'message', 'timestamp', 'id']


class DeviceSerializer(serializers.ModelSerializer):
    user = PublicUserSerializer(read_only=True)
    player_id = serializers.UUIDField(validators=[])
    type = HumanChoiceField(choices=Device.TYPES)

    class Meta:
        model = Device
        fields = ['player_id', 'type', 'user']


class TestSerializer(serializers.ModelSerializer):
    notifications = NotificationSerializer(many=True)

    class Meta:
        model = User
        fields = ['notifications', 'email']
