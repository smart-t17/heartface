#!/usr/bin/env python
# coding=utf-8
from allauth.account.views import ConfirmEmailView
from django.conf.urls import url

from heartface.apps.auth.views import FacebookLoginView, ConfirmEmailRedirectView

urlpatterns = [
    url('^facebook/$', FacebookLoginView.as_view(), name='fb_login'),
    # url(r'^/account-confirm-email/(?P<key>.+)/$',
    #     AccountConfirmEmailView.as_view(), name='account_confirm_email'),
    url(r'^account-confirm-email/(?P<key>[-:\w]+)/$', ConfirmEmailView.as_view(), name='account_confirm_email'),
    url(r'^account-confirm-email-redirect/$', ConfirmEmailRedirectView.as_view(), name="account_confirm_email_redirect")
]
