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
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from campagnes.models import Campagne, Cohorte, Formation, StatutCampagne
from candidatures.models import Candidature, StatutCandidature
from utilisateurs.models import NomRole, Role, Utilisateur
from .models import (
    AffectationCandidat,
    AffectationEvaluateur,
    Etape,
    Evaluation,
    ParticipationEtape,
    Question,
    Session,
    StatutEtape,
    TypeQuestion,
)
from .views import build_interview_id


class EvaluatorEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.role_evaluateur = Role.objects.create(nom=NomRole.EVALUATEUR)
        self.role_candidat = Role.objects.create(nom=NomRole.CANDIDAT)
        self.role_pedagogie = Role.objects.create(nom=NomRole.EQUIPE_PEDAGOGIQUE)

        self.evaluateur = Utilisateur.objects.create_user(
            username='eval.tech',
            email='eval.tech@example.com',
            password='pass',
            role=self.role_evaluateur,
        )
        self.evaluateur_bis = Utilisateur.objects.create_user(
            username='eval.tech2',
            email='eval.tech2@example.com',
            password='pass',
            role=self.role_evaluateur,
        )
        self.candidat = Utilisateur.objects.create_user(
            username='candidate',
            email='candidate@example.com',
            password='pass',
            first_name='Awa',
            last_name='Ndiaye',
            role=self.role_candidat,
        )
        self.pedagogie = Utilisateur.objects.create_user(
            username='pedagogie',
            email='pedagogie@example.com',
            password='pass',
            role=self.role_pedagogie,
        )

        self.formation = Formation.objects.create(nom='Dev Web')
        self.cohorte = Cohorte.objects.create(nom='Promo 1', formation=self.formation)
        self.campagne = Campagne.objects.create(
            nom='Campagne Dev Web',
            dateOuverture=timezone.now() - timedelta(days=1),
            dateCloture=timezone.now() + timedelta(days=10),
            statut=StatutCampagne.OUVERTE,
            cohorte=self.cohorte,
        )
        self.candidature = Candidature.objects.create(
            numero='CAND-001',
            utilisateur=self.candidat,
            campagne=self.campagne,
            statut=StatutCandidature.EN_COURS,
        )
        self.etape = Etape.objects.create(nom='Entretiens', ordre=1, cohorte=self.cohorte)
        self.participation = ParticipationEtape.objects.create(
            candidature=self.candidature,
            etape=self.etape,
            statut=StatutEtape.EN_COURS,
        )
        self.session = Session.objects.create(
            date=date.today(),
            heureDebut=time(9, 0),
            heureFin=time(10, 0),
            lieu='Salle 1',
            capacite=10,
            etape=self.etape,
        )
        self.affectation = AffectationCandidat.objects.create(
            participation_etape=self.participation,
            session=self.session,
        )
        AffectationEvaluateur.objects.create(
            evaluateur=self.evaluateur,
            session=self.session,
            roleEncadrement=AffectationEvaluateur.RoleEncadrement.TECHNIQUE,
        )
        AffectationEvaluateur.objects.create(
            evaluateur=self.evaluateur,
            session=self.session,
            roleEncadrement=AffectationEvaluateur.RoleEncadrement.MOTIVATION,
        )
        self.question_technique = Question.objects.create(
            contenu='Explique Django REST Framework.',
            type=TypeQuestion.TECHNIQUE,
            baremeMax=Decimal('20.00'),
            ordre=1,
            cohorte=self.cohorte,
        )
        self.question_motivation = Question.objects.create(
            contenu='Pourquoi cette formation ?',
            type=TypeQuestion.SOFT_SKILLS_MOTIVATION,
            baremeMax=Decimal('20.00'),
            ordre=1,
            cohorte=self.cohorte,
        )

    def interview_url(self, role, suffix='evaluation/'):
        interview_id = build_interview_id(self.affectation, role)
        return f'/api/evaluations/evaluator/interviews/{interview_id}/{suffix}'

    def save_evaluation(self, role, question, note='15', reponse='Réponse complète'):
        return self.client.post(
            self.interview_url(role),
            {
                'notes': {str(question.id): note},
                'answers': {str(question.id): reponse},
                'comment': 'Bon échange',
            },
            format='json',
        )

    def test_evaluator_gets_convoked_candidates_and_questionnaire(self):
        self.client.force_authenticate(self.evaluateur)

        candidates_response = self.client.get('/api/evaluations/evaluator/candidates/')
        self.assertEqual(candidates_response.status_code, status.HTTP_200_OK)
        self.assertEqual(candidates_response.data[0]['candidatureId'], self.candidature.id)

        evaluation_response = self.client.get(
            self.interview_url(AffectationEvaluateur.RoleEncadrement.TECHNIQUE)
        )
        self.assertEqual(evaluation_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(evaluation_response.data['questions']), 1)
        self.assertEqual(evaluation_response.data['questions'][0]['id'], str(self.question_technique.id))

    def test_validated_interview_is_read_only_and_hides_answers(self):
        self.client.force_authenticate(self.evaluateur)

        save_response = self.save_evaluation(
            AffectationEvaluateur.RoleEncadrement.TECHNIQUE,
            self.question_technique,
        )
        self.assertEqual(save_response.status_code, status.HTTP_200_OK)

        validate_response = self.client.post(
            self.interview_url(AffectationEvaluateur.RoleEncadrement.TECHNIQUE, 'evaluation/validate/')
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)
        evaluation = validate_response.data['evaluation']
        self.assertTrue(evaluation['validated'])
        self.assertEqual(evaluation['questions'], [])
        self.assertEqual(evaluation['answers'], {})
        self.assertEqual(evaluation['notes'], {})
        self.assertEqual(evaluation['averageScore'], 15.0)

        update_response = self.save_evaluation(
            AffectationEvaluateur.RoleEncadrement.TECHNIQUE,
            self.question_technique,
            note='18',
        )
        self.assertEqual(update_response.status_code, status.HTTP_400_BAD_REQUEST)

        self.question_technique.contenu = 'Question modifiée'
        with self.assertRaises(ValidationError):
            self.question_technique.save()

    def test_candidate_is_finished_after_technical_and_motivation_validation(self):
        self.client.force_authenticate(self.evaluateur)

        self.save_evaluation(
            AffectationEvaluateur.RoleEncadrement.TECHNIQUE,
            self.question_technique,
            note='14',
        )
        self.client.post(
            self.interview_url(AffectationEvaluateur.RoleEncadrement.TECHNIQUE, 'evaluation/validate/')
        )
        self.save_evaluation(
            AffectationEvaluateur.RoleEncadrement.MOTIVATION,
            self.question_motivation,
            note='16',
        )
        validate_response = self.client.post(
            self.interview_url(AffectationEvaluateur.RoleEncadrement.MOTIVATION, 'evaluation/validate/')
        )
        self.assertEqual(validate_response.status_code, status.HTTP_200_OK)

        self.participation.refresh_from_db()
        self.candidature.refresh_from_db()
        self.assertEqual(self.participation.statut, StatutEtape.REUSSIE)
        self.assertEqual(self.candidature.statut, StatutCandidature.TERMINEE)
        self.assertIsNotNone(self.participation.dateSortie)

    def test_second_evaluator_cannot_overwrite_an_existing_interview(self):
        AffectationEvaluateur.objects.create(
            evaluateur=self.evaluateur_bis,
            session=self.session,
            roleEncadrement=AffectationEvaluateur.RoleEncadrement.TECHNIQUE,
        )
        self.client.force_authenticate(self.evaluateur)
        self.save_evaluation(
            AffectationEvaluateur.RoleEncadrement.TECHNIQUE,
            self.question_technique,
            note='12',
        )

        self.client.force_authenticate(self.evaluateur_bis)
        response = self.save_evaluation(
            AffectationEvaluateur.RoleEncadrement.TECHNIQUE,
            self.question_technique,
            note='19',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Evaluation.objects.get(question=self.question_technique).note, Decimal('12.00'))

    def test_pedagogical_team_can_create_questionnaires(self):
        self.client.force_authenticate(self.pedagogie)

        response = self.client.post(
            '/api/evaluations/questions/',
            {
                'cohorte': str(self.cohorte.id),
                'type': TypeQuestion.TECHNIQUE,
                'question': 'Nouvelle question technique',
                'maxScore': '10.00',
                'ordre': 2,
            },
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['question'], 'Nouvelle question technique')
        self.assertEqual(response.data['type'], TypeQuestion.TECHNIQUE)
        self.assertEqual(Question.objects.get(id=response.data['id']).baremeMax, Decimal('10.00'))
