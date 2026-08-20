import uuid
from django.db import models


# ─────────────────────────────────────────────
# Types de champs disponibles
# ─────────────────────────────────────────────

class TypeChamp(models.TextChoices):
    TEXTE             = 'TEXTE',             'Texte court'
    EMAIL             = 'EMAIL',             'Email'
    TELEPHONE         = 'TELEPHONE',         'Téléphone'
    DATE              = 'DATE',              'Date'
    NOMBRE            = 'NOMBRE',            'Nombre'
    LISTE_DEROULANTE  = 'LISTE_DEROULANTE',  'Liste déroulante'
    CHOIX_MULTIPLES   = 'CHOIX_MULTIPLES',   'Choix multiples'
    CASE_A_COCHER     = 'CASE_A_COCHER',     'Case à cocher'
    ZONE_TEXTE        = 'ZONE_TEXTE',        'Zone de texte'
    FICHIER           = 'FICHIER',           'Fichier'


# Types de champs qui nécessitent des options (liste / choix)
TYPES_AVEC_OPTIONS = {
    TypeChamp.LISTE_DEROULANTE,
    TypeChamp.CHOIX_MULTIPLES,
    TypeChamp.CASE_A_COCHER,
}


# ─────────────────────────────────────────────
# Formulaire
# ─────────────────────────────────────────────

class Formulaire(models.Model):
    """Représente le formulaire dynamique configuré pour une campagne de recrutement."""
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre            = models.CharField(max_length=255)
    description      = models.TextField(blank=True, null=True)
    publie           = models.BooleanField(default=False)
    dateCreation     = models.DateTimeField(auto_now_add=True)
    dateModification = models.DateTimeField(auto_now=True)

    # Un formulaire peut être lié à une campagne (1-to-1) OU à une étape
    campagne = models.OneToOneField(
        'campagnes.Campagne',
        on_delete=models.SET_NULL,
        related_name='formulaire',
        null=True, blank=True,
    )
    etape = models.ForeignKey(
        'evaluations.Etape',
        on_delete=models.SET_NULL,
        related_name='formulaires',
        null=True, blank=True,
    )

    creePar = models.ForeignKey(
        'utilisateurs.Utilisateur',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='formulaires_crees',
    )

    class Meta:
        verbose_name = 'Formulaire'
        verbose_name_plural = 'Formulaires'
        ordering = ['-dateCreation']

    def __str__(self):
        return self.titre

    def publier(self):
        """Publie le formulaire (le rend visible aux candidats)."""
        self.publie = True
        self.save(update_fields=['publie', 'dateModification'])

    def depublier(self):
        self.publie = False
        self.save(update_fields=['publie', 'dateModification'])

    def save(self, *args, **kwargs):
        if self.campagne:
            self.publie = self.campagne.est_ouverte()
        super().save(*args, **kwargs)

    def nombre_champs(self) -> int:
        return self.champs.count()


# ─────────────────────────────────────────────
# Champ de formulaire
# ─────────────────────────────────────────────

class ChampFormulaire(models.Model):
    id               = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libelle          = models.CharField(max_length=255)
    type             = models.CharField(max_length=30, choices=TypeChamp.choices)
    description      = models.CharField(max_length=512, blank=True, null=True,
                                        help_text="Texte d'aide affiché sous le champ")
    placeholderTexte = models.CharField(max_length=255, blank=True, null=True)
    obligatoire      = models.BooleanField(default=True)
    ordre            = models.IntegerField(default=0)

    # Règles de validation JSON (ex: {"min": 2, "max": 100, "pattern": "..."})
    regleValidation  = models.JSONField(blank=True, null=True,
                                        help_text='Règles de validation JSON : ex {"min": 2, "max": 100}')

    # Pour FICHIER : types MIME autorisés et taille max en Mo
    typesMimeAutorises = models.CharField(max_length=255, blank=True, null=True,
                                          help_text='Ex: .pdf,.docx')
    tailleMaxMo        = models.IntegerField(blank=True, null=True,
                                             help_text='Taille max en Mo')

    formulaire = models.ForeignKey(Formulaire, on_delete=models.CASCADE, related_name='champs')

    class Meta:
        ordering = ['ordre']
        verbose_name = 'Champ de formulaire'
        verbose_name_plural = 'Champs de formulaire'

    def __str__(self):
        return f"{self.libelle} ({self.get_type_display()})"

    def a_options(self) -> bool:
        return self.type in TYPES_AVEC_OPTIONS


# ─────────────────────────────────────────────
# Options d'un champ (liste / choix multiples / cases)
# ─────────────────────────────────────────────

class OptionChamp(models.Model):
    id     = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    libelle = models.CharField(max_length=255)
    valeur  = models.CharField(max_length=255, blank=True, null=True,
                               help_text='Valeur technique (optionnel, égale au libellé par défaut)')
    ordre  = models.IntegerField(default=0)

    champ = models.ForeignKey(ChampFormulaire, on_delete=models.CASCADE, related_name='options')

    class Meta:
        ordering = ['ordre']
        verbose_name = 'Option de champ'
        verbose_name_plural = 'Options de champ'

    def __str__(self):
        return self.libelle
