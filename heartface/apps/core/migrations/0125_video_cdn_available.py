# Generated by Django 2.0.1 on 2018-10-28 11:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0124_auto_20181024_1607'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='cdn_available',
            field=models.BooleanField(default=False),
        ),
    ]