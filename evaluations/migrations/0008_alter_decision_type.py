# Generated manually to align decisions with the pedagogical workflow.

from django.db import migrations, models


def normalize_decisions(apps, schema_editor):
    Decision = apps.get_model('evaluations', 'Decision')
    Decision.objects.filter(type='ADMISSION').update(type='ADMIS')
    Decision.objects.filter(type='NON_ADMISSION').update(type='REFUSE')


class Migration(migrations.Migration):

    dependencies = [
        ('evaluations', '0007_evaluation_reponse_and_more'),
    ]

    operations = [
        migrations.RunPython(normalize_decisions, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='decision',
            name='type',
            field=models.CharField(
                choices=[
                    ('ADMIS', 'Admis'),
                    ('REFUSE', 'Refusé'),
                    ('EN_ATTENTE', 'En attente'),
                ],
                max_length=20,
            ),
        ),
    ]
