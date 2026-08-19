from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from .models import NomRole, Role, StatutUtilisateur, Utilisateur


class ConnexionTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.role = Role.objects.create(nom=NomRole.ADMINISTRATEUR)
        self.user = Utilisateur.objects.create_user(
            username='jules',
            email='jule30@gmail.com',
            password='jule1234',
            first_name='Jules',
            role=self.role,
            is_active=True,
            compteActive=True,
            statut=StatutUtilisateur.ACTIF,
        )

    def test_login_accepts_email_field(self):
        response = self.client.post(
            '/api/auth/connexion/',
            {'email': 'jule30@gmail.com', 'password': 'jule1234'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['role'], NomRole.ADMINISTRATEUR)

    def test_login_accepts_username_field_as_email(self):
        response = self.client.post(
            '/api/auth/connexion/',
            {'username': 'jule30@gmail.com', 'password': 'jule1234'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_login_rejects_inactive_account(self):
        self.user.compteActive = False
        self.user.save(update_fields=['compteActive'])

        response = self.client.post(
            '/api/auth/connexion/',
            {'email': 'jule30@gmail.com', 'password': 'jule1234'},
            format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
