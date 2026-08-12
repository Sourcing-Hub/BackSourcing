from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from sourcing_backend.views import DashboardStatsView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Dashboard Stats
    path('api/dashboard/stats/', DashboardStatsView.as_view(), name='dashboard-stats'),

    # Auth + Utilisateurs
    path('api/', include('utilisateurs.urls')),

    # Campagnes (formations, cohortes, campagnes)
    path('api/campagnes/', include('campagnes.urls')),

    # Formulaires dynamiques
    path('api/formulaires/', include('formulaires.urls')),

    # Documentation API (Swagger / ReDoc)
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/docs/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
]
