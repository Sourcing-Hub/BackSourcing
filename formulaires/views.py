"""
Vues pour la gestion des Formulaires dynamiques.

Endpoints :
  Formulaires :
    GET    /api/formulaires/                            → Liste
    POST   /api/formulaires/                            → Créer un formulaire
    GET    /api/formulaires/<id>/                       → Détail (avec tous les champs)
    PUT    /api/formulaires/<id>/                       → Modifier le titre/description
    DELETE /api/formulaires/<id>/                       → Supprimer
    POST   /api/formulaires/<id>/publier/               → Publier le formulaire
    POST   /api/formulaires/<id>/depublier/             → Dépublier
    POST   /api/formulaires/<id>/associer-campagne/     → Associer à une campagne
    POST   /api/formulaires/<id>/reorganiser-champs/    → Réorganiser les champs (drag & drop)
    GET    /api/formulaires/<id>/previsualiser/         → Prévisualisation publique

  Champs :
    POST   /api/formulaires/<id>/champs/                → Ajouter un champ
    PUT    /api/formulaires/champs/<champ_id>/          → Modifier un champ
    DELETE /api/formulaires/champs/<champ_id>/          → Supprimer un champ

  Options :
    POST   /api/formulaires/champs/<champ_id>/options/  → Ajouter une option
    DELETE /api/formulaires/options/<option_id>/        → Supprimer une option
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny

from utilisateurs.permissions import EstAdminOuPedagogie, EstPersonnel
from .models import Formulaire, ChampFormulaire, OptionChamp
from .serializers import (
    FormulaireListeSerializer,
    FormulaireDetailSerializer,
    ChampFormulaireSerializer,
    OptionChampSerializer,
    ReorganisationChampsSerializer,
    AssociationCampagneSerializer,
)


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _get_formulaire(pk):
    try:
        return Formulaire.objects.prefetch_related('champs__options').get(pk=pk)
    except Formulaire.DoesNotExist:
        return None


def _get_champ(champ_id):
    try:
        return ChampFormulaire.objects.select_related('formulaire').get(pk=champ_id)
    except ChampFormulaire.DoesNotExist:
        return None


# ─────────────────────────────────────────────
# Formulaires — CRUD
# ─────────────────────────────────────────────

class FormulaireListeView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def get(self, request):
        qs = Formulaire.objects.select_related('campagne').prefetch_related('champs').all()
        return Response(FormulaireListeSerializer(qs, many=True).data)

    def post(self, request):
        s = FormulaireDetailSerializer(data=request.data, context={'request': request})
        if s.is_valid():
            formulaire = s.save()
            return Response(FormulaireDetailSerializer(formulaire).data, status=status.HTTP_201_CREATED)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


class FormulaireDetailView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def get(self, request, pk):
        obj = _get_formulaire(pk)
        if not obj:
            return Response({"detail": "Formulaire introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return Response(FormulaireDetailSerializer(obj).data)

    def put(self, request, pk):
        obj = _get_formulaire(pk)
        if not obj:
            return Response({"detail": "Formulaire introuvable."}, status=status.HTTP_404_NOT_FOUND)
        s = FormulaireDetailSerializer(obj, data=request.data, partial=True, context={'request': request})
        if s.is_valid():
            s.save()
            return Response(FormulaireDetailSerializer(obj).data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        obj = _get_formulaire(pk)
        if not obj:
            return Response({"detail": "Formulaire introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if obj.publie:
            return Response(
                {"detail": "Impossible de supprimer un formulaire publié. Dépubliez-le d'abord."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FormulairePublierView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def post(self, request, pk):
        obj = _get_formulaire(pk)
        if not obj:
            return Response({"detail": "Formulaire introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if obj.champs.count() == 0:
            return Response(
                {"detail": "Impossible de publier un formulaire sans champs."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        obj.publier()
        return Response({"detail": f"Le formulaire « {obj.titre} » a été publié."})


class FormulaireDepublierView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def post(self, request, pk):
        obj = _get_formulaire(pk)
        if not obj:
            return Response({"detail": "Formulaire introuvable."}, status=status.HTTP_404_NOT_FOUND)
        obj.depublier()
        return Response({"detail": f"Le formulaire « {obj.titre} » a été dépublié."})


class FormulaireAssocierCampagneView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def post(self, request, pk):
        obj = _get_formulaire(pk)
        if not obj:
            return Response({"detail": "Formulaire introuvable."}, status=status.HTTP_404_NOT_FOUND)
        s = AssociationCampagneSerializer(data=request.data, context={'formulaire': obj})
        if s.is_valid():
            s.save()
            return Response({"detail": "Formulaire associé à la campagne avec succès."})
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


class FormulaireReorganiserChampsView(APIView):
    """Reçoit la liste ordonnée des IDs de champs et met à jour leur position."""
    permission_classes = [EstAdminOuPedagogie]

    def post(self, request, pk):
        obj = _get_formulaire(pk)
        if not obj:
            return Response({"detail": "Formulaire introuvable."}, status=status.HTTP_404_NOT_FOUND)
        s = ReorganisationChampsSerializer(data=request.data, context={'formulaire': obj})
        if s.is_valid():
            s.save()
            # Retourner les champs avec leur nouvel ordre
            champs = ChampFormulaire.objects.filter(formulaire=obj).prefetch_related('options')
            return Response(ChampFormulaireSerializer(champs, many=True).data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


class FormulairePrevisualisationView(APIView):
    """Retourne le formulaire avec ses champs pour prévisualisation (accès public ou personnel)."""
    permission_classes = [EstPersonnel]

    def get(self, request, pk):
        try:
            obj = Formulaire.objects.prefetch_related('champs__options').get(pk=pk)
        except Formulaire.DoesNotExist:
            return Response({"detail": "Formulaire introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return Response(FormulaireDetailSerializer(obj).data)


# ─────────────────────────────────────────────
# Champs
# ─────────────────────────────────────────────

class ChampListeView(APIView):
    """Ajouter un champ à un formulaire."""
    permission_classes = [EstAdminOuPedagogie]

    def post(self, request, pk):
        obj = _get_formulaire(pk)
        if not obj:
            return Response({"detail": "Formulaire introuvable."}, status=status.HTTP_404_NOT_FOUND)

        # Auto-ordre : on met le champ à la fin
        max_ordre = obj.champs.count()
        data = {**request.data, 'ordre': request.data.get('ordre', max_ordre)}

        s = ChampFormulaireSerializer(data=data)
        if s.is_valid():
            champ = s.save(formulaire=obj)
            return Response(ChampFormulaireSerializer(champ).data, status=status.HTTP_201_CREATED)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


class ChampDetailView(APIView):
    """Modifier ou supprimer un champ de formulaire."""
    permission_classes = [EstAdminOuPedagogie]

    def put(self, request, champ_id):
        champ = _get_champ(champ_id)
        if not champ:
            return Response({"detail": "Champ introuvable."}, status=status.HTTP_404_NOT_FOUND)
        s = ChampFormulaireSerializer(champ, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            return Response(ChampFormulaireSerializer(champ).data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, champ_id):
        champ = _get_champ(champ_id)
        if not champ:
            return Response({"detail": "Champ introuvable."}, status=status.HTTP_404_NOT_FOUND)
        champ.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────
# Options de champ
# ─────────────────────────────────────────────

class OptionListeView(APIView):
    """Ajouter une option à un champ (liste/choix/cases)."""
    permission_classes = [EstAdminOuPedagogie]

    def post(self, request, champ_id):
        champ = _get_champ(champ_id)
        if not champ:
            return Response({"detail": "Champ introuvable."}, status=status.HTTP_404_NOT_FOUND)
        if not champ.a_options():
            return Response(
                {"detail": f"Le type « {champ.type} » n'accepte pas d'options."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        s = OptionChampSerializer(data=request.data)
        if s.is_valid():
            option = s.save(champ=champ)
            return Response(OptionChampSerializer(option).data, status=status.HTTP_201_CREATED)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


class OptionDetailView(APIView):
    """Supprimer une option."""
    permission_classes = [EstAdminOuPedagogie]

    def delete(self, request, option_id):
        try:
            option = OptionChamp.objects.get(pk=option_id)
        except OptionChamp.DoesNotExist:
            return Response({"detail": "Option introuvable."}, status=status.HTTP_404_NOT_FOUND)
        option.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
