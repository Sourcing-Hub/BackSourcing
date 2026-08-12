from rest_framework import serializers
from .models import Candidature, ReponseFormulaire, Document
from utilisateurs.models import Utilisateur
from campagnes.models import Campagne

class CandidatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Utilisateur
        fields = ['id', 'email', 'first_name', 'last_name', 'telephone', 'sexe']

class CampagneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Campagne
        fields = ['id', 'nom', 'description']

class DocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Document
        fields = ['id', 'nom', 'chemin', 'typeMime', 'taille', 'dateDepot']

class ReponseFormulaireSerializer(serializers.ModelSerializer):
    champ_libelle = serializers.ReadOnlyField(source='champ.libelle')
    champ_type = serializers.ReadOnlyField(source='champ.type')
    
    class Meta:
        model = ReponseFormulaire
        fields = ['id', 'valeur', 'champ', 'champ_libelle', 'champ_type']

class CandidatureDetailSerializer(serializers.ModelSerializer):
    candidat = CandidatSerializer(source='utilisateur', read_only=True)
    campagne_details = CampagneSerializer(source='campagne', read_only=True)
    reponses = ReponseFormulaireSerializer(many=True, read_only=True)
    documents = DocumentSerializer(many=True, read_only=True)
    formation_nom = serializers.SerializerMethodField()
    cohorte_nom = serializers.SerializerMethodField()

    class Meta:
        model = Candidature
        fields = [
            'id', 'numero', 'dateSoumission', 'statut',
            'candidat', 'campagne', 'campagne_details',
            'formation_nom', 'cohorte_nom',
            'reponses', 'documents'
        ]

    def get_formation_nom(self, obj):
        return obj.campagne.cohorte.formation.nom if obj.campagne.cohorte else None

    def get_cohorte_nom(self, obj):
        return obj.campagne.cohorte.nom if obj.campagne.cohorte else None

class CandidatureListSerializer(serializers.ModelSerializer):
    candidat_nom = serializers.SerializerMethodField()
    candidat_email = serializers.SerializerMethodField()
    campagne_nom = serializers.ReadOnlyField(source='campagne.nom')
    formation_nom = serializers.SerializerMethodField()

    class Meta:
        model = Candidature
        fields = [
            'id', 'numero', 'dateSoumission', 'statut',
            'candidat_nom', 'candidat_email', 'campagne_nom', 'formation_nom'
        ]

    def get_candidat_nom(self, obj):
        return f"{obj.utilisateur.first_name} {obj.utilisateur.last_name}" if obj.utilisateur else ""

    def get_candidat_email(self, obj):
        return obj.utilisateur.email if obj.utilisateur else ""

    def get_formation_nom(self, obj):
        return obj.campagne.cohorte.formation.nom if obj.campagne.cohorte else None
