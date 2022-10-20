from django.db import migrations


def add_tasks(apps, schema_editor):
    IntervalSchedule = apps.get_model('django_celery_beat', 'IntervalSchedule')
    CrontabSchedule = apps.get_model('django_celery_beat', 'CrontabSchedule')
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    daily, _ = IntervalSchedule.objects.get_or_create(every=1, period='days')
    PeriodicTask.objects.create(
        interval=daily,
        name='Check the trendiness',
        task='heartface.apps.core.tasks.check_trending'
    )

    hourly, _ = IntervalSchedule.objects.get_or_create(every=1, period='hours')
    PeriodicTask.objects.create(
        interval=hourly,
        name='Cleanup unpublished videos',
        task='heartface.apps.core.tasks.cleanup_unpublished_vids'
    )

    stockx_crontab, _ = CrontabSchedule.objects.get_or_create(minute=12, hour=1)
    PeriodicTask.objects.create(
        crontab=stockx_crontab,
        name='Update products from StockX',
        task='heartface.apps.core.tasks.stockx_crawler_update_product'
    )

def del_tasks(apps, schema_editor):
    PeriodicTask = apps.get_model('django_celery_beat', 'PeriodicTask')

    PeriodicTask.objects.filter(
        name='Check the trendiness',
        task='heartface.apps.core.tasks.check_trending'
    ).delete()
    PeriodicTask.objects.filter(
        name='Cleanup unpublished videos',
        task='heartface.apps.core.tasks.cleanup_unpublished_vids'
    ).delete()
    PeriodicTask.objects.filter(
        name='Update products from StockX',
        task='heartface.apps.core.tasks.stockx_crawler_update_product'
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0132_missingproduct'),
        ('django_celery_beat', '0006_periodictask_priority'),
    ]

    operations = [
        migrations.RunPython(code=add_tasks, reverse_code=del_tasks),
    ]
