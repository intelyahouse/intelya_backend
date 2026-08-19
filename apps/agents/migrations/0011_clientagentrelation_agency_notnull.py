import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0010_backfill_clientagentrelation_agency'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clientagentrelation',
            name='agency',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='client_relations', to='agencies.agency'),
        ),
    ]
