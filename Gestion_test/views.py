from django.shortcuts import render
from rest_framework import viewsets
from .models import Test
from .serializers import TestSerializer
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth import get_user_model
from .serializers import SoumissionTestSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from .models import SoumissionTest


class TestViewSet(viewsets.ModelViewSet):
    queryset = Test.objects.all().order_by('-date_creation')
    serializer_class = TestSerializer

    @action(detail=True, methods=['post'])
    def publier(self, request, pk=None):
        test = self.get_object()
        
        # 1. Récupérer les données envoyées depuis la modale du frontend
        candidats_ids = request.data.get('candidats_ids', [])
        sujet = request.data.get('sujet', f"Votre test '{test.nom}' est disponible")
        message_contenu = request.data.get('message', 'Bonjour, le test est maintenant disponible.')

        if not candidats_ids:
            return Response({"detail": "Veuillez sélectionner au moins un candidat."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Mettre à jour le statut du test (ex: 'ACTIF' selon tes choix de statut)
        test.statut = 'ACTIF'  
        test.save()

        # 3. Récupérer les emails des utilisateurs sélectionnés qui ont le rôle 'Candidat'
        # On filtre via le nom du rôle lié (Role.nom == NomRole.Candidat)
        candidats = User.objects.filter(
            id__in=candidats_ids, 
            role__nom='Candidat' # Ou NomRole.Candidat
        )
        destinataires = [user.email for user in candidats if user.email]

        if destinataires:
            # 4. Envoyer l'e-mail
            try:
                send_mail(
                    subject=sujet,
                    message=message_contenu,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=destinataires,
                    fail_silently=False,
                )
            except Exception as e:
                return Response({"detail": f"Erreur lors de l'envoi de l'email : {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({
            "detail": "Test publié avec succès et e-mails envoyés aux candidats.",
            "statut_actuel": test.statut
        }, status=status.HTTP_200_OK)


