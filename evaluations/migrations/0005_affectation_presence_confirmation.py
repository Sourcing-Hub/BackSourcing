import uuid

from django.db import migrations, models


def creer_tokens_confirmation(apps, schema_editor):
    AffectationCandidat = apps.get_model('evaluations', 'AffectationCandidat')
    for affectation in AffectationCandidat.objects.filter(tokenConfirmation__isnull=True):
        affectation.tokenConfirmation = uuid.uuid4()
        affectation.save(update_fields=['tokenConfirmation'])


class Migration(migrations.Migration):
    dependencies = [('evaluations', '0004_normalize_selection_stages')]

    operations = [
        migrations.AddField(
            model_name='affectationcandidat',
            name='statutPresence',
            field=models.CharField(
                choices=[('A_ATTENDRE', 'En attente de pointage'), ('PRESENT', 'Présent'), ('ABSENT', 'Absent')],
                default='A_ATTENDRE', max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='affectationcandidat',
            name='dateEmargement',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='affectationcandidat',
            name='dateConfirmation',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='affectationcandidat',
            name='tokenConfirmation',
            field=models.UUIDField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(creer_tokens_confirmation, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='affectationcandidat',
            name='tokenConfirmation',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]
