import re

from django.conf import settings
from django.db import migrations


def _notification_types(apps, schema_editor):
    User = apps.get_model('core', 'User')
    dummy_user, _ = User.objects.get_or_create(email=settings.MIGRATIONS_PLACEHOLDER_USER_PARAMS['email'],
                                            defaults=settings.MIGRATIONS_PLACEHOLDER_USER_PARAMS)

    for n in apps.get_model('core', 'Notification').objects.all():
        if 'is now following you' in n.message:
            n.notification_type = 0
            sender = re.findall(r'(.*) is now following you', n.message)[0]
        elif 'liked your video' in n.message:
            n.notification_type = 1
            sender = re.findall(r'(.*) liked your video', n.message)[0]
        elif 'commented on your video' in n.message:
            n.notification_type = 2
            sender = re.findall(r'(.*) commented on your video', n.message)[0]
        else:
            sender = dummy_user.username

        try:
            n.sender = User.objects.get(username=sender)
        except User.DoesNotExist:
            n.sender = dummy_user

        n.save()


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0102_notification_sender'),
    ]

    operations = [
        migrations.RunPython(code=_notification_types,  reverse_code=migrations.RunPython.noop)
    ]
