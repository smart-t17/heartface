# Generated by Django 2.0.1 on 2018-02-05 14:47

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0022_merge_20180204_1845'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='editorialrecommendation',
            name='featured_videos',
        ),
        migrations.AddField(
            model_name='editorialrecommendation',
            name='featured_video',
            field=models.ForeignKey(default=None, on_delete=django.db.models.deletion.CASCADE, related_name='+', to='core.Video'),
            preserve_default=False,
        ),
    ]
