from django.db import migrations


def backfill_agency(apps, schema_editor):
    ClientAgentRelation = apps.get_model('agents', 'ClientAgentRelation')
    AgentProfile = apps.get_model('agents', 'AgentProfile')

    for relation in ClientAgentRelation.objects.filter(agency__isnull=True).select_related('agent'):
        try:
            profile = AgentProfile.objects.get(user_id=relation.agent_id)
        except AgentProfile.DoesNotExist:
            continue
        if profile.agency_id:
            relation.agency_id = profile.agency_id
            relation.save(update_fields=['agency'])


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0009_clientagentrelation_agency_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_agency, migrations.RunPython.noop),
    ]
