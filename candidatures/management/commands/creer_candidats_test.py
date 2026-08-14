from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from campagnes.models import Campagne, Cohorte, StatutCampagne
from candidatures.models import Candidature
from utilisateurs.models import NomRole, Role, Sexe, StatutUtilisateur, Utilisateur


TEST_CANDIDATES = [
    ('Awa', 'Diop'), ('Moussa', 'Ndiaye'), ('Fatou', 'Fall'), ('Ibrahima', 'Sow'),
    ('Mariama', 'Ba'), ('Cheikh', 'Diallo'), ('Khady', 'Sarr'), ('Ousmane', 'Faye'),
    ('Aminata', 'Kane'), ('Mamadou', 'Gueye'), ('Ndeye', 'Sy'), ('Seydou', 'Thiam'),
    ('Astou', 'Camara'), ('Babacar', 'Cisse'), ('Coumba', 'Dieng'), ('Alioune', 'Lo'),
    ('Rokhaya', 'Mbaye'), ('Malick', 'Seck'), ('Sokhna', 'Ka'), ('Pape', 'Toure'),
    ('Dieynaba', 'Samb'), ('Abdou', 'Niang'), ('Mame', 'Wade'), ('Binta', 'Gning'),
    ('Lamine', 'Diouf'),
]


class Command(BaseCommand):
    help = 'Crée des candidats fictifs et leurs candidatures pour tester les convocations.'

    def add_arguments(self, parser):
        parser.add_argument('--cohorte', default='p12', help='Nom de la cohorte cible (défaut : p12).')
        parser.add_argument('--nombre', type=int, default=25, help='Nombre de candidats à créer, jusqu’à 25.')

    @transaction.atomic
    def handle(self, *args, **options):
        nombre = options['nombre']
        if not 1 <= nombre <= len(TEST_CANDIDATES):
            raise CommandError(f'Le nombre doit être compris entre 1 et {len(TEST_CANDIDATES)}.')

        try:
            cohorte = Cohorte.objects.get(nom=options['cohorte'])
        except Cohorte.DoesNotExist as error:
            raise CommandError(f"La cohorte « {options['cohorte']} » est introuvable.") from error

        role, _ = Role.objects.get_or_create(nom=NomRole.CANDIDAT)
        now = timezone.now()
        campagne, _ = Campagne.objects.get_or_create(
            nom=f'Campagne de test — {cohorte.nom}',
            cohorte=cohorte,
            defaults={
                'description': 'Données de démonstration pour les convocations.',
                'dateOuverture': now - timedelta(days=1),
                'dateCloture': now + timedelta(days=60),
                'statut': StatutCampagne.OUVERTE,
                'publiee': True,
            },
        )

        comptes_crees = 0
        candidatures_creees = 0
        for index, (prenom, nom) in enumerate(TEST_CANDIDATES[:nombre], start=1):
            email = f'candidat.test.{index:02d}@sourcing.local'
            utilisateur, compte_cree = Utilisateur.objects.get_or_create(
                email=email,
                defaults={
                    'username': f'candidat_test_{index:02d}',
                    'first_name': prenom,
                    'last_name': nom,
                    'telephone': f'77 000 {index:02d} {index:02d}',
                    'sexe': Sexe.FEMME if index % 2 else Sexe.HOMME,
                    'role': role,
                    'statut': StatutUtilisateur.ACTIF,
                    'compteActive': True,
                    'is_active': True,
                    'profilComplet': True,
                },
            )
            _, candidature_creee = Candidature.objects.get_or_create(
                utilisateur=utilisateur,
                campagne=campagne,
                defaults={'numero': f'TEST-{cohorte.nom.upper()}-{index:03d}'},
            )
            comptes_crees += int(compte_cree)
            candidatures_creees += int(candidature_creee)

        self.stdout.write(self.style.SUCCESS(
            f'{candidatures_creees} candidature(s) créée(s) ({comptes_crees} nouveau(x) compte(s)) '
            f'pour « {cohorte.nom} ». Total de test : {Candidature.objects.filter(campagne=campagne).count()}.',
        ))
