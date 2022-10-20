#!/usr/bin/env python
# coding=utf-8
import datetime
import json

from django.utils import timezone


class Clock(object):
    DEFAULT_TICK_LENGTH = datetime.timedelta(seconds=1)

    def __init__(self, start_at=None, tick_length=datetime.timedelta(0)):
        if start_at is None:
            start_at = timezone.now()
        elif isinstance(start_at, datetime.timedelta):
            start_at += timezone.now()

        self.time = start_at
        self.length = tick_length or self.DEFAULT_TICK_LENGTH

    def tick(self, length=datetime.timedelta(0)):
        self.time += length or self.length

        return self.time

def ps(response):
    try:
        return json.dumps(json.loads(response.content), indent=4)
    except:
        return response.content

def pp(response):
    print(ps(response))
