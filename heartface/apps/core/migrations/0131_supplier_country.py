# Generated by Django 2.0.1 on 2018-11-15 11:55

from django.db import migrations
import django_countries.fields


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0130_user_country'),
    ]

    operations = [
        migrations.AddField(
            model_name='supplier',
            name='country',
            field=django_countries.fields.CountryField(blank=True, default='GB', max_length=2),
        ),
    ]
