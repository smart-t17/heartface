from django.db import migrations


def _remove_prods(apps, schema_editor):
    Product = apps.get_model('core', 'Product')
    Product.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0108_merge_20180828_1210'),
    ]

    operations = [
        migrations.RunPython(code=_remove_prods,  reverse_code=migrations.RunPython.noop)
    ]
