# Generated by Django 2.0.1 on 2018-03-28 02:51

from django.db import migrations, models
import heartface.apps.core.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0048_move_product_data'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='link',
            field=models.URLField(default='', null=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=9, null=True),
        ),
        migrations.AlterField(
            model_name='product',
            name='supplier',
            field=models.ForeignKey('Supplier', default='', null=True, related_name='products', on_delete=models.CASCADE)
        ),
    ]
