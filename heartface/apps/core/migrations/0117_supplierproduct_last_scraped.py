# Generated by Django 2.0.1 on 2018-09-19 04:29

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0116_auto_20180907_0455'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplierproduct',
            name='last_scraped',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]