from django.db import migrations


def backfill_agency(apps, schema_editor):
    OwnerAgentRelation = apps.get_model('agents', 'OwnerAgentRelation')
    AgentProfile = apps.get_model('agents', 'AgentProfile')

    for relation in OwnerAgentRelation.objects.filter(agency__isnull=True).select_related('agent'):
        try:
            profile = AgentProfile.objects.get(user_id=relation.agent_id)
        except AgentProfile.DoesNotExist:
            continue
        if profile.agency_id:
            relation.agency_id = profile.agency_id
            relation.save(update_fields=['agency'])


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0006_owneragentrelation_agency'),
    ]

    operations = [
        migrations.RunPython(backfill_agency, migrations.RunPython.noop),
    ]
