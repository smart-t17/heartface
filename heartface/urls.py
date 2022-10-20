""" Default urlconf for heartface """
from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin

from heartface.apps.auth.views import LoginView


from rest_framework_swagger.views import get_swagger_view
schema_view = get_swagger_view(title='Heartface API')


admin.autodiscover()

import heartface.apps.core.urls
import heartface.apps.auth.urls


def bad(request):
    """ Simulates a server error """
    1 / 0

urlpatterns = [
    url(r'^', include(heartface.apps.core.urls)),
    url(r'^payments/', include('djstripe.urls', namespace="djstripe")),
    url(r'^admin/', admin.site.urls),
    url(r'^accounts/', include('allauth.urls')),
    url(r'^rest-auth/login/$', LoginView.as_view(), name='rest_login'),
    url(r'^rest-auth/', include('rest_auth.urls')),
    url(r'^rest-auth/registration/', include('rest_auth.registration.urls')),
    url(r'^rest-auth/', include(heartface.apps.auth.urls)),
    url(r'^docs/$', schema_view, name='swagger_docs'),
]

admin.site.site_header = 'Heartface TV (revision %s @ %s)' % (settings.VERSION, settings.VERSION_TIMESTAMP.isoformat())
