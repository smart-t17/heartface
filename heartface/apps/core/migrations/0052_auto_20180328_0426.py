# Generated by Django 2.0.1 on 2018-03-28 04:26

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0051_supplierproduct_sizes'),
    ]

    operations = [
        migrations.AlterField(
            model_name='supplierproduct',
            name='supplier',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='core.Supplier'),
        ),
    ]
