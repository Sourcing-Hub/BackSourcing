import uuid
from django.db import models
from django.conf import settings

class StatutCandidature(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente'
    EN_COURS = 'EN_COURS', 'En cours'
    TERMINEE = 'TERMINEE', 'Terminée'

class Candidature(models.Model):
    """Représente le dossier de candidature d'un utilisateur pour une campagne."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.CharField(max_length=50, unique=True)
    dateSoumission = models.DateTimeField(auto_now_add=True)
    statut = models.CharField(max_length=20, choices=StatutCandidature.choices, default=StatutCandidature.EN_ATTENTE)

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='candidatures')
    campagne = models.ForeignKey('campagnes.Campagne', on_delete=models.CASCADE, related_name='candidatures')

    def __str__(self):
        return f"Candidature {self.numero} - {self.utilisateur}"

class ReponseFormulaire(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    valeur = models.TextField(blank=True, null=True)

    candidature = models.ForeignKey(Candidature, on_delete=models.CASCADE, related_name='reponses')
    champ = models.ForeignKey('formulaires.ChampFormulaire', on_delete=models.CASCADE, related_name='reponses')

    def __str__(self):
        return f"Réponse à {self.champ.libelle} pour {self.candidature.numero}"

class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=255)
    chemin = models.FileField(upload_to='documents_candidature/')
    typeMime = models.CharField(max_length=100)
    taille = models.BigIntegerField()
    dateDepot = models.DateTimeField(auto_now_add=True)

    candidature = models.ForeignKey(Candidature, on_delete=models.CASCADE, related_name='documents')

    def __str__(self):
        return self.nom
