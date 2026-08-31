from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from campagnes.models import Campagne, Cohorte, Formation, StatutCampagne
from candidatures.models import Candidature
from evaluations.models import (
    AffectationCandidat,
    Etape,
    ParticipationEtape,
    Session,
    StatutPresence,
)
from notifications.models import Notification, TypeNotification
from utilisateurs.models import NomRole, Role, Utilisateur

from .models import Test


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PublicationTestTests(TestCase):
    def setUp(self):
        now = timezone.now()
        formation = Formation.objects.create(nom='Developpement web')
        cohorte = Cohorte.objects.create(nom='P1', formation=formation)
        self.campagne = Campagne.objects.create(
            nom='Campagne test',
            cohorte=cohorte,
            dateOuverture=now - timedelta(days=2),
            dateCloture=now + timedelta(days=2),
            statut=StatutCampagne.OUVERTE,
        )
        self.reunion = Etape.objects.create(
            nom="Reunion d'information", ordre=1, cohorte=cohorte,
        )
        self.entretien = Etape.objects.create(
            nom='Entretien', ordre=2, cohorte=cohorte,
        )
        self.test = Test.objects.create(
            nom='Test technique',
            campagne_assossiee=self.campagne,
            description='Consignes',
            date_ouverture=now,
            date_cloture=now + timedelta(days=1),
        )

    def creer_candidature(self, numero, email):
        utilisateur = Utilisateur.objects.create_user(
            username=numero,
            email=email,
            first_name=numero,
            password='password',
        )
        return Candidature.objects.create(
            numero=numero,
            utilisateur=utilisateur,
            campagne=self.campagne,
        )

    def marquer_presence(self, candidature, etape, presence):
        participation = ParticipationEtape.objects.create(
            candidature=candidature,
            etape=etape,
        )
        session = Session.objects.create(
            date=timezone.localdate(),
            heureDebut=timezone.datetime(2026, 1, 1, 9, 0).time(),
            heureFin=timezone.datetime(2026, 1, 1, 10, 0).time(),
            capacite=20,
            etape=etape,
        )
        AffectationCandidat.objects.create(
            participation_etape=participation,
            session=session,
            statutPresence=presence,
        )

    def test_liste_uniquement_les_presents_de_la_reunion(self):
        present = self.creer_candidature('CND-001', 'present@example.com')
        absent = self.creer_candidature('CND-002', 'absent@example.com')
        present_entretien = self.creer_candidature('CND-003', 'entretien@example.com')
        self.marquer_presence(present, self.reunion, StatutPresence.PRESENT)
        self.marquer_presence(absent, self.reunion, StatutPresence.ABSENT)
        self.marquer_presence(present_entretien, self.entretien, StatutPresence.PRESENT)

        response = self.client.get(
            reverse('test-candidats-presents', args=[self.test.id]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.json()], [str(present.id)])

    def test_publication_notifie_uniquement_le_candidat_present_selectionne(self):
        present = self.creer_candidature('CND-001', 'present@example.com')
        absent = self.creer_candidature('CND-002', 'absent@example.com')
        self.marquer_presence(present, self.reunion, StatutPresence.PRESENT)
        self.marquer_presence(absent, self.reunion, StatutPresence.ABSENT)

        response = self.client.post(
            reverse('test-publier', args=[self.test.id]),
            {'candidats_ids': [str(present.id), str(absent.id)]},
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['emails_envoyes'], 1)
        self.assertEqual(mail.outbox[0].to, ['present@example.com'])
        self.assertTrue(Notification.objects.filter(
            type=TypeNotification.TEST,
            candidature=present,
        ).exists())

    def test_candidat_present_voit_ses_tests_actifs(self):
        present = self.creer_candidature('CND-001', 'present@example.com')
        present.utilisateur.role, _ = Role.objects.get_or_create(nom=NomRole.CANDIDAT)
        present.utilisateur.save(update_fields=['role'])
        self.marquer_presence(present, self.reunion, StatutPresence.PRESENT)
        self.test.statut = Test.StatusChoices.ACTIF
        self.test.save(update_fields=['statut'])

        client = APIClient()
        client.force_authenticate(user=present.utilisateur)
        response = client.get(reverse('test-mes-tests'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual([item['id'] for item in response.json()], [self.test.id])
