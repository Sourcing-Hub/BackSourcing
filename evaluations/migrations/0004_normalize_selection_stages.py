from django.db import migrations


def normalize_selection_stages(apps, schema_editor):
    Etape = apps.get_model('evaluations', 'Etape')
    Session = apps.get_model('evaluations', 'Session')
    ParticipationEtape = apps.get_model('evaluations', 'ParticipationEtape')

    for cohorte_id in Etape.objects.values_list('cohorte_id', flat=True).distinct():
        etapes = Etape.objects.filter(cohorte_id=cohorte_id)
        technique = etapes.filter(nom='Entretien technique').first()
        motivation = etapes.filter(nom='Entretien de motivation').first()
        combinee = etapes.filter(nom='Entretien technique et motivation').first()

        cible = combinee or technique or motivation
        if cible:
            cible.nom = 'Entretien technique et motivation'
            cible.ordre = 2
            cible.save(update_fields=['nom', 'ordre'])

            for ancienne_etape in (technique, motivation):
                if ancienne_etape and ancienne_etape.pk != cible.pk:
                    Session.objects.filter(etape_id=ancienne_etape.pk).update(etape_id=cible.pk)
                    ParticipationEtape.objects.filter(etape_id=ancienne_etape.pk).update(etape_id=cible.pk)
                    ancienne_etape.delete()

        if not Etape.objects.filter(cohorte_id=cohorte_id, nom='Entretien final').exists():
            Etape.objects.create(cohorte_id=cohorte_id, nom='Entretien final', ordre=3)


class Migration(migrations.Migration):
    dependencies = [
        ('evaluations', '0003_affectationevaluateur_role_encadrement'),
    ]

    operations = [
        migrations.RunPython(normalize_selection_stages, migrations.RunPython.noop),
    ]
