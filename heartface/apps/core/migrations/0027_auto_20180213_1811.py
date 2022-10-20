# Generated by Django 2.0.1 on 2018-02-13 18:11

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0026_auto_20180208_1559'),
    ]

    operations = [
        migrations.AlterField(
            model_name='reportedvideo',
            name='video',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to='core.Video'),
        ),
        migrations.AddField(
            model_name='reportedvideo',
            name='id',
            field=models.AutoField(auto_created=True, default=None, primary_key=True, serialize=False, verbose_name='ID'),
            preserve_default=False,
        ),
    ]