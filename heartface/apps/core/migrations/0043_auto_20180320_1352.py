# Generated by Django 2.0.1 on 2018-03-20 13:52

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0042_auto_20180320_1347'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='user',
            name='first_name',
        ),
        migrations.RemoveField(
            model_name='user',
            name='last_name',
        ),
    ]