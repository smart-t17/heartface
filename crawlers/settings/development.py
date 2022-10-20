"""
Development settings.
"""
from .base import *


# Don't store images to CDN
ITEM_PIPELINES = {
    'crawlers.pipelines.CeleryQueuePipeline': 300,
    'crawlers.pipelines.DropPipeline': 299,
}
