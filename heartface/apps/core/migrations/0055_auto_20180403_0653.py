# Generated by Django 2.0.1 on 2018-04-03 06:53

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0054_merge_20180403_0652'),
    ]

    operations = [
        # migrations.RemoveField(
        #     model_name='device',
        #     name='type_device',
        # ),
        migrations.RenameField(
            model_name='device',
            old_name='type_device',
            new_name='type'
        ),
        migrations.AlterField(
            model_name='device',
            name='type',
            field=models.IntegerField(choices=[(0, 'iOS'), (1, 'Android')], default=0),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='video',
            name='title',
            field=models.CharField(default='', max_length=255),
        ),
    ]
