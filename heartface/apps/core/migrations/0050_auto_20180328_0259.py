# Generated by Django 2.0.1 on 2018-03-28 02:59

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0049_auto_20180328_0251'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='link',
        ),
        migrations.RemoveField(
            model_name='product',
            name='price',
        ),
        migrations.RemoveField(
            model_name='product',
            name='supplier',
        ),
    ]
