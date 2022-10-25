# -*- coding: utf-8 -*-

# Scrapy settings for crawlers project
#
# For simplicity, this file contains only settings considered important or
# commonly used. You can find more settings consulting the documentation:
#
#     https://doc.scrapy.org/en/latest/topics/settings.html
#     https://doc.scrapy.org/en/latest/topics/downloader-middleware.html
#     https://doc.scrapy.org/en/latest/topics/spider-middleware.html

BOT_NAME = 'crawlers'

SPIDER_MODULES = ['crawlers.spiders']
NEWSPIDER_MODULE = 'crawlers.spiders'


# Crawl responsibly by identifying yourself (and your website) on the user-agent
#USER_AGENT = 'crawlers (+http://www.yourdomain.com)'

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Configure maximum concurrent requests performed by Scrapy (default: 16)
#CONCURRENT_REQUESTS = 32

# Configure a delay for requests for the same website (default: 0)
# See https://doc.scrapy.org/en/latest/topics/settings.html#download-delay
# See also autothrottle settings and docs
DOWNLOAD_DELAY = 0.5
# The download delay setting will honor only one of:
#CONCURRENT_REQUESTS_PER_DOMAIN = 16
#CONCURRENT_REQUESTS_PER_IP = 16

# Disable cookies (enabled by default)
COOKIES_ENABLED = False

# Disable Telnet Console (enabled by default)
#TELNETCONSOLE_ENABLED = False

# Override the default request headers:
DEFAULT_REQUEST_HEADERS = {
    'dnt': '1',
    'accept-encoding': 'gzip, deflate, br',
    'accept-language': 'en-US,en;q=0.9,ru;q=0.8,fi;q=0.7',
    'x-requested-with': 'XMLHttpRequest',
    'jwt-authorization': 'false',
    'appos': 'web',
    'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36',
    'appversion': '0.1',
    'accept': '*/*',
}

# Enable or disable spider middlewares
# See https://doc.scrapy.org/en/latest/topics/spider-middleware.html
#SPIDER_MIDDLEWARES = {
#    'crawlers.middlewares.CrawlersSpiderMiddleware': 543,
#}

# Enable or disable downloader middlewares
# See https://doc.scrapy.org/en/latest/topics/downloader-middleware.html
DOWNLOADER_MIDDLEWARES = {
    'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
    'scrapy_fake_useragent.middleware.RandomUserAgentMiddleware': 400,
    # 'crawlers.middlewares.RandomProxy': 749,
    # 'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': 750,
}

# Enable or disable extensions
# See https://doc.scrapy.org/en/latest/topics/extensions.html
EXTENSIONS = {
    # 'scrapy.extensions.telnet.TelnetConsole': None,
    'crawlers.extensions.ErrorStatsMailer': 500,
    'crawlers.extensions.UniqueIDStats': 500,
}

# Who to send scraping alerts to
STATSMAILER_RCPTS = ['urvesh@heartface.io']
# How many items minimum before alert email
STATSMAILER_MIN_ITEMS_SCRAPED = 16000
# How many errors in log before alert email
STATSMAILER_MAX_ERRORS = 1
MAIL_FROM = 'scrapy@heartface.io'
MAIL_HOST = 'smtp.sendgrid.net'
MAIL_PORT = 587
MAIL_USER = 'heartface'
MAIL_PASS = 'AdQ%p(EnTbBz9Fxr'
MAIL_TLS = True


# Configure item pipelines
# See https://doc.scrapy.org/en/latest/topics/item-pipeline.html
ITEM_PIPELINES = {
    'crawlers.pipelines.CeleryQueuePipeline': 300,
    'crawlers.pipelines.DropPipeline': 299,
    'crawlers.pipelines.CustomImagesPipeline': 1,
}


# Enable and configure the AutoThrottle extension (disabled by default)
# See https://doc.scrapy.org/en/latest/topics/autothrottle.html
#AUTOTHROTTLE_ENABLED = True
# The initial download delay
#AUTOTHROTTLE_START_DELAY = 5
# The maximum download delay to be set in case of high latencies
#AUTOTHROTTLE_MAX_DELAY = 60
# The average number of requests Scrapy should be sending in parallel to
# each remote server
#AUTOTHROTTLE_TARGET_CONCURRENCY = 1.0
# Enable showing throttling stats for every response received:
#AUTOTHROTTLE_DEBUG = False

# Enable and configure HTTP caching (disabled by default)
# See https://doc.scrapy.org/en/latest/topics/downloader-middleware.html#httpcache-middleware-settings
#HTTPCACHE_ENABLED = True
#HTTPCACHE_EXPIRATION_SECS = 0
#HTTPCACHE_DIR = 'httpcache'
#HTTPCACHE_IGNORE_HTTP_CODES = []
#HTTPCACHE_STORAGE = 'scrapy.extensions.httpcache.FilesystemCacheStorage'

import os
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# settings for Scraper Image Pipeline
# Should be hfproductstaging for staging
IMAGES_STORE = '<set_per_env>'
# CDN where we store images
BUNNY_CDN_ACCESS_KEY = '31288a41-38bd-4c4c-8ca8632ade40-f0d5-42ce'

# 30 days of delay for images expiration
IMAGES_EXPIRES = 30
#
# IMAGES_THUMBS = {
#     'small': (50, 50),
#     'big': (270, 270),
# }
