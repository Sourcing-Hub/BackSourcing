from django.urls import path
from .views import TextAssistantView

urlpatterns = [path('text/', TextAssistantView.as_view(), name='assistant-text')]
