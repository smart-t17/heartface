# Generated by Django 2.0.1 on 2018-02-14 12:14

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0027_auto_20180213_1811'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='likevideo',
            name='like',
        ),
        migrations.RemoveField(
            model_name='likevideo',
            name='video',
        ),
        migrations.AddField(
            model_name='like',
            name='video',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, related_name='video_likes', to='core.Video'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='like',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_likes', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='video',
            name='likes',
            field=models.ManyToManyField(blank=True, related_name='liked_videos', through='core.Like', to=settings.AUTH_USER_MODEL),
        ),
        migrations.DeleteModel(
            name='LikeVideo',
        ),
    ]
