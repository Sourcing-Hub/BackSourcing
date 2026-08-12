from django.urls import path
from .views import (
    FormationListeView, FormationDetailView,
    CohorteListeView, CohorteDetailView,
    CampagneListeView, CampagneDetailView,
    CampagneOuvrirView, CampagneFermerView, CampagneArchiverView,
)

urlpatterns = [
    # Formations
    path('formations/', FormationListeView.as_view(), name='formations-liste'),
    path('formations/<uuid:pk>/', FormationDetailView.as_view(), name='formations-detail'),

    # Cohortes
    path('cohortes/', CohorteListeView.as_view(), name='cohortes-liste'),
    path('cohortes/<uuid:pk>/', CohorteDetailView.as_view(), name='cohortes-detail'),

    # Campagnes
    path('', CampagneListeView.as_view(), name='campagnes-liste'),
    path('<uuid:pk>/', CampagneDetailView.as_view(), name='campagnes-detail'),
    path('<uuid:pk>/ouvrir/', CampagneOuvrirView.as_view(), name='campagnes-ouvrir'),
    path('<uuid:pk>/fermer/', CampagneFermerView.as_view(), name='campagnes-fermer'),
    path('<uuid:pk>/archiver/', CampagneArchiverView.as_view(), name='campagnes-archiver'),
]
