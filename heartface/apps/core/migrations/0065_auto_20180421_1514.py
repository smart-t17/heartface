# Generated by Django 2.0.1 on 2018-04-21 15:14

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0064_view'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='view',
            unique_together={('video', 'user')},
        ),
    ]
