"""
Sérialiseurs pour les Campagnes et les Formulaires.
"""
from rest_framework import serializers
from .models import Formation, Cohorte, Campagne, StatutCampagne


# ─────────────────────────────────────────────
# Formation
# ─────────────────────────────────────────────

class FormationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Formation
        fields = ['id', 'nom', 'description', 'dateDebut', 'dateFin']

    def validate(self, data):
        debut = data.get('dateDebut')
        fin   = data.get('dateFin')
        if debut and fin and debut >= fin:
            raise serializers.ValidationError(
                {"dateFin": "La date de fin doit être postérieure à la date de début."}
            )
        return data


# ─────────────────────────────────────────────
# Cohorte
# ─────────────────────────────────────────────

class CohorteSerializer(serializers.ModelSerializer):
    formation_nom = serializers.SerializerMethodField()

    class Meta:
        model = Cohorte
        fields = ['id', 'nom', 'dateDebut', 'dateFin', 'formation', 'formation_nom']

    def get_formation_nom(self, obj):
        return obj.formation.nom if obj.formation else None

    def validate(self, data):
        debut = data.get('dateDebut')
        fin   = data.get('dateFin')
        if debut and fin and debut >= fin:
            raise serializers.ValidationError(
                {"dateFin": "La date de fin doit être postérieure à la date de début."}
            )
        return data


# ─────────────────────────────────────────────
# Campagne
# ─────────────────────────────────────────────

class CampagneListeSerializer(serializers.ModelSerializer):
    """Sérialiseur léger pour la liste des campagnes."""
    cohorte_nom   = serializers.SerializerMethodField()
    formation_nom = serializers.SerializerMethodField()
    a_formulaire  = serializers.SerializerMethodField()

    class Meta:
        model = Campagne
        fields = [
            'id', 'nom', 'description', 'dateOuverture', 'dateCloture',
            'statut', 'publiee', 'archivee',
            'cohorte', 'cohorte_nom', 'formation_nom',
            'a_formulaire', 'dateCreation',
        ]

    def get_cohorte_nom(self, obj):
        return obj.cohorte.nom if obj.cohorte else None

    def get_formation_nom(self, obj):
        return obj.cohorte.formation.nom if obj.cohorte and obj.cohorte.formation else None

    def get_a_formulaire(self, obj):
        return hasattr(obj, 'formulaire') and obj.formulaire is not None


class CampagneDetailSerializer(serializers.ModelSerializer):
    """Sérialiseur complet pour création et mise à jour."""
    cohorte_detail = CohorteSerializer(source='cohorte', read_only=True)

    class Meta:
        model = Campagne
        fields = [
            'id', 'nom', 'description',
            'dateOuverture', 'dateCloture',
            'statut', 'publiee', 'archivee',
            'cohorte', 'cohorte_detail',
            'dateCreation', 'dateModification',
        ]
        read_only_fields = ['id', 'statut', 'publiee', 'archivee', 'dateCreation', 'dateModification']

    def validate(self, data):
        ouverture = data.get('dateOuverture')
        cloture   = data.get('dateCloture')
        if ouverture and cloture and ouverture >= cloture:
            raise serializers.ValidationError(
                {"dateCloture": "La date de clôture doit être postérieure à la date d'ouverture."}
            )
        return data

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['creePar'] = request.user if request else None
        return super().create(validated_data)
