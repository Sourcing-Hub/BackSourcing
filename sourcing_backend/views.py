from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from campagnes.models import Campagne, StatutCampagne
from candidatures.models import Candidature, StatutCandidature
from evaluations.models import Session

class DashboardStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        campagnes_actives = Campagne.objects.filter(statut=StatutCampagne.OUVERTE).count()
        candidatures_en_cours = Candidature.objects.filter(statut=StatutCandidature.EN_COURS).count()
        entretiens_prevus = Session.objects.filter(date__gte=timezone.now().date()).count()

        return Response({
            "campagnes_actives": campagnes_actives,
            "candidatures_en_cours": candidatures_en_cours,
            "entretiens_prevus": entretiens_prevus,
        })
