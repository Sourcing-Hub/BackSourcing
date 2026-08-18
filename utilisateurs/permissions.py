"""
Permissions personnalisées par rôle pour SourcingHub.
Chaque classe vérifie que l'utilisateur est authentifié ET possède le rôle requis.
"""
from rest_framework.permissions import BasePermission
from .models import NomRole


class EstAdministrateur(BasePermission):
    """Autorise uniquement les administrateurs."""
    message = "Accès réservé aux administrateurs."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.est_admin()
        )


class EstEquipePedagogique(BasePermission):
    """Autorise uniquement les membres de l'équipe pédagogique authentifiés."""
    message = "Accès réservé à l'équipe pédagogique."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.est_equipe_pedagogique()
        )


class EstEvaluateur(BasePermission):
    """Autorise uniquement les évaluateurs."""
    message = "Accès réservé aux évaluateurs."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.est_evaluateur()
        )


class EstGestionProjet(BasePermission):
    """Autorise uniquement l'équipe gestion de projet."""
    message = "Accès réservé à l'équipe de gestion de projet."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.est_equipe_gestion_projet()
        )


class EstCandidat(BasePermission):
    """Autorise uniquement les candidats."""
    message = "Accès réservé aux candidats."

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.est_candidat()
        )


class EstAdminOuPedagogie(BasePermission):
    """Autorise les administrateurs, l'équipe pédagogique ou l'équipe de gestion de projet."""
    message = "Accès réservé aux administrateurs, à l'équipe pédagogique et à l'équipe de gestion de projet."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return (
            request.user.est_admin()
            or request.user.est_equipe_pedagogique()
            or request.user.est_equipe_gestion_projet()
        )


class EstPersonnel(BasePermission):
    """Autorise tout le personnel (sauf candidats) : admin, pédagogie, évaluateur, gestion."""
    message = "Accès réservé au personnel."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return not request.user.est_candidat()


class EstAdminOuGestionProjet(BasePermission):
    """Autorise les administrateurs OU l'équipe de gestion de projet."""
    message = "Accès réservé aux administrateurs et à l'équipe de gestion de projet."

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return request.user.est_admin() or request.user.est_equipe_gestion_projet()
