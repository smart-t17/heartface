#!/usr/bin/env python
# coding=utf-8
import re
import base64
import random
import json
import logging
import requests

from django.utils import timezone
from django.core.files.base import ContentFile
from urllib.parse import urlparse

from retrying import retry

from collections import defaultdict

from django.conf import settings
from heartface.apps.core.models import Proxy

from bs4 import BeautifulSoup

from ebaysdk.shopping import Connection as Shopping

from urllib.parse import unquote

from fake_useragent import UserAgent

logger = logging.getLogger(__name__)

# Used in clean_dec func
DEC_RGX = re.compile(r"\d+(?:\.\d{1,2}){0,}")

MARKETPLACE_SUPPLIERS = ['eBay', 'StockX', ]


class ScrapingException(Exception):
    pass


class UnsupportedSupplierException(Exception):
    pass


def raise_log_exc(exc, msg):
    """
    Raise exception `exc` and log msg `msg`
    """
    logger.error(msg)
    raise exc(msg)


def download_image(url):
    """
    Downloads image
    """
    try:
        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
    except Exception as img_exc:
        raise_log_exc(ScrapingException, str(img_exc))
    # We generate name from UUID anyway but image.save requires name arg
    name = urlparse(url).path.split('/')[-1]
    # TODO: Will this name always work? For Foot Locker image doesn't have
    # suffix like .jpg, and I think that might cause UploadDir an issue
    return name, ContentFile(resp.content)


def get_element(soup, selectors=[], fail_msg='Could not extract data', fail_loudly=True):
    """
    Try alternative selectors until one hits data
    If none hits raise the `fail_msg` if `fail_loudly`
    """
    for sel in selectors:
        try:
            return soup.select_one(sel).getText()
        except Exception:
            continue
    if fail_loudly:
        raise_log_exc(ScrapingException, fail_msg)


def take_first(l):
    '''
    Helper func: Take the first non null element of list
    '''
    for el in l:
        if el is not None:
            return el
    return None


def drop_qs(url):
    """
    Drop the query string component of URL
    """
    return url.split('?', maxsplit=1)[0]


def clean_sizes(lst):
    """
    Helper func: Take a list of strings representing sizes
    and clean them by removing certain words etc
    NB Sizes aren't always numeric, could be S, M, L, XL
    or 0-3years, 3-5years etc
    """
    clean_sizes = []
    drop_words = ['select', 'size (uk)', ]  # If any of these words found in the size, drop it (usually default)
    replace_words = ['low stock', '-', 'in stock', 'out of stock', 'size']  # Replace occurances with ''
    for size in lst:
        if any([word in size.lower() for word in drop_words]):
            continue
        for rword in replace_words:
            size = re.sub(rword, "", size, flags=re.I)
        size = size.strip()
        if size:
            clean_sizes.append(size)
    return clean_sizes


def clean_dec(lst):
    """
    Helper func: Take a list of strings and extract only the numeric
    elements, e.g. cleaning a dropdown list of sizes to list of decs
    """
    # Clean them
    return list(filter(lambda x: x is not None,
                       map(lambda x: take_first(DEC_RGX.findall(x)), lst)))


def ebay_scraper(url):
    """
    Use the eBay Shopping API to get product title/image if User
    tags a product with a URL from eBay
    """
    try:
        shop_api = Shopping(appid=settings.EBAY_APPID, config_file=None)

        # Get the ItemID from URL
        itemID = urlparse(url).path.split('/')[-1]

        shop_response = shop_api.execute('GetSingleItem', {'ItemID': itemID})

        item = shop_response.reply.get('Item')

        # All we need is title and pic
        return {'title': item.get('Title'),
                'primary_image': take_first(item.get('PictureURL')),
                'description': ''}

    except Exception as exc:
        raise_log_exc(ScrapingException, str(exc))


def stockx_scraper(url):

    product_dict = defaultdict(lambda: None)

    try:
        resp = requests.get(url, timeout=3)
        resp.raise_for_status()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))

    # Make Soup
    soup = BeautifulSoup(resp.text, 'html.parser')

    product_dict['title'] = get_element(soup, fail_msg='Missing title on URL %s' % url,
                                        selectors=['h1[class="name"]'])

    # Optional fields
    product_dict['description'] = ' '.join([content for p in soup.select('div[class*="product-description"] p')
                                            for content in p.contents])

    # Images are rendered by React, cheat and just grab first from meta
    try:
        img = soup.select('div[class="image-container"] img')
        if not img:
            img = soup.select('img[class="product-image"]')
        product_dict['primary_image'] = img[0].attrs['src']
    except Exception:
        raise_log_exc(ScrapingException, 'Could not get image on URL %s' % url)

    return product_dict


def update_supplierprod(supplier_product):
    """
    Scrape prices and sizes to update supplier product
    """

    # Determine action by supplier (scraper functions should be named
    # accordingly - Supplier name with white space removed and lowercase
    # followed by _scraper)
    scraper_name = '{}_scraper'.format(supplier_product.supplier.name.replace(' ', '').lower())

    if scraper_name not in globals():
        return

    scraper = globals()[scraper_name]

    # Perform the scrape
    product_dict = scraper(supplier_product.link)

    # Update the SupplierProduct with the scraped prize/sizes
    supplier_product.price = product_dict.get('price')
    supplier_product.sizes = product_dict.get('sizes', [])
    supplier_product.last_scraped = timezone.now()
    logger.debug('Updated supplierprod %s with price %s and sizes %s' % (supplier_product.pk,
                                                                         product_dict.get('price'),
                                                                         product_dict.get('sizes', [])))
    supplier_product.save()
    return supplier_product


def retry_if_non_404(exception):
    """Return True if we should retry (in this case when not 404), False otherwise"""
    has_non_null_response = hasattr(exception, 'response') and exception.response is not None
    return has_non_null_response and exception.response.status_code != 404


@retry(stop_max_attempt_number=3, wait_random_min=1000, wait_random_max=2000, retry_on_exception=retry_if_non_404)
def retry_request(url, headers=None, proxies=None):
    headers = headers or {}
    proxies = proxies or []
    # Random user-agent
    if 'User-Agent' not in headers:
        user_agent = UserAgent(fallback="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_8_2) AppleWebKit/537.17 (KHTML, like Gecko) Chrome/24.0.1309.0 Safari/537.17")
        headers['User-Agent'] = user_agent.random
    # Choose a proxy at random each retry
    if len(proxies) > 0:
        proxy_choice = random.choice(proxies)
        # http://docs.python-requests.org/en/latest/user/advanced/#proxies
        proxies = {schema: '{}://{}:{}'.format(schema, proxy_choice.ip_address,
                                               proxy_choice.port)
                   for schema in ['http', 'https']}
        if proxy_choice.username and proxy_choice.password:
            proxies = {schema: '{}://{}:{}@{}:{}'.format(schema, proxy_choice.username,
                                                         proxy_choice.password, proxy_choice.ip_address,
                                                         proxy_choice.port)
                       for schema in ['http', 'https']}
        logger.debug('Request URL {} with proxy {} and '
                     'user-agent {}'.format(url, proxies['https'], headers['User-Agent']))
        response = requests.get(url, headers=headers, timeout=3, proxies=proxies)
    else:
        logger.debug('Request URL {} without proxy and '
                     ' user-agent {}'.format(url, headers['User-Agent']))
        response = requests.get(url, headers=headers, timeout=3)
    response.raise_for_status()
    return response


class SimpleScraper:

    def __init__(self, url, **kwargs):

        self.headers = {
            'cache-control': 'max-age=0',
            'upgrade-insecure-requests': '1',
            'dnt': '1',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
            'accept-encoding': 'gzip, deflate',
            'accept-language': 'en-US,en;q=0.9,ru;q=0.8,fi;q=0.7',
        }
        if kwargs.get('headers'):
            self.headers.update(kwargs['headers'])
        # Retry a few times
        self.response = retry_request(url, headers=self.headers, proxies=Proxy.objects.all())
        self.soup = BeautifulSoup(self.response.text, 'html.parser')
        self.result = dict(sizes=[], price=None)

    def results(self):
        self.result['sizes'] = sorted(list(set(self.result['sizes'])))
        self.clean_price()
        return self.result

    def clean_price(self):
        price = str(self.result.get('price', '')) or ''
        price = re.sub('[$£€]', '', price).strip()
        price = re.sub('[GBP|USD|EUR]', '', price).strip()
        try:
            price = float(price)
        except ValueError as e:
            if ',' not in price:
                raise e

            price_pattern = '\d+\.\d+,{1}\d*$'  # match for pattern 1.000,00 converts to 1000.00
            if re.match(price_pattern, price):
                price = price.replace('.', '').replace(',', '.')
            else:
                price = price.replace(',', '')
            price = float(price)
        self.result['price'] = price


def offspring_scraper(url):
    try:
        scraper = SimpleScraper(url)
        size_options = scraper.soup.select('#sizeShoe option')
        for size_option in size_options:
            extracted_size = re.findall(r'[\d.]+', size_option.text)
            if extracted_size:
                scraper.result['sizes'].append(float(extracted_size[0]))

        price = float(scraper.soup.select('#now_price')[0]['data-value'])
        scraper.result['price'] = price
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def schuh_scraper(url):
    try:
        scraper = SimpleScraper(url)
        size_options = scraper.soup.select('#sizes option.sizeAvailable')
        for size_option in size_options:
            extracted_size = re.findall(r'[\d.]+', size_option.text)
            if extracted_size:
                scraper.result['sizes'].append(float(extracted_size[0]))

        price_text = scraper.soup.select('#price')[0].text
        price = re.findall(r'[\d.]+', price_text)[0]
        scraper.result['price'] = price
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def footasylum_scraper(url):
    try:
        scraper = SimpleScraper(url)
        pf_id = re.sub('\?.*', '', url)
        pf_id = pf_id.strip('/').rsplit('-')[-1]
        text_data = re.findall(r'variants = ({.+} })', scraper.response.text)[0]
        text_data = text_data.replace('\'', '"')
        json_data = json.loads(text_data)
        for key, item in json_data.items():
            if item['stock_status'] == 'in stock' and item['pf_id'] == pf_id:
                scraper.result['sizes'].append(float(item['option2']))
                if not scraper.result['price']:
                    scraper.result['price'] = item['price'].split(';')[1]
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def nike_scraper(url):
    """
    On demand scraper for Nike store
    url: https://www.nike.com/gb/t/vaporfly-4-flyknit-running-shoe-7R7zSn
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['sizes'] = [i.get('aria-label') for i in scraper.soup.select('div[name="skuAndSize"] input')
                                   if not i.has_attr('disabled')]
        scraper.result['price'] = scraper.soup.select_one('meta[property="og:price:amount"]')['content']
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def vans_scraper(url):
    """
    On demand scraper for Vans store
    url: https://www.vans.com/shop/sk8-hi-grisaille-true-white#hero=0
    """
    product_api = "https://www.vans.com/webapp/wcs/stores/servlet/VFAjaxProductAvailabilityView?" \
                  "productId={}&storeId=10153&langId=-1&requesttype=ajax"
    try:
        scraper = SimpleScraper(url)
        product_id = scraper.soup.select_one('input[name="catEntryId"]')['value']
        scraper.result['price'] = scraper.soup.select('meta[property="og:price:amount"]')[0]['content']
        api_response = retry_request(product_api.format(product_id), headers=scraper.headers, proxies=Proxy.objects.all())
        api_response.raise_for_status()
        in_stock_products = [int(key) for key, value in api_response.json()['stock'].items() if not value == 0]
        scraper.result['sizes'] = [stock['display'] for stock in api_response.json()[
            'attributes']['7000000000000000452'] if stock['catentryId'][0] in in_stock_products]
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def urbanindustry_scraper(url):
    try:
        scraper = SimpleScraper(url)
        price_text = scraper.soup.select('meta[property="og:price:amount"]')[0]['content']
        scraper.result['price'] = price_text
        sizes = [float(x.text.replace('UK', '')) for x in scraper.soup.select('.choices-eh li label') if not x.get('class')]
        scraper.result['sizes'] = sizes
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def timberland_scraper(url):
    try:
        scraper = SimpleScraper(url)
        price = scraper.soup.select('meta[property="og:price:amount"]')[0]['content']
        scraper.result['price'] = price
        product_id = scraper.soup.select('div#product-imgs')[0]['data-product-id']
        text_data = re.findall(r'itemPrices = ({[\d\D]+?});', scraper.response.text)[0]
        data = json.loads(text_data)
        sizes = []
        for size in data[product_id]['pricing']['7000000000000003503'].keys():
            sizes.append(size)
        scraper.result['sizes'] = sizes
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def endclothing_scraper(url):
    try:
        scraper = SimpleScraper(url)
        text_data = re.findall('"spConfig":(.*),', scraper.soup.text)[0]
        data = json.loads(text_data)
        scraper.result['price'] = data['prices']['finalPrice']['amount']
        scraper.result['sizes'] = [item['label'] for item in data['attributes']['173']['options']]
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def reebok_scraper(url):
    try:
        scraper = SimpleScraper(url)
        price = scraper.soup.select('meta[itemprop="price"]')[0]['content']
        scraper.result['price'] = price
        product_id = url.split('.html')[0].split('/')[-1]
        api_url = 'https://www.reebok.co.uk/api/products/{}/availability'.format(product_id)
        api_data = retry_request(api_url, headers=scraper.headers, proxies=Proxy.objects.all()).json()
        scraper.result['sizes'] = [x['size'] for x in api_data['variation_list']]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def adidas_scraper(url):
    """
    On demand scraper for Adidas store - Supports US and UK stores
    url (US): https://www.adidas.com/us/ultraboost-all-terrain-shoes/B37699.html
    url (UK): https://www.adidas.co.uk/ultraboost-all-terrain-shoes/B37699.html
    """
    api_url = 'https://{}/api/products/{}/availability'
    headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:64.0)'
                             ' Gecko/20100101 Firefox/64.0'}
    try:
        scraper = SimpleScraper(url, headers=headers)
        netloc = urlparse(url)[1]
        product_id = scraper.soup.select_one('meta[itemprop="sku"]')['content']
        scraper.result['price'] = scraper.soup.select_one('meta[itemprop="price"]')['content']
        api_data = retry_request(api_url.format(netloc, product_id), headers=headers,
                                 proxies=Proxy.objects.all()).json()
        scraper.result['sizes'] = [item['size'] for item in api_data['variation_list']
                                   if item["availability_status"] == "IN_STOCK"]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def footpatrol_scraper(url):
    try:
        scraper = SimpleScraper(url + '/stock/')
        buttons = scraper.soup.select('div#productSizeStock button')
        scraper.result['price'] = re.findall(r'\d+', buttons[0]['data-price'])[0]
        scraper.result['sizes'] = [re.findall(r'[\d\.]+', x.text.strip())[0] for x in buttons]
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def consortium_scraper(url):
    try:
        scraper = SimpleScraper(url)
        data = json.loads(re.findall(r'ConfigDefaultText\(({.+?})\);', scraper.response.text)[0])
        scraper.result['price'] = data['basePrice']
        scraper.result['sizes'] = [x['label'] for x in data['attributes']['502']['options']]
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def sportsdirect_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select(
            'div.pdpPrice span[id="dnn_ctr103511_ViewTemplate_ctl00_ctl08_lblSellingPrice"]')[0].text[1:]
        scraper.result['sizes'] = [x.text.split()[0] for x in scraper.soup.select('select.SizeDropDown option')[1:]
                                   if 'greyOut' not in x.get('class', [])]
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def footlocker_scraper(url):
    """
    On demand scraper for Footlocker store
    url(US): https://www.footlocker.com/product/Nike-Zoom-LeBron-3---Men-s/2434001.html
    url(UK): https://www.footlocker.co.uk/en/p/nike-air-max-95-men-shoes-330?v=314213525604#!
             searchCategory=men/shoes
    """
    products_api = 'https://www.footlocker.co.uk/INTERSHOP/web/WFS/Footlocker-Footlocker_GB-Site/en_GB/-/GBP/' \
                   'ViewProduct-ProductVariationSelect?BaseSKU={}&InventoryServerity=ProductDetail'
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/71.0.3578.98 Safari/537.36'}
    netloc = urlparse(url).netloc
    price, sizes = 0, []
    try:
        scraper = SimpleScraper(url, headers=headers)
        if '.com' in netloc:
            price = scraper.soup.select_one('div.list span').text
            sizes = [item.text for item in scraper.soup.select(
                'div[class="c-form-field c-form-field--radio custom c-size"]')]
        if '.co.uk' in netloc:
            product_id = re.findall(r'\d{12}', url)[0]
            price = scraper.soup.select_one('meta[itemprop="price"]')['content'].replace(',', '.')
            sizes_data = retry_request(products_api.format(product_id), headers=scraper.headers,
                                       proxies=Proxy.objects.all()).json()['content']
            sizes_soup = BeautifulSoup(sizes_data, 'html.parser')
            sizes = [item.text.strip() for item in sizes_soup.select('div.fl-product-size')[2].select(
                'button[class="fl-product-size--item"]')]
        scraper.result['price'] = price
        scraper.result['sizes'] = sizes
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def kickz_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select('#varPriceId')[0]['value'].split()[-1]
        scraper.result['sizes'] = [x.text for x in scraper.soup.select('a.chooseSizeLink') if 'UK' in x['id']]
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def size_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select('meta[itemprop="price"]')[0]['content']
        scraper.result['sizes'] = [re.findall(r'[\d.]+', x.text)[0] for x in scraper.soup.select('div[id="productSizeStock"] button')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def jdsports_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select('meta[itemprop="price"]')[0]['content']
        buttons = scraper.soup.select('div#productSizeStock button')
        scraper.result['sizes'] = [re.findall(r'[\d\.]+', x.text.strip())[0] for x in buttons]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def spartoo_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select('span.price')[0].text
        scraper.result['sizes'] = [re.findall(r'[\d.]+', x.text)[0] for x in scraper.soup.select('select[name="size"]')[0].select('option') if 'in stock' in x.text]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def kickgame_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select('meta[itemprop="price"]')[0]['content']
        scraper.result['sizes'] = [re.sub(r'\s+', ' ', x.text.strip()) for x in scraper.soup.select('option')[1:]]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def fruugo_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select('meta[itemprop="price"]')[0]['content'][1:]
        scraper.result['sizes'] = [x.text.split()[0] for x in scraper.soup.select('#attribute-Size option')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def aasports_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = re.findall(r'"productPrice":([\d.]+?),', scraper.response.text)[0]
        scraper.result['sizes'] = set(re.findall(r'UK [\d.]+', scraper.response.text))
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def kellersports_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = re.findall(r"value: ([\d.]+), currency: 'GBP'", scraper.response.text)[0]
        scraper.result['sizes'] = [x['data-name'].split(' - ')[0].replace(',', '.') for x in scraper.soup.select('div.sizes div')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def very_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select('meta[property="product:price:amount"]')[0]['content']
        scraper.result['sizes'] = [x['value'] for x in scraper.soup.select('input[name="SIZE"]')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def zalando_scraper(url):
    try:
        scraper = SimpleScraper(url)
        data = json.loads(re.findall(r'CDATA\[([\s\S]+?)\]\]\>', scraper.response.text)[4])
        scraper.result['price'] = data['model']['displayPrice']['price']['value']
        scraper.result['sizes'] = [x['size']['local'] for x in data['model']['articleInfo']['units'] if x['available']]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def urbanoutfitters_scraper(url):
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select('meta[property="product:price:amount"]')[0]['content']
        scraper.result['sizes'] = [x.select('input')[0]['value'] for x in scraper.soup.select('fieldset[class="c-product-sizes__field-set"] li') if 'is-disabled' not in x['class']]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def asos_scraper(url):
    try:
        scraper = SimpleScraper(url)
        data = json.loads(re.findall(r'view\(\'(\{.+?\})\'', scraper.response.text)[0])
        product_id = url.split('/')[-1].split('?')[0]
        stock_data = json.loads(SimpleScraper('https://www.asos.com/api/product/catalogue/v2/stockprice?productIds={}&currency=GBP&store=COM'.format(product_id)).response.text)
        scraper.result['price'] = data['price']['current']
        in_stock = {x['variantId']: x['isInStock'] for x in stock_data[0]['variants']}
        variants = data['variants']
        scraper.result['sizes'] = [x['size'] for x in variants if in_stock[x['variantId']]]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def newbalance_scraper(url):
    try:
        url = unquote(url)
        product_id = url.split('.html')[0].split('/')[-1]
        color = re.findall(r'#color=([a-zA-Z_1-9- ]+)', url)[0]
        scraper = SimpleScraper('https://www.newbalance.co.uk/on/demandware.store/Sites-newbalance_uk2-Site/en_GB/Product-GetVariants?pid={}'.format(product_id))
        data = json.loads(scraper.response.text)
        for key, value in data['attributeValues'].items():
            if value.get('value') == color:
                current_color_code = key
                break
        for variant in data['variants']:
            if variant['attributes']['color'] == current_color_code and variant['availability']['inStock']:
                size = data['attributeValues'][variant['attributes']['size']]['displayValue']
                size = size.split(' / ')[-1]
                scraper.result['sizes'].append(size)

        for key, value in data['priceModels'].items():
            scraper.result['price'] = value['pricing']['salesPrice']
        return scraper.results()

    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def yoox_scraper(url):
    """
    On demand scrapper for yoox store
    url: https://www.yoox.com/uk/11588943CR/item#dept=men&sts=sr_men80&cod10=11588943CR&sizeId=1&sizeName=4
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = re.findall(r'[\d.]+', scraper.soup.select('span[itemprop="price"]')[0].text)[0]
        scraper.result['sizes'] = [re.sub(r'[^\d.]', '', x.text) for x in scraper.soup.select("div#itemSizes li")]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def soldsoles_scraper(url):
    """
    On demand scraper for SoldSoles store
    url: https://soldsoles.co.uk/collections/latest/products/nike-air-max-97-plus-black-shock-orange
    """
    products_api = "https://gapi.beeketing.com/v1/product/products.json?ref_id={}&" \
                   "api_key=4255a426d51453387038af4916eb233d"
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select_one('span[itemprop="price"]')['content']
        ref_id = re.findall('"rid":(\d*)', scraper.response.text)[0]
        api_response = retry_request(products_api.format(ref_id), headers=scraper.headers, proxies=Proxy.objects.all())
        api_response.raise_for_status()
        json_data = api_response.json()[0]['variants']
        for item in json_data:
            if not item['is_out_stock']:
                scraper.result['sizes'].append(float(item['option1'].split(' ')[1]))
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def drome_scraper(url):
    """
    On demand scraper for Drome store
    url: https://www.drome.co.uk/tommy-hilfiger-vulc-flag-trainer-129544/
    """
    try:
        scraper = SimpleScraper(url)
        prod_pfId = scraper.soup.select_one('span[id="prod_pfId"]').getText()
        scraper.result['price'] = scraper.soup.select('span[itemprop="price"]')[0].text
        text_data = re.findall(r'variants : ({".*}})', scraper.response.text)[0]
        text_data = text_data.replace('\'', '"')
        json_data = json.loads(text_data)
        for key, item in json_data.items():
            if item['stock_status'] == 'in stock' and item['pf_id'] == prod_pfId:
                scraper.result['sizes'].append(float(item['option2']))
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def mrporter_scraper(url):
    """
    On demand scraper for MR Porter store
    url: https://www.mrporter.com/en-in/mens/nike_running/epic-react-rubber-trimmed-flyknit-running-sneakers/1127550
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['sizes'] = [re.sub(r'[^A-Z0-9.]+$', '', item.text).split('-')[0] for item in scraper.soup.
            select('option[data-stock]') if 'Sold out' not in item.text]
        scraper.result['price'] = scraper.soup.select_one('span[itemprop="price"]').getText()
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def pacsun_scraper(url):
    """
    On demand scraper for Pacsun store
    url: https://www.pacsun.com/adidas/deerupt-runner-red-blue-shoes-7233554.html
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = re.findall('(\d+\.\d+)', scraper.soup.select_one('div[class="product-price group"]')
                                             .getText())[-1]
        scraper.result['sizes'] = [re.sub(r'[^\d.]', '', item.text) for item in scraper.soup.select(
            'ul[class="rwd-variation-select"] li')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def stevemadden_scraper(url):
    """
    On demand scraper for Stevemadden store
    url: https://www.stevemadden.com/collections/mens-sneakers/products/raving-red?variant=12365733462106
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select_one('meta[property="og:price:amount"]')['content']
        scraper.result['sizes'] = [item.text.strip() for item in scraper.soup.select(
            'div[class="swatch clearfix select_size"] div')[1:] if 'available' in item.get('class')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def toms_scraper(url):
    """
    On demand scraper for Toms store
    url: https://www.toms.com/men/black-space-dye-mens-cabrillo-sneakers
    """
    try:
        scraper = SimpleScraper(url)
        try:
            price = scraper.soup.select_one('span.regPrice').getText()
        except Exception:
            price = scraper.soup.select_one('span.salePrice').getText()
        scraper.result['price'] = price
        scraper.result['sizes'] = [re.sub(r'[^\d.]', '', item.text) for item in scraper.soup.select(
            'li[role="option"] a') if 'Currently out of stock' not in item.text]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def zappos_scraper(url):
    """
    On demand scraper for Zappos.com
    url: https://www.zappos.com/p/nike-air-max-axis-black-anthracite/product/9011448/color/3897
    """
    variants_api = "https://api.zcloudcat.com/v3/productBundle?productId={}&siteId=1"
    try:
        scraper = SimpleScraper(url)
        url_data = re.findall('/(\d+)', url)
        product_id = url_data[0]
        color_id = url_data[1]
        api_response = retry_request(variants_api.format(product_id), headers=scraper.headers,
                                     proxies=Proxy.objects.all())
        api_response.raise_for_status()
        api_response = api_response.json()
        product_data = api_response['product'][0]['styles']
        for item in product_data:
            if item['colorId'] == str(color_id):
                if not scraper.result['price']:
                    scraper.result['price'] = item['price']
                scraper.result['sizes'] = [x['size'] for x in item['stocks']]
                break
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def nordstromrack_scraper(url):
    """
    On demand scraper for Nordstromrack Store
    url: https://www.nordstromrack.com/shop/product/2494081/nike-running-swift-sneaker?color=BLACK%2FWHITE
    """
    try:
        scraper = SimpleScraper(url)
        price = 0
        try:
            price = scraper.soup.select_one('span["class*=pricing-and-style__sale-price"]')
            if price is not None:
                price = price.getText()
            else:
                price = scraper.soup.select_one('meta[property="og:price:amount"]')['content']
        except Exception:
            pass
        scraper.result['price'] = price
        scraper.result['sizes'] = [item.contents[0]['value'] for item in scraper.soup.find_all('label', {'class': [
            'sku-item sku-item--available sku-item--text', 'sku-item sku-item--available sku-item--low-quantity sku'
                                                           '-item--text']})]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def dcshoes_scraper(url):
    """
    On demand scraper for DC Shoes store
    url: https://www.dcshoes.com/manteca-shoes-ADYS100177.html
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select_one('div.salesprice').getText()
        scraper.result['sizes'] = [item.text.strip() for item in scraper.soup.select(
            'li[class="variations-box-variation emptyswatch"]')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def puma_scraper(url):
    """
    On demand scraper for Puma store
    url: https://us.puma.com/en/us/pd/hybrid-rocket-runner-men%E2%80%99s-running-shoes/191592.html
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select_one('div[class="prices col-12 col-md-6"] span').getText()
        scraper.result['sizes'] = [item.text.strip() for item in scraper.soup.select(
            'select[class="select-size"] option')[1:]]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def stylebop_scraper(url):
    """
    On demand scraper for Stylebop store
    url: https://www.stylebop.com/en-us/women/nike-air-max-95-og-sneakers-with-mesh-297065.html
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = re.findall('\d+', scraper.soup.select_one('div.price-info span.price').text)[0]
        scraper.result['sizes'] = [re.sub('[^A-Z\d,]+$', '', item.text).replace(',', '.').split('-')[0] for item in
                                   scraper.soup.select('a[data-attribute="size"]')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def dillards_scraper(url):
    """
    On demand scraper for Dillards store
    url: https://www.dillards.com/p/nike-womens-air-zoom-pegasus-35-running-shoes/507872958
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select('span.price')[-1].getText()
        scraper.result['sizes'] = [item.text for item in scraper.soup.select(
            'ul.productDisplay__ul--flatSizeWrapper li')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def academy_scraper(url):
    """
    On demand scraper for Academy store
    url: https://www.academy.com/shop/pdp/nike-mens-air-max-torch-4-running-shoes-200097971
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select_one('span[itemprop="price"]').getText()
        scraper.result['sizes'] = list(filter(None, [re.sub('[^\d.]+', '', item.text) for item in scraper.soup.select(
            'div[class="row m-0 css-1l0z8uk"] button') if not item.find('svg')]))
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def forever21_scraper(url):
    """
    On demand scraper for Forever21 store
    url: https://www.forever21.com/us/shop/catalog/product/21men/mens-shoes/2000262398
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = re.findall('[\d.]+', scraper.soup.select_one(
            'meta[name="description"]')['content'])[-1]
        text_data = re.findall('var pData = (.*);', scraper.response.text)[0]
        text_data = text_data.replace('\'', '"')
        json_data = json.loads(text_data)
        variants = [item['Sizes'] for item in json_data['Variants'] if json_data[
            'RepColorCode'] == item['ColorId']]
        scraper.result['sizes'] = [variant['SizeName'] for variant in variants[0] if variant['Available']]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def nordstrom_scraper(url):
    """
    On demand scraper for Nordstrom Store
    url: https://shop.nordstrom.com/s/nike-air-max-270-sneaker-men/4700645
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select_one('span.currentPriceString_ZR90Ht').getText()
        size_array = re.findall('"size":{"allIds":\[(.*?)]', scraper.response.text)[0]
        scraper.result['sizes'] = re.findall('[\d.]+', size_array)
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def finishline_scraper(url):
    """
    On demand scraper for Finishline store
    url:
    """
    products_api = 'https://www.finishline.com/store/browse/json/productSizesJson.jsp?productId={}&styleId={}&colorId={}'
    try:
        scraper = SimpleScraper(url)
        variant_id = scraper.soup.select_one('div[itemprop="productID"]').getText()
        style_id = scraper.soup.select_one("#productStyleId")['value']
        color_id = scraper.soup.select_one("#productColorId")['value']
        product_id = '{}-{}'.format(style_id, color_id)
        scraper.result['price'] = re.findall('[\d.d]+', scraper.soup.select_one('div#prices_{}'.format(product_id))
                                             .getText())[0]
        headers = {'x-requested-with':  'XMLHttpRequest'}
        api_response = retry_request(products_api.format(variant_id, style_id, color_id), headers=headers,
                                     proxies=Proxy.objects.all())
        api_response.raise_for_status()
        scraper.result['sizes'] = [item['sizeValue'] for item in api_response.json()['productSizes'] if
                                   item['productId'] == product_id and not item['sizeClass'] == 'unavailable']
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def roadrunnersports_scraper(url):
    """
    On demand scraper for Road Runner Sports store
    url: https://www.roadrunnersports.com/rrs/products/05229/mens-nike-lunar-caldra/
    """
    try:
        scraper = SimpleScraper(url)
        try:
            price = float(scraper.soup.select('span[class="prod_detail_sale_price"]')[-1].text)
        except IndexError:
            # Sometimes shoes are not on sale
            price = float(scraper.soup.select('span[class="prod_detail_reg_price"]')[-1].text)
        except ValueError:
            price = 0
        scraper.result['price'] = price
        scraper.result['sizes'] = [item.text for item in scraper.soup.select('a[class="ref2QISize size--available"]')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def eastbay_scraper(url):
    """
    On demand scraper for Eastbay store
    url: https://www.eastbay.com/product/model:291476/sku:0630441/nike-free-x-metcon-mens/blue/white/
    """
    try:
        scraper = SimpleScraper(url)
        scraper.result['price'] = scraper.soup.select_one('div.product_price').getText()
        json_data = json.loads(re.findall('var sizeObj =(.*);', scraper.response.text)[0])
        scraper.result['sizes'] = [item['size'].strip() for item in json_data if item['availability'] == 'In Stock']
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))


def ladyfootlocker_scraper(url):
    """
    On demand scraper for Ladyfootlocker store
    url: https://www.ladyfootlocker.com/product/nike-shox-gravity---women-s/Q8554106.html
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/71.0.3578.98 Safari/537.36'}
    try:
        scraper = SimpleScraper(url, headers=headers)
        try:
            price = scraper.soup.select_one('span.final').getText()
        except AttributeError:
            price = scraper.soup.select_one('div[class="c-product-price"] span').getText()
        scraper.result['price'] = price
        scraper.result['sizes'] = [item.text for item in scraper.soup.select(
            'div[class="c-form-field c-form-field--radio custom c-size"]')]
        return scraper.results()
    except Exception as req_exc:
        raise_log_exc(ScrapingException, str(req_exc))
