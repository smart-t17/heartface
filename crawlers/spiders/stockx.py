# -*- coding: utf-8 -*-
import scrapy
import json
from datetime import datetime, timedelta
from itertools import count


# relative imports so works from cmdline and celery
from ..loaders import ProductLoader
from ..items import ProductItem

URL_DATE_TEMPLATE = "https://stockx.com/api/browse?productCategory=sneakers&releaseTime=range({}|{})"
URL_CAT_TEMPLATE = "https://stockx.com/api/browse?_tags={}&productCategory=sneakers&currency=GBP"


class StockxSpider(scrapy.Spider):
    name = 'stockx'
    stockx_ids = set()
    duplicate_stockx_ids = list()

    # Choosing scraing mode on start..
    def __init__(self, **kwargs):
        if kwargs.get('mode') == 'all':
            self.start_requests = self.crawl_all
        else:
            self.start_requests = self.crawl_last_week

    def parseCategories(self, response):
        # Parse categories
        browse_props = json.loads(response.xpath('//script/text()[contains(., "preLoadedBrowseProps")]').re_first(
            'window.preLoadedBrowseProps = (.*);'))
        categories = [child for child in browse_props['filters']['sneakers']['children']
                      if child['name'] == 'Categories'][0]
        for algolia_query in self.recurse_category(categories):
            yield scrapy.Request(url=URL_CAT_TEMPLATE.format(algolia_query), callback=self.parse)

    def recurse_category(self, category, algolia="", depth=0):
        """
        Recurse over the JSON from which the filter menu brand categories
        are constructed, building up the algolia search query from parent
        to child. Make request only at lowest depth/finest filter
        to best ensure fewer products and guard against shallow pagination
        """
        if algolia:
            algolia = '%s,%s' % (algolia, category['algolia'])
        elif category['algolia'].strip() != '_tags':
            algolia = category['algolia']
        self.logger.debug('{} {}:{}'.format(depth*'\t', category['name'], algolia))
        if category.get('children'):
            results = []
            for subcategory in category.get('children', []):
                results.extend(self.recurse_category(subcategory, algolia=algolia, depth=depth + 1))
            return results
        else:
            # Deepest sub category reached
            # Actual algolia query will be reverse to top-down collection
            algolia = ','.join(algolia.split(',')[::-1])
            self.logger.debug('(Depth {}) Make request for {}'.format(depth, algolia))
            return [algolia]

    # Crawl all the items month-by-month until 2001, and everything before 2001 then..
    def crawl_all(self):
        # Crawl over categories too (since some sneakers have no release dates,
        # so the dates crawl doesn't capture everything. Equally pagination is
        # shallow when trying to parse all 23k products with no filter - only
        # 25 pages max of 40 items)
        yield scrapy.Request(url="https://stockx.com/sneakers", callback=self.parseCategories)

        # Parse dates
        for i in count():
            ts = int((datetime.today() - timedelta(days=30 * i)).timestamp())
            ts_minus_month = int((datetime.today() - timedelta(days=30 * (i + 1))).timestamp())
            if ts > datetime(2001, 1, 1).timestamp():
                yield scrapy.Request(url=URL_DATE_TEMPLATE.format(ts, ts_minus_month), callback=self.parse)
            else:
                yield scrapy.Request(url='https://stockx.com/api/browse?productCategory=sneakers&year=lt-2001', callback=self.parse)
                break

    # Crawl items for the last 7 days..
    def crawl_last_week(self):
        week_ago = int((datetime.now() - timedelta(days=7)).timestamp())
        yield scrapy.Request(url='https://stockx.com/api/browse?productCategory=sneakers&releaseTime=gt-{}'.format(week_ago), callback=self.parse)

    # Parsing API response JSON
    def parse(self, response):
        try:
            data = json.loads(response.body_as_unicode())
        except json.decoder.JSONDecodeError as jexc:
            self.logger.error('JSON decoding error {}. {} Response was {}'.format(jexc, response.url, response.body[:100]))
            return

        next_page_url = data['Pagination'].get('nextPage')
        products = data['Products']
        if next_page_url and products:
            next_page_url = next_page_url.replace('/v3/', '/')
            url = response.urljoin(next_page_url)
            self.logger.debug('Requesting next page %s' % url)
            yield scrapy.Request(url=url, callback=self.parse, dont_filter=True)

        FROM_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
        TO_DATE_FORMAT = "%Y-%m-%d"
        for product in products:
            product_loader = ProductLoader(item=ProductItem())
            product_loader.add_value('name', product.get('title'))
            product_loader.add_value('image_urls', product.get('media', {}).get('imageUrl'))
            product_loader.add_value('stockx_id', product.get('tickerSymbol'))
            release_date = None
            try:
                release_date = datetime.strptime(product.get('releaseDate'),
                                                 FROM_DATE_FORMAT).strftime(TO_DATE_FORMAT)
            except (ValueError, TypeError):
                try:
                    release_date = datetime.fromtimestamp(product.get('releaseTime')).strftime(
                        TO_DATE_FORMAT)
                except (ValueError, TypeError):
                    pass
            product_loader.add_value('release_date', release_date)
            product_loader.add_value('style_code', product.get('styleId'))
            product_loader.add_value('colorway', product.get('colorway'))
            product_loader.add_value('description', '')
            # The images pipeline will populate this
            product_loader.add_value('images', [])
            yield product_loader.load_item()
