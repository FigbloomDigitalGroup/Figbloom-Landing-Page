from django.db import migrations, models


def move_team_activities_to_updates(apps, schema_editor):
    """Team activities are posted as Updates now. Anything already filed under
    the old "team" category moves across, so it keeps showing up (under the
    Updates tab) instead of pointing at a category that no longer exists."""
    Activity = apps.get_model('activities', 'Activity')
    Activity.objects.filter(category='team').update(category='update')


class Migration(migrations.Migration):

    dependencies = [
        ('activities', '0001_initial'),
    ]

    operations = [
        # No way back for the data: once moved, nothing records which updates
        # used to be team activities. Reversing just leaves them as updates.
        migrations.RunPython(move_team_activities_to_updates, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='activity',
            name='category',
            field=models.CharField(choices=[('event', 'Event'), ('update', 'Update'), ('community', 'Community'), ('achievement', 'Achievement'), ('workshop', 'Workshop')], db_index=True, default='event', max_length=20),
        ),
    ]
