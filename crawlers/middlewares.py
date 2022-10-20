# -*- coding: utf-8 -*-

# Define here the models for your spider middleware
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/spider-middleware.html
import base64
import random

from django.db.models import F
from scrapy import signals

from twisted.internet import defer
from twisted.web.client import ResponseFailed
from twisted.internet.error import TimeoutError, \
    ConnectionRefusedError, ConnectionDone, ConnectError, \
    ConnectionLost, TCPTimedOutError


# Django setup
import django
import os
import sys
DJANGO_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../')
sys.path.insert(0, DJANGO_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", 'heartface.settings')
django.setup()
from heartface.apps.core.models import Proxy


class ProxyPoolExhausted(Exception):
        pass


class RandomProxy(object):
    PROXY_FAIL_EXCEPTIONS = (defer.TimeoutError, TimeoutError,
                             ConnectionRefusedError, ConnectionDone, ConnectError,
                             ConnectionLost, TCPTimedOutError, ResponseFailed,
                             )

    def __init__(self, crawler):
        # How many fails before a proxy is blacklisted?
        self.max_fails = crawler.settings.get('PROXY_MAX_FAILS', 5)
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        mw = cls(crawler)
        crawler.signals.connect(mw.spider_opened, signal=signals.spider_opened)
        return mw

    def spider_opened(self, spider):
        """
        Ensure the proxies have their fail counts reset
        """
        Proxy.objects.update(fail_count=0)

    def process_request(self, request, spider):
        """
        The HttpProxyMiddleware uses the meta key "proxy" to determine
        which proxy to direct requests through, we simply choose a proxy
        from our database at random then set that meta key for it to use.
        Along with the 'Proxy-Authorization' header

        We select only proxies that have no failed more than max times

        Args:
            self --- The middleware class instance
            request --- The Scrapy http Request instance being processed
            spider --- The Scrapy spider instance
        """
        # Get the pool excluding failed proxies
        alive_proxies = Proxy.objects.exclude(fail_count__gte=self.max_fails)
        if(len(alive_proxies) > 0):
            # Pick a proxy from the available pool
            proxy_choice = random.choice(alive_proxies)
            request.meta['proxy'] = '{}:{}'.format(proxy_choice.ip_address, proxy_choice.port)
            if proxy_choice.username and proxy_choice.password:
                proxy_user_pass = '{}:{}'.format(proxy_choice.username, proxy_choice.password)
                basic_auth = b'Basic ' + base64.b64encode(proxy_user_pass.encode('utf8'))
                request.headers['Proxy-Authorization'] = basic_auth
            spider.logger.debug('Using proxy {} when getting URL {}'.format(proxy_choice.ip_address, request.url))
        else:
            # The custom retry middleware should catch this and then try the request
            raise ProxyPoolExhausted('Proxy pool is exhausted...')

    def process_exception(self, request, exception, spider):
        """
        Errback

        If the pool is exhausted kill the crawl

        If the exception is one that we deem to be a potential proxy failure, then
        increment the fail count of the proxy in the db
        """
        if type(exception) == ProxyPoolExhausted:
            spider.logger.error('Killing crawl as all proxies exhausted...')
            self.crawler.stop()
            return None

        if isinstance(exception, self.PROXY_FAIL_EXCEPTIONS):
            # Record a fail
            proxy = request.meta.get('proxy', "")
            ip_address = proxy.split(':')[0]
            Proxy.objects.filter(ip_address=ip_address).update(fail_count=F('fail_count') + 1)
