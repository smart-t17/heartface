# Generated by Django 2.0.1 on 2018-09-02 15:24

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0114_auto_20180902_1516'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='status',
            field=models.IntegerField(choices=[(0, 'scraped'), (1, 'queued'), (2, 'processed')], default=0),
        ),
    ]
