import uuid
from django.db import models
from django.conf import settings

class StatutEtape(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente'
    EN_COURS = 'EN_COURS', 'En cours'
    REUSSIE = 'REUSSIE', 'Réussie'
    ECHOUEE = 'ECHOUEE', 'Échouée'
    ABSENT = 'ABSENT', 'Absent'
    ANNULEE = 'ANNULEE', 'Annulée'

class TypeDecision(models.TextChoices):
    ADMISSION = 'ADMISSION', 'Admission'
    NON_ADMISSION = 'NON_ADMISSION', 'Non admission'

class TypeQuestion(models.TextChoices):
    TECHNIQUE = 'TECHNIQUE', 'Technique'
    SOFT_SKILLS_MOTIVATION = 'SOFT_SKILLS_MOTIVATION', 'Soft skills / Motivation'

class Etape(models.Model):
    """Modèle représentant une étape du processus d'évaluation/recrutement d'une cohorte."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=255)
    ordre = models.IntegerField()
    
    cohorte = models.ForeignKey('campagnes.Cohorte', on_delete=models.CASCADE, related_name='etapes')

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return f"{self.nom} (Cohorte: {self.cohorte.nom})"

class ParticipationEtape(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    statut = models.CharField(max_length=20, choices=StatutEtape.choices, default=StatutEtape.EN_ATTENTE)
    dateEntree = models.DateTimeField(auto_now_add=True)
    dateSortie = models.DateTimeField(blank=True, null=True)
    motif = models.TextField(blank=True, null=True)

    candidature = models.ForeignKey('candidatures.Candidature', on_delete=models.CASCADE, related_name='participations')
    etape = models.ForeignKey(Etape, on_delete=models.CASCADE, related_name='participations')

    def __str__(self):
        return f"Participation de {self.candidature.numero} à {self.etape.nom}"

class Session(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    date = models.DateField()
    heureDebut = models.TimeField()
    heureFin = models.TimeField()
    lieu = models.CharField(max_length=255, blank=True, null=True)
    localisation = models.CharField(max_length=255, blank=True, null=True)
    capacite = models.IntegerField()

    etape = models.ForeignKey(Etape, on_delete=models.CASCADE, related_name='sessions')

    def __str__(self):
        return f"Session du {self.date} pour {self.etape.nom}"

class AffectationCandidat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dateAffectation = models.DateTimeField(auto_now_add=True)
    
    participation_etape = models.OneToOneField(ParticipationEtape, on_delete=models.CASCADE, related_name='affectation_session')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='affectations_candidats')

class AffectationEvaluateur(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dateAffectation = models.DateTimeField(auto_now_add=True)

    evaluateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='affectations_sessions')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='affectations_evaluateurs')

class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contenu = models.TextField()
    type = models.CharField(max_length=30, choices=TypeQuestion.choices)
    baremeMax = models.DecimalField(max_digits=5, decimal_places=2)
    ordre = models.IntegerField()
    
    cohorte = models.ForeignKey('campagnes.Cohorte', on_delete=models.CASCADE, related_name='questions')

    class Meta:
        ordering = ['ordre']

class Evaluation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.DecimalField(max_digits=5, decimal_places=2)
    commentaire = models.TextField(blank=True, null=True)
    dateEvaluation = models.DateTimeField(auto_now_add=True)
    validee = models.BooleanField(default=False)

    evaluateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='evaluations_donnees')
    participation = models.ForeignKey(ParticipationEtape, on_delete=models.CASCADE, related_name='evaluations')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='evaluations')

class Decision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=20, choices=TypeDecision.choices)
    motif = models.TextField(blank=True, null=True)
    dateDecision = models.DateTimeField(auto_now_add=True)
    
    candidature = models.OneToOneField('candidatures.Candidature', on_delete=models.CASCADE, related_name='decision_finale')
