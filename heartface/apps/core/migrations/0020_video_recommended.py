# Generated by Django 2.0.1 on 2018-02-01 15:33

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_video_published'),
    ]

    operations = [
        migrations.AddField(
            model_name='video',
            name='recommended',
            field=models.BooleanField(default=False),
        ),
    ]