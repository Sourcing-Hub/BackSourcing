from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from utilisateurs.models import Utilisateur
from candidatures.models import Candidature
from .models import Etape, ParticipationEtape, StatutEtape
from .serializers import ParticipationEtapeSerializer

class IsStaffOrAdmin(IsAuthenticated):
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        return (user.est_admin() or 
                user.est_equipe_pedagogique() or 
                user.est_equipe_gestion_projet())

class CandidatScanDetailsView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def get(self, request, candidate_id):
        candidate = get_object_or_404(Utilisateur, pk=candidate_id)
        
        # Get candidate's candidature
        candidature = Candidature.objects.filter(utilisateur=candidate).first()
        if not candidature:
            return Response(
                {"detail": "Aucune candidature trouvée pour ce candidat."},
                status=status.HTTP_404_NOT_FOUND
            )

        campagne = candidature.campagne
        cohorte = campagne.cohorte if campagne else None

        if not cohorte:
            return Response(
                {"detail": "La campagne de ce candidat n'est associée à aucune cohorte active."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure all cohort steps have a ParticipationEtape record
        etapes = Etape.objects.filter(cohorte=cohorte)
        for etape in etapes:
            ParticipationEtape.objects.get_or_create(
                candidature=candidature,
                etape=etape,
                defaults={'statut': StatutEtape.EN_ATTENTE}
            )

        # Get all participations
        participations = ParticipationEtape.objects.filter(candidature=candidature).select_related('etape')
        participations_data = ParticipationEtapeSerializer(participations, many=True).data

        return Response({
            "candidat": {
                "id": candidate.id,
                "nom": candidate.last_name,
                "prenom": candidate.first_name,
                "email": candidate.email,
                "telephone": candidate.telephone,
                "sexe": candidate.sexe
            },
            "candidature": {
                "id": candidature.id,
                "numero": candidature.numero,
                "statut": candidature.statut,
                "campagne_nom": campagne.nom if campagne else None,
                "cohorte_nom": cohorte.nom
            },
            "participations": participations_data
        })

class ParticipationEtapeChangerStatutView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def patch(self, request, pk):
        participation = get_object_or_404(ParticipationEtape, pk=pk)
        
        nouveau_statut = request.data.get('statut')
        if not nouveau_statut:
            return Response(
                {"detail": "Le paramètre 'statut' est requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if nouveau_statut not in StatutEtape.values:
            return Response(
                {"detail": f"Statut '{nouveau_statut}' invalide. Valeurs autorisées: {StatutEtape.values}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        participation.statut = nouveau_statut
        
        # If successfully finished or failed/absent, set dateSortie
        if nouveau_statut in [StatutEtape.REUSSIE, StatutEtape.ECHOUEE, StatutEtape.ABSENT, StatutEtape.ANNULEE]:
            participation.dateSortie = timezone.now()
        else:
            participation.dateSortie = None

        motif = request.data.get('motif')
        if motif is not None:
            participation.motif = motif

        participation.save()

        return Response(ParticipationEtapeSerializer(participation).data)
