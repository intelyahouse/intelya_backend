from django.db import migrations


def seed_tiers(apps, schema_editor):
    RentFeeTier = apps.get_model('payments', 'RentFeeTier')
    if RentFeeTier.objects.exists():
        return
    RentFeeTier.objects.create(min_rent=1, max_rent=50000, fee_amount=500)
    RentFeeTier.objects.create(min_rent=50001, max_rent=100000, fee_amount=1000)


def remove_seeded_tiers(apps, schema_editor):
    RentFeeTier = apps.get_model('payments', 'RentFeeTier')
    RentFeeTier.objects.filter(min_rent__in=[1, 50001], fee_amount__in=[500, 1000]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('payments', '0005_rentfeetier_transaction_agency_fee_amount'),
    ]

    operations = [
        migrations.RunPython(seed_tiers, remove_seeded_tiers),
    ]
