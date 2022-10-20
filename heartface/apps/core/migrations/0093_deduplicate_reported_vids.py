from django.db import migrations
from heartface.libs.utils import _dedup


def _dedep_reported_vids(apps, schema_editor):
    _dedup(apps.get_model('core', 'ReportedVideo'), ['reporting_user', 'video'], '-created')


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0092_merge_20180619_0044'),
    ]

    operations = [
        migrations.RunPython(code=_dedep_reported_vids,  reverse_code=migrations.RunPython.noop)
    ]
