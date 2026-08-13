from django.urls import path
from .views import CandidatScanDetailsView, ParticipationEtapeChangerStatutView

urlpatterns = [
    path('candidat/<uuid:candidate_id>/scan-details/', CandidatScanDetailsView.as_view(), name='candidat-scan-details'),
    path('participations/<uuid:pk>/changer-statut/', ParticipationEtapeChangerStatutView.as_view(), name='participation-etape-changer-statut'),
]
