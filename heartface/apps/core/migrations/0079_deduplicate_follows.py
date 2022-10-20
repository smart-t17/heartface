from django.db import migrations
from heartface.libs.utils import _dedup


def _dedep_like_follow(apps, schema_editor):
    _dedup(apps.get_model('core', 'Follow'), ['followed', 'follower'], '-created')
    _dedup(apps.get_model('core', 'Like'), ['user', 'video'], '-created')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0079_user_followers'),
    ]

    operations = [
        migrations.RunPython(code=_dedep_like_follow,  reverse_code=migrations.RunPython.noop)
    ]
