# Generated by Django 2.0.1 on 2018-03-16 06:01

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0039_merge_20180311_1553'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='is_verified',
        ),
    ]
