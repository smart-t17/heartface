# Generated by Django 2.0.1 on 2018-04-20 13:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0063_order_handled_by'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='supplierproduct',
            unique_together={('supplier', 'product')},
        ),
    ]
