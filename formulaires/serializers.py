"""
Sérialiseurs pour les Formulaires dynamiques.
Gestion des champs, options, réorganisation et publication.
"""
from rest_framework import serializers
from .models import Formulaire, ChampFormulaire, OptionChamp, TYPES_AVEC_OPTIONS


# ─────────────────────────────────────────────
# Option de champ
# ─────────────────────────────────────────────

class OptionChampSerializer(serializers.ModelSerializer):
    class Meta:
        model = OptionChamp
        fields = ['id', 'libelle', 'valeur', 'ordre']


# ─────────────────────────────────────────────
# Champ de formulaire
# ─────────────────────────────────────────────

class ChampFormulaireSerializer(serializers.ModelSerializer):
    options = OptionChampSerializer(many=True, required=False)

    class Meta:
        model = ChampFormulaire
        fields = [
            'id', 'libelle', 'type', 'description', 'placeholderTexte',
            'obligatoire', 'ordre', 'regleValidation',
            'typesMimeAutorises', 'tailleMaxMo',
            'options',
        ]

    def validate(self, data):
        type_champ = data.get('type') or (self.instance.type if self.instance else None)
        options    = data.get('options', [])

        if type_champ in TYPES_AVEC_OPTIONS and not options and not self.instance:
            raise serializers.ValidationError(
                {"options": f"Le type « {type_champ} » requiert au moins une option."}
            )
        return data

    def create(self, validated_data):
        options_data = validated_data.pop('options', [])
        champ = ChampFormulaire.objects.create(**validated_data)
        for opt in options_data:
            OptionChamp.objects.create(champ=champ, **opt)
        return champ

    def update(self, instance, validated_data):
        options_data = validated_data.pop('options', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Si des options sont fournies, on remplace complètement
        if options_data is not None:
            instance.options.all().delete()
            for opt in options_data:
                OptionChamp.objects.create(champ=instance, **opt)

        return instance


# ─────────────────────────────────────────────
# Formulaire — Liste
# ─────────────────────────────────────────────

class FormulaireListeSerializer(serializers.ModelSerializer):
    nombre_champs = serializers.SerializerMethodField()
    campagne_nom  = serializers.SerializerMethodField()

    class Meta:
        model = Formulaire
        fields = [
            'id', 'titre', 'description', 'publie',
            'campagne', 'campagne_nom', 'nombre_champs',
            'dateCreation', 'dateModification',
        ]

    def get_nombre_champs(self, obj):
        return obj.champs.count()

    def get_campagne_nom(self, obj):
        return obj.campagne.nom if obj.campagne else None


# ─────────────────────────────────────────────
# Formulaire — Détail complet (avec champs)
# ─────────────────────────────────────────────

class FormulaireDetailSerializer(serializers.ModelSerializer):
    champs                 = ChampFormulaireSerializer(many=True, read_only=True)
    campagne_nom           = serializers.SerializerMethodField()
    campagne_est_ouverte   = serializers.SerializerMethodField()

    class Meta:
        model = Formulaire
        fields = [
            'id', 'titre', 'description', 'publie',
            'campagne', 'campagne_nom', 'campagne_est_ouverte',
            'champs',
            'dateCreation', 'dateModification',
        ]
        read_only_fields = ['id', 'publie', 'dateCreation', 'dateModification']

    def get_campagne_nom(self, obj):
        return obj.campagne.nom if obj.campagne else None

    def get_campagne_est_ouverte(self, obj):
        return obj.campagne.est_ouverte() if obj.campagne else True

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['creePar'] = request.user if request else None
        return super().create(validated_data)


# ─────────────────────────────────────────────
# Réorganisation des champs (drag & drop)
# ─────────────────────────────────────────────

class ReorganisationChampsSerializer(serializers.Serializer):
    """
    Reçoit une liste ordonnée d'IDs de champs et met à jour leur `ordre`.
    Exemple : { "ordre": ["<uuid1>", "<uuid2>", ...] }
    """
    ordre = serializers.ListField(
        child=serializers.UUIDField(),
        allow_empty=False,
    )

    def validate_ordre(self, valeur):
        formulaire = self.context['formulaire']
        ids_champs = set(str(c.id) for c in formulaire.champs.all())
        for uid in valeur:
            if str(uid) not in ids_champs:
                raise serializers.ValidationError(
                    f"L'identifiant {uid} ne correspond à aucun champ de ce formulaire."
                )
        return valeur

    def save(self):
        formulaire = self.context['formulaire']
        for index, champ_id in enumerate(self.validated_data['ordre']):
            ChampFormulaire.objects.filter(id=champ_id, formulaire=formulaire).update(ordre=index)
        return formulaire


# ─────────────────────────────────────────────
# Association formulaire ↔ campagne
# ─────────────────────────────────────────────

class AssociationCampagneSerializer(serializers.Serializer):
    campagne_id = serializers.UUIDField()

    def validate_campagne_id(self, valeur):
        from campagnes.models import Campagne
        try:
            campagne = Campagne.objects.get(id=valeur)
        except Campagne.DoesNotExist:
            raise serializers.ValidationError("Campagne introuvable.")

        # Vérifier qu'aucun formulaire n'est déjà lié à cette campagne
        if hasattr(campagne, 'formulaire') and campagne.formulaire is not None:
            if campagne.formulaire != self.context.get('formulaire'):
                raise serializers.ValidationError(
                    "Cette campagne possède déjà un formulaire associé."
                )
        return campagne

    def save(self):
        formulaire = self.context['formulaire']
        formulaire.campagne = self.validated_data['campagne_id']
        formulaire.save()
        return formulaire
