from django.db import migrations, models
from django.utils import timezone


def _map_bool_to_datetime(apps, schema_editor):
    Video = apps.get_model('core', 'Video')
    for video in Video.objects.all():
        if video.cdn_available:
            video.cdn_available_temp = timezone.now()
        else:
            video.cdn_available_temp = None
        video.save()


def _map_datetime_to_bool(apps, schema_editor):
    Video = apps.get_model('core', 'Video')
    for video in Video.objects.all():
        if video.cdn_available_temp:
            video.cdn_available = True
        else:
            video.cdn_available = False
        video.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0126_auto_20181105_1354'),
    ]

    operations = [
        # Temporary datetime field
        migrations.AddField(
            model_name='video',
            name='cdn_available_temp',
            field=models.DateTimeField(blank=True, default=None, null=True),
        ),
        # Forward: map booleans from cdn_available to cdn_available_temp
        # Reverse: map datetimes from cdn_available temp to booleans in
        # cdn_available
        migrations.RunPython(code=_map_bool_to_datetime,  reverse_code=_map_datetime_to_bool),
    ]
