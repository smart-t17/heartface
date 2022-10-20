#!/usr/bin/env python
# coding=utf-8

from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from rest_auth.registration.views import SocialLoginView
from .serializers import CustomSocialLoginSerializer
from rest_framework.reverse import reverse
from django.conf import settings
from django.views.generic import TemplateView
from rest_framework.authentication import TokenAuthentication
from rest_auth import registration


class ConfirmEmailRedirectView(TemplateView):
    template_name = "auth/confirm_email.html"
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super().get_context_data(**kwargs)
        # Add in a QuerySet of all the books
        if self.request.user_agent.os.family == 'iOS':
            context['redirect_link'] = settings.EMAIL_CONFIRM_REDIRECT['ios']
        elif self.request.user_agent.os.family == 'Android':
            context['redirect_link'] = settings.EMAIL_CONFIRM_REDIRECT['android']
        else:
            context['redirect_link'] = reverse(settings.EMAIL_CONFIRM_REDIRECT['desktop'])
        return context


class FacebookLoginView(SocialLoginView):
    adapter_class = FacebookOAuth2Adapter
    client_class = OAuth2Client
    serializer_class = CustomSocialLoginSerializer


class LoginView(registration.views.LoginView):
    authentication_classes = (TokenAuthentication,)
