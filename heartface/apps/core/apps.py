#!/usr/bin/env python
# coding=utf-8

import logging
import analytics

from django.apps import AppConfig
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import ProgrammingError
from django.conf import settings
from django.db.models.signals import post_save

import stripe
from django.http.request import validate_host

logger = logging.getLogger(__name__)

class CoreAppConfig(AppConfig):
    name = 'heartface.apps.core'
    verbose_name = 'Heartface Core'

    def ready(self):
        # Segement
        analytics.write_key = settings.SEGMENT_WRITE_KEY

        if settings.STRIPE_LIVE_MODE:
            stripe.api_key = settings.STRIPE_LIVE_SECRET_KEY
        else:
            stripe.api_key = settings.STRIPE_TEST_SECRET_KEY

        self.configure_sites()
        self.configure_social_apps()
        self.init_suppliers()

        from . import signals

    def test_ready(self):
        self.ready()


    def init_suppliers(self):
        from .models import Supplier

        try:
            for supplier_name in settings.SUPPLIERS:
                Supplier.objects.get_or_create(name=supplier_name)
        except Exception:
            logger.error('Creating Supplier objects failed (migrations have not been run yet, probably)')


    def configure_sites(self):
        """
        Setup sites settings in the db. (Sites is conceptually flawed, but needed for allauth.)
        """

        try:
            from django.contrib.sites.models import Site
            if validate_host(settings.SITE_CONFIG['domain'], settings.ALLOWED_HOSTS):
                Site.objects.update_or_create(pk=settings.SITE_ID, defaults=settings.SITE_CONFIG)
            else:
                raise ImproperlyConfigured('Specified domain "%s" is not in ALLOWED_HOSTS' % settings.SITE_CONFIG['domain'])
        except ProgrammingError:
            # We haven't run the migrations yet
            pass


    def configure_social_apps(self):
        """
        Update or create SocialApp settings in the db from the settings file. (Allauth suggests doing it from the
        admin app, but that would make automated deployments to multiple environments impossible. Think
        dev/testing/staging/production.)
        """
        try:
            from allauth.socialaccount.models import SocialApp
            # from allauth.socialaccount import providers

            for provider, social_config in settings.SOCIAL_APPS.items():
                social_config['name'] = provider
                # print(social_config)
                social_app, _ = SocialApp.objects.update_or_create(provider=provider, defaults=social_config)
                # print(_, social_app.provider, social_app.name, social_config)
                social_app.sites.add(settings.SITE_ID)
        except ProgrammingError:
            # We haven't run the migrations yet
            pass
