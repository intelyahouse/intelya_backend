from django.db import migrations


def backfill_agency(apps, schema_editor):
    AgentProfile = apps.get_model('agents', 'AgentProfile')
    Agency = apps.get_model('agencies', 'Agency')

    for profile in AgentProfile.objects.filter(agency__isnull=True).select_related('user'):
        user = profile.user
        full_name = f"{user.first_name} {user.last_name}".strip()
        name = (profile.agency_name or "").strip() or f"Agence de {full_name or user.email}"
        agency = Agency.objects.create(name=name, owner_agent=user, is_solo=True)
        profile.agency = agency
        profile.save(update_fields=['agency'])


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0003_agentprofile_agency'),
    ]

    operations = [
        migrations.RunPython(backfill_agency, migrations.RunPython.noop),
    ]
