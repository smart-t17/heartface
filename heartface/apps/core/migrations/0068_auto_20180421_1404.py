# Generated by Django 2.0.1 on 2018-04-21 14:04

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0067_auto_20180421_1303'),
    ]

    operations = [
        migrations.AlterField(
            model_name='supplierproduct',
            name='link',
            field=models.URLField(max_length=500, unique=True),
        ),
    ]