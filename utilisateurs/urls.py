from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    ConnexionView,
    DeconnexionView,
    ActivationCompteView,
    DemandeReinitMotDePasseView,
    ConfirmationReinitMotDePasseView,
    MonProfilView,
    ChangementMotDePasseView,
    CreationPersonnelView,
    CreationEvaluateurView,
    ListeUtilisateursView,
    UtilisateurQrCodeView,
)

urlpatterns = [
    # ─── Authentification ───
    path('auth/connexion/', ConnexionView.as_view(), name='auth-connexion'),
    path('auth/deconnexion/', DeconnexionView.as_view(), name='auth-deconnexion'),
    path('auth/rafraichir/', TokenRefreshView.as_view(), name='auth-rafraichir-token'),
    path('auth/activer/', ActivationCompteView.as_view(), name='auth-activation'),
    path('auth/reinit-mdp/', DemandeReinitMotDePasseView.as_view(), name='auth-reinit-mdp'),
    path('auth/reinit-mdp/confirmer/', ConfirmationReinitMotDePasseView.as_view(), name='auth-reinit-mdp-confirmer'),

    # ─── Utilisateurs ───
    path('utilisateurs/', ListeUtilisateursView.as_view(), name='utilisateurs-liste'),
    path('utilisateurs/mon-profil/', MonProfilView.as_view(), name='utilisateurs-mon-profil'),
    path('utilisateurs/changer-mdp/', ChangementMotDePasseView.as_view(), name='utilisateurs-changer-mdp'),
    path('utilisateurs/creer-personnel/', CreationPersonnelView.as_view(), name='utilisateurs-creer-personnel'),
    path('utilisateurs/creer-evaluateur/', CreationEvaluateurView.as_view(), name='utilisateurs-creer-evaluateur'),
    path('utilisateurs/<uuid:pk>/qr-code/', UtilisateurQrCodeView.as_view(), name='utilisateur-qr-code'),
]
