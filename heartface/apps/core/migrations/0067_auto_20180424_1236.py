# Generated by Django 2.0.1 on 2018-04-24 12:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0066_merge_20180421_1609'),
    ]

    operations = [
        migrations.AlterField(
            model_name='trendinghashtag',
            name='score',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=9),
        ),
        migrations.AlterField(
            model_name='trendingprofile',
            name='score',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=9),
        ),
    ]
