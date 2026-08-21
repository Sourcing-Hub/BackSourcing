"""
Sérialiseurs pour la gestion des utilisateurs : authentification, activation,
création de comptes, modification du profil et des mots de passe.
"""
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import Utilisateur, Role, NomRole


# ─────────────────────────────────────────────
# JWT — Token personnalisé (inclut le rôle)
# ─────────────────────────────────────────────

class ConnexionTokenSerializer(TokenObtainPairSerializer):
    """
    Surcharge du serializer JWT pour injecter le rôle de l'utilisateur
    dans le payload du token.
    """
    username = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].required = False
        self.fields['username'].allow_blank = True
        self.fields['email'] = serializers.EmailField(required=False, allow_blank=True)

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['email'] = user.email
        token['nom'] = user.last_name
        token['prenom'] = user.first_name
        token['role'] = user.role.nom if user.role else None
        token['profilComplet'] = user.profilComplet
        return token

    def validate(self, attrs):
        # Accepte les deux formats: {username, password} et {email, password}.
        email = attrs.get('username') or attrs.get('email', '')
        password = attrs.get('password', '')
        if not email:
            raise serializers.ValidationError({"email": "L'email est obligatoire."})

        try:
            utilisateur = Utilisateur.objects.get(email=email)
        except Utilisateur.DoesNotExist:
            raise serializers.ValidationError("Identifiants incorrects.")

        if not utilisateur.compteActive:
            raise serializers.ValidationError("Ce compte n'a pas encore été activé.")

        user = authenticate(username=utilisateur.username, password=password)
        if not user:
            raise serializers.ValidationError("Identifiants incorrects.")

        # Remplace l'attribut 'username' pour que le parent fonctionne correctement
        attrs['username'] = utilisateur.username
        data = super().validate(attrs)
        data['role'] = utilisateur.role.nom if utilisateur.role else None
        data['profilComplet'] = utilisateur.profilComplet
        return data


# ─────────────────────────────────────────────
# Activation du compte (invitation)
# ─────────────────────────────────────────────

class ActivationCompteSerializer(serializers.Serializer):
    """Utilisé par le personnel invité pour activer son compte et choisir son mot de passe."""
    token = serializers.UUIDField()
    mot_de_passe = serializers.CharField(
        min_length=8, write_only=True, validators=[validate_password]
    )
    mot_de_passe_confirmation = serializers.CharField(min_length=8, write_only=True)

    def validate(self, data):
        if data['mot_de_passe'] != data['mot_de_passe_confirmation']:
            raise serializers.ValidationError(
                {"mot_de_passe_confirmation": "Les mots de passe ne correspondent pas."}
            )
        try:
            utilisateur = Utilisateur.objects.get(tokenActivation=data['token'])
        except Utilisateur.DoesNotExist:
            raise serializers.ValidationError({"token": "Token d'activation invalide."})

        if not utilisateur.token_activation_valide():
            raise serializers.ValidationError(
                {"token": "Ce lien d'activation a expiré. Veuillez contacter votre administrateur."}
            )

        data['utilisateur'] = utilisateur
        return data

    def save(self):
        utilisateur = self.validated_data['utilisateur']
        utilisateur.activer_compte(self.validated_data['mot_de_passe'])
        return utilisateur


# ─────────────────────────────────────────────
# Création de comptes par l'admin / la pédagogie
# ─────────────────────────────────────────────

class CreationPersonnelSerializer(serializers.Serializer):
    """
    Utilisé par l'administrateur pour créer un compte Personnel
    (Équipe Pédagogique ou Équipe Gestion de Projet).
    """
    email = serializers.EmailField()
    prenom = serializers.CharField(required=False, allow_blank=True, default='')
    nom = serializers.CharField(required=False, allow_blank=True, default='')
    role = serializers.ChoiceField(choices=[
        NomRole.EQUIPE_PEDAGOGIQUE,
        NomRole.EQUIPE_GESTION_PROJET,
        NomRole.EVALUATEUR,
        NomRole.ADMINISTRATEUR,
    ])

    def validate_email(self, valeur):
        if Utilisateur.objects.filter(email=valeur).exists():
            raise serializers.ValidationError("Un compte avec cet email existe déjà.")
        return valeur

    def validate_role(self, valeur):
        try:
            return Role.objects.get(nom=valeur)
        except Role.DoesNotExist:
            raise serializers.ValidationError(f"Le rôle « {valeur} » n'existe pas en base.")

    def create(self, validated_data):
        email = validated_data['email']
        role = validated_data['role']
        first_name = validated_data.get('prenom') or validated_data.get('first_name', '')
        last_name = validated_data.get('nom') or validated_data.get('last_name', '')

        utilisateur = Utilisateur.objects.create(
            email=email,
            username=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_active=False,
            compteActive=False,
        )
        utilisateur.generer_token_activation()
        return utilisateur


class CreationEvaluateurSerializer(serializers.Serializer):
    """
    Utilisé par l'équipe pédagogique pour créer un compte Évaluateur.
    """
    email = serializers.EmailField()
    prenom = serializers.CharField(required=False, allow_blank=True, default='')
    nom = serializers.CharField(required=False, allow_blank=True, default='')

    def validate_email(self, valeur):
        if Utilisateur.objects.filter(email=valeur).exists():
            raise serializers.ValidationError("Un compte avec cet email existe déjà.")
        return valeur

    def create(self, validated_data):
        email = validated_data['email']
        role = Role.objects.get(nom=NomRole.EVALUATEUR)
        first_name = validated_data.get('prenom') or validated_data.get('first_name', '')
        last_name = validated_data.get('nom') or validated_data.get('last_name', '')

        utilisateur = Utilisateur.objects.create(
            email=email,
            username=email,
            first_name=first_name,
            last_name=last_name,
            role=role,
            is_active=False,
            compteActive=False,
        )
        utilisateur.generer_token_activation()
        return utilisateur


# ─────────────────────────────────────────────
# Profil utilisateur
# ─────────────────────────────────────────────

class ProfilUtilisateurSerializer(serializers.ModelSerializer):
    role_nom = serializers.SerializerMethodField()

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'first_name', 'last_name',
            'telephone', 'sexe', 'statut',
            'compteActive', 'profilComplet', 'role_nom',
            'dateCreation', 'dateModification',
        ]
        read_only_fields = ['id', 'email', 'statut', 'compteActive', 'role_nom', 'dateCreation', 'dateModification']

    def get_role_nom(self, obj):
        return obj.role.nom if obj.role else None

    def validate_telephone(self, value):
        if value and len(value.strip()) < 8:
            raise serializers.ValidationError("Le numéro de téléphone doit comporter au moins 8 caractères.")
        return value

    def update(self, instance, validated_data):
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        # Marque le profil comme complet si nom + prénom + téléphone renseignés
        if instance.first_name and instance.last_name and instance.telephone:
            instance.profilComplet = True

        instance.save()
        return instance


# ─────────────────────────────────────────────
# Changement de mot de passe (utilisateur connecté)
# ─────────────────────────────────────────────

class ChangementMotDePasseSerializer(serializers.Serializer):
    ancien_mot_de_passe = serializers.CharField(write_only=True)
    nouveau_mot_de_passe = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    confirmation = serializers.CharField(write_only=True)

    def validate(self, data):
        utilisateur = self.context['request'].user
        if not utilisateur.check_password(data['ancien_mot_de_passe']):
            raise serializers.ValidationError(
                {"ancien_mot_de_passe": "L'ancien mot de passe est incorrect."}
            )
        if data['nouveau_mot_de_passe'] != data['confirmation']:
            raise serializers.ValidationError(
                {"confirmation": "Les mots de passe ne correspondent pas."}
            )
        return data

    def save(self):
        utilisateur = self.context['request'].user
        utilisateur.set_password(self.validated_data['nouveau_mot_de_passe'])
        utilisateur.save(update_fields=['password'])
        return utilisateur


# ─────────────────────────────────────────────
# Réinitialisation du mot de passe
# ─────────────────────────────────────────────

class DemandeReinitMotDePasseSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, valeur):
        try:
            return Utilisateur.objects.get(email=valeur)
        except Utilisateur.DoesNotExist:
            # On ne révèle pas si l'email existe ou non (sécurité)
            return None

    def save(self):
        return self.validated_data.get('email')


class ConfirmationReinitMotDePasseSerializer(serializers.Serializer):
    token = serializers.UUIDField()
    nouveau_mot_de_passe = serializers.CharField(
        write_only=True, validators=[validate_password]
    )
    confirmation = serializers.CharField(write_only=True)

    def validate(self, data):
        if data['nouveau_mot_de_passe'] != data['confirmation']:
            raise serializers.ValidationError(
                {"confirmation": "Les mots de passe ne correspondent pas."}
            )
        try:
            utilisateur = Utilisateur.objects.get(tokenActivation=data['token'])
        except Utilisateur.DoesNotExist:
            raise serializers.ValidationError({"token": "Token invalide."})

        if not utilisateur.token_activation_valide():
            raise serializers.ValidationError({"token": "Ce lien a expiré."})

        data['utilisateur'] = utilisateur
        return data

    def save(self):
        utilisateur = self.validated_data['utilisateur']
        utilisateur.activer_compte(self.validated_data['nouveau_mot_de_passe'])
        return utilisateur


# ─────────────────────────────────────────────
# Liste des utilisateurs (admin)
# ─────────────────────────────────────────────

class ListeUtilisateursSerializer(serializers.ModelSerializer):
    role_nom = serializers.SerializerMethodField()
    prenom = serializers.CharField(source='first_name', read_only=True)
    nom = serializers.CharField(source='last_name', read_only=True)

    class Meta:
        model = Utilisateur
        fields = [
            'id', 'email', 'first_name', 'last_name', 'prenom', 'nom',
            'telephone', 'statut', 'compteActive', 'profilComplet',
            'role_nom', 'dateCreation', 'is_active',
        ]

    def get_role_nom(self, obj):
        return obj.role.nom if obj.role else None
