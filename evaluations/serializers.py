from rest_framework import serializers
from django.db import transaction
from utilisateurs.models import Utilisateur, NomRole
from .models import (
    AffectationEvaluateur, Etape, ParticipationEtape, Question, Session,
    TestQCM, QuestionQCM, OptionQCM, PassageTestQCM, ReponseCandidatQCM, StatutPassageTest
)


class EtapeSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la consultation des étapes d'évaluation."""
    class Meta:
        model = Etape
        fields = ['id', 'nom', 'ordre']

class ParticipationEtapeSerializer(serializers.ModelSerializer):
    etape_detail = EtapeSerializer(source='etape', read_only=True)
    
    class Meta:
        model = ParticipationEtape
        fields = ['id', 'statut', 'dateEntree', 'dateSortie', 'motif', 'etape', 'etape_detail']
        read_only_fields = ['id', 'dateEntree', 'dateSortie', 'etape']


class PlanningSerializer(serializers.ModelSerializer):
    """Représentation d'une session planifiée pour une étape de sélection."""
    etape_nom = serializers.CharField(source='etape.nom', read_only=True)
    cohorte_nom = serializers.CharField(source='etape.cohorte.nom', read_only=True)
    formation_nom = serializers.CharField(source='etape.cohorte.formation.nom', read_only=True)

    class Meta:
        model = Session
        fields = [
            'id', 'date', 'heureDebut', 'heureFin', 'lieu', 'localisation', 'capacite',
            'etape', 'etape_nom', 'cohorte_nom', 'formation_nom',
        ]
        read_only_fields = ['id', 'etape_nom', 'cohorte_nom', 'formation_nom']

    def validate(self, data):
        heure_debut = data.get('heureDebut', getattr(self.instance, 'heureDebut', None))
        heure_fin = data.get('heureFin', getattr(self.instance, 'heureFin', None))
        if heure_debut and heure_fin and heure_debut >= heure_fin:
            raise serializers.ValidationError({
                'heureFin': "L'heure de fin doit être postérieure à l'heure de début."
            })
        capacite = data.get('capacite', getattr(self.instance, 'capacite', None))
        if capacite is not None and capacite <= 0:
            raise serializers.ValidationError({'capacite': 'La capacité doit être supérieure à zéro.'})
        return data


class PlanningConfigurationSerializer(serializers.Serializer):
    """Crée en une fois les sessions correspondant aux jours et créneaux configurés."""
    etape = serializers.PrimaryKeyRelatedField(queryset=Etape.objects.all())
    lieu = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    localisation = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=255)
    encadreur = serializers.PrimaryKeyRelatedField(queryset=Utilisateur.objects.all(), required=False, allow_null=True)
    coachTechnique = serializers.PrimaryKeyRelatedField(queryset=Utilisateur.objects.all(), required=False, allow_null=True)
    coachMotivation = serializers.PrimaryKeyRelatedField(queryset=Utilisateur.objects.all(), required=False, allow_null=True)
    jours = serializers.ListField(child=serializers.DictField(), allow_empty=False)

    def validate_jours(self, jours):
        for jour in jours:
            if not jour.get('date'):
                raise serializers.ValidationError('Chaque jour doit contenir une date.')
            creneaux = jour.get('creneaux', [])
            if not creneaux:
                raise serializers.ValidationError('Chaque jour doit contenir au moins un créneau.')
            for creneau in creneaux:
                try:
                    debut, fin, capacite = creneau['heureDebut'], creneau['heureFin'], int(creneau['capacite'])
                except (KeyError, TypeError, ValueError):
                    raise serializers.ValidationError('Chaque créneau doit avoir ses horaires et sa capacité.')
                if debut >= fin:
                    raise serializers.ValidationError("L'heure de fin doit être postérieure à l'heure de début.")
                if capacite <= 0:
                    raise serializers.ValidationError('La capacité doit être supérieure à zéro.')
        return jours

    def validate(self, data):
        for encadreur_key in ('encadreur', 'coachTechnique', 'coachMotivation'):
            user = data.get(encadreur_key)
            if user and (user.est_candidat() or (user.role and user.role.nom == NomRole.CANDIDAT)):
                raise serializers.ValidationError({encadreur_key: "L'encadreur ne peut pas être un candidat."})
        return data

    @transaction.atomic
    def create(self, validated_data):
        jours = validated_data.pop('jours')
        encadreur = validated_data.pop('encadreur', None) or validated_data.pop('coachTechnique', None)
        coach_motivation = validated_data.pop('coachMotivation', None)
        etape = validated_data.pop('etape')
        sessions = []
        for jour in jours:
            for creneau in jour['creneaux']:
                session = Session.objects.create(
                    etape=etape, date=jour['date'], heureDebut=creneau['heureDebut'],
                    heureFin=creneau['heureFin'], capacite=creneau['capacite'], **validated_data,
                )
                if encadreur:
                    AffectationEvaluateur.objects.create(evaluateur=encadreur, session=session)
                if coach_motivation:
                    AffectationEvaluateur.objects.create(evaluateur=coach_motivation, session=session, roleEncadrement='MOTIVATION')
                sessions.append(session)
        return sessions


# ============================================================================
# SÉRIALISEURS QCM (ÉQUIPE PÉDAGOGIQUE & CANDIDATS)
# ============================================================================

class OptionQCMSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptionQCM
        fields = ['id', 'texte', 'estCorrecte', 'ordre']


class QuestionQCMSerializer(serializers.ModelSerializer):
    options = OptionQCMSerializer(many=True, required=False)

    class Meta:
        model = QuestionQCM
        fields = ['id', 'intitule', 'explication', 'typeQuestion', 'points', 'ordre', 'options']


class TestQCMSerializer(serializers.ModelSerializer):
    questions = QuestionQCMSerializer(many=True, required=False)
    etape_nom = serializers.CharField(source='etape.nom', read_only=True)
    cohorte_nom = serializers.CharField(source='etape.cohorte.nom', read_only=True)
    formation_nom = serializers.CharField(source='etape.cohorte.formation.nom', read_only=True)
    nombreQuestions = serializers.IntegerField(source='questions.count', read_only=True)

    class Meta:
        model = TestQCM
        fields = [
            'id', 'titre', 'description', 'dureeMinutes', 'baremeTotal', 'notePassage',
            'estPublie', 'dateCreation', 'etape', 'etape_nom', 'cohorte_nom', 'formation_nom',
            'creePar', 'nombreQuestions', 'questions'
        ]
        read_only_fields = ['id', 'dateCreation', 'creePar', 'etape_nom', 'cohorte_nom', 'formation_nom', 'nombreQuestions']

    @transaction.atomic
    def create(self, validated_data):
        questions_data = validated_data.pop('questions', [])
        validated_data['creePar'] = self.context['request'].user
        test = TestQCM.objects.create(**validated_data)
        
        for q_idx, q_data in enumerate(questions_data, start=1):
            options_data = q_data.pop('options', [])
            q_data['ordre'] = q_data.get('ordre', q_idx)
            question = QuestionQCM.objects.create(test=test, **q_data)
            for o_idx, o_data in enumerate(options_data, start=1):
                o_data['ordre'] = o_data.get('ordre', o_idx)
                OptionQCM.objects.create(question=question, **o_data)
                
        return test

    @transaction.atomic
    def update(self, instance, validated_data):
        questions_data = validated_data.pop('questions', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if questions_data is not None:
            instance.questions.all().delete()
            for q_idx, q_data in enumerate(questions_data, start=1):
                options_data = q_data.pop('options', [])
                q_data['ordre'] = q_data.get('ordre', q_idx)
                question = QuestionQCM.objects.create(test=instance, **q_data)
                for o_idx, o_data in enumerate(options_data, start=1):
                    o_data['ordre'] = o_data.get('ordre', o_idx)
                    OptionQCM.objects.create(question=question, **o_data)

        return instance


class OptionCandidatQCMSerializer(serializers.ModelSerializer):
    """Option sans le champ estCorrecte pour le candidat."""
    class Meta:
        model = OptionQCM
        fields = ['id', 'texte', 'ordre']


class QuestionCandidatQCMSerializer(serializers.ModelSerializer):
    """Question sans l'explication ni estCorrecte pour le candidat."""
    options = OptionCandidatQCMSerializer(many=True, read_only=True)

    class Meta:
        model = QuestionQCM
        fields = ['id', 'intitule', 'typeQuestion', 'points', 'ordre', 'options']


class TestCandidatQCMSerializer(serializers.ModelSerializer):
    """Test avec questions filtrées pour le candidat."""
    questions = QuestionCandidatQCMSerializer(many=True, read_only=True)

    class Meta:
        model = TestQCM
        fields = ['id', 'titre', 'description', 'dureeMinutes', 'baremeTotal', 'questions']


class ReponseSoumissionSerializer(serializers.Serializer):
    questionId = serializers.UUIDField()
    optionIds = serializers.ListField(child=serializers.UUIDField(), allow_empty=True)


class SoumissionTestQCMSerializer(serializers.Serializer):
    reponses = ReponseSoumissionSerializer(many=True)

class QuestionSerializer(serializers.ModelSerializer):
    contenu = serializers.CharField(required=False)
    question = serializers.CharField(source='contenu', required=False)
    baremeMax = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    maxScore = serializers.DecimalField(source='baremeMax', max_digits=5, decimal_places=2, required=False)
    cohorte_nom = serializers.CharField(source='cohorte.nom', read_only=True)
    formation_nom = serializers.CharField(source='cohorte.formation.nom', read_only=True)
    verrouillee = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            'id', 'contenu', 'question', 'type', 'baremeMax', 'maxScore',
            'ordre', 'cohorte', 'cohorte_nom', 'formation_nom', 'verrouillee',
        ]
        read_only_fields = ['id', 'cohorte_nom', 'formation_nom', 'verrouillee']

    def get_verrouillee(self, obj):
        return obj.evaluations.filter(validee=True).exists()

    def validate(self, data):
        if 'contenu' not in data and self.initial_data.get('question') is not None:
            data['contenu'] = self.initial_data.get('question')
        if 'baremeMax' not in data and self.initial_data.get('maxScore') is not None:
            data['baremeMax'] = self.initial_data.get('maxScore')
        if not data.get('contenu'):
            raise serializers.ValidationError({'question': 'La question est requise.'})
        if data.get('baremeMax') is None:
            raise serializers.ValidationError({'maxScore': 'Le barème est requis.'})
        return data


class EvaluatorCandidateSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    firstName = serializers.CharField()
    lastName = serializers.CharField()
    email = serializers.EmailField()
    phone = serializers.CharField(allow_blank=True, allow_null=True)
    formation = serializers.CharField(allow_blank=True)
    promotion = serializers.CharField(allow_blank=True)
    candidatureId = serializers.UUIDField()
    numero = serializers.CharField()
    statut = serializers.CharField()


class EvaluatorInterviewSerializer(serializers.Serializer):
    id = serializers.CharField()
    candidateId = serializers.UUIDField()
    candidateName = serializers.CharField()
    type = serializers.CharField()
    typeLabel = serializers.CharField()
    date = serializers.DateField()
    startTime = serializers.TimeField()
    endTime = serializers.TimeField()
    location = serializers.CharField(allow_blank=True, allow_null=True)
    status = serializers.CharField()
    statusLabel = serializers.CharField()
    participationId = serializers.UUIDField()
    candidatureId = serializers.UUIDField()
    sessionId = serializers.UUIDField()


class EvaluatorEvaluationSerializer(serializers.Serializer):
    type = serializers.CharField()
    questions = serializers.ListField(read_only=True)
    answers = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False)
    notes = serializers.DictField(required=False)
    score = serializers.FloatField(required=False, allow_null=True)
    averageScore = serializers.FloatField(required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    status = serializers.CharField(read_only=True)
    validated = serializers.BooleanField(read_only=True)
