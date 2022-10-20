import logging
from collections import defaultdict

from django.db import migrations, IntegrityError
from django.db import transaction

from heartface import settings

logger = logging.getLogger('migrations')

# No longer use this in libs.scrape so cant just import it
# Reproduce here so the migration still works
HOST_INFO = {'(.*\.)?offspring.co.uk': {'Supplier': 'Offspring', 'Scraper': None},
             '(.*\.)?schuh.co.uk': {'Supplier': 'Schuh', 'Scraper': None},
             '(.*\.)?footasylum.com': {'Supplier': 'Footasylum', 'Scraper': None},
             '(.*\.)?sportsdirect.com': {'Supplier': 'Sports Direct',
                                         'Scraper': None,
                                         'allowed_params': ['colcode'],
                                         'headers': {'X-Forward-Cookie': 'ChosenSite=www; SportsDirect_AnonymousUserCurrency=GBP;'}
                                         },
             '(.*\.)?vans.co.uk': {'Supplier': 'Vans', 'Scraper': None},
             '(.*\.)?newbalance.co.uk': {'Supplier': 'New Balance', 'Scraper': None},
             '(.*\.)?timberland.co.uk': {'Supplier': 'Timberland', 'Scraper': None},
             '(.*\.)?adidas.co.uk': {'Supplier': 'Adidas', 'Scraper': None},
             '(.*\.)?urbanoutfitters.com': {'Supplier': 'Urban Outfitters', 'Scraper': None},
             '(.*\.)?flightclub.com': {'Supplier': 'Fight Club', 'Scraper': None,
                                       'headers': {'X-Forward-Cookie': 'currency=GBP;'}
                                       },
             '(.*\.)?urbanindustry.co.uk': {'Supplier': 'Urban Industry', 'Scraper': None},
             '(.*\.)?nike.com': {'Supplier': 'Nike', 'Scraper': None},
             '(.*\.)?footlocker.co.uk': {'Supplier': 'Foot Locker', 'Scraper': None,
                                         'allowed_params': ['v', ]},
             '(.*\.)?ebay.co.uk': {'Supplier': 'eBay', 'Scraper': None},
             '(.*\.)?stockx.com': {'Supplier': 'StockX', 'Scraper': None},
             }


def _dedep_suppliers(apps, schema_editor):
    Supplier = apps.get_model('core', 'Supplier')
    SupplierProduct = apps.get_model('core', 'SupplierProduct')

    supplier_name_to_id = defaultdict(lambda: None, {v['Supplier']: k for k, v in HOST_INFO.items()})

    for sname in Supplier.objects.values_list('name', flat=True).distinct():
        # Point all SupplierProduct instances at the Supplier instance
        # with name `sname` that we plan to retain. (Which should be the one we have in HOST_INFO at the moment as
        # that will be the one being recreated on next startup automatically.)
        s = Supplier.objects.filter(name=sname, supplier_id=supplier_name_to_id[sname]).first() or Supplier.objects.filter(name=sname).first()
        for sp in SupplierProduct.objects.filter(supplier__name=sname):
            # Sometimes we have SupplierProduct instances with
            # same Product associated but Supplier with same name,
            # but different supplier_id. We can only retain one such instance.
            try:
                with transaction.atomic():
                    sp.supplier = s
                    sp.save()
            except IntegrityError:
                # Deleting the SupplierProduct would delete related Orders and this would be unacceptable in production
                if not sp.orders.count() or settings.env_name in ['dev', 'development', 'test', 'staging']:
                    sp.delete()
                else:
                    logger.error('Refusing to delete duplicate SupplierProduct [id = %s] having associated Orders. You will have to resolve this manually.' % sp.pk)
        # Delete all Supplier instances with name `sname` except `s`
        Supplier.objects.filter(name=sname).exclude(pk=s.pk).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0096_merge_20180627_0954'),
    ]

    operations = [
        migrations.RunPython(code=_dedep_suppliers,  reverse_code=migrations.RunPython.noop)
    ]
