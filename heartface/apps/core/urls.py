import analytics
from django.conf.urls import url
from django.urls import include
from django.conf import settings


analytics.debug = True  # turn on debug logging
analytics.write_key = settings.SEGMENT_WRITE_KEY


# from . import api.urls
from . import api
# import heartface.apps.core.api.urls

urlpatterns = [
    # NOTE: Temporary solution. We'll need to collect the API urls (through a unified router) in a separate app to
    # provide a unified top level url for the whole API (that will probably span across multiple apps)
    url('^api/v1/', include(api.urls))
]
