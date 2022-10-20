# Generated by Django 2.0.1 on 2018-08-27 10:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0106_auto_20180806_1230'),
    ]

    operations = [
        migrations.AlterField(
            model_name='device',
            name='type',
            field=models.IntegerField(choices=[(0, 'ios'), (1, 'android')]),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.IntegerField(choices=[(0, 'new'), (1, 'processing'), (2, 'ordered'), (3, 'confirmed')], default=0),
        ),
        migrations.AlterField(
            model_name='user',
            name='gender',
            field=models.CharField(choices=[('male', 'male'), ('female', 'female'), ('other', 'other')], max_length=6),
        ),
    ]
