# Generated by Django 2.0.1 on 2018-02-05 17:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_merge_20180204_1845'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='video',
            name='url',
        ),
        migrations.AlterField(
            model_name='video',
            name='published',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
    ]
