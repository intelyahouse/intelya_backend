from django.db import migrations


def backfill_agency(apps, schema_editor):
    Complaint = apps.get_model('leases', 'Complaint')

    for complaint in Complaint.objects.filter(agency__isnull=True, lease__agency__isnull=False).select_related('lease'):
        complaint.agency_id = complaint.lease.agency_id
        complaint.save(update_fields=['agency'])


class Migration(migrations.Migration):

    dependencies = [
        ('leases', '0003_complaint_agency_and_more'),
        ('contracts', '0004_backfill_leasecontract_agency'),
    ]

    operations = [
        migrations.RunPython(backfill_agency, migrations.RunPython.noop),
    ]
