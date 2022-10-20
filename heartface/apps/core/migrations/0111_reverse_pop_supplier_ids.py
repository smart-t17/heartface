from django.db import migrations

SUPPLIERS = ['Offspring', 'Schuh', 'Footasylum', 'Sports Direct',
             'Vans', 'New Balance', 'Timberland', 'Adidas',	'Urban Outfitters',
             'Fight Club', 'Urban Industry', 'Nike', 'Foot Locker',
             'eBay', 'StockX']


def _populate_suppliers(apps, schema_editor):
    Supplier = apps.get_model('core', 'Supplier')
    for supplier_name in SUPPLIERS:
        Supplier.objects.filter(name=supplier_name).update(supplier_id=supplier_name.replace(' ', '').lower())


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0111_nonunique_nullable_supplier_id'),
    ]

    operations = [
        migrations.RunPython(code=migrations.RunPython.noop,  reverse_code=_populate_suppliers)
    ]
