from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('evaluations', '0002_initial')]

    operations = [
        migrations.AddField(
            model_name='affectationevaluateur',
            name='roleEncadrement',
            field=models.CharField(choices=[('TECHNIQUE', 'Coach technique'), ('MOTIVATION', 'Coach motivation')], default='TECHNIQUE', max_length=20),
        ),
        migrations.AddConstraint(
            model_name='affectationevaluateur',
            constraint=models.UniqueConstraint(fields=('evaluateur', 'session', 'roleEncadrement'), name='affectation_evaluateur_role_unique'),
        ),
    ]
