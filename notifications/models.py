import uuid
from django.db import models
from django.conf import settings

class TypeNotification(models.TextChoices):
    ACTIVATION = 'ACTIVATION', 'Activation'
    CONVOCATION = 'CONVOCATION', 'Convocation'
    RESULTAT = 'RESULTAT', 'Résultat'
    FIN_PARCOURS = 'FIN_PARCOURS', 'Fin de parcours'
    ADMISSION = 'ADMISSION', 'Admission'

class StatutNotification(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente'
    ENVOYEE = 'ENVOYEE', 'Envoyée'
    ECHEC = 'ECHEC', 'Échec'

class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=20, choices=TypeNotification.choices)
    objet = models.CharField(max_length=255)
    contenu = models.TextField()
    statut = models.CharField(max_length=20, choices=StatutNotification.choices, default=StatutNotification.EN_ATTENTE)
    dateEnvoi = models.DateTimeField(auto_now_add=True)

    utilisateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    candidature = models.ForeignKey('candidatures.Candidature', on_delete=models.CASCADE, related_name='notifications', blank=True, null=True)

    def __str__(self):
        return self.objet
