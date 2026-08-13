import uuid
from django.db import models
from django.utils import timezone

# ─────────────────────────────────────────────
# Énumérations
# ─────────────────────────────────────────────

class StatutCampagne(models.TextChoices):
    BROUILLON  = 'BROUILLON',  'Brouillon'
    OUVERTE    = 'OUVERTE',    'Ouverte'
    FERMEE     = 'FERMEE',     'Fermée'


# ─────────────────────────────────────────────
# Formation
# ─────────────────────────────────────────────

class Formation(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom         = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True, null=True)
    dateDebut   = models.DateField(blank=True, null=True)
    dateFin     = models.DateField(blank=True, null=True)

    class Meta:
        verbose_name = 'Formation'
        verbose_name_plural = 'Formations'
        ordering = ['nom']

    def __str__(self):
        return self.nom


# ─────────────────────────────────────────────
# Cohorte
# ─────────────────────────────────────────────

class Cohorte(models.Model):
    id        = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom       = models.CharField(max_length=255)  # Unique par formation (voir unique_together)
    dateDebut = models.DateField(blank=True, null=True)
    dateFin   = models.DateField(blank=True, null=True)
    formation = models.ForeignKey(Formation, on_delete=models.CASCADE, related_name='cohortes')

    class Meta:
        verbose_name = 'Cohorte'
        verbose_name_plural = 'Cohortes'
        ordering = ['-dateDebut']
        unique_together = [('nom', 'formation')]  # P1 peut exister pour chaque formation

    def __str__(self):
        return f"{self.nom} — {self.formation.nom}"


# ─────────────────────────────────────────────
# Campagne
# ─────────────────────────────────────────────

class Campagne(models.Model):
    id            = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom           = models.CharField(max_length=255)
    description   = models.TextField(blank=True, null=True)
    dateOuverture = models.DateTimeField()
    dateCloture   = models.DateTimeField()
    statut        = models.CharField(
        max_length=20,
        choices=StatutCampagne.choices,
        default=StatutCampagne.BROUILLON,
    )
    # Rétrocompatibilité avec le diagramme original
    publiee  = models.BooleanField(default=False)
    archivee = models.BooleanField(default=False)

    cohorte     = models.ForeignKey(Cohorte, on_delete=models.CASCADE, related_name='campagnes')
    creePar     = models.ForeignKey(
        'utilisateurs.Utilisateur',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='campagnes_creees',
    )
    dateCreation    = models.DateTimeField(auto_now_add=True)
    dateModification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Campagne'
        verbose_name_plural = 'Campagnes'
        ordering = ['-dateCreation']

    def __str__(self):
        return self.nom

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        try:
            if hasattr(self, 'formulaire') and self.formulaire:
                form = self.formulaire
                expected_publie = self.est_ouverte()
                if form.publie != expected_publie:
                    form.publie = expected_publie
                    form.save(update_fields=['publie'])
        except Exception:
            pass

    # ── Actions métier ──────────────────────────────────────
    def est_ouverte(self) -> bool:
        now = timezone.now()
        return self.statut == StatutCampagne.OUVERTE and self.dateOuverture <= now <= self.dateCloture

    def ouvrir(self):
        has_form = False
        try:
            if hasattr(self, 'formulaire') and self.formulaire:
                has_form = True
        except Exception:
            pass

        if not has_form:
            from django.core.exceptions import ValidationError
            raise ValidationError("Impossible d'ouvrir cette campagne car aucun formulaire ne lui est associé.")

        self.statut  = StatutCampagne.OUVERTE
        self.publiee = True
        self.save(update_fields=['statut', 'publiee', 'dateModification'])

    def fermer(self):
        self.statut = StatutCampagne.FERMEE
        self.save(update_fields=['statut', 'dateModification'])
