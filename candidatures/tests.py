import json

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from campagnes.models import Campagne, Cohorte, Formation, StatutCampagne
from formulaires.models import ChampFormulaire, Formulaire, OptionChamp, TypeChamp
from utilisateurs.models import NomRole, Role, Utilisateur


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='SourcingHub <test@sourcinghub.local>',
    FRONTEND_URL='http://localhost:5173',
)
class CandidatureSoumissionTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.role_candidat = Role.objects.create(nom=NomRole.CANDIDAT)
        formation = Formation.objects.create(nom='Developpement web')
        cohorte = Cohorte.objects.create(nom='Cohorte 1', formation=formation)
        self.campagne = Campagne.objects.create(
            nom='Appel a candidature',
            cohorte=cohorte,
            dateOuverture=timezone.now() - timezone.timedelta(days=1),
            dateCloture=timezone.now() + timezone.timedelta(days=7),
            statut=StatutCampagne.OUVERTE,
            publiee=True,
        )
        self.formulaire = Formulaire.objects.create(
            titre='Formulaire candidature',
            campagne=self.campagne,
        )
        self.champ_prenom = ChampFormulaire.objects.create(
            formulaire=self.formulaire,
            libelle='Prénom',
            type=TypeChamp.TEXTE,
            obligatoire=True,
            ordre=0,
        )
        self.champ_nom = ChampFormulaire.objects.create(
            formulaire=self.formulaire,
            libelle='Nom',
            type=TypeChamp.TEXTE,
            obligatoire=True,
            ordre=1,
        )
        self.champ_email = ChampFormulaire.objects.create(
            formulaire=self.formulaire,
            libelle='Adresse Email',
            type=TypeChamp.EMAIL,
            obligatoire=True,
            ordre=2,
        )
        self.champ_telephone = ChampFormulaire.objects.create(
            formulaire=self.formulaire,
            libelle='Téléphone',
            type=TypeChamp.TELEPHONE,
            obligatoire=True,
            ordre=3,
        )
        self.champ_genre = ChampFormulaire.objects.create(
            formulaire=self.formulaire,
            libelle='Genre',
            type=TypeChamp.LISTE_DEROULANTE,
            obligatoire=True,
            ordre=4,
        )
        OptionChamp.objects.create(champ=self.champ_genre, libelle='Homme', valeur='HOMME', ordre=0)
        OptionChamp.objects.create(champ=self.champ_genre, libelle='Femme', valeur='FEMME', ordre=1)

    def test_soumission_anonyme_envoie_mail_activation_candidat(self):
        reponses = [
            {'champ_id': str(self.champ_prenom.id), 'valeur': 'Awa'},
            {'champ_id': str(self.champ_nom.id), 'valeur': 'Diop'},
            {'champ_id': str(self.champ_email.id), 'valeur': 'awa.diop@example.com'},
            {'champ_id': str(self.champ_telephone.id), 'valeur': '+221 770000000'},
            {'champ_id': str(self.champ_genre.id), 'valeur': 'FEMME'},
        ]

        response = self.client.post(
            reverse('candidature-soumettre'),
            {
                'campagne': str(self.campagne.id),
                'reponses': json.dumps(reponses),
            },
            format='multipart',
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        candidat = Utilisateur.objects.get(email='awa.diop@example.com')
        self.assertFalse(candidat.is_active)
        self.assertFalse(candidat.compteActive)
        self.assertIsNotNone(candidat.tokenActivation)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['awa.diop@example.com'])
        self.assertIn('Activation de votre compte Candidat', mail.outbox[0].subject)
        self.assertIn(f'auth/activer/{candidat.tokenActivation}', mail.outbox[0].body)
