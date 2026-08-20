import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


# ─────────────────────────────────────────────
# Enumerations
# ─────────────────────────────────────────────

class Sexe(models.TextChoices):
    HOMME = 'HOMME', 'Homme'
    FEMME = 'FEMME', 'Femme'


class StatutUtilisateur(models.TextChoices):
    ACTIF = 'ACTIF', 'Actif'
    INACTIF = 'INACTIF', 'Inactif'


# ─────────────────────────────────────────────
# Noms des rôles (constantes)
# ─────────────────────────────────────────────

class NomRole:
    CANDIDAT = 'Candidat'
    ADMINISTRATEUR = 'Administrateur'
    EVALUATEUR = 'evaluateur'
    EQUIPE_PEDAGOGIQUE = 'equipe pedagogique'
    EQUIPE_GESTION_PROJET = 'Équipe Gestion de Projet'

    TOUS = [
        CANDIDAT,
        ADMINISTRATEUR,
        EVALUATEUR,
        EQUIPE_PEDAGOGIQUE,
        EQUIPE_GESTION_PROJET,
    ]


# ─────────────────────────────────────────────
# Modèle Role
# ─────────────────────────────────────────────

class Role(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Rôle'
        verbose_name_plural = 'Rôles'

    def __str__(self):
        return self.nom


# ─────────────────────────────────────────────
# Custom QuerySet / Helper Methods
# ─────────────────────────────────────────────

class UtilisateurManager(models.Manager):
    """Manager personnalisé pour filtrer les utilisateurs actifs et par rôle."""
    def actifs(self):
        return self.filter(is_active=True, compteActive=True)



class Utilisateur(AbstractUser):
    """
    Modèle utilisateur personnalisé (Custom User Model) étendant AbstractUser.
    Gère les rôles, statuts d'activation et métadonnées de profil.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Champs personnels
    telephone = models.CharField(max_length=20, blank=True, null=True)
    sexe = models.CharField(max_length=10, choices=Sexe.choices, blank=True, null=True)
    statut = models.CharField(
        max_length=20,
        choices=StatutUtilisateur.choices,
        default=StatutUtilisateur.INACTIF,
    )
    compteActive = models.BooleanField(default=False)
    profilComplet = models.BooleanField(default=False)

    # Rôle
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='utilisateurs',
    )

    # Token d'activation du compte (pour les invitations par email)
    tokenActivation = models.UUIDField(default=uuid.uuid4, null=True, blank=True)
    tokenExpiration = models.DateTimeField(null=True, blank=True)

    # Timestamps
    dateCreation = models.DateTimeField(auto_now_add=True)
    dateModification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'

    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.role})"

    def a_role(self, nom_role: str) -> bool:
        """Vérifie si l'utilisateur possède le rôle spécifié."""
        return self.role is not None and self.role.nom == nom_role

    def est_admin(self) -> bool:
        return self.a_role(NomRole.ADMINISTRATEUR)

    def est_evaluateur(self) -> bool:
        return self.a_role(NomRole.EVALUATEUR)

    def est_equipe_pedagogique(self) -> bool:
        return self.a_role(NomRole.EQUIPE_PEDAGOGIQUE)

    def est_equipe_gestion_projet(self) -> bool:
        return self.a_role(NomRole.EQUIPE_GESTION_PROJET)

    def est_candidat(self) -> bool:
        return self.a_role(NomRole.CANDIDAT)

    def token_activation_valide(self) -> bool:
        """Vérifie que le token d'activation n'est pas expiré."""
        if not self.tokenExpiration:
            return False
        return timezone.now() < self.tokenExpiration

    def generer_token_activation(self):
        """Génère un nouveau token d'activation et définit sa date d'expiration."""
        from django.conf import settings
        self.tokenActivation = uuid.uuid4()
        self.tokenExpiration = timezone.now() + timezone.timedelta(
            hours=getattr(settings, 'DELAI_ACTIVATION_TOKEN_HEURES', 48)
        )
        self.save(update_fields=['tokenActivation', 'tokenExpiration'])

    def activer_compte(self, mot_de_passe: str):
        """Active le compte et définit le mot de passe."""
        self.set_password(mot_de_passe)
        self.compteActive = True
        self.statut = StatutUtilisateur.ACTIF
        self.is_active = True
        self.tokenActivation = None
        self.tokenExpiration = None
        self.save(update_fields=[
            'password', 'compteActive', 'statut', 'is_active',
            'tokenActivation', 'tokenExpiration'
        ])
