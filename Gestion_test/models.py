from django.db import models

class Test(models.Model):
    class StatusChoices(models.TextChoices):
        ACTIF = 'actif', 'Actif'
        INACTIF = 'inactif', 'Inactif'
        NOUVEAU = 'nouveau', 'Nouveau'

    nom = models.CharField(max_length=255, verbose_name="Nom du test")
   
    campagne_assossiée = models.CharField(max_length=255, verbose_name="Formation/Offre associée", blank=True, null=True)
    
    lien_ressource = models.URLField(max_length=500, blank=True, null=True, verbose_name="Lien de la ressource (URL)")
    
    fichier_ressource = models.FileField(upload_to='tests_resources/', blank=True, null=True, verbose_name="Fichier de ressource")
    
    description = models.TextField(verbose_name="Description / Consignes")
    
    statut = models.CharField(
        max_length=20, 
        choices=StatusChoices.choices, 
        default=StatusChoices.NOUVEAU, 
        verbose_name="Statut"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="Date de création")

    date_ouverture = models.DateTimeField()

    date_cloture = models.DateTimeField()

    def __str__(self):
        return f"{self.nom} ({self.get_statut_display()})"



class SoumissionTest(models.Model):

    nom_candidat = models.CharField(max_length=100)

    email_candidat = models.EmailField()

    fichier_test = models.FileField(upload_to='soumissions/')
    
    # Date et heure de l'upload
    date_soumission = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Soumission de {self.nom_candidat} - {self.date_soumission.strftime('%d/%m/%Y')}"