#!/usr/bin/env python
# coding=utf-8
from django.utils.functional import Promise
from elasticsearch import JSONSerializer


class CustomJSONSerializer(JSONSerializer):
    def default(self, data):
        if isinstance(data, Promise):
            return str(data)
        else:
            return super().default(data)
