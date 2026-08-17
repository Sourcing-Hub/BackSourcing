from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from campagnes.models import Campagne, Cohorte, Formation, StatutCampagne
from candidatures.models import Candidature, StatutCandidature
from evaluations.models import AffectationCandidat, Etape, ParticipationEtape, Session, StatutEtape, StatutPresence
from utilisateurs.models import NomRole, Role, Sexe, StatutUtilisateur, Utilisateur


NOMS = [
    ('Awa', 'Diop'), ('Moussa', 'Ndiaye'), ('Fatou', 'Fall'), ('Ibrahima', 'Sow'),
    ('Mariama', 'Ba'), ('Cheikh', 'Diallo'), ('Khady', 'Sarr'), ('Ousmane', 'Faye'),
    ('Aminata', 'Kane'), ('Mamadou', 'Gueye'), ('Ndeye', 'Sy'), ('Seydou', 'Thiam'),
    ('Astou', 'Camara'), ('Babacar', 'Cisse'), ('Coumba', 'Dieng'), ('Alioune', 'Lo'),
    ('Rokhaya', 'Mbaye'), ('Malick', 'Seck'), ('Sokhna', 'Ka'), ('Pape', 'Toure'),
    ('Dieynaba', 'Samb'), ('Abdou', 'Niang'), ('Mame', 'Wade'), ('Binta', 'Gning'), ('Lamine', 'Diouf'),
]


class Command(BaseCommand):
    help = 'Crée un jeu de démonstration complet pour les convocations et l’émargement.'

    @transaction.atomic
    def handle(self, *args, **options):
        now = timezone.now()
        formation, _ = Formation.objects.get_or_create(nom='Développeur Web — Démo')
        cohorte, _ = Cohorte.objects.get_or_create(
            nom='Promotion Démo 2026', formation=formation,
            defaults={'dateDebut': now.date(), 'dateFin': (now + timedelta(days=90)).date()},
        )
        campagne, _ = Campagne.objects.get_or_create(
            nom='Campagne Démo Émargement 2026', cohorte=cohorte,
            defaults={
                'description': 'Jeu de données de démonstration.', 'dateOuverture': now - timedelta(days=1),
                'dateCloture': now + timedelta(days=60), 'statut': StatutCampagne.OUVERTE, 'publiee': True,
            },
        )
        info, _ = Etape.objects.get_or_create(cohorte=cohorte, ordre=1, defaults={'nom': "Réunion d'information"})
        technique, _ = Etape.objects.get_or_create(cohorte=cohorte, ordre=2, defaults={'nom': 'Entretien technique et motivation'})
        Etape.objects.get_or_create(cohorte=cohorte, ordre=3, defaults={'nom': 'Entretien final'})
        session_info, _ = Session.objects.get_or_create(
            etape=info, date=(now + timedelta(days=1)).date(), heureDebut='09:00', heureFin='12:00',
            defaults={'lieu': 'Salle Démo A', 'localisation': 'Dakar', 'capacite': 20},
        )
        Session.objects.get_or_create(
            etape=technique, date=(now + timedelta(days=3)).date(), heureDebut='10:00', heureFin='13:00',
            defaults={'lieu': 'Salle Démo B', 'localisation': 'Dakar', 'capacite': 15},
        )

        role = Role.objects.get(nom=NomRole.CANDIDAT)
        candidatures = []
        for index, (prenom, nom) in enumerate(NOMS, start=1):
            email = f'candidat.test.{index:02d}@sourcing.local'
            user, _ = Utilisateur.objects.get_or_create(
                email=email,
                defaults={
                    'username': f'candidat_test_{index:02d}', 'first_name': prenom, 'last_name': nom,
                    'telephone': f'77 000 {index:02d} {index:02d}', 'sexe': Sexe.FEMME if index % 2 else Sexe.HOMME,
                    'role': role, 'statut': StatutUtilisateur.ACTIF, 'compteActive': True, 'is_active': True, 'profilComplet': True,
                },
            )
            candidature, _ = Candidature.objects.get_or_create(
                utilisateur=user, campagne=campagne,
                defaults={'numero': f'DEMO-2026-{index:03d}', 'statut': StatutCandidature.EN_ATTENTE},
            )
            candidatures.append(candidature)

        for index, candidature in enumerate(candidatures[:12], start=1):
            participation, _ = ParticipationEtape.objects.get_or_create(
                candidature=candidature, etape=info, defaults={'statut': StatutEtape.EN_COURS},
            )
            if participation.statut == StatutEtape.EN_ATTENTE:
                participation.statut = StatutEtape.EN_COURS
                participation.save(update_fields=['statut'])
            affectation, _ = AffectationCandidat.objects.get_or_create(participation_etape=participation, defaults={'session': session_info})
            if index <= 6:
                affectation.statutPresence = StatutPresence.PRESENT
                affectation.dateEmargement = now
                affectation.save(update_fields=['statutPresence', 'dateEmargement'])

        self.stdout.write(self.style.SUCCESS(
            f'Démo prête : {len(candidatures)} candidatures, {session_info.affectations_candidats.count()} convocations '
            f'pour la session du {session_info.date} ({session_info.affectations_candidats.filter(statutPresence=StatutPresence.PRESENT).count()} présents).',
        ))
