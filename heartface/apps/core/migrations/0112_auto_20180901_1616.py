# Generated by Django 2.0.1 on 2018-09-01 16:16

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0111_remove_supplier_supplier_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='handled_by',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.DO_NOTHING, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='product',
            name='status',
            field=models.IntegerField(choices=[(0, 'queued'), (1, 'processing')], default=0),
        ),
    ]
