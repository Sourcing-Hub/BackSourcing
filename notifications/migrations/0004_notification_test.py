from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('notifications', '0003_notification_confirmation')]

    operations = [
        migrations.AlterField(
            model_name='notification',
            name='type',
            field=models.CharField(
                choices=[
                    ('ACTIVATION', 'Activation'),
                    ('CONVOCATION', 'Convocation'),
                    ('RESULTAT', 'Résultat'),
                    ('FIN_PARCOURS', 'Fin de parcours'),
                    ('ADMISSION', 'Admission'),
                    ('CONFIRMATION', 'Confirmation de présence'),
                    ('TEST', 'Test disponible'),
                ],
                max_length=20,
            ),
        ),
    ]
