# Generated by Django 2.0.1 on 2018-07-30 11:17

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0100_homepagecontent'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='homepagecontent',
            options={'ordering': ('-created',)},
        ),
        migrations.AddField(
            model_name='notification',
            name='notification_type',
            field=models.IntegerField(choices=[(0, 'New Follower'), (1, 'New Like'), (2, 'New Comment')], default=0),
        ),
        migrations.AddField(
            model_name='notification',
            name='video',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to='core.Video'),
        ),
    ]
