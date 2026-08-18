from django.urls import path
from .views import (
    CandidatScanDetailsView, ParticipationEtapeChangerStatutView,
    PlanningListeView, PlanningDetailView, PlanningConfigurationView, EncadrantsPlanningView,
    ConvocationCandidatsView, ConvocationAffectationView,
    EmargementSessionsView, EmargementSessionDetailView, EmargementPresenceView, EmargementQrView,
    EmargementCloturerView, ConfirmationPresenceView,
)

urlpatterns = [
    path('candidat/<uuid:candidate_id>/scan-details/', CandidatScanDetailsView.as_view(), name='candidat-scan-details'),
    path('participations/<uuid:pk>/changer-statut/', ParticipationEtapeChangerStatutView.as_view(), name='participation-etape-changer-statut'),
    path('plannings/', PlanningListeView.as_view(), name='plannings-liste'),
    path('plannings/configurer/', PlanningConfigurationView.as_view(), name='plannings-configurer'),
    path('plannings/encadrants/', EncadrantsPlanningView.as_view(), name='plannings-encadrants'),
    path('convocations/candidats/', ConvocationCandidatsView.as_view(), name='convocations-candidats'),
    path('convocations/affecter/', ConvocationAffectationView.as_view(), name='convocations-affecter'),
    path('emargement/sessions/', EmargementSessionsView.as_view(), name='emargement-sessions'),
    path('emargement/sessions/<uuid:session_id>/', EmargementSessionDetailView.as_view(), name='emargement-session-detail'),
    path('emargement/sessions/<uuid:session_id>/cloturer/', EmargementCloturerView.as_view(), name='emargement-cloturer'),
    path('emargement/affectations/<uuid:affectation_id>/presence/', EmargementPresenceView.as_view(), name='emargement-presence'),
    path('emargement/qr/<uuid:token>/', EmargementQrView.as_view(), name='emargement-qr'),
    path('confirmation-presence/<uuid:token>/', ConfirmationPresenceView.as_view(), name='confirmation-presence'),
    path('plannings/<uuid:pk>/', PlanningDetailView.as_view(), name='plannings-detail'),
]
