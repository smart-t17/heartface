# Generated by Django 2.0.1 on 2018-01-30 21:33

import datetime
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_auto_20180126_0033'),
    ]

    operations = [
        migrations.CreateModel(
            name='Like',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='like', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.RemoveField(
            model_name='video',
            name='likes',
        ),
        migrations.AddField(
            model_name='video',
            name='created',
            field=models.DateTimeField(auto_now_add=True, default=datetime.datetime(2018, 1, 30, 21, 33, 26, 720818, tzinfo=utc)),
            preserve_default=False,
        ),
    ]
