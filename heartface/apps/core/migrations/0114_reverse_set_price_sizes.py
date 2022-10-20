from django.db import migrations


def _populate_price_sizes(apps, schema_editor):
    SupplierProduct = apps.get_model('core', 'SupplierProduct')
    SupplierProduct.objects.filter(price__isnull=True).update(price=0.0)
    SupplierProduct.objects.filter(sizes__isnull=True).update(sizes=["N/A"])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0113_auto_20180902_1053'),
    ]

    operations = [
        migrations.RunPython(code=migrations.RunPython.noop,  reverse_code=_populate_price_sizes)
    ]
