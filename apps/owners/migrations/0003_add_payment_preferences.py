# Generated migration for PaymentPreferences and BankAccount improvements

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('owners', '0002_add_bank_account_model'),
    ]

    operations = [
        # Ajouter UUID à BankAccount s'il n'existe pas
        migrations.AddField(
            model_name='bankaccount',
            name='id',
            field=models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False),
            preserve_default=False,
        ),
        
        # Créer le modèle PaymentPreferences
        migrations.CreateModel(
            name='PaymentPreferences',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('payout_frequency', models.CharField(
                    choices=[
                        ('end_of_month', 'Fin de mois'),
                        ('mid_month', 'Milieu de mois'),
                        ('weekly', 'Hebdomadaire'),
                        ('on_demand', 'À la demande')
                    ],
                    default='end_of_month',
                    max_length=20
                )),
                ('minimum_payout_amount', models.DecimalField(decimal_places=2, default=50000.0, max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('owner', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='payment_preferences', to='owners.ownerprofile')),
                ('preferred_bank_account', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='owners.bankaccount')),
            ],
            options={
                'verbose_name': 'Préférences de paiement',
            },
        ),
    ]
