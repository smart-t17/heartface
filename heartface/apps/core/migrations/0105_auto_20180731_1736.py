# Generated by Django 2.0.1 on 2018-07-31 17:36

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0104_auto_20180730_1140'),
    ]

    operations = [
        migrations.RenameField(
            model_name='notification',
            old_name='notification_type',
            new_name='type',
        ),
    ]
