import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('agents', '0007_backfill_owneragentrelation_agency'),
    ]

    operations = [
        migrations.AlterField(
            model_name='owneragentrelation',
            name='agency',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='mandates', to='agencies.agency'),
        ),
    ]
