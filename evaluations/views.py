from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings
from django.core.mail import EmailMessage, send_mail
from decimal import Decimal, InvalidOperation

from utilisateurs.models import Utilisateur, NomRole
from candidatures.models import Candidature
from .models import (
    AffectationCandidat, AffectationEvaluateur, Etape, Evaluation, ParticipationEtape,
    Question, Session, StatutEtape, StatutPresence, TypeDecision, TypeQuestion, Decision,
    TestQCM, QuestionQCM, OptionQCM, PassageTestQCM, ReponseCandidatQCM, StatutPassageTest, TypeChoixQCM
)
from .serializers import (
    ParticipationEtapeSerializer, PlanningConfigurationSerializer, PlanningSerializer,
    QuestionSerializer, TestQCMSerializer, TestCandidatQCMSerializer, SoumissionTestQCMSerializer
)
from utilisateurs.permissions import EstAdminOuGestionProjet, EstAdminOuPedagogie, EstEvaluateur
from candidatures.models import Candidature, StatutCandidature
from notifications.models import Notification, StatutNotification, TypeNotification



class IsStaffOrAdmin(IsAuthenticated):
    """Permission permettant l'accès aux membres Admin, Pédagogie et Gestion de Projet."""
    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        user = request.user
        return (user.est_admin() or 
                user.est_equipe_pedagogique() or 
                user.est_equipe_gestion_projet())

class CandidatScanDetailsView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def get(self, request, candidate_id):
        candidate = get_object_or_404(Utilisateur, pk=candidate_id)
        
        # Get candidate's candidature
        candidature = Candidature.objects.filter(utilisateur=candidate).first()
        if not candidature:
            return Response(
                {"detail": "Aucune candidature trouvée pour ce candidat."},
                status=status.HTTP_404_NOT_FOUND
            )

        campagne = candidature.campagne
        cohorte = campagne.cohorte if campagne else None

        if not cohorte:
            return Response(
                {"detail": "La campagne de ce candidat n'est associée à aucune cohorte active."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Ensure all cohort steps have a ParticipationEtape record
        etapes = Etape.objects.filter(cohorte=cohorte)
        for etape in etapes:
            ParticipationEtape.objects.get_or_create(
                candidature=candidature,
                etape=etape,
                defaults={'statut': StatutEtape.EN_ATTENTE}
            )

        # Get all participations
        participations = ParticipationEtape.objects.filter(candidature=candidature).select_related('etape')
        participations_data = ParticipationEtapeSerializer(participations, many=True).data

        return Response({
            "candidat": {
                "id": candidate.id,
                "nom": candidate.last_name,
                "prenom": candidate.first_name,
                "email": candidate.email,
                "telephone": candidate.telephone,
                "sexe": candidate.sexe
            },
            "candidature": {
                "id": candidature.id,
                "numero": candidature.numero,
                "statut": candidature.statut,
                "campagne_nom": campagne.nom if campagne else None,
                "cohorte_nom": cohorte.nom
            },
            "participations": participations_data
        })

class ParticipationEtapeChangerStatutView(APIView):
    permission_classes = [IsStaffOrAdmin]

    def patch(self, request, pk):
        participation = get_object_or_404(ParticipationEtape, pk=pk)
        
        nouveau_statut = request.data.get('statut')
        if not nouveau_statut:
            return Response(
                {"detail": "Le paramètre 'statut' est requis."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if nouveau_statut not in StatutEtape.values:
            return Response(
                {"detail": f"Statut '{nouveau_statut}' invalide. Valeurs autorisées: {StatutEtape.values}."},
                status=status.HTTP_400_BAD_REQUEST
            )

        participation.statut = nouveau_statut
        
        # If successfully finished or failed/absent, set dateSortie
        if nouveau_statut in [StatutEtape.REUSSIE, StatutEtape.ECHOUEE, StatutEtape.ABSENT, StatutEtape.ANNULEE]:
            participation.dateSortie = timezone.now()
        else:
            participation.dateSortie = None

        motif = request.data.get('motif')
        if motif is not None:
            participation.motif = motif

        participation.save()

        return Response(ParticipationEtapeSerializer(participation).data)


class PlanningListeView(APIView):
    """Liste et création des sessions de planification."""
    permission_classes = [EstAdminOuPedagogie]

    def get(self, request):
        plannings = Session.objects.select_related('etape__cohorte__formation').all().order_by(
            'date', 'heureDebut'
        )
        etape_id = request.query_params.get('etape')
        if etape_id:
            plannings = plannings.filter(etape_id=etape_id)
        return Response(PlanningSerializer(plannings, many=True).data)

    def post(self, request):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({'detail': 'Réservé aux administrateurs et à la gestion de projet.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PlanningSerializer(data=request.data)
        if serializer.is_valid():
            planning = serializer.save()
            return Response(PlanningSerializer(planning).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class PlanningDetailView(APIView):
    """Consultation, modification et suppression d'un planning."""
    permission_classes = [EstAdminOuPedagogie]

    def _get_object(self, pk):
        return get_object_or_404(Session.objects.select_related('etape__cohorte__formation'), pk=pk)

    def get(self, request, pk):
        return Response(PlanningSerializer(self._get_object(pk)).data)

    def put(self, request, pk):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({'detail': 'Réservé aux administrateurs et à la gestion de projet.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PlanningSerializer(self._get_object(pk), data=request.data, partial=True)
        if serializer.is_valid():
            planning = serializer.save()
            return Response(PlanningSerializer(planning).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({'detail': 'Réservé aux administrateurs et à la gestion de projet.'}, status=status.HTTP_403_FORBIDDEN)
        self._get_object(pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PlanningConfigurationView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def post(self, request):
        if not (request.user.est_admin() or request.user.est_equipe_gestion_projet()):
            return Response({'detail': 'Réservé aux administrateurs et à la gestion de projet.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PlanningConfigurationSerializer(data=request.data)
        if serializer.is_valid():
            sessions = serializer.save()
            return Response(PlanningSerializer(sessions, many=True).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EncadrantsPlanningView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def get(self, request):
        encadrants = Utilisateur.objects.select_related('role').filter(
            is_active=True
        ).exclude(
            role__nom=NomRole.CANDIDAT
        ).order_by('first_name', 'last_name')
        
        result = []
        for user in encadrants:
            nom_complet = f"{user.first_name} {user.last_name}".strip()
            if not nom_complet:
                local_part = user.email.split('@')[0]
                parts = local_part.replace('_', '.').replace('-', '.').split('.')
                nom_complet = ' '.join(p.capitalize() for p in parts if p)
            result.append({
                'id': user.id,
                'prenom': user.first_name,
                'nom': user.last_name,
                'nomComplet': nom_complet,
                'role': user.role.nom if user.role else 'Sans rôle',
            })
        return Response(result)


from django.db.models import Q

def get_eligibilite_convocation(candidature, session, participations):
    """Retourne l'éligibilité d'une candidature au créneau demandé."""
    etape_cible = session.etape
    participation_cible = participations.get(etape_cible.id)
    decision_type = getattr(getattr(candidature, 'decision_finale', None), 'type', None)

    if decision_type == TypeDecision.REFUSE:
        return False, 'Cette candidature est refusée et ne peut plus être convoquée.', participation_cible
    if etape_cible.ordre >= 3 and decision_type != TypeDecision.ADMIS:
        return False, 'Le candidat doit être admis avant une convocation à l’entretien final.', participation_cible

    etapes_precedentes = Etape.objects.filter(
        cohorte=etape_cible.cohorte,
        ordre__lt=etape_cible.ordre,
    )

    if participation_cible and getattr(participation_cible, 'affectation_session', None) is not None:
        return False, 'Déjà convoqué pour un créneau.', participation_cible
    if participation_cible and participation_cible.statut != StatutEtape.EN_ATTENTE:
        return False, 'Cette étape est déjà en cours ou terminée.', participation_cible
    if etape_cible.ordre > 1 and any(
        participations.get(etape.id, None) is None
        or participations[etape.id].statut != StatutEtape.REUSSIE
        for etape in etapes_precedentes
    ):
        return False, 'Les étapes précédentes ne sont pas encore validées.', participation_cible
    return True, '', participation_cible


class ConvocationCandidatsView(APIView):
    """Candidats d'une promo éligibles à une session de sélection."""
    permission_classes = [EstAdminOuPedagogie]

    def get(self, request):
        planning_id = request.query_params.get('planning')
        if not planning_id:
            return Response({'detail': 'Le planning est requis.'}, status=status.HTTP_400_BAD_REQUEST)

        session = get_object_or_404(
            Session.objects.select_related('etape__cohorte__formation'),
            pk=planning_id,
        )
        
        candidatures_filter = Q(campagne__cohorte=session.etape.cohorte)
        if session.etape.cohorte and session.etape.cohorte.formation:
            candidatures_filter |= Q(campagne__cohorte__formation=session.etape.cohorte.formation)

        candidatures = list(Candidature.objects.filter(
            candidatures_filter,
        ).distinct().select_related(
            'utilisateur',
            'campagne',
            'campagne__cohorte',
            'decision_finale',
        ).order_by('utilisateur__last_name', 'utilisateur__first_name'))
        
        participations = ParticipationEtape.objects.filter(
            candidature__in=candidatures,
        ).select_related('etape', 'affectation_session')
        participations_par_candidature = {}
        for participation in participations:
            participations_par_candidature.setdefault(participation.candidature_id, {})[participation.etape_id] = participation

        candidats = []
        for candidature in candidatures:
            eligible, raison, _ = get_eligibilite_convocation(
                candidature,
                session,
                participations_par_candidature.get(candidature.id, {}),
            )
            nom_candidat = f'{candidature.utilisateur.first_name} {candidature.utilisateur.last_name}'.strip() or candidature.utilisateur.get_full_name() or candidature.utilisateur.email
            candidats.append({
                'id': candidature.id,
                'numero': candidature.numero,
                'nom': nom_candidat,
                'email': candidature.utilisateur.email,
                'telephone': candidature.utilisateur.telephone,
                'eligible': eligible,
                'raison': raison,
            })

        assignes = AffectationCandidat.objects.filter(session=session).count()
        return Response({
            'planning': PlanningSerializer(session).data,
            'capacite': session.capacite,
            'assignes': assignes,
            'places_restantes': max(session.capacite - assignes, 0),
            'candidats': candidats,
        })


class ConvocationAffectationView(APIView):
    """Affecte une sélection de candidats à un créneau de planning."""
    permission_classes = [EstAdminOuGestionProjet]

    @transaction.atomic
    def post(self, request):
        planning_id = request.data.get('planning')
        candidature_ids = request.data.get('candidatures', [])
        if not planning_id or not isinstance(candidature_ids, list) or not candidature_ids:
            return Response(
                {'detail': 'Un planning et au moins un candidat sont requis.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = get_object_or_404(
            Session.objects.select_for_update().select_related('etape__cohorte__formation'),
            pk=planning_id,
        )
        candidature_ids = list(dict.fromkeys(candidature_ids))
        
        candidatures_filter = Q(id__in=candidature_ids) & (
            Q(campagne__cohorte=session.etape.cohorte) |
            Q(campagne__cohorte__formation=session.etape.cohorte.formation)
        )
        candidatures = list(Candidature.objects.filter(
            candidatures_filter,
        ).distinct().select_related('utilisateur'))
        if len(candidatures) != len(candidature_ids):
            return Response(
                {'detail': 'Un ou plusieurs candidats ne correspondent pas à la promo ou formation de ce planning.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        deja_assignes = AffectationCandidat.objects.filter(session=session).count()
        if deja_assignes + len(candidatures) > session.capacite:
            return Response(
                {'detail': f'Capacité insuffisante : {session.capacite - deja_assignes} place(s) restante(s).'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        erreurs = []
        affectations = []
        for candidature in candidatures:
            participations = {
                participation.etape_id: participation
                for participation in ParticipationEtape.objects.filter(
                    candidature=candidature,
                ).select_related('affectation_session')
            }
            eligible, raison, participation = get_eligibilite_convocation(candidature, session, participations)
            if not eligible:
                erreurs.append(f'{candidature.numero} : {raison}')
                continue
            if not participation:
                participation = ParticipationEtape.objects.create(
                    candidature=candidature,
                    etape=session.etape,
                    statut=StatutEtape.EN_ATTENTE,
                )
            affectations.append((candidature, participation))

        if erreurs:
            return Response({'detail': 'Affectation impossible.', 'erreurs': erreurs}, status=status.HTTP_400_BAD_REQUEST)

        for candidature, participation in affectations:
            affectation = AffectationCandidat.objects.create(participation_etape=participation, session=session)
            participation.statut = StatutEtape.EN_COURS
            participation.save(update_fields=['statut'])
            if candidature.statut == 'EN_ATTENTE':
                candidature.statut = 'EN_COURS'
                candidature.save(update_fields=['statut'])
            transaction.on_commit(
                lambda candidature=candidature, token=affectation.tokenConfirmation: envoyer_convocation_email(candidature, session, token),
            )

        return Response({
            'affectes': len(affectations),
            'places_restantes': session.capacite - deja_assignes - len(affectations),
            'emailsProgrammes': len(affectations),
        }, status=status.HTTP_201_CREATED)


def envoyer_notification(candidature, notification_type, objet, contenu, attachment=None):
    """Conserve toujours une trace de l'envoi, même si la messagerie est indisponible."""
    notification = Notification.objects.create(
        type=notification_type,
        objet=objet,
        contenu=contenu,
        utilisateur=candidature.utilisateur,
        candidature=candidature,
    )
    try:
        if attachment:
            email = EmailMessage(objet, contenu, settings.DEFAULT_FROM_EMAIL, [candidature.utilisateur.email])
            email.attach('qr-convocation.png', attachment, 'image/png')
            email.send(fail_silently=False)
        else:
            send_mail(objet, contenu, settings.DEFAULT_FROM_EMAIL, [candidature.utilisateur.email], fail_silently=False)
        notification.statut = StatutNotification.ENVOYEE
    except Exception:
        notification.statut = StatutNotification.ECHEC
    notification.save(update_fields=['statut'])
    return notification


def envoyer_convocation_email(candidature, session, token):
    utilisateur = candidature.utilisateur
    etape = session.etape
    objet = f'Convocation — {etape.nom}'
    lieu = session.lieu or session.localisation or 'Lieu à préciser'
    qr_data = f'{settings.FRONTEND_URL}/scan-emargement/{token}'
    contenu = (
        f'Bonjour {utilisateur.get_full_name() or utilisateur.email},\n\n'
        f'Votre candidature {candidature.numero} est convoquée à l étape « {etape.nom} ».\n\n'
        f'Date : {session.date.strftime("%d/%m/%Y")}\n'
        f'Horaire : {session.heureDebut.strftime("%H:%M")} – {session.heureFin.strftime("%H:%M")}\n'
        f'Lieu : {lieu}\n'
        f'Formation : {etape.cohorte.formation.nom}\n'
        f'Promotion : {etape.cohorte.nom}\n\n'
        'Merci de vous présenter quelques minutes avant l heure indiquée.\n\n'
        f'Votre QR code de pointage est joint à cet email. En cas de besoin, utilisez ce lien : {qr_data}\n\n'
        'Cordialement,\nL équipe Sourcing Connect'
    )
    import io
    import qrcode
    qr = qrcode.make(qr_data)
    buffer = io.BytesIO()
    qr.save(buffer, format='PNG')
    return envoyer_notification(candidature, TypeNotification.CONVOCATION, objet, contenu, buffer.getvalue())


def serialiser_affectation(affectation):
    candidature = affectation.participation_etape.candidature
    utilisateur = candidature.utilisateur
    return {
        'id': affectation.id,
        'candidatureId': candidature.id,
        'numero': candidature.numero,
        'nom': utilisateur.get_full_name() or utilisateur.email,
        'email': utilisateur.email,
        'telephone': utilisateur.telephone,
        'statutPresence': affectation.statutPresence,
        'dateEmargement': affectation.dateEmargement,
        'dateConfirmation': affectation.dateConfirmation,
        'statutEtape': affectation.participation_etape.statut,
    }


class EmargementSessionsView(APIView):
    """Sessions convoquées à suivre pour le pointage."""
    permission_classes = [EstAdminOuPedagogie]

    def get(self, request):
        sessions = Session.objects.select_related(
            'etape__cohorte__formation'
        ).distinct().order_by('-date', 'heureDebut')
        data = []
        for session in sessions:
            affectations = session.affectations_candidats.all()
            data.append({
                'id': session.id,
                'date': session.date,
                'heureDebut': session.heureDebut,
                'heureFin': session.heureFin,
                'etapeNom': session.etape.nom,
                'cohorteNom': session.etape.cohorte.nom,
                'formationNom': session.etape.cohorte.formation.nom,
                'total': affectations.count(),
                'presents': affectations.filter(statutPresence=StatutPresence.PRESENT).count(),
                'absents': affectations.filter(statutPresence=StatutPresence.ABSENT).count(),
                'enAttente': affectations.filter(statutPresence=StatutPresence.A_ATTENDRE).count(),
            })
        return Response(data)


class EmargementSessionDetailView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def get(self, request, session_id):
        session = get_object_or_404(Session.objects.select_related('etape__cohorte__formation'), pk=session_id)
        affectations = AffectationCandidat.objects.filter(session=session).select_related(
            'participation_etape__candidature__utilisateur'
        ).order_by('participation_etape__candidature__utilisateur__last_name')
        return Response({
            'session': {
                'id': session.id, 'date': session.date, 'heureDebut': session.heureDebut,
                'heureFin': session.heureFin, 'lieu': session.lieu, 'localisation': session.localisation,
                'etapeNom': session.etape.nom, 'cohorteNom': session.etape.cohorte.nom,
            },
            'affectations': [serialiser_affectation(affectation) for affectation in affectations],
        })


class EmargementPresenceView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    @transaction.atomic
    def patch(self, request, affectation_id):
        statut_presence = request.data.get('statutPresence') or getattr(request, 'forced_presence', None)
        if statut_presence not in StatutPresence.values:
            return Response({'detail': 'Statut de présence invalide.'}, status=status.HTTP_400_BAD_REQUEST)
        affectation = get_object_or_404(AffectationCandidat.objects.select_for_update().select_related(
            'participation_etape__candidature__utilisateur'
        ), pk=affectation_id)
        was_absent = affectation.statutPresence == StatutPresence.ABSENT
        affectation.statutPresence = statut_presence
        affectation.dateEmargement = timezone.now() if statut_presence != StatutPresence.A_ATTENDRE else None
        affectation.save(update_fields=['statutPresence', 'dateEmargement'])
        if statut_presence == StatutPresence.ABSENT:
            participation = affectation.participation_etape
            participation.statut = StatutEtape.ABSENT
            participation.dateSortie = timezone.now()
            participation.motif = request.data.get('motif') or 'Absent lors de la session.'
            participation.save(update_fields=['statut', 'dateSortie', 'motif'])
            candidature = participation.candidature
            candidature.statut = StatutCandidature.TERMINEE
            candidature.save(update_fields=['statut'])
            if not was_absent:
                envoyer_notification(candidature, TypeNotification.FIN_PARCOURS, 'Fin de votre parcours de sélection', 'Vous avez été marqué(e) absent(e) à votre session. Votre parcours de sélection est terminé.')
        return Response(serialiser_affectation(affectation))


class EmargementQrView(APIView):
    """Lecture d'un QR de convocation par un membre autorisé."""
    permission_classes = [EstAdminOuPedagogie]

    def get_permissions(self):
        # La présentation du QR par le candidat peut être enregistrée sans connexion.
        if self.request.method in ('GET', 'POST'):
            return []
        return super().get_permissions()

    def get(self, request, token):
        affectation = get_object_or_404(AffectationCandidat.objects.select_related(
            'session__etape__cohorte__formation',
            'participation_etape__candidature__utilisateur',
        ), tokenConfirmation=token)
        candidature = affectation.participation_etape.candidature
        return Response({
            'id': affectation.id,
            'nom': candidature.utilisateur.get_full_name() or candidature.utilisateur.email,
            'email': candidature.utilisateur.email,
            'numero': candidature.numero,
            'statutPresence': affectation.statutPresence,
            'session': {
                'id': affectation.session.id,
                'etapeNom': affectation.session.etape.nom,
                'cohorteNom': affectation.session.etape.cohorte.nom,
                'date': affectation.session.date,
                'heureDebut': affectation.session.heureDebut,
                'heureFin': affectation.session.heureFin,
                'lieu': affectation.session.lieu or affectation.session.localisation,
            },
        })

    def patch(self, request, token):
        affectation = get_object_or_404(AffectationCandidat, tokenConfirmation=token)
        return EmargementPresenceView().patch(request, affectation.id)

    def post(self, request, token):
        """Pointage automatique lors de la présentation du QR le jour J."""
        affectation = get_object_or_404(AffectationCandidat, tokenConfirmation=token)
        request.forced_presence = StatutPresence.PRESENT
        EmargementPresenceView().patch(request, affectation.id)
        return self.get(request, token)


class EmargementCloturerView(APIView):
    """Clôture la session : les personnes non pointées sont absentes, les présentes reçoivent la confirmation."""
    permission_classes = [EstAdminOuPedagogie]

    @transaction.atomic
    def post(self, request, session_id):
        session = get_object_or_404(Session.objects.select_for_update().select_related('etape'), pk=session_id)
        affectations = list(AffectationCandidat.objects.select_for_update().filter(session=session).select_related(
            'participation_etape__candidature__utilisateur'
        ))
        absents = 0
        confirmations = 0
        for affectation in affectations:
            participation = affectation.participation_etape
            candidature = participation.candidature
            if affectation.statutPresence == StatutPresence.A_ATTENDRE:
                affectation.statutPresence = StatutPresence.ABSENT
                affectation.dateEmargement = timezone.now()
                affectation.save(update_fields=['statutPresence', 'dateEmargement'])
                participation.statut = StatutEtape.ABSENT
                participation.dateSortie = timezone.now()
                participation.motif = 'Absent lors de la clôture automatique de la session.'
                participation.save(update_fields=['statut', 'dateSortie', 'motif'])
                candidature.statut = StatutCandidature.TERMINEE
                candidature.save(update_fields=['statut'])
                envoyer_notification(candidature, TypeNotification.FIN_PARCOURS, 'Fin de votre parcours de sélection', 'Vous avez été marqué(e) absent(e) à votre session. Votre parcours de sélection est terminé.')
                absents += 1
            elif affectation.statutPresence == StatutPresence.PRESENT and not affectation.dateConfirmation:
                lien = f"{settings.FRONTEND_URL}/confirmation-presence/{affectation.tokenConfirmation}"
                envoyer_notification(candidature, TypeNotification.CONFIRMATION, 'Confirmez votre présence', f'Votre présence a été enregistrée. Confirmez-la via ce lien : {lien}')
                confirmations += 1
        return Response({'absents': absents, 'confirmationsEnvoyees': confirmations})


class ConfirmationPresenceView(APIView):
    """Page publique utilisée par le lien envoyé après le pointage / clôture pour valider le souhait de continuer le parcours."""
    permission_classes = []
    authentication_classes = []

    def get(self, request, token):
        affectation = get_object_or_404(AffectationCandidat.objects.select_related(
            'session__etape__cohorte', 'participation_etape__candidature__utilisateur'
        ), tokenConfirmation=token, statutPresence=StatutPresence.PRESENT)
        
        candidature = affectation.participation_etape.candidature
        
        return Response({
            'nom': candidature.utilisateur.get_full_name() or candidature.utilisateur.email,
            'etapeNom': affectation.session.etape.nom,
            'date': affectation.session.date,
            'confirmee': bool(affectation.dateConfirmation),
            'statutCandidature': candidature.statut,
        })

    @transaction.atomic
    def post(self, request, token):
        affectation = get_object_or_404(
            AffectationCandidat.objects.select_for_update().select_related('session__etape__cohorte', 'participation_etape__candidature'),
            tokenConfirmation=token,
            statutPresence=StatutPresence.PRESENT
        )
        
        continuer = request.data.get('continuer', True)
        participation = affectation.participation_etape
        candidature = participation.candidature

        if not affectation.dateConfirmation:
            affectation.dateConfirmation = timezone.now()
            affectation.save(update_fields=['dateConfirmation'])

        if continuer:
            # Valider l'étape 2 (Réunion d'information)
            participation.statut = StatutEtape.REUSSIE
            participation.dateSortie = timezone.now()
            participation.save(update_fields=['statut', 'dateSortie'])

            # Créer automatiquement la participation à l'Étape 3 (Test) pour ce candidat qui souhaite continuer !
            etapes_cohorte = list(Etape.objects.filter(cohorte=affectation.session.etape.cohorte).order_by('ordre'))
            etape_test = next((e for e in etapes_cohorte if 'test' in e.nom.lower() or e.ordre == 3), None)
            
            part_test = None
            if etape_test:
                part_test, _ = ParticipationEtape.objects.get_or_create(
                    candidature=candidature,
                    etape=etape_test,
                    defaults={'statut': StatutEtape.EN_ATTENTE}
                )

            envoyer_notification(
                candidature,
                TypeNotification.CONVOCATION,
                'Étape 3 : Accès au Test QCM',
                'Votre confirmation a bien été enregistrée. Vous pouvez désormais passer votre test QCM depuis votre espace candidat.'
            )

            return Response({
                'detail': 'Choix enregistré. Vous continuez la procédure de candidature !',
                'continuer': True,
                'participationTestId': part_test.id if part_test else None
            })

        else:
            # Le candidat a choisi de ne pas continuer
            participation.statut = StatutEtape.ANNULEE
            participation.dateSortie = timezone.now()
            participation.motif = 'Le candidat a choisi d arrêter sa candidature après la réunion d information.'
            participation.save(update_fields=['statut', 'dateSortie', 'motif'])

            candidature.statut = StatutCandidature.TERMINEE
            candidature.save(update_fields=['statut'])

            envoyer_notification(
                candidature,
                TypeNotification.FIN_PARCOURS,
                'Fin de votre candidature',
                'Votre décision d arrêter votre candidature a bien été prise en compte.'
            )

            return Response({
                'detail': 'Votre décision d arrêter votre candidature a bien été enregistrée.',
                'continuer': False
            })


# ============================================================================
# VUES QCM (ÉQUIPE PÉDAGOGIQUE)
# ============================================================================

class TestQCMViewSet(viewsets.ModelViewSet):
    """API CRUD pour les tests QCM gérés par l'Équipe Pédagogique."""
    queryset = TestQCM.objects.all()
    serializer_class = TestQCMSerializer
    permission_classes = [EstAdminOuPedagogie]

    def get_queryset(self):
        queryset = super().get_queryset()
        etape_id = self.request.query_params.get('etape')
        if etape_id:
            queryset = queryset.filter(etape_id=etape_id)
        cohorte_id = self.request.query_params.get('cohorte')
        if cohorte_id:
            queryset = queryset.filter(etape__cohorte_id=cohorte_id)
        return queryset

    @action(detail=True, methods=['post'], url_path='publier')
    def publier(self, request, pk=None):
        test = self.get_object()
        if not test.questions.exists():
            return Response(
                {"detail": "Impossible de publier un test sans question."},
                status=status.HTTP_400_BAD_REQUEST
            )
        test.estPublie = not test.estPublie
        test.save(update_fields=['estPublie'])

        if test.estPublie:
            # Informer les candidats à l'Étape 3 que le test est publié
            participations = ParticipationEtape.objects.filter(
                etape=test.etape,
                candidature__statut__in=[StatutCandidature.EN_COURS, StatutCandidature.EN_ATTENTE]
            ).select_related('candidature')
            for part in participations:
                envoyer_notification(
                    part.candidature,
                    TypeNotification.CONVOCATION,
                    'Étape 3 : Le Test QCM est désormais disponible',
                    f'Le test QCM « {test.titre} » a été publié par l\'Équipe Pédagogique. Vous pouvez dès à présent le passer sur votre espace candidat.'
                )

        statut_txt = "publié" if test.estPublie else "dépublié"
        return Response({"detail": f"Le test QCM est désormais {statut_txt}.", "estPublie": test.estPublie})

    @action(detail=True, methods=['get'], url_path='passages')
    def passages(self, request, pk=None):
        test = self.get_object()
        passages = test.passages.select_related('participation__candidature__utilisateur').all()
        data = []
        for p in passages:
            cand = p.participation.candidature
            user = cand.utilisateur
            data.append({
                "id": p.id,
                "candidatureNumero": cand.numero,
                "candidatNom": user.get_full_name() or user.email,
                "candidatEmail": user.email,
                "scoreObtenu": float(p.scoreObtenu),
                "estAdmis": p.estAdmis,
                "statut": p.statut,
                "dateDebut": p.dateDebut,
                "dateFin": p.dateFin
            })
        return Response(data)


# ============================================================================
# VUES QCM (CANDIDAT - ÉTAPE 3)
# ============================================================================

class CandidateTestDetailsView(APIView):
    """Récupère les détails du test QCM assigné à une participation (Étape 3)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, participation_id):
        participation = get_object_or_404(ParticipationEtape, pk=participation_id)
        
        # Vérification que l'utilisateur est le propriétaire de la candidature
        if participation.candidature.utilisateur != request.user and not request.user.est_admin():
            return Response({"detail": "Accès non autorisé."}, status=status.HTTP_403_FORBIDDEN)

        # Recherche d'un test publié associé à l'étape
        test = TestQCM.objects.filter(etape=participation.etape, estPublie=True).first()
        if not test:
            return Response(
                {"detail": "Aucun test QCM n'est encore disponible pour cette étape."},
                status=status.HTTP_404_NOT_FOUND
            )

        passage = PassageTestQCM.objects.filter(participation=participation, test=test).first()

        data = {
            "test": TestCandidatQCMSerializer(test).data,
            "participationId": participation.id,
            "statutParticipation": participation.statut,
            "passage": {
                "id": passage.id,
                "statut": passage.statut,
                "scoreObtenu": float(passage.scoreObtenu),
                "estAdmis": passage.estAdmis,
                "dateDebut": passage.dateDebut,
                "dateFin": passage.dateFin
            } if passage else None
        }

        return Response(data)


class CandidateStartTestView(APIView):
    """Démarre le chrono d'un passage de test QCM."""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, participation_id):
        participation = get_object_or_404(ParticipationEtape, pk=participation_id)

        if participation.candidature.utilisateur != request.user and not request.user.est_admin():
            return Response({"detail": "Accès non autorisé."}, status=status.HTTP_403_FORBIDDEN)

        test = get_object_or_404(TestQCM, etape=participation.etape, estPublie=True)

        passage, created = PassageTestQCM.objects.get_or_create(
            participation=participation,
            test=test,
            defaults={'statut': StatutPassageTest.EN_COURS}
        )

        return Response({
            "passageId": passage.id,
            "dateDebut": passage.dateDebut,
            "dureeMinutes": test.dureeMinutes,
            "statut": passage.statut,
            "test": TestCandidatQCMSerializer(test).data
        })


class CandidateSubmitTestView(APIView):
    """Soumet les réponses au test QCM, calcule le score et fait passer le candidat à l'Étape 4 (Non bloquant)."""
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, participation_id):
        participation = get_object_or_404(ParticipationEtape, pk=participation_id)

        if participation.candidature.utilisateur != request.user and not request.user.est_admin():
            return Response({"detail": "Accès non autorisé."}, status=status.HTTP_403_FORBIDDEN)

        test = get_object_or_404(TestQCM, etape=participation.etape, estPublie=True)
        passage = get_object_or_404(PassageTestQCM, participation=participation, test=test)

        if passage.statut in [StatutPassageTest.SOUMIS, StatutPassageTest.EXPIRE]:
            return Response({"detail": "Ce test a déjà été soumis."}, status=status.HTTP_400_BAD_REQUEST)

        serializer = SoumissionTestQCMSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reponses_data = serializer.validated_data['reponses']
        
        score_total = 0.0

        for r in reponses_data:
            q_id = r['questionId']
            opt_ids = r['optionIds']
            
            question = get_object_or_404(QuestionQCM, pk=q_id, test=test)
            reponse_obj, _ = ReponseCandidatQCM.objects.get_or_create(passage=passage, question=question)
            
            options_choisies = OptionQCM.objects.filter(pk__in=opt_ids, question=question)
            reponse_obj.optionsChoisies.set(options_choisies)

            # Calcul des points de la question
            correct_options = set(question.options.filter(estCorrecte=True).values_list('id', flat=True))
            user_options = set(options_choisies.values_list('id', flat=True))

            if correct_options == user_options and len(user_options) > 0:
                score_total += float(question.points)

        # Clôture du passage
        passage.scoreObtenu = score_total
        passage.statut = StatutPassageTest.SOUMIS
        passage.dateFin = timezone.now()

        # Évaluation indicative de la réussite
        est_admis = (score_total >= float(test.notePassage))
        passage.estAdmis = est_admis
        passage.save()

        # Validation de la participation à l'Étape 3
        participation.statut = StatutEtape.REUSSIE
        participation.dateSortie = timezone.now()
        participation.save()

        # Passage automatique à l'Étape 4 (Entretien technique & Motivation) - Étape 3 NON BLOQUANTE !
        etape_suivante_creee = False
        etapes_cohorte = list(Etape.objects.filter(cohorte=participation.etape.cohorte).order_by('ordre'))
        try:
            current_idx = [e.id for e in etapes_cohorte].index(participation.etape.id)
            if current_idx + 1 < len(etapes_cohorte):
                next_etape = etapes_cohorte[current_idx + 1]
                ParticipationEtape.objects.get_or_create(
                    candidature=participation.candidature,
                    etape=next_etape,
                    defaults={'statut': StatutEtape.EN_ATTENTE}
                )
                etape_suivante_creee = True
        except ValueError:
            pass

        return Response({
            "detail": "Test QCM soumis avec succès.",
            "scoreObtenu": score_total,
            "baremeTotal": float(test.baremeTotal),
            "notePassage": float(test.notePassage),
            "estAdmis": est_admis,
            "statutEtape": participation.statut,
            "etapeSuivanteCreee": etape_suivante_creee
        })



class QuestionListeView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def get(self, request):
        questions = Question.objects.select_related('cohorte__formation').order_by(
            'cohorte__formation__nom', 'cohorte__nom', 'type', 'ordre'
        )
        cohorte_id = request.query_params.get('cohorte')
        type_question = request.query_params.get('type')
        if cohorte_id:
            questions = questions.filter(cohorte_id=cohorte_id)
        if type_question:
            questions = questions.filter(type=type_question)
        return Response(QuestionSerializer(questions, many=True).data)

    def post(self, request):
        serializer = QuestionSerializer(data=request.data)
        if serializer.is_valid():
            question = serializer.save()
            return Response(QuestionSerializer(question).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QuestionDetailView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def get_object(self, pk):
        return get_object_or_404(Question.objects.select_related('cohorte__formation'), pk=pk)

    def get(self, request, pk):
        return Response(QuestionSerializer(self.get_object(pk)).data)

    def put(self, request, pk):
        serializer = QuestionSerializer(self.get_object(pk), data=request.data, partial=True)
        if serializer.is_valid():
            try:
                question = serializer.save()
            except ValidationError as exc:
                return Response({'detail': exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
            return Response(QuestionSerializer(question).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        try:
            self.get_object(pk).delete()
        except ValidationError as exc:
            return Response({'detail': exc.messages[0]}, status=status.HTTP_400_BAD_REQUEST)
        return Response(status=status.HTTP_204_NO_CONTENT)


ROLE_TO_QUESTION_TYPE = {
    AffectationEvaluateur.RoleEncadrement.TECHNIQUE: TypeQuestion.TECHNIQUE,
    AffectationEvaluateur.RoleEncadrement.MOTIVATION: TypeQuestion.SOFT_SKILLS_MOTIVATION,
}

ROLE_LABELS = {
    AffectationEvaluateur.RoleEncadrement.TECHNIQUE: 'Entretien technique',
    AffectationEvaluateur.RoleEncadrement.MOTIVATION: 'Entretien de motivation',
}


def get_candidate_type_summary(candidature, question_type):
    questions = Question.objects.filter(
        cohorte=candidature.campagne.cohorte,
        type=question_type,
    )
    evaluations = Evaluation.objects.filter(
        participation__candidature=candidature,
        question__type=question_type,
    )
    validated = evaluations.filter(validee=True)
    required_count = questions.count()
    validated_count = validated.count()

    if required_count and validated_count >= required_count:
        status_value = 'completed'
    elif evaluations.exists():
        status_value = 'progress'
    else:
        status_value = 'En-attente'

    total = sum((item.note for item in validated), Decimal('0'))
    average = (total / validated_count) if validated_count else None

    return {
        'status': status_value,
        'statusLabel': 'Terminé' if status_value == 'completed' else ('En cours' if status_value == 'progress' else 'En-attente'),
        'averageScore': float(average) if average is not None else None,
        'validated': status_value == 'completed',
    }


def get_candidate_evaluation_overview(candidature):
    technique = get_candidate_type_summary(candidature, TypeQuestion.TECHNIQUE)
    motivation = get_candidate_type_summary(candidature, TypeQuestion.SOFT_SKILLS_MOTIVATION)
    averages = [
        item['averageScore']
        for item in (technique, motivation)
        if item['averageScore'] is not None
    ]
    general_average = sum(averages) / len(averages) if averages else None
    can_decide = technique['validated'] and motivation['validated']

    return technique, motivation, general_average, can_decide


def serialize_pedagogical_candidate(candidature):
    utilisateur = candidature.utilisateur
    cohorte = candidature.campagne.cohorte if candidature.campagne else None
    formation = cohorte.formation if cohorte else None
    technique, motivation, general_average, can_decide = get_candidate_evaluation_overview(candidature)
    decision = getattr(candidature, 'decision_finale', None)
    affectation = AffectationCandidat.objects.filter(
        participation_etape__candidature=candidature,
    ).select_related('session__etape').order_by('-session__date', '-session__heureDebut').first()

    return {
        'id': str(candidature.id),
        'candidatureId': str(candidature.id),
        'candidateId': str(utilisateur.id),
        'numero': candidature.numero,
        'nom': utilisateur.get_full_name() or utilisateur.email,
        'prenom': utilisateur.first_name,
        'nomFamille': utilisateur.last_name,
        'email': utilisateur.email,
        'telephone': utilisateur.telephone,
        'formation': formation.nom if formation else '',
        'cohorte': cohorte.nom if cohorte else '',
        'statutCandidature': candidature.statut,
        'statutPresence': affectation.statutPresence if affectation else '',
        'statutEtape': affectation.participation_etape.statut if affectation else '',
        'etape': affectation.session.etape.nom if affectation else '',
        'date': affectation.session.date if affectation else '',
        'heureDebut': affectation.session.heureDebut if affectation else '',
        'heureFin': affectation.session.heureFin if affectation else '',
        'lieu': (affectation.session.lieu or affectation.session.localisation) if affectation else '',
        'technique': technique,
        'motivation': motivation,
        'final': {},
        'moyenneGenerale': round(general_average, 2) if general_average is not None else None,
        'canDecide': can_decide,
        'decision': {
            'id': str(decision.id),
            'type': decision.type,
            'motif': decision.motif,
        } if decision else None,
    }


class InterviewCandidatesView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def get(self, request, candidature_id=None):
        queryset = Candidature.objects.filter(
            participations__affectation_session__isnull=False,
        ).distinct().select_related(
            'utilisateur',
            'campagne__cohorte__formation',
            'decision_finale',
        ).order_by('utilisateur__last_name', 'utilisateur__first_name')

        if candidature_id:
            candidature = get_object_or_404(queryset, pk=candidature_id)
            return Response(serialize_pedagogical_candidate(candidature))

        return Response([
            serialize_pedagogical_candidate(candidature)
            for candidature in queryset
        ])


def build_interview_id(affectation, role):
    return f'{affectation.id}:{role.lower()}'


def parse_interview_id(interview_id):
    try:
        affectation_id, role = str(interview_id).split(':', 1)
    except ValueError:
        affectation_id, role = str(interview_id), AffectationEvaluateur.RoleEncadrement.TECHNIQUE
    role = role.upper()
    if role not in ROLE_TO_QUESTION_TYPE:
        raise ValueError('Type d entretien invalide.')
    return affectation_id, role


def get_evaluator_interview(request, interview_id):
    affectation_id, role = parse_interview_id(interview_id)
    affectation = get_object_or_404(
        AffectationCandidat.objects.select_related(
            'session__etape__cohorte__formation',
            'participation_etape__candidature__utilisateur',
        ),
        pk=affectation_id,
    )
    get_object_or_404(
        AffectationEvaluateur,
        session=affectation.session,
        evaluateur=request.user,
        roleEncadrement=role,
    )
    return affectation, role


def get_interview_questions(affectation, role):
    return Question.objects.filter(
        cohorte=affectation.session.etape.cohorte,
        type=ROLE_TO_QUESTION_TYPE[role],
    ).order_by('ordre')


def get_interview_evaluations(affectation, role):
    question_type = ROLE_TO_QUESTION_TYPE[role]
    return Evaluation.objects.filter(
        participation=affectation.participation_etape,
        question__type=question_type,
    ).select_related('question').order_by('question__ordre')


def serialize_question_for_interview(question):
    return {
        'id': str(question.id),
        'text': question.contenu,
        'question': question.contenu,
        'maxScore': float(question.baremeMax),
        'ordre': question.ordre,
    }


def get_interview_evaluation_owner(affectation, role):
    evaluation = get_interview_evaluations(affectation, role).first()
    return evaluation.evaluateur if evaluation else None


def evaluator_can_edit_interview(request, affectation, role):
    owner = get_interview_evaluation_owner(affectation, role)
    return owner is None or owner == request.user


def serialize_candidate_from_candidature(candidature):
    utilisateur = candidature.utilisateur
    cohorte = candidature.campagne.cohorte if candidature.campagne else None
    formation = cohorte.formation if cohorte else None
    return {
        'id': utilisateur.id,
        'firstName': utilisateur.first_name,
        'lastName': utilisateur.last_name,
        'email': utilisateur.email,
        'phone': utilisateur.telephone,
        'formation': formation.nom if formation else '',
        'promotion': cohorte.nom if cohorte else '',
        'campagneId': candidature.campagne.id if candidature.campagne else '',
        'campagneName': candidature.campagne.nom if candidature.campagne else '',
        'candidatureId': candidature.id,
        'numero': candidature.numero,
        'statut': candidature.statut,
    }


def evaluation_summary(affectation, role):
    questions = list(get_interview_questions(affectation, role))
    evaluations = list(get_interview_evaluations(affectation, role))
    validated = bool(questions) and len(evaluations) == len(questions) and all(item.validee for item in evaluations)
    if validated:
        status_value = 'completed'
    elif evaluations:
        status_value = 'progress'
    else:
        status_value = 'En-attente'
    total = sum((item.note for item in evaluations), Decimal('0'))
    average = (total / len(evaluations)) if evaluations else None
    return questions, evaluations, validated, status_value, average


def mark_candidate_finished_if_all_interviews_done(participation):
    required_types = [TypeQuestion.TECHNIQUE, TypeQuestion.SOFT_SKILLS_MOTIVATION]
    for question_type in required_types:
        questions = Question.objects.filter(cohorte=participation.etape.cohorte, type=question_type)
        if not questions.exists():
            return
        validated_count = Evaluation.objects.filter(
            participation=participation,
            question__in=questions,
            validee=True,
        ).count()
        if validated_count != questions.count():
            return
    participation.statut = StatutEtape.REUSSIE
    participation.dateSortie = timezone.now()
    participation.save(update_fields=['statut', 'dateSortie'])
    candidature = participation.candidature
    candidature.statut = StatutCandidature.TERMINEE
    candidature.save(update_fields=['statut'])


def serialize_interview(affectation, role):
    candidature = affectation.participation_etape.candidature
    utilisateur = candidature.utilisateur
    _, _, _, status_value, _ = evaluation_summary(affectation, role)
    return {
        'id': build_interview_id(affectation, role),
        'candidateId': utilisateur.id,
        'candidateName': utilisateur.get_full_name() or utilisateur.email,
        'candidateEmail': utilisateur.email,
        'campagneId': candidature.campagne.id if candidature.campagne else '',
        'campagneName': candidature.campagne.nom if candidature.campagne else '',
        'type': 'motivation' if role == AffectationEvaluateur.RoleEncadrement.MOTIVATION else 'technique',
        'typeLabel': ROLE_LABELS[role],
        'date': affectation.session.date,
        'startTime': affectation.session.heureDebut,
        'endTime': affectation.session.heureFin,
        'location': affectation.session.lieu or affectation.session.localisation or '',
        'status': status_value,
        'statusLabel': 'Terminé' if status_value == 'completed' else ('En cours' if status_value == 'progress' else 'En-attente'),
        'participationId': affectation.participation_etape.id,
        'candidatureId': candidature.id,
        'sessionId': affectation.session.id,
    }


def serialize_evaluation_sheet(affectation, role):
    questions, evaluations, validated, status_value, average = evaluation_summary(affectation, role)
    response = {
        'type': 'motivation' if role == AffectationEvaluateur.RoleEncadrement.MOTIVATION else 'technique',
        'questions': [] if validated else [serialize_question_for_interview(question) for question in questions],
        'answers': {},
        'notes': {},
        'score': float(average) if average is not None else None,
        'averageScore': float(average) if average is not None else None,
        'comment': '',
        'status': status_value,
        'validated': validated,
    }
    if not validated:
        for evaluation in evaluations:
            question_id = str(evaluation.question_id)
            response['answers'][question_id] = evaluation.reponse or ''
            response['notes'][question_id] = float(evaluation.note)
            response['comment'] = evaluation.commentaire or response['comment']
    return response


class EvaluatorCandidatesView(APIView):
    permission_classes = [EstEvaluateur]

    def get(self, request):
        affectations = AffectationCandidat.objects.filter(
            session__affectations_evaluateurs__evaluateur=request.user,
        ).select_related(
            'participation_etape__candidature__utilisateur',
            'participation_etape__candidature__campagne__cohorte__formation',
        ).exclude(statutPresence=StatutPresence.ABSENT).distinct().order_by(
            'participation_etape__candidature__utilisateur__last_name',
            'participation_etape__candidature__utilisateur__first_name',
        )
        candidatures = []
        vus = set()
        for affectation in affectations:
            candidature = affectation.participation_etape.candidature
            if candidature.id in vus:
                continue
            vus.add(candidature.id)
            candidatures.append(serialize_candidate_from_candidature(candidature))
        return Response(candidatures)


class EvaluatorCandidateDetailView(APIView):
    permission_classes = [EstEvaluateur]

    def get(self, request, candidate_id):
        candidature = get_object_or_404(
            Candidature.objects.select_related('utilisateur', 'campagne__cohorte__formation').distinct(),
            utilisateur_id=candidate_id,
            participations__affectation_session__session__affectations_evaluateurs__evaluateur=request.user,
        )
        return Response(serialize_candidate_from_candidature(candidature))


class EvaluatorInterviewsView(APIView):
    permission_classes = [EstEvaluateur]

    def get(self, request):
        evaluator_assignments = AffectationEvaluateur.objects.filter(
            evaluateur=request.user,
            roleEncadrement__in=ROLE_TO_QUESTION_TYPE.keys(),
        ).select_related('session')
        roles_by_session = {}
        for assignment in evaluator_assignments:
            roles_by_session.setdefault(assignment.session_id, set()).add(assignment.roleEncadrement)
        affectations = AffectationCandidat.objects.filter(
            session_id__in=roles_by_session.keys(),
        ).select_related(
            'session__etape__cohorte__formation',
            'participation_etape__candidature__utilisateur',
        ).exclude(statutPresence=StatutPresence.ABSENT).order_by('session__date', 'session__heureDebut')
        data = []
        for affectation in affectations:
            for role in sorted(roles_by_session.get(affectation.session_id, [])):
                data.append(serialize_interview(affectation, role))
        return Response(data)


class EvaluatorInterviewDetailView(APIView):
    permission_classes = [EstEvaluateur]

    def get(self, request, interview_id):
        try:
            affectation, role = get_evaluator_interview(request, interview_id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_interview(affectation, role))


class EvaluatorEvaluationView(APIView):
    permission_classes = [EstEvaluateur]

    def get(self, request, interview_id):
        try:
            affectation, role = get_evaluator_interview(request, interview_id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serialize_evaluation_sheet(affectation, role))

    @transaction.atomic
    def post(self, request, interview_id):
        try:
            affectation, role = get_evaluator_interview(request, interview_id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not evaluator_can_edit_interview(request, affectation, role):
            return Response(
                {'detail': 'Cet entretien est déjà pris en charge par un autre évaluateur.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        if get_interview_evaluations(affectation, role).filter(validee=True).exists():
            return Response({'detail': 'Cet entretien est validé et ne peut plus être modifié.'}, status=status.HTTP_400_BAD_REQUEST)
        questions = list(get_interview_questions(affectation, role))
        if not questions:
            return Response({'detail': 'Aucune question configurée pour cet entretien.'}, status=status.HTTP_400_BAD_REQUEST)
        notes = request.data.get('notes') or {}
        answers = request.data.get('answers') or {}
        commentaire = request.data.get('comment') or request.data.get('commentaire') or ''
        for question in questions:
            question_id = str(question.id)
            if question_id not in notes or answers.get(question_id) in (None, ''):
                return Response({'detail': 'Toutes les questions doivent avoir une réponse et une note.'}, status=status.HTTP_400_BAD_REQUEST)
            try:
                note = Decimal(str(notes[question_id]))
            except (InvalidOperation, TypeError):
                return Response({'detail': 'Une note est invalide.'}, status=status.HTTP_400_BAD_REQUEST)
            if note < 0 or note > question.baremeMax:
                return Response({'detail': f'La note de "{question.contenu}" doit être comprise entre 0 et {question.baremeMax}.'}, status=status.HTTP_400_BAD_REQUEST)
            Evaluation.objects.update_or_create(
                participation=affectation.participation_etape,
                question=question,
                defaults={
                    'evaluateur': request.user,
                    'note': note,
                    'reponse': answers.get(question_id, ''),
                    'commentaire': commentaire,
                    'validee': False,
                },
            )
        return Response(serialize_evaluation_sheet(affectation, role))


class EvaluatorEvaluationValidateView(APIView):
    permission_classes = [EstEvaluateur]

    @transaction.atomic
    def post(self, request, interview_id):
        try:
            affectation, role = get_evaluator_interview(request, interview_id)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not evaluator_can_edit_interview(request, affectation, role):
            return Response(
                {'detail': 'Cet entretien est déjà pris en charge par un autre évaluateur.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        questions = list(get_interview_questions(affectation, role))
        evaluations = list(get_interview_evaluations(affectation, role).select_for_update())
        if not questions or len(evaluations) != len(questions):
            return Response({'detail': 'Toutes les questions doivent être évaluées avant validation.'}, status=status.HTTP_400_BAD_REQUEST)
        if all(evaluation.validee for evaluation in evaluations):
            return Response({'evaluation': serialize_evaluation_sheet(affectation, role)})
        Evaluation.objects.filter(id__in=[evaluation.id for evaluation in evaluations]).update(validee=True)
        mark_candidate_finished_if_all_interviews_done(affectation.participation_etape)
        return Response({'evaluation': serialize_evaluation_sheet(affectation, role)})


class DecisionCandidatureView(APIView):
    permission_classes = [EstAdminOuPedagogie]

    def post(self, request, candidature_id):

        try:
            candidature = Candidature.objects.select_related(
                'utilisateur',
                'campagne__cohorte__formation',
                'decision_finale',
            ).get(
                id=candidature_id
            )

        except Candidature.DoesNotExist:

            return Response(
                {
                    'detail': 'Candidature introuvable.'
                },
                status=status.HTTP_404_NOT_FOUND
            )

        decision_type = request.data.get('decision')

        decisions_valides = [
            TypeDecision.ADMIS,
            TypeDecision.REFUSE,
            TypeDecision.EN_ATTENTE,
        ]

        if decision_type not in decisions_valides:

            return Response(
                {
                    'detail': 'Décision invalide.',
                    'decisions_valides': decisions_valides
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        _, _, _, can_decide = get_candidate_evaluation_overview(candidature)
        if not can_decide:
            return Response(
                {
                    'detail': 'Les deux entretiens doivent être terminés avant de prendre une décision.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        decision, created = Decision.objects.update_or_create(

            candidature=candidature,

            defaults={
                'type': decision_type,
                'motif': request.data.get('motif', '')
            }

        )

        return Response(
            {
                'message': 'Décision enregistrée avec succès.',
                'decision': {
                    'id': str(decision.id),
                    'type': decision.type,
                    'motif': decision.motif,
                    'candidature': str(candidature.id),
                }
            },
            status=status.HTTP_201_CREATED if created
            else status.HTTP_200_OK
        )
