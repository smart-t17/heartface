# Generated by Django 2.0.1 on 2018-02-08 15:59

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0025_merge_20180207_1219'),
    ]

    operations = [
        migrations.RenameField(
            model_name='product',
            old_name='url',
            new_name='link',
        ),
    ]
