from scrapy.loader import ItemLoader
from scrapy.loader.processors import TakeFirst, MapCompose
from w3lib.html import remove_tags


class KeepNonNull(object):
    def __call__(self, values):
        return [value for value in values if value]


class ProductLoader(ItemLoader):
    """
    Very basic loader. Add more field-specific cleaning if needed. See BAC-64 task
    """
    default_output_processor = TakeFirst()
    default_input_processor = MapCompose(remove_tags, str.strip)

    # Keep as list as images pipeline expects that
    image_urls_out = KeepNonNull()
