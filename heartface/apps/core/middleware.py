#!/usr/bin/env python
# coding=utf-8
from django.conf import settings


class VersionInfoMiddleware(object):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        response['HEARTFACE-VERSION'] = '%s %s' % (settings.VERSION, settings.VERSION_TIMESTAMP.isoformat())

        return response
