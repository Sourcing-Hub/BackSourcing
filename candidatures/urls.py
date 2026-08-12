from django.urls import path
from .views import CandidatureSoumissionView, CandidatureListeView, CandidatureDetailView

urlpatterns = [
    path('soumettre/', CandidatureSoumissionView.as_view(), name='candidature-soumettre'),
    path('', CandidatureListeView.as_view(), name='candidature-liste'),
    path('<uuid:pk>/', CandidatureDetailView.as_view(), name='candidature-detail'),
]
