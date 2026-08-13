"""
Vues (API endpoints) pour la gestion des utilisateurs.

Endpoints disponibles :
  Authentification (publics) :
    POST   /api/auth/connexion/           → Connexion JWT
    POST   /api/auth/deconnexion/         → Déconnexion (blacklist refresh token)
    GET    /api/auth/activer/<token>/     → Activation du compte par lien email
    POST   /api/auth/reinit-mdp/          → Demande de réinitialisation de mot de passe
    POST   /api/auth/reinit-mdp/confirmer/ → Confirmation et nouveau mot de passe

  Utilisateurs (authentifiés) :
    GET/PUT /api/utilisateurs/mon-profil/           → Consulter/modifier son propre profil
    PUT     /api/utilisateurs/changer-mdp/          → Changer son mot de passe
    POST    /api/utilisateurs/creer-personnel/      → Créer un compte personnel (admin only)
    POST    /api/utilisateurs/creer-evaluateur/     → Créer un compte évaluateur (pédagogie only)
    GET     /api/utilisateurs/                      → Lister tous les utilisateurs (admin only)
"""
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.exceptions import TokenError

from .models import Utilisateur
from .serializers import (
    ConnexionTokenSerializer,
    ActivationCompteSerializer,
    CreationPersonnelSerializer,
    CreationEvaluateurSerializer,
    ProfilUtilisateurSerializer,
    ChangementMotDePasseSerializer,
    DemandeReinitMotDePasseSerializer,
    ConfirmationReinitMotDePasseSerializer,
    ListeUtilisateursSerializer,
)
from .permissions import EstAdministrateur, EstEquipePedagogique
from .emails import (
    envoyer_email_invitation_personnel,
    envoyer_email_invitation_evaluateur,
    envoyer_email_reinitialisation_mdp,
)


# ─────────────────────────────────────────────
# AUTHENTIFICATION
# ─────────────────────────────────────────────

class ConnexionView(TokenObtainPairView):
    """
    POST /api/auth/connexion/
    Corps : { "username": "email@example.com", "password": "****" }
    Retourne : { access, refresh, role, profilComplet }
    """
    serializer_class = ConnexionTokenSerializer
    permission_classes = [AllowAny]


class DeconnexionView(APIView):
    """
    POST /api/auth/deconnexion/
    Corps : { "refresh": "<refresh_token>" }
    Blackliste le token de rafraîchissement pour invalider la session.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            token = RefreshToken(request.data.get('refresh'))
            token.blacklist()
        except TokenError:
            return Response(
                {"detail": "Token invalide ou déjà révoqué."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"detail": "Déconnexion réussie."},
            status=status.HTTP_205_RESET_CONTENT,
        )


class ActivationCompteView(APIView):
    """
    POST /api/auth/activer/
    Corps : { "token": "<uuid>", "mot_de_passe": "***", "mot_de_passe_confirmation": "***" }
    Active le compte du personnel ou de l'évaluateur invité.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ActivationCompteSerializer(data=request.data)
        if serializer.is_valid():
            utilisateur = serializer.save()
            return Response(
                {
                    "detail": "Votre compte a été activé avec succès. Vous pouvez maintenant vous connecter.",
                    "email": utilisateur.email,
                },
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DemandeReinitMotDePasseView(APIView):
    """
    POST /api/auth/reinit-mdp/
    Corps : { "email": "..." }
    Envoie un email de réinitialisation si l'email est connu.
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = DemandeReinitMotDePasseSerializer(data=request.data)
        if serializer.is_valid():
            utilisateur = serializer.save()
            if utilisateur:
                utilisateur.generer_token_activation()
                try:
                    envoyer_email_reinitialisation_mdp(utilisateur)
                except Exception:
                    pass  # Ne pas révéler l'erreur côté client
        # Même réponse que l'email existe ou non (sécurité anti-énumération)
        return Response(
            {"detail": "Si un compte correspond à cet email, un lien de réinitialisation a été envoyé."},
            status=status.HTTP_200_OK,
        )


class ConfirmationReinitMotDePasseView(APIView):
    """
    POST /api/auth/reinit-mdp/confirmer/
    Corps : { "token": "<uuid>", "nouveau_mot_de_passe": "***", "confirmation": "***" }
    """
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ConfirmationReinitMotDePasseSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Mot de passe réinitialisé avec succès."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# PROFIL
# ─────────────────────────────────────────────

class MonProfilView(APIView):
    """
    GET  /api/utilisateurs/mon-profil/ → Consulter son profil
    PUT  /api/utilisateurs/mon-profil/ → Mettre à jour son profil
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfilUtilisateurSerializer(request.user)
        return Response(serializer.data)

    def put(self, request):
        serializer = ProfilUtilisateurSerializer(
            request.user, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangementMotDePasseView(APIView):
    """
    PUT /api/utilisateurs/changer-mdp/
    Corps : { "ancien_mot_de_passe": "***", "nouveau_mot_de_passe": "***", "confirmation": "***" }
    """
    permission_classes = [IsAuthenticated]

    def put(self, request):
        serializer = ChangementMotDePasseSerializer(
            data=request.data, context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({"detail": "Mot de passe modifié avec succès."})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────
# GESTION DES COMPTES (admin / pédagogie)
# ─────────────────────────────────────────────

class CreationPersonnelView(APIView):
    """
    POST /api/utilisateurs/creer-personnel/
    Réservé à l'administrateur.
    Corps : { "email": "...", "role": "Équipe Pédagogique" | "Équipe Gestion de Projet" }
    """
    permission_classes = [EstAdministrateur]

    def post(self, request):
        serializer = CreationPersonnelSerializer(data=request.data)
        if serializer.is_valid():
            utilisateur = serializer.save()
            try:
                envoyer_email_invitation_personnel(utilisateur)
            except Exception as e:
                return Response(
                    {
                        "detail": "Compte créé, mais l'envoi de l'email a échoué.",
                        "erreur": str(e),
                    },
                    status=status.HTTP_201_CREATED,
                )
            return Response(
                {
                    "detail": f"Compte créé. Un email d'invitation a été envoyé à {utilisateur.email}.",
                    "email": utilisateur.email,
                    "role": utilisateur.role.nom,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CreationEvaluateurView(APIView):
    """
    POST /api/utilisateurs/creer-evaluateur/
    Réservé à l'équipe pédagogique.
    Corps : { "email": "..." }
    """
    permission_classes = [EstEquipePedagogique]

    def post(self, request):
        serializer = CreationEvaluateurSerializer(data=request.data)
        if serializer.is_valid():
            utilisateur = serializer.save()
            try:
                envoyer_email_invitation_evaluateur(utilisateur, createur=request.user)
            except Exception as e:
                return Response(
                    {
                        "detail": "Compte créé, mais l'envoi de l'email a échoué.",
                        "erreur": str(e),
                    },
                    status=status.HTTP_201_CREATED,
                )
            return Response(
                {
                    "detail": f"Compte évaluateur créé. Un email d'invitation a été envoyé à {utilisateur.email}.",
                    "email": utilisateur.email,
                },
                status=status.HTTP_201_CREATED,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ListeUtilisateursView(APIView):
    """
    GET /api/utilisateurs/
    Réservé à l'administrateur. Retourne la liste de tous les utilisateurs.
    """
    permission_classes = [EstAdministrateur]

    def get(self, request):
        role_filtre = request.query_params.get('role')
        qs = Utilisateur.objects.select_related('role').all().order_by('dateCreation')

        if role_filtre:
            qs = qs.filter(role__nom=role_filtre)

        serializer = ListeUtilisateursSerializer(qs, many=True)
        return Response(serializer.data)


class UtilisateurQrCodeView(APIView):
    """
    GET /api/utilisateurs/<uuid:pk>/qr-code/
    Génère dynamiquement un code QR d'identification pour l'utilisateur.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = request.user
        # Seul l'utilisateur lui-même ou les membres de l'équipe (admin/pedagogy/project) peuvent voir le code QR
        if not (user.id == pk or user.est_admin() or user.est_equipe_pedagogique() or user.est_equipe_gestion_projet()):
            return Response({"detail": "Non autorisé."}, status=status.HTTP_403_FORBIDDEN)

        try:
            target_user = Utilisateur.objects.get(pk=pk)
        except Utilisateur.DoesNotExist:
            return Response({"detail": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

        import qrcode
        from qrcode.image.pil import PilImage
        import io
        from django.http import HttpResponse
        from django.conf import settings

        frontend_url = getattr(settings, 'FRONTEND_URL', 'http://localhost:5173')
        qr_data = f"{frontend_url}/scan-candidat/{target_user.id}"

        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(qr_data)
        qr.make(fit=True)

        img = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white")
        
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        
        return HttpResponse(buffer.getvalue(), content_type="image/png")


class AdminUtilisateurDetailView(APIView):
    """
    PATCH  /api/utilisateurs/<uuid:pk>/ -> Bloquer / Débloquer ou modifier un utilisateur
    DELETE /api/utilisateurs/<uuid:pk>/ -> Supprimer définitivement un utilisateur
    """
    permission_classes = [EstAdministrateur]

    def patch(self, request, pk):
        try:
            user = Utilisateur.objects.get(pk=pk)
        except Utilisateur.DoesNotExist:
            return Response({"detail": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if user == request.user:
            return Response({"detail": "Vous ne pouvez pas modifier votre propre compte."}, status=status.HTTP_400_BAD_REQUEST)

        action = request.data.get('action')
        if action == 'bloquer':
            user.is_active = False
            user.statut = StatutUtilisateur.INACTIF
            user.save()
            return Response({"detail": "Compte bloqué avec succès."})
        elif action == 'debloquer':
            user.is_active = True
            user.statut = StatutUtilisateur.ACTIF
            user.save()
            return Response({"detail": "Compte débloqué avec succès."})

        serializer = ListeUtilisateursSerializer(user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            user = Utilisateur.objects.get(pk=pk)
        except Utilisateur.DoesNotExist:
            return Response({"detail": "Utilisateur introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if user == request.user:
            return Response({"detail": "Vous ne pouvez pas supprimer votre propre compte."}, status=status.HTTP_400_BAD_REQUEST)

        user.delete()
        return Response({"detail": "Utilisateur supprimé avec succès."}, status=status.HTTP_200_OK)
