# Generated by Django 2.0.1 on 2018-02-15 12:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_auto_20180208_1559'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='product',
            field=models.ForeignKey(default='', on_delete=django.db.models.deletion.CASCADE, related_name='product', to='core.Product'),
            preserve_default=False,
        ),
    ]
