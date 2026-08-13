from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
import json
import datetime
from django.db import transaction
from django.db.models import Q

from .models import Candidature, ReponseFormulaire, Document, StatutCandidature
from campagnes.models import Campagne
from utilisateurs.models import Utilisateur, Role, NomRole
from utilisateurs.emails import envoyer_email_activation_candidat
from .serializers import CandidatureDetailSerializer, CandidatureListSerializer

class CandidatureSoumissionView(APIView):
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        data = request.data
        
        # 1. Vérification de la campagne
        campagne_id = data.get('campagne')
        if not campagne_id:
            return Response({"detail": "La campagne est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            campagne = Campagne.objects.get(id=campagne_id)
        except Campagne.DoesNotExist:
            return Response({"detail": "Campagne introuvable."}, status=status.HTTP_404_NOT_FOUND)

        if not campagne.est_ouverte():
            return Response({"detail": "Cette campagne est clôturée ou fermée."}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Gestion de l'utilisateur (Candidat)
        user = None
        if request.user and request.user.is_authenticated:
            user = request.user
            if not user.est_candidat():
                return Response({"detail": "Seuls les candidats peuvent soumettre une candidature."}, status=status.HTTP_403_FORBIDDEN)
        else:
            # Utilisateur anonyme : on doit créer son compte
            email = data.get('email')
            prenom = data.get('prenom')
            nom = data.get('nom')
            telephone = data.get('telephone')
            sexe = data.get('sexe')

            # Extraction dynamique depuis les réponses
            if not (email and prenom and nom and telephone and sexe):
                reponses_str = data.get('reponses', '[]')
                try:
                    reponses = json.loads(reponses_str)
                except Exception:
                    reponses = reponses_str if isinstance(reponses_str, list) else []

                from formulaires.models import ChampFormulaire
                for rep in reponses:
                    champ_id = rep.get('champ_id')
                    valeur = str(rep.get('valeur', '')).strip()
                    if not valeur:
                        continue
                    try:
                        champ = ChampFormulaire.objects.get(id=champ_id, formulaire__campagne=campagne)
                        libelle_lower = champ.libelle.lower()
                        if 'email' in libelle_lower or champ.type == 'EMAIL':
                            email = email or valeur
                        elif 'prénom' in libelle_lower:
                            prenom = prenom or valeur
                        elif 'nom' in libelle_lower:
                            nom = nom or valeur
                        elif 'téléphone' in libelle_lower or champ.type == 'TELEPHONE':
                            telephone = telephone or valeur
                        elif 'genre' in libelle_lower:
                            if 'femme' in valeur.lower() or valeur.upper() == 'FEMME':
                                sexe = sexe or 'FEMME'
                            else:
                                sexe = sexe or 'HOMME'
                    except ChampFormulaire.DoesNotExist:
                        continue

            if not email or not prenom or not nom or not telephone or not sexe:
                return Response({"detail": "Tous les champs du profil candidat sont obligatoires (email, prenom, nom, telephone, sexe)."}, status=status.HTTP_400_BAD_REQUEST)

            # Vérifier si l'utilisateur existe déjà
            if Utilisateur.objects.filter(email=email).exists():
                return Response({"detail": "Un compte avec cet e-mail existe déjà. Veuillez vous connecter pour candidater."}, status=status.HTTP_400_BAD_REQUEST)

            try:
                role_candidat = Role.objects.get(nom=NomRole.CANDIDAT)
            except Role.DoesNotExist:
                return Response({"detail": "Rôle Candidat introuvable dans le système."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            user = Utilisateur.objects.create(
                email=email,
                username=email,
                first_name=prenom,
                last_name=nom,
                telephone=telephone,
                sexe=sexe,
                role=role_candidat,
                is_active=False,
                compteActive=False,
                profilComplet=True
            )
            user.generer_token_activation()

        # 3. Vérifier que le candidat n'a pas déjà postulé à cette campagne
        if Candidature.objects.filter(utilisateur=user, campagne=campagne).exists():
            return Response({"detail": "Vous avez déjà déposé une candidature pour cette campagne."}, status=status.HTTP_400_BAD_REQUEST)

        # 4. Générer le numéro de candidature
        year = datetime.datetime.now().year
        count = Candidature.objects.filter(dateSoumission__year=year).count() + 1
        numero = f"CAND-{year}-{count:04d}"

        # 5. Créer la candidature
        candidature = Candidature.objects.create(
            numero=numero,
            utilisateur=user,
            campagne=campagne,
            statut=StatutCandidature.EN_ATTENTE
        )

        # 6. Enregistrer les réponses du formulaire
        reponses_str = data.get('reponses', '[]')
        try:
            reponses = json.loads(reponses_str)
        except Exception:
            reponses = reponses_str if isinstance(reponses_str, list) else []

        for rep in reponses:
            champ_id = rep.get('champ_id')
            valeur = rep.get('valeur', '')
            
            # Récupérer le champ pour s'assurer qu'il appartient bien au formulaire
            from formulaires.models import ChampFormulaire
            try:
                champ = ChampFormulaire.objects.get(id=champ_id, formulaire__campagne=campagne)
            except ChampFormulaire.DoesNotExist:
                continue

            # Si c'est un fichier
            if champ.type == 'FICHIER':
                file_obj = request.FILES.get(f"file_{champ_id}")
                if file_obj:
                    # Enregistrer le document
                    doc = Document.objects.create(
                        nom=file_obj.name,
                        chemin=file_obj,
                        typeMime=file_obj.content_type,
                        taille=file_obj.size,
                        candidature=candidature
                    )
                    valeur = file_obj.name
                else:
                    if champ.obligatoire:
                        transaction.set_rollback(True)
                        return Response({"detail": f"Le document pour le champ '{champ.libelle}' est requis."}, status=status.HTTP_400_BAD_REQUEST)
                    valeur = ""

            # Validation du champ obligatoire
            if champ.obligatoire and not valeur:
                transaction.set_rollback(True)
                return Response({"detail": f"Le champ '{champ.libelle}' est obligatoire."}, status=status.HTTP_400_BAD_REQUEST)

            ReponseFormulaire.objects.create(
                candidature=candidature,
                champ=champ,
                valeur=valeur
            )

        # 7. Envoyer le mail d'activation si l'utilisateur vient d'être créé
        if not (request.user and request.user.is_authenticated):
            try:
                envoyer_email_activation_candidat(user)
            except Exception as e:
                print("Erreur d'envoi du mail d'activation:", e)

        return Response(CandidatureDetailSerializer(candidature).data, status=status.HTTP_201_CREATED)


class CandidatureListeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        if user.est_candidat():
            # Retourne uniquement ses candidatures
            qs = Candidature.objects.filter(utilisateur=user).select_related('campagne__cohorte__formation', 'utilisateur')
            return Response(CandidatureListSerializer(qs, many=True).data)
            
        elif user.est_admin() or user.est_equipe_pedagogique() or user.est_equipe_gestion_projet():
            # Retourne toutes les candidatures avec filtres
            qs = Candidature.objects.select_related('campagne__cohorte__formation', 'utilisateur').all()
            
            # Filtre campagne
            campagne_id = request.query_params.get('campagne')
            if campagne_id:
                qs = qs.filter(campagne_id=campagne_id)
                
            # Filtre statut
            statut = request.query_params.get('statut')
            if statut:
                qs = qs.filter(statut=statut)
                
            # Recherche
            search = request.query_params.get('search')
            if search:
                qs = qs.filter(
                    Q(numero__icontains=search) | 
                    Q(utilisateur__first_name__icontains=search) | 
                    Q(utilisateur__last_name__icontains=search) |
                    Q(utilisateur__email__icontains=search)
                )
                
            return Response(CandidatureListSerializer(qs, many=True).data)
            
        else:
            return Response({"detail": "Accès interdit."}, status=status.HTTP_403_FORBIDDEN)


class CandidatureDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            candidature = Candidature.objects.prefetch_related('reponses__champ', 'documents').select_related('campagne__cohorte__formation', 'utilisateur').get(pk=pk)
        except Candidature.DoesNotExist:
            return Response({"detail": "Candidature introuvable."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user
        # Sécurité : Un candidat ne peut voir que sa propre candidature
        if user.est_candidat() and candidature.utilisateur != user:
            return Response({"detail": "Accès interdit."}, status=status.HTTP_403_FORBIDDEN)
            
        return Response(CandidatureDetailSerializer(candidature).data)
