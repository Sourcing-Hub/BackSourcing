"""
Commande personnalisée pour créer les 5 rôles de la plateforme SourcingHub.

Usage :
    python manage.py creer_roles
"""
from django.core.management.base import BaseCommand
from utilisateurs.models import Role, NomRole


class Command(BaseCommand):
    help = "Crée les 5 rôles de la plateforme SourcingHub en base de données."

    def handle(self, *args, **options):
        roles_definitions = [
            {
                'nom': NomRole.CANDIDAT,
                'description': 'Candidat soumettant une candidature à une campagne de recrutement.',
            },
            {
                'nom': NomRole.ADMINISTRATEUR,
                'description': 'Administrateur de la plateforme. Gère les utilisateurs et la configuration générale.',
            },
            {
                'nom': NomRole.EVALUATEUR,
                'description': "Évaluateur participant aux sessions d'entretien et d'évaluation des candidats.",
            },
            {
                'nom': NomRole.EQUIPE_PEDAGOGIQUE,
                'description': "Membre de l'équipe pédagogique. Gère les évaluateurs et le parcours de sélection.",
            },
            {
                'nom': NomRole.EQUIPE_GESTION_PROJET,
                'description': "Membre de l'équipe de gestion de projet. Suit l'avancement des campagnes.",
            },
        ]

        creés = 0
        existants = 0

        for role_def in roles_definitions:
            role, created = Role.objects.get_or_create(
                nom=role_def['nom'],
                defaults={'description': role_def['description']},
            )
            if created:
                creés += 1
                self.stdout.write(self.style.SUCCESS(f"  [OK] Role cree : {role.nom}"))
            else:
                existants += 1
                self.stdout.write(self.style.WARNING(f"  [--] Role existant : {role.nom}"))

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Initialisation terminée : {creés} rôle(s) créé(s), {existants} déjà existant(s)."
            )
        )
