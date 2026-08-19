from django.db import migrations


def backfill_agency(apps, schema_editor):
    LeaseContract = apps.get_model('contracts', 'LeaseContract')
    AgentProfile = apps.get_model('agents', 'AgentProfile')

    for lease in LeaseContract.objects.filter(agency__isnull=True, agent__isnull=False):
        try:
            profile = AgentProfile.objects.get(user_id=lease.agent_id)
        except AgentProfile.DoesNotExist:
            continue
        if profile.agency_id:
            lease.agency_id = profile.agency_id
            lease.save(update_fields=['agency'])


class Migration(migrations.Migration):

    dependencies = [
        ('contracts', '0003_leasecontract_agency_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_agency, migrations.RunPython.noop),
    ]
