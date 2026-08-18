from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.core.mail import EmailMessage, send_mail

from utilisateurs.models import Utilisateur, NomRole
from candidatures.models import Candidature
from .models import AffectationCandidat, Etape, ParticipationEtape, Session, StatutEtape, StatutPresence
from .serializers import ParticipationEtapeSerializer, PlanningConfigurationSerializer, PlanningSerializer
from utilisateurs.permissions import EstAdminOuGestionProjet, EstAdminOuPedagogie
from candidatures.models import StatutCandidature
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
        ).distinct().select_related('utilisateur', 'campagne', 'campagne__cohorte').order_by('utilisateur__last_name', 'utilisateur__first_name'))
        
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
    """Page publique utilisée par le lien envoyé après le pointage."""
    permission_classes = []
    authentication_classes = []

    def get(self, request, token):
        affectation = get_object_or_404(AffectationCandidat.objects.select_related(
            'session__etape', 'participation_etape__candidature__utilisateur'
        ), tokenConfirmation=token, statutPresence=StatutPresence.PRESENT)
        return Response({
            'nom': affectation.participation_etape.candidature.utilisateur.get_full_name(),
            'etapeNom': affectation.session.etape.nom,
            'date': affectation.session.date,
            'confirmee': bool(affectation.dateConfirmation),
        })

    def post(self, request, token):
        affectation = get_object_or_404(AffectationCandidat.objects.select_for_update(), tokenConfirmation=token, statutPresence=StatutPresence.PRESENT)
        if not affectation.dateConfirmation:
            affectation.dateConfirmation = timezone.now()
            affectation.save(update_fields=['dateConfirmation'])
        return Response({'detail': 'Présence confirmée.'})
