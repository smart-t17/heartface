from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0127_cdn_available'),
    ]

    operations = [
        # Remove the boolean field
        migrations.RemoveField(
            model_name='video',
            name='cdn_available',
        ),
        # Rename the dt field
        migrations.RenameField(
            model_name='video',
            old_name='cdn_available_temp',
            new_name='cdn_available',
        ),
    ]
