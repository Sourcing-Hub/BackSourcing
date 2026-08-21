from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CandidatScanDetailsView, ParticipationEtapeChangerStatutView,
    PlanningListeView, PlanningDetailView, PlanningConfigurationView, EncadrantsPlanningView,
    ConvocationCandidatsView, ConvocationAffectationView,
    EmargementSessionsView, EmargementSessionDetailView, EmargementPresenceView, EmargementQrView,
    EmargementCloturerView, ConfirmationPresenceView,
    TestQCMViewSet, CandidateTestDetailsView, CandidateStartTestView, CandidateSubmitTestView,
)

router = DefaultRouter()
router.register(r'tests', TestQCMViewSet, basename='tests-qcm')

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

    # Routes QCM (Équipe Pédagogique)
    path('', include(router.urls)),

    # Routes QCM (Candidats - Étape 3)
    path('participations/<uuid:participation_id>/test-details/', CandidateTestDetailsView.as_view(), name='candidat-test-details'),
    path('participations/<uuid:participation_id>/commencer-test/', CandidateStartTestView.as_view(), name='candidat-commencer-test'),
    path('participations/<uuid:participation_id>/soumettre-test/', CandidateSubmitTestView.as_view(), name='candidat-soumettre-test'),
]

