from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('notifications', '0002_initial')]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(
                choices=[
                    ('ACTIVATION', 'Activation'), ('CONVOCATION', 'Convocation'),
                    ('RESULTAT', 'Résultat'), ('FIN_PARCOURS', 'Fin de parcours'),
                    ('ADMISSION', 'Admission'), ('CONFIRMATION', 'Confirmation de présence'),
                ],
                max_length=20,
            ),
        ),
    ]
