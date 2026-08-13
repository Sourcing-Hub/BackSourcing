"""
Vues pour la gestion des Campagnes.

Endpoints :
  Formations :
    GET    /api/campagnes/formations/                → Liste des formations
    POST   /api/campagnes/formations/                → Créer une formation
    GET    /api/campagnes/formations/<id>/           → Détail
    PUT    /api/campagnes/formations/<id>/           → Modifier
    DELETE /api/campagnes/formations/<id>/           → Supprimer

  Cohortes :
    GET    /api/campagnes/cohortes/                  → Liste des cohortes
    POST   /api/campagnes/cohortes/                  → Créer
    GET    /api/campagnes/cohortes/<id>/             → Détail
    PUT    /api/campagnes/cohortes/<id>/             → Modifier

  Campagnes :
    GET    /api/campagnes/                           → Liste
    POST   /api/campagnes/                           → Créer
    GET    /api/campagnes/<id>/                      → Détail
    PUT    /api/campagnes/<id>/                      → Modifier
    POST   /api/campagnes/<id>/ouvrir/               → Ouvrir la campagne
    POST   /api/campagnes/<id>/fermer/               → Fermer la campagne
    POST   /api/campagnes/<id>/archiver/             → Archiver la campagne
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from utilisateurs.permissions import EstAdministrateur, EstAdminOuPedagogie, EstPersonnel, EstAdminOuGestionProjet
from .models import Formation, Cohorte, Campagne
from .serializers import (
    FormationSerializer,
    CohorteSerializer,
    CampagneListeSerializer,
    CampagneDetailSerializer,
)


# ─────────────────────────────────────────────
# Formations
# ─────────────────────────────────────────────

class FormationListeView(APIView):
    permission_classes = [EstPersonnel]

    def get(self, request):
        qs = Formation.objects.all()
        return Response(FormationSerializer(qs, many=True).data)

    def post(self, request):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        s = FormationSerializer(data=request.data)
        if s.is_valid():
            s.save()
            return Response(s.data, status=status.HTTP_201_CREATED)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


class FormationDetailView(APIView):
    permission_classes = [EstPersonnel]

    def _get_object(self, pk):
        try:
            return Formation.objects.get(pk=pk)
        except Formation.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Formation introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return Response(FormationSerializer(obj).data)

    def put(self, request, pk):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Formation introuvable."}, status=status.HTTP_404_NOT_FOUND)
        s = FormationSerializer(obj, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Formation introuvable."}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────
# Cohortes
# ─────────────────────────────────────────────

class CohorteListeView(APIView):
    permission_classes = [EstPersonnel]

    def get(self, request):
        formation_id = request.query_params.get('formation')
        qs = Cohorte.objects.select_related('formation').all()
        if formation_id:
            qs = qs.filter(formation__id=formation_id)
        return Response(CohorteSerializer(qs, many=True).data)

    def post(self, request):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        s = CohorteSerializer(data=request.data)
        if s.is_valid():
            s.save()
            return Response(s.data, status=status.HTTP_201_CREATED)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


class CohorteDetailView(APIView):
    permission_classes = [EstPersonnel]

    def _get_object(self, pk):
        try:
            return Cohorte.objects.select_related('formation').get(pk=pk)
        except Cohorte.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Cohorte introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CohorteSerializer(obj).data)

    def put(self, request, pk):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Cohorte introuvable."}, status=status.HTTP_404_NOT_FOUND)
        s = CohorteSerializer(obj, data=request.data, partial=True)
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Cohorte introuvable."}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─────────────────────────────────────────────
# Campagnes
# ─────────────────────────────────────────────

class CampagneListeView(APIView):
    permission_classes = [EstPersonnel]

    def get(self, request):
        qs = Campagne.objects.select_related('cohorte__formation').all()

        # Filtres optionnels
        statut = request.query_params.get('statut')
        if statut:
            qs = qs.filter(statut=statut)

        return Response(CampagneListeSerializer(qs, many=True).data)

    def post(self, request):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        s = CampagneDetailSerializer(data=request.data, context={'request': request})
        if s.is_valid():
            campagne = s.save()
            return Response(CampagneDetailSerializer(campagne).data, status=status.HTTP_201_CREATED)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)


class CampagneDetailView(APIView):
    permission_classes = [EstPersonnel]

    def _get_object(self, pk):
        try:
            return Campagne.objects.select_related('cohorte__formation').get(pk=pk)
        except Campagne.DoesNotExist:
            return None

    def get(self, request, pk):
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CampagneDetailSerializer(obj).data)

    def put(self, request, pk):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)
        s = CampagneDetailSerializer(obj, data=request.data, partial=True, context={'request': request})
        if s.is_valid():
            s.save()
            return Response(s.data)
        return Response(s.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({"detail": "Réservé aux administrateurs."}, status=status.HTTP_403_FORBIDDEN)
        obj = self._get_object(pk)
        if not obj:
            return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CampagneOuvrirView(APIView):
    permission_classes = [EstAdminOuGestionProjet]

    def post(self, request, pk):
        try:
            campagne = Campagne.objects.get(pk=pk)
        except Campagne.DoesNotExist:
            return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)
        
        from django.core.exceptions import ValidationError
        try:
            campagne.ouvrir()
        except ValidationError as e:
            msg = e.message if hasattr(e, 'message') else str(e)
            # Remove list styling from django error if raised as list
            if isinstance(msg, list):
                msg = ", ".join(msg)
            elif hasattr(e, 'message_dict') and e.message_dict:
                msg = ", ".join([f"{k}: {', '.join(v)}" for k, v in e.message_dict.items()])
            return Response({"detail": msg}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"detail": f"La campagne « {campagne.nom} » est maintenant ouverte."})


class CampagneFermerView(APIView):
    permission_classes = [EstAdminOuGestionProjet]

    def post(self, request, pk):
        try:
            campagne = Campagne.objects.get(pk=pk)
        except Campagne.DoesNotExist:
            return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)
        campagne.fermer()
        return Response({"detail": f"La campagne « {campagne.nom} » a été fermée."})


class CampagnePubliqueListeView(APIView):
    """
    GET /api/campagnes/publiques/
    Accès public. Liste uniquement les campagnes ouvertes et publiées.
    """
    permission_classes = []

    def get(self, request):
        from django.utils import timezone
        now = timezone.now()
        qs = Campagne.objects.filter(
            statut='OUVERTE',
            publiee=True,
            dateOuverture__lte=now,
            dateCloture__gte=now
        ).select_related('cohorte__formation')
        return Response(CampagneListeSerializer(qs, many=True).data)


class CampagnePubliqueDetailView(APIView):
    """
    GET /api/campagnes/publiques/<id>/
    Accès public. Retourne les détails d'une campagne ouverte et publiée.
    """
    permission_classes = []

    def get(self, request, pk):
        from django.utils import timezone
        now = timezone.now()
        try:
            obj = Campagne.objects.select_related('cohorte__formation').get(
                pk=pk,
                statut='OUVERTE',
                publiee=True,
                dateOuverture__lte=now,
                dateCloture__gte=now
            )
        except Campagne.DoesNotExist:
            return Response({"detail": "Cette campagne de recrutement n'est pas accessible ou est fermée."}, status=status.HTTP_404_NOT_FOUND)
        return Response(CampagneDetailSerializer(obj).data)


