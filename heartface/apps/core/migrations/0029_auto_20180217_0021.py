# Generated by Django 2.0.1 on 2018-02-17 00:21

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0028_auto_20180214_1214'),
    ]

    operations = [
        migrations.AlterField(
            model_name='like',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='like',
            name='video',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='core.Video'),
        ),
        migrations.AlterField(
            model_name='video',
            name='likes',
            field=models.ManyToManyField(blank=True, related_name='likes', through='core.Like', to=settings.AUTH_USER_MODEL),
        ),
    ]