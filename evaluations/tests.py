from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from utilisateurs.models import Utilisateur, Role, NomRole
from campagnes.models import Formation, Cohorte, Campagne
from candidatures.models import Candidature, StatutCandidature
from evaluations.models import (
    Etape, ParticipationEtape, TestQCM, QuestionQCM, OptionQCM,
    PassageTestQCM, StatutPassageTest, StatutEtape
)

class TestQCMWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        
        # Rôles
        self.role_admin = Role.objects.create(nom=NomRole.ADMINISTRATEUR)
        self.role_candidat = Role.objects.create(nom=NomRole.CANDIDAT)

        # Users
        self.admin = Utilisateur.objects.create_user(
            username='admin@test.com', email='admin@test.com', password='password123', role=self.role_admin, is_staff=True
        )
        self.candidat_user = Utilisateur.objects.create_user(
            username='candidat@test.com', email='candidat@test.com', password='password123', role=self.role_candidat
        )

        # Formation et Cohorte
        self.formation = Formation.objects.create(nom='Développement Web')
        self.cohorte = Cohorte.objects.create(nom='Promo 2026', formation=self.formation)

        # Étapes
        self.etape1 = Etape.objects.create(nom='Candidature', ordre=1, cohorte=self.cohorte)
        self.etape2 = Etape.objects.create(nom="Réunion d'information", ordre=2, cohorte=self.cohorte)
        self.etape3 = Etape.objects.create(nom='Test', ordre=3, cohorte=self.cohorte)
        self.etape4 = Etape.objects.create(nom='Entretien technique & Motivation', ordre=4, cohorte=self.cohorte)
        self.etape5 = Etape.objects.create(nom='Entretien Final', ordre=5, cohorte=self.cohorte)

        # Campagne
        from django.utils import timezone
        self.campagne = Campagne.objects.create(
            nom='Campagne Test 2026',
            cohorte=self.cohorte,
            dateOuverture=timezone.now(),
            dateCloture=timezone.now()
        )

        # Candidature
        self.candidature = Candidature.objects.create(
            utilisateur=self.candidat_user,
            campagne=self.campagne,
            numero='CND-2026-001',
            statut=StatutCandidature.EN_COURS
        )
        self.part3 = ParticipationEtape.objects.create(
            candidature=self.candidature,
            etape=self.etape3,
            statut=StatutEtape.EN_COURS
        )

        # QCM
        self.test = TestQCM.objects.create(
            titre='Test Pédagogique QCM',
            description='Test d evaluation',
            dureeMinutes=20,
            baremeTotal=20.00,
            notePassage=10.00,
            estPublie=True,
            etape=self.etape3,
            creePar=self.admin
        )

        self.question1 = QuestionQCM.objects.create(
            test=self.test, intitule='Question 1', points=10.00, ordre=1
        )
        self.opt1_vrai = OptionQCM.objects.create(question=self.question1, texte='Reponse A', estCorrecte=True)
        self.opt1_faux = OptionQCM.objects.create(question=self.question1, texte='Reponse B', estCorrecte=False)

    def test_start_and_submit_qcm_non_bloquant(self):
        self.client.force_authenticate(user=self.candidat_user)
        
        # 1. Obtenir les détails
        url_details = reverse('candidat-test-details', kwargs={'participation_id': self.part3.id})
        response = self.client.get(url_details)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['test']['titre'], 'Test Pédagogique QCM')

        # 2. Démarrer le test
        url_start = reverse('candidat-commencer-test', kwargs={'participation_id': self.part3.id})
        response = self.client.post(url_start)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('passageId', response.data)

        # 3. Soumettre le test avec mauvaise réponse (note < notePassage)
        url_submit = reverse('candidat-soumettre-test', kwargs={'participation_id': self.part3.id})
        payload = {
            'reponses': [
                {'questionId': str(self.question1.id), 'optionIds': [str(self.opt1_faux.id)]}
            ]
        }
        response = self.client.post(url_submit, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scoreObtenu'], 0.0)
        self.assertFalse(response.data['estAdmis'])
        
        # 4. Vérifier que la participation à l'Étape 3 est validée (REUSSIE) et que l'Étape 4 est créée
        self.part3.refresh_from_db()
        self.assertEqual(self.part3.statut, StatutEtape.REUSSIE)
        self.assertTrue(
            ParticipationEtape.objects.filter(candidature=self.candidature, etape=self.etape4).exists()
        )

    def test_delete_qcm_by_admin(self):
        self.client.force_authenticate(user=self.admin)
        url = reverse('tests-qcm-detail', kwargs={'pk': self.test.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TestQCM.objects.filter(id=self.test.id).exists())
