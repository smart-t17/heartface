# Generated by Django 2.0.1 on 2018-03-05 13:31

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0035_order_retailer_order_id'),
        # ('core', '0035_user_followers'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='address',
            field=models.CharField(max_length=255, null=True, verbose_name='address'),
        ),
    ]
