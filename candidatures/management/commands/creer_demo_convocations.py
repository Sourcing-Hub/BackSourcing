from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from campagnes.models import Campagne, Cohorte, Formation, StatutCampagne
from candidatures.models import Candidature, StatutCandidature
from evaluations.models import Etape, Session
from utilisateurs.models import NomRole, Role, Sexe, StatutUtilisateur, Utilisateur


NOMS = [
    ('Awa', 'Diop'), ('Moussa', 'Ndiaye'), ('Fatou', 'Fall'), ('Ibrahima', 'Sow'),
    ('Mariama', 'Ba'), ('Cheikh', 'Gueye'), ('Ndeye', 'Mbaye'), ('Saliou', 'Cissé'),
    ('Aminata', 'Kane'), ('Mamadou', 'Gueye'), ('Astou', 'Camara'), ('Babacar', 'Dieng'),
    ('Coumba', 'Sarr'), ('Alioune', 'Lo'), ('Rokhaya', 'Seck'), ('Malick', 'Ka'),
    ('Sokhna', 'Samb'), ('Pape', 'Niang'), ('Dieynaba', 'Wade'), ('Binta', 'Diouf'),
]


class Command(BaseCommand):
    help = 'Crée des candidats non assignés pour tester l écran Convocations.'

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        formation, _ = Formation.objects.get_or_create(nom='dev web IA')
        cohorte, _ = Cohorte.objects.get_or_create(
            nom='promotion 2025',
            defaults={'formation': formation, 'dateDebut': now.date(), 'dateFin': (now + timedelta(days=90)).date()},
        )
        if cohorte.formation_id != formation.id:
            cohorte.formation = formation
            cohorte.save(update_fields=['formation'])

        campagne, _ = Campagne.objects.get_or_create(
            nom='Campagne Convocations Démo 2025',
            defaults={
                'cohorte': cohorte,
                'description': 'Candidats de démonstration pour préparer les convocations.',
                'dateOuverture': now - timedelta(days=1),
                'dateCloture': now + timedelta(days=60),
                'statut': StatutCampagne.OUVERTE,
                'publiee': True,
            },
        )
        role = Role.objects.get(nom=NomRole.CANDIDAT)
        for index, (prenom, nom) in enumerate(NOMS, start=1):
            email = f'convocation.demo.{index:02d}@sourcing.local'
            user, _ = Utilisateur.objects.get_or_create(
                email=email,
                defaults={
                    'username': f'convocation_demo_{index:02d}',
                    'first_name': prenom,
                    'last_name': nom,
                    'telephone': f'77 100 {index:02d} {index:02d}',
                    'sexe': Sexe.FEMME if index % 2 else Sexe.HOMME,
                    'role': role,
                    'statut': StatutUtilisateur.ACTIF,
                    'compteActive': True,
                    'is_active': True,
                    'profilComplet': True,
                },
            )
            Candidature.objects.get_or_create(
                numero=f'CONVOC-2025-{index:03d}',
                defaults={'utilisateur': user, 'campagne': campagne, 'statut': StatutCandidature.EN_ATTENTE},
            )

        etape, _ = Etape.objects.get_or_create(
            cohorte=cohorte, ordre=1, defaults={'nom': "Réunion d'information"},
        )
        # Les créneaux sont disponibles pour l'affectation depuis l'écran Convocations.
        Session.objects.get_or_create(
            etape=etape, date=now.date(), heureDebut='09:00', heureFin='12:00',
            defaults={'lieu': 'Dakar Cité Keur Gorgui', 'localisation': 'Dakar', 'capacite': 20},
        )
        Session.objects.get_or_create(
            etape=etape, date=now.date(), heureDebut='14:00', heureFin='17:00',
            defaults={'lieu': 'Mermoz', 'localisation': 'Dakar', 'capacite': 20},
        )

        total = Candidature.objects.filter(campagne=campagne).count()
        self.stdout.write(self.style.SUCCESS(
            f'Convocations prêtes : {total} candidats disponibles pour {cohorte.nom}.',
        ))
