# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

import scrapy
import os
import sys
# from collections import defaultdict
from scrapy_djangoitem import DjangoItem

# Django setup
import django
DJANGO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')
sys.path.insert(0, DJANGO_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", 'heartface.settings')
django.setup()
from heartface.apps.core.models import Product


class ProductItem(DjangoItem):
    django_model = Product
    images = scrapy.Field(default=[])
    image_urls = scrapy.Field(default=[])
