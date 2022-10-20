import django
from scrapy.exceptions import DropItem
from scrapy.pipelines.images import ImagesPipeline
from .storages import BunnyCDNFilesStore
from scrapy.pipelines.files import FSFilesStore, S3FilesStore

django.setup()

# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://doc.scrapy.org/en/latest/topics/item-pipeline.html

from heartface.apps.core.models import Product
from heartface.apps.core.tasks import save_scraped_product


class DuplicateDropItem(DropItem):
    """
    For more refined Drop stats
    """
    pass


class CeleryQueuePipeline(object):
    def process_item(self, item, spider):
        if item.get('images'):
            # The imagespipeline downloaded locally. This is the path to it
            item['primary_picture'] = item.pop('images')[0]['path']
        data = dict((k,  item.get(k)) for k in item._values if
                    k in item._model_fields)
        save_scraped_product.delay(data)
        return item


class CustomImagesPipeline(ImagesPipeline):
    STORE_SCHEMES = {
        '': FSFilesStore,
        'file': FSFilesStore,
        's3': S3FilesStore,
        'bunnycdn': BunnyCDNFilesStore
    }

    @classmethod
    def from_settings(cls, settings):
        bunnyCDNStore = cls.STORE_SCHEMES['bunnycdn']
        bunnyCDNStore.BUNNY_CDN_ACCESS_KEY = settings['BUNNY_CDN_ACCESS_KEY']
        # So we don't break s3 support (not that we need it atm)
        s3store = cls.STORE_SCHEMES['s3']
        s3store.AWS_ACCESS_KEY_ID = settings['AWS_ACCESS_KEY_ID']
        s3store.AWS_SECRET_ACCESS_KEY = settings['AWS_SECRET_ACCESS_KEY']

        store_uri = settings['IMAGES_STORE']
        return cls(store_uri, settings=settings)


class DropPipeline(object):

    def process_item(self, item, spider):

        stockx_id = item.get('stockx_id')
        # Duplicates
        if stockx_id in spider.stockx_ids:
            spider.duplicate_stockx_ids.append(stockx_id)
            raise DuplicateDropItem('Duplicate stockX ID item: {}'.format(item))
        elif stockx_id is None or not stockx_id.strip():
            # NB also guards against item = {'stock_id': None,...}
            raise DropItem('stockx_id: {} is null')
        else:
            spider.stockx_ids.add(stockx_id)

        # Checks on TextField/CharFields fields
        str_fields = [field for field in Product._meta.fields
                      if field.get_internal_type() in ['TextField', 'CharField']]
        for field in str_fields:
            # Check item data is str (only check if non null)
            if item.get(field.name) and not isinstance(item[field.name], str):
                raise DropItem('{}: {} is not in string format for'
                               ' stockx_id {}'.format(field.name, item[field.name], stockx_id))

            # Check present (and not empty str) if required
            if not field.blank and (item.get(field.name) is None or not item[field.name].strip()):
                raise DropItem('{}: field is not blank but we do not have a non-null/non-empty'
                               ' value for stockx_id {}'.format(field.name, stockx_id))

            if field.blank and item.get(field.name) is None:
                # Ensure null means empty string not None for blank=True
                # fields like description consistent with Django
                # charfield/textfield null defn
                item[field.name] = ''

            if field.max_length and len(item.get(field.name) or '') > field.max_length:
                raise DropItem('{} has len {} which is greater'
                               ' than max_length {} for item with'
                               ' stockx_id {}'.format(field.name, len(item[field.name]),
                                                      field.max_length, stockx_id))
        return item
