from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from sourcing_backend.views import DashboardStatsView
from sourcing_backend.sourcingchat_views import SourcingChatView, SourcingChatSuggestionsView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Dashboard Stats
    path('api/dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),

    # SourcingChat IA (Endpoints principaux)
    path('api/sourcingchat/chat/', SourcingChatView.as_view(), name='sourcingchat-chat'),
    path('api/sourcingchat/suggestions/', SourcingChatSuggestionsView.as_view(), name='sourcingchat-suggestions'),

    # Alias rétrocompatibilité copilot
    path('api/copilot/chat/', SourcingChatView.as_view(), name='copilot-chat'),
    path('api/copilot/suggestions/', SourcingChatSuggestionsView.as_view(), name='copilot-suggestions'),

    # Auth + Utilisateurs
    path('api/', include('utilisateurs.urls')),

    # Campagnes (formations, cohortes, campagnes)
    path('api/campagnes/', include('campagnes.urls')),

    # Formulaires dynamiques
    path('api/formulaires/', include('formulaires.urls')),

    # Candidatures
    path('api/candidatures/', include('candidatures.urls')),

    # Evaluations / Participations (Suivi de présence QR Code)
    path('api/evaluations/', include('evaluations.urls')),

    # Documentation API (Swagger / ReDoc)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
