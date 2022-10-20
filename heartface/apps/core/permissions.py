#!/usr/bin/env python
# coding=utf-8
from rest_framework import permissions
from rest_framework.permissions import BasePermission


class SelfOrReadOnly(BasePermission):
    def has_object_permission(self, request, view, user):
        return request.method in permissions.SAFE_METHODS or user == request.user


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return request.method in permissions.SAFE_METHODS or obj.owner == request.user


class IsAuthenticatedAndEnabled(permissions.IsAuthenticated):
    """
    Permission to only allow users who are not disabled
    """
    def has_permission(self, request, view):
        return super(IsAuthenticatedAndEnabled, self).has_permission(request, view) and not request.user.disabled


class IsAuthenticatedAndMaybeDisabled(permissions.IsAuthenticated):
    """
    Permission to only allow users who are authenticated but may be disabled or enabled
    """
    pass
