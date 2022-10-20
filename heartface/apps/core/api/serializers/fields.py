#!/usr/bin/env python
# coding=utf-8
from rest_framework import serializers


class HumanChoiceField(serializers.ChoiceField):
    """
    If `choices` is model_utils Choices then this field
    we cause DRF to render human-readable choice like 'iOS',
    and write from the literal, like 'ios'
    """
    def __init__(self, choices, **kwargs):
        self._modelutil_choices = choices
        super(HumanChoiceField, self).__init__(choices, **kwargs)

    def to_representation(self, value):
        if value in ('', None):
            return value
        return self._modelutil_choices[value]

    def to_internal_value(self, data):
        if data == '' and self.allow_blank:
            return ''
        try:
            return getattr(self._modelutil_choices, data)
        except AttributeError:
            self.fail('invalid_choice', input=data)
