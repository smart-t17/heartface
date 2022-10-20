# Generated by Django 2.0.1 on 2018-06-20 10:56

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0093_deduplicate_reported_vids'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='reportedvideo',
            options={'ordering': ('-created',)},
        ),
        migrations.AlterUniqueTogether(
            name='reportedvideo',
            unique_together={('reporting_user', 'video')},
        ),
    ]