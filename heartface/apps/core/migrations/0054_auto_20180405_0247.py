# Generated by Django 2.0.3 on 2018-04-05 02:47
from django.db import migrations, models, transaction
import django.db.models.deletion
from django.db.models import F


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0053_merge_20180402_0536'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='supplier_product',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='core.SupplierProduct'),
        ),
        migrations.AlterField(
            model_name='order',
            name='product',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='orders', to='core.Product'),
        ),
        migrations.AlterField(
            model_name='video',
            name='title',
            field=models.CharField(default='', max_length=255),
        ),
        migrations.AddField(
            model_name='order',
            name='size',
            field=models.DecimalField(
                choices=[(1.0, 1.0), (1.5, 1.5), (2.0, 2.0), (2.5, 2.5), (3.0, 3.0), (3.5, 3.5), (4.0, 4.0), (4.5, 4.5),
                         (5.0, 5.0), (5.5, 5.5), (6.0, 6.0), (6.5, 6.5), (7.0, 7.0), (7.5, 7.5), (8.0, 8.0), (8.5, 8.5),
                         (9.0, 9.0), (9.5, 9.5), (10.0, 10.0), (10.5, 10.5), (11.0, 11.0), (11.5, 11.5), (12.0, 12.0),
                         (12.5, 12.5), (13.0, 13.0), (13.5, 13.5), (14.0, 14.0), (14.5, 14.5), (15.0, 15.0),
                         (15.5, 15.5), (16.0, 16.0), (16.5, 16.5), (17.0, 17.0), (17.5, 17.5), (18.0, 18.0),
                         (18.5, 18.5), (19.0, 19.0), (19.5, 19.5)], decimal_places=1, max_digits=3, null=True),
        ),
    ]
