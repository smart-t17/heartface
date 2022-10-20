#!/usr/bin/env python
# coding=utf-8
from django.apps import apps
from django_nose import NoseTestSuiteRunner


class TestRunner(NoseTestSuiteRunner):
    def setup_databases(self):
        result = super().setup_databases()

        for app_config in apps.get_app_configs():
            if hasattr(app_config, 'test_ready'):
                app_config.test_ready()

        return result
