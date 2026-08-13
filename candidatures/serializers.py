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
    """Sérialiseur pour les fichiers joints aux candidatures."""
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
    candidat_compte_active = serializers.BooleanField(source='utilisateur.compteActive', read_only=True)
    campagne_nom = serializers.ReadOnlyField(source='campagne.nom')
    formation_nom = serializers.SerializerMethodField()
    cohorte_nom = serializers.SerializerMethodField()
    etape_actuelle = serializers.SerializerMethodField()

    class Meta:
        model = Candidature
        fields = [
            'id', 'numero', 'dateSoumission', 'statut',
            'candidat_nom', 'candidat_email', 'candidat_compte_active',
            'campagne_nom', 'formation_nom', 'cohorte_nom', 'etape_actuelle'
        ]

    def get_candidat_nom(self, obj):
        return f"{obj.utilisateur.first_name} {obj.utilisateur.last_name}" if obj.utilisateur else ""

    def get_candidat_email(self, obj):
        return obj.utilisateur.email if obj.utilisateur else ""

    def get_formation_nom(self, obj):
        return obj.campagne.cohorte.formation.nom if obj.campagne.cohorte else None

    def get_cohorte_nom(self, obj):
        return obj.campagne.cohorte.nom if obj.campagne.cohorte else None

    def get_etape_actuelle(self, obj):
        # Récupérer les participations de la candidature triées par l'ordre de l'étape
        participations = obj.participations.all()
        if not participations:
            return {
                "nom": "Dossier",
                "statut": "EN_ATTENTE",
                "label": "Dossier soumis (en attente)"
            }
        
        # Ordonner en python pour éviter les requêtes N+1 si déjà préchargées
        ordered_parts = sorted(participations, key=lambda p: p.etape.ordre)
        
        # 1. Éliminé si une étape est échouée, absent ou annulée
        pour_elimination = next((p for p in ordered_parts if p.statut in ['ECHOUEE', 'ABSENT', 'ANNULEE']), None)
        if pour_elimination:
            return {
                "nom": pour_elimination.etape.nom,
                "statut": pour_elimination.statut,
                "label": f"Éliminé - {pour_elimination.etape.nom} ({pour_elimination.get_statut_display()})"
            }
            
        # 2. En cours
        pour_en_cours = next((p for p in ordered_parts if p.statut == 'EN_COURS'), None)
        if pour_en_cours:
            return {
                "nom": pour_en_cours.etape.nom,
                "statut": pour_en_cours.statut,
                "label": f"En cours - {pour_en_cours.etape.nom}"
            }
            
        # 3. Prochaine étape en attente
        pour_en_attente = next((p for p in ordered_parts if p.statut == 'EN_ATTENTE'), None)
        if pour_en_attente:
            return {
                "nom": pour_en_attente.etape.nom,
                "statut": pour_en_attente.statut,
                "label": f"À venir - {pour_en_attente.etape.nom}"
            }
            
        # 4. Si tout est réussi
        pour_reussie = next((p for p in reversed(ordered_parts) if p.statut == 'REUSSIE'), None)
        if pour_reussie:
            return {
                "nom": pour_reussie.etape.nom,
                "statut": 'REUSSIE',
                "label": "Réussie - Toutes étapes validées"
            }
            
        return {
            "nom": "Dossier",
            "statut": "EN_ATTENTE",
            "label": "Dossier soumis"
        }
