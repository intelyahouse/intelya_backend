import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0004_backfill_agency'),
    ]

    operations = [
        migrations.AlterField(
            model_name='agentprofile',
            name='agency',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='agents', to='agencies.agency'),
        ),
    ]
