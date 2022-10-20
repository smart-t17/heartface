from django.db import migrations
from heartface.libs.utils import _dedup


def _dedep_trending(apps, schema_editor):
    _dedup(apps.get_model('core', 'TrendingProfile'), ['user', 'trending'], 'score')
    _dedup(apps.get_model('core', 'TrendingHashtag'), ['hashtag', 'trending'], 'score')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0080_auto_20180513_1313'),
    ]

    operations = [
        migrations.RunPython(code=_dedep_trending,  reverse_code=migrations.RunPython.noop)
    ]
