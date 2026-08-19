from rest_framework import serializers
from django.db import transaction
from utilisateurs.models import Utilisateur, NomRole
from .models import AffectationEvaluateur, Etape, ParticipationEtape, Session

class EtapeSerializer(serializers.ModelSerializer):
    """Sérialiseur pour faire la consultation des étapes d'évaluation."""
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
        for coach_key in ('coachTechnique', 'coachMotivation'):
            coach = data.get(coach_key)
            if coach and not (coach.a_role(NomRole.EVALUATEUR) or coach.est_equipe_pedagogique()):
                raise serializers.ValidationError({coach_key: 'Le coach doit être un évaluateur ou un membre de l’équipe pédagogique.'})
        return data

    @transaction.atomic
    def create(self, validated_data):
        jours = validated_data.pop('jours')
        coach_technique = validated_data.pop('coachTechnique', None)
        coach_motivation = validated_data.pop('coachMotivation', None)
        etape = validated_data.pop('etape')
        sessions = []
        for jour in jours:
            for creneau in jour['creneaux']:
                session = Session.objects.create(
                    etape=etape, date=jour['date'], heureDebut=creneau['heureDebut'],
                    heureFin=creneau['heureFin'], capacite=creneau['capacite'], **validated_data,
                )
                if coach_technique:
                    AffectationEvaluateur.objects.create(evaluateur=coach_technique, session=session, roleEncadrement='TECHNIQUE')
                if coach_motivation:
                    AffectationEvaluateur.objects.create(evaluateur=coach_motivation, session=session, roleEncadrement='MOTIVATION')
                sessions.append(session)
        return sessions
