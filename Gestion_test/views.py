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
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.http import HttpResponse


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



    @action(detail=True, methods=['get'])
    def telecharger_pdf(self, request, pk=None):
        """
        Gendère et télécharge un PDF contenant les détails du test.
        URL générée par DRF : /api/tests/<pk>/telecharger_pdf/
        """
        test = self.get_object()

        # 1. Création d'un buffer mémoire pour stocker le PDF temporairement
        buffer = io.BytesIO()

        # 2. Configuration du document PDF avec ReportLab
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter

        # --- Design / Contenu du PDF ---
        # Titre du test
        p.setFont("Helvetica-Bold", 18)
        p.drawString(50, height - 50, f"Fiche du Test : {test.nom}")

        # Description ou informations du test
        p.setFont("Helvetica", 12)
        y_position = height - 100
        
        p.drawString(50, y_position, f"Statut actuel : {getattr(test, 'statut', 'N/A')}")
        y_position -= 30

        # Description détaillée si elle existe
        description = getattr(test, 'description', 'Aucune description disponible pour ce test.')
        p.drawString(50, y_position, "Description :")
        y_position -= 20
        
        # Petit texte simple pour l'exemple
        p.drawString(70, y_position, description)

        # Pied de page / Fin du document
        p.showPage()
        p.save()

        # 3. Récupération des données du buffer
        buffer.seek(0)
        pdf_data = buffer.getvalue()
        buffer.close()

        # 4. Retourner le fichier PDF sous forme de réponse HTTP téléchargeable
        response = HttpResponse(pdf_data, content_type='application/pdf')
        # 'attachment' force le téléchargement du fichier au lieu de l'ouvrir dans l'onglet
        response['Content-Disposition'] = f'attachment; filename="test_{test.id}.pdf"'
        
        return response



class SoumissionTestViewSet(viewsets.ModelViewSet):
      queryset = SoumissionTest.objects.all().order_by('-date_soumission')
      serializer_class = SoumissionTestSerializer
    
    # INDISPENSABLE pour l'upload de fichiers : 
    # Ces parsers indiquent à Django qu'il doit accepter les données de type "multipart/form-data" (fichiers + texte)
      parser_classes = (MultiPartParser, FormParser)     