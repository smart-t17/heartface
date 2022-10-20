#!/usr/bin/env python
# coding=utf-8
from rest_framework import serializers

from heartface.apps.core.api.serializers.accounts import PublicUserSerializer
from heartface.apps.core.models import Like


class FollowSerializer(serializers.HyperlinkedModelSerializer):
    followed = PublicUserSerializer(read_only=True)
    follower = PublicUserSerializer(read_only=True)
    created = serializers.ReadOnlyField()
    timestamp = serializers.DateTimeField(source='created', read_only=True)

    class Meta:
        model = Like
        fields = [
            'followed',
            'follower',
            'created',
            'timestamp'
        ]
