import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class StatutEtape(models.TextChoices):
    EN_ATTENTE = 'EN_ATTENTE', 'En attente'
    EN_COURS = 'EN_COURS', 'En cours'
    REUSSIE = 'REUSSIE', 'Réussie'
    ECHOUEE = 'ECHOUEE', 'Échouée'
    ABSENT = 'ABSENT', 'Absent'
    ANNULEE = 'ANNULEE', 'Annulée'


class StatutPresence(models.TextChoices):
    A_ATTENDRE = 'A_ATTENDRE', 'En attente de pointage'
    PRESENT = 'PRESENT', 'Présent'
    ABSENT = 'ABSENT', 'Absent'

class TypeDecision(models.TextChoices):
    ADMIS = 'ADMIS', 'Admis'
    REFUSE = 'REFUSE', 'Refusé'
    EN_ATTENTE = 'EN_ATTENTE', 'En attente'

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
    statutPresence = models.CharField(max_length=20, choices=StatutPresence.choices, default=StatutPresence.A_ATTENDRE)
    dateEmargement = models.DateTimeField(blank=True, null=True)
    tokenConfirmation = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    dateConfirmation = models.DateTimeField(blank=True, null=True)
    
    participation_etape = models.OneToOneField(ParticipationEtape, on_delete=models.CASCADE, related_name='affectation_session')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='affectations_candidats')

class AffectationEvaluateur(models.Model):
    class RoleEncadrement(models.TextChoices):
        TECHNIQUE = 'TECHNIQUE', 'Encadreur technique'
        MOTIVATION = 'MOTIVATION', 'Encadreur motivation'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dateAffectation = models.DateTimeField(auto_now_add=True)
    roleEncadrement = models.CharField(max_length=20, choices=RoleEncadrement.choices, default=RoleEncadrement.TECHNIQUE)

    evaluateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='affectations_sessions')
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='affectations_evaluateurs')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['evaluateur', 'session', 'roleEncadrement'], name='affectation_evaluateur_role_unique'),
        ]

class Question(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contenu = models.TextField()
    type = models.CharField(max_length=30, choices=TypeQuestion.choices)
    baremeMax = models.DecimalField(max_digits=5, decimal_places=2)
    ordre = models.IntegerField()
    
    cohorte = models.ForeignKey('campagnes.Cohorte', on_delete=models.CASCADE, related_name='questions')

    class Meta:
        ordering = ['ordre']

    def _has_validated_answers(self):
        return self.evaluations.filter(validee=True).exists() # pyright: ignore[reportAttributeAccessIssue]

    def save(self, *args, **kwargs):
        if self.pk and self._has_validated_answers():
            ancienne = Question.objects.get(pk=self.pk)
            champs_verrouilles = ('contenu', 'type', 'baremeMax', 'cohorte_id')
            if any(getattr(ancienne, champ) != getattr(self, champ) for champ in champs_verrouilles):
                raise ValidationError("Cette question ne peut plus être modifiée car elle possède des réponses validées.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self._has_validated_answers():
            raise ValidationError("Cette question ne peut plus être supprimée car elle possède des réponses validées.")
        return super().delete(*args, **kwargs)

class Evaluation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.DecimalField(max_digits=5, decimal_places=2)
    reponse = models.TextField(blank=True, null=True)
    commentaire = models.TextField(blank=True, null=True)
    dateEvaluation = models.DateTimeField(auto_now_add=True)
    validee = models.BooleanField(default=False)

    evaluateur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='evaluations_donnees')
    participation = models.ForeignKey(ParticipationEtape, on_delete=models.CASCADE, related_name='evaluations')
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='evaluations')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['participation', 'question'], name='evaluation_unique_par_question_candidat'),
        ]

    def save(self, *args, **kwargs):
        if self.pk and Evaluation.objects.filter(pk=self.pk, validee=True).exists():
            raise ValidationError("Cette réponse est validée et ne peut plus être modifiée.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.validee or (self.pk and Evaluation.objects.filter(pk=self.pk, validee=True).exists()):
            raise ValidationError("Cette réponse est validée et ne peut plus être supprimée.")
        return super().delete(*args, **kwargs)

class Decision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=20, choices=TypeDecision.choices)
    motif = models.TextField(blank=True, null=True)
    dateDecision = models.DateTimeField(auto_now_add=True)
    
    candidature = models.OneToOneField('candidatures.Candidature', on_delete=models.CASCADE, related_name='decision_finale')


class TypeChoixQCM(models.TextChoices):
    CHOIX_UNIQUE = 'CHOIX_UNIQUE', 'Choix unique'
    CHOIX_MULTIPLE = 'CHOIX_MULTIPLE', 'Choix multiple'


class StatutPassageTest(models.TextChoices):
    EN_COURS = 'EN_COURS', 'En cours'
    SOUMIS = 'SOUMIS', 'Soumis'
    EXPIRE = 'EXPIRE', 'Expiré'


class TestQCM(models.Model):
    """Test QCM créé par l'Équipe Pédagogique rattaché à une Étape (Étape 3 - Test)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    titre = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    dureeMinutes = models.PositiveIntegerField(default=30, help_text="Durée maximale du test en minutes")
    baremeTotal = models.DecimalField(max_digits=5, decimal_places=2, default=20.00)
    notePassage = models.DecimalField(max_digits=5, decimal_places=2, default=10.00, help_text="Note minimale pour valider l'étape")
    estPublie = models.BooleanField(default=False)
    dateCreation = models.DateTimeField(auto_now_add=True)
    
    etape = models.ForeignKey(Etape, on_delete=models.CASCADE, related_name='tests_qcm')
    creePar = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='tests_crees')

    class Meta:
        ordering = ['-dateCreation']

    def __str__(self):
        return f"QCM: {self.titre} ({self.etape.nom})"


class QuestionQCM(models.Model):
    """Question individuelle d'un test QCM."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    intitule = models.TextField()
    explication = models.TextField(blank=True, null=True, help_text="Explication de la réponse affichée après évaluation")
    typeQuestion = models.CharField(max_length=20, choices=TypeChoixQCM.choices, default=TypeChoixQCM.CHOIX_UNIQUE)
    points = models.DecimalField(max_digits=5, decimal_places=2, default=1.00)
    ordre = models.IntegerField(default=1)

    test = models.ForeignKey(TestQCM, on_delete=models.CASCADE, related_name='questions')

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return f"Q{self.ordre}: {self.intitule[:50]}"


class OptionQCM(models.Model):
    """Proposition de réponse pour une question QCM."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    texte = models.TextField()
    estCorrecte = models.BooleanField(default=False)
    ordre = models.IntegerField(default=1)

    question = models.ForeignKey(QuestionQCM, on_delete=models.CASCADE, related_name='options')

    class Meta:
        ordering = ['ordre']

    def __str__(self):
        return f"Option {self.ordre} ({'Vrai' if self.estCorrecte else 'Faux'})"


class PassageTestQCM(models.Model):
    """Session d'un candidat passant un test QCM."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dateDebut = models.DateTimeField(auto_now_add=True)
    dateFin = models.DateTimeField(blank=True, null=True)
    scoreObtenu = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    statut = models.CharField(max_length=20, choices=StatutPassageTest.choices, default=StatutPassageTest.EN_COURS)
    estAdmis = models.BooleanField(default=False)

    participation = models.OneToOneField(ParticipationEtape, on_delete=models.CASCADE, related_name='passage_test_qcm')
    test = models.ForeignKey(TestQCM, on_delete=models.CASCADE, related_name='passages')

    def __str__(self):
        return f"Passage de {self.participation.candidature.numero} au QCM {self.test.titre}"


class ReponseCandidatQCM(models.Model):
    """Réponse(s) sélectionnée(s) par le candidat pour une question."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    passage = models.ForeignKey(PassageTestQCM, on_delete=models.CASCADE, related_name='reponses')
    question = models.ForeignKey(QuestionQCM, on_delete=models.CASCADE, related_name='reponses_candidats')
    optionsChoisies = models.ManyToManyField(OptionQCM, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['passage', 'question'], name='reponse_unique_par_question_passage')
        ]

