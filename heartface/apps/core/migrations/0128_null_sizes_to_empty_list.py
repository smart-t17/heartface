from django.db import migrations


def _map_null_sizes_to_empty_list(apps, schema_editor):
    SupplierProduct = apps.get_model('core', 'SupplierProduct')
    SupplierProduct.objects.filter(sizes__isnull=True).update(sizes=[])


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0127_cdn_available_b'),
    ]

    operations = [
        migrations.RunPython(code=_map_null_sizes_to_empty_list,  reverse_code=migrations.RunPython.noop)
    ]
