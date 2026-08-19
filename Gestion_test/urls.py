from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import TestViewSet
from .views import SoumissionTestViewSet


router = DefaultRouter()
router.register(r'tests', TestViewSet, basename='test')
router.register(r'soumissions', SoumissionTestViewSet, basename='soumission')

urlpatterns = [
    path('', include(router.urls)),
]