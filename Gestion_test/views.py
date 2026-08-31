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
from evaluations.models import AffectationCandidat, StatutPresence
from notifications.models import Notification, StatutNotification, TypeNotification
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from django.http import HttpResponse
from rest_framework.permissions import AllowAny, IsAuthenticated


def candidats_presents_reunion_information(campagne):
    """Candidatures présentes à la première étape, la réunion d'information."""
    return (
        AffectationCandidat.objects.filter(
            participation_etape__candidature__campagne=campagne,
            participation_etape__etape__ordre=1,
            statutPresence=StatutPresence.PRESENT,
            participation_etape__candidature__utilisateur__email__isnull=False,
        )
        .exclude(participation_etape__candidature__utilisateur__email='')
        .select_related('participation_etape__candidature__utilisateur')
        .order_by(
            'participation_etape__candidature__utilisateur__last_name',
            'participation_etape__candidature__utilisateur__first_name',
        )
    )

class TestViewSet(viewsets.ModelViewSet):
    queryset = Test.objects.all().order_by('-date_creation')
    serializer_class = TestSerializer
    permission_classes = [AllowAny]

    @action(detail=False, methods=['get'], url_path='mes-tests', permission_classes=[IsAuthenticated])
    def mes_tests(self, request):
        """Tests actifs accessibles au candidat connecté."""
        if not request.user.est_candidat():
            return Response(
                {'detail': 'Cette ressource est réservée aux candidats.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        tests = Test.objects.filter(
            statut=Test.StatusChoices.ACTIF,
            campagne_assossiee__candidatures__utilisateur=request.user,
            campagne_assossiee__candidatures__participations__etape__ordre=1,
            campagne_assossiee__candidatures__participations__affectation_session__statutPresence=StatutPresence.PRESENT,
        ).select_related('campagne_assossiee').distinct().order_by('-date_creation')

        data = []
        for test in tests:
            ressource_url = test.lien_ressource
            if not ressource_url and test.fichier_ressource:
                ressource_url = request.build_absolute_uri(test.fichier_ressource.url)
            data.append({
                'id': test.id,
                'nom': test.nom,
                'description': test.description,
                'date_ouverture': test.date_ouverture,
                'date_cloture': test.date_cloture,
                'campagne': test.campagne_assossiee.nom,
                'ressource_url': ressource_url,
            })
        return Response(data)

    @action(detail=True, methods=['get'], url_path='candidats-presents')
    def candidats_presents(self, request, pk=None):
        """Liste les candidats présents et notifiables de la campagne du test."""
        test = self.get_object()
        if not test.campagne_assossiee:
            return Response(
                {'detail': 'Ce test n’est associé à aucune campagne.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidats = []
        seen_candidatures = set()
        for affectation in candidats_presents_reunion_information(test.campagne_assossiee):
            candidature = affectation.participation_etape.candidature
            if candidature.id in seen_candidatures:
                continue
            seen_candidatures.add(candidature.id)
            utilisateur = candidature.utilisateur
            candidats.append({
                'id': candidature.id,
                'numero': candidature.numero,
                'nom': utilisateur.get_full_name() or utilisateur.email,
                'email': utilisateur.email,
            })
        return Response(candidats)

    @action(detail=True, methods=['post'])
    def publier(self, request, pk=None):
        test = self.get_object()

        campagne = test.campagne_assossiee
        if not campagne:
            return Response(
                {'detail': 'Ce test n’est associé à aucune campagne.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        candidats_ids = request.data.get('candidats_ids', [])
        if isinstance(candidats_ids, str):
            try:
                import json
                candidats_ids = json.loads(candidats_ids)
            except (TypeError, ValueError):
                candidats_ids = [candidats_ids]
        if not isinstance(candidats_ids, list) or not candidats_ids:
            return Response(
                {'detail': 'Veuillez sélectionner au moins un candidat.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        affectations = candidats_presents_reunion_information(campagne).filter(
            participation_etape__candidature_id__in=candidats_ids,
        )

        candidats = {}
        for affectation in affectations:
            candidature = affectation.participation_etape.candidature
            candidats[candidature.id] = candidature

        if not candidats:
            return Response(
                {'detail': 'Aucun candidat présent à la réunion d’information pour cette campagne.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        sujet = request.data.get('sujet') or f"Votre test « {test.nom} » est disponible"
        instructions = request.data.get('message') or test.description
        lien = test.lien_ressource or f"{settings.FRONTEND_URL.rstrip('/')}/mes-tests"
        date_limite = test.date_cloture.strftime('%d/%m/%Y à %H:%M') if test.date_cloture else 'non précisée'
        envoyes = 0

        try:
            for candidature in candidats.values():
                utilisateur = candidature.utilisateur
                message = (
                    f"Bonjour {utilisateur.first_name or utilisateur.email},\n\n"
                    f"Le test « {test.nom} » est maintenant disponible.\n\n"
                    f"Lien : {lien}\n\n"
                    f"Instructions :\n{instructions}\n\n"
                    f"Date limite : {date_limite}\n\n"
                    "Cordialement,\nL’équipe SourcingHub"
                )
                send_mail(
                    subject=sujet,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[utilisateur.email],
                    fail_silently=False,
                )
                Notification.objects.create(
                    type=TypeNotification.TEST,
                    objet=sujet,
                    contenu=message,
                    statut=StatutNotification.ENVOYEE,
                    utilisateur=utilisateur,
                    candidature=candidature,
                )
                envoyes += 1
        except Exception as exc:
            return Response(
                {'detail': f"Le test n’a pas été activé : erreur d’envoi après {envoyes} email(s). {exc}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        test.statut = Test.StatusChoices.ACTIF
        test.save(update_fields=['statut'])

        return Response({
            'detail': 'Test publié et notifications envoyées aux candidats présents.',
            'statut_actuel': test.statut,
            'emails_envoyes': envoyes,
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
      permission_classes = [AllowAny]
    
    # INDISPENSABLE pour l'upload de fichiers : 
    # Ces parsers indiquent à Django qu'il doit accepter les données de type "multipart/form-data" (fichiers + texte)
      parser_classes = (MultiPartParser, FormParser)     
