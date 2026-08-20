from django.db import migrations
from django.db.models import Avg, Count


def backfill_reputation(apps, schema_editor):
    Agency = apps.get_model('agencies', 'Agency')
    Review = apps.get_model('reviews', 'Review')
    Dispute = apps.get_model('disputes', 'Dispute')
    AgentProfile = apps.get_model('agents', 'AgentProfile')

    for agency in Agency.objects.all():
        member_user_ids = list(AgentProfile.objects.filter(agency=agency).values_list('user_id', flat=True))
        reviews = Review.objects.filter(agent_id__in=member_user_ids, agent_rating__isnull=False)
        agg = reviews.aggregate(avg=Avg('agent_rating'), count=Count('id'))
        agency.reliability_score = round(agg['avg'], 2) if agg['avg'] else 0.0
        agency.total_reviews = agg['count'] or 0
        agency.disputes_confirmed_against = Dispute.objects.filter(
            agency=agency, decision='claimant_wins'
        ).count()
        agency.save(update_fields=['reliability_score', 'total_reviews', 'disputes_confirmed_against'])


class Migration(migrations.Migration):

    dependencies = [
        ('agencies', '0004_agency_disputes_confirmed_against_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_reputation, migrations.RunPython.noop),
    ]
