# Generated by Django 2.0.1 on 2018-03-27 01:10

from django.db import migrations, models
import heartface.apps.core.models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0045_merge_20180323_0750'),
    ]

    operations = [
        migrations.RenameField(
            model_name='comment',
            old_name='timestamp',
            new_name='created',
        ),
        migrations.AlterField(
            model_name='collection',
            name='cover_photo',
            field=models.FileField(upload_to=heartface.apps.core.models.UploadDir('collection_covers')),
        ),
        migrations.AlterField(
            model_name='user',
            name='photo',
            field=models.FileField(blank=True, upload_to=heartface.apps.core.models.UploadDir('photo')),
        ),
        migrations.AlterField(
            model_name='video',
            name='videofile',
            field=models.FileField(upload_to=heartface.apps.core.models.UploadDir('videos')),
        ),
    ]
