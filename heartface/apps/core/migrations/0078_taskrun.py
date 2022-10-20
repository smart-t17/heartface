# Generated by Django 2.0.1 on 2018-05-02 14:13

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0077_order_commission_earned'),
    ]

    operations = [
        migrations.CreateModel(
            name='TaskRun',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('task_label', models.CharField(max_length=30, verbose_name='task label')),
                ('started_at', models.DateTimeField(auto_now_add=True)),
                ('terminated_at', models.DateTimeField(blank=True, default=None, null=True)),
            ],
            options={
                'ordering': ('-started_at',),
            },
        ),
    ]
