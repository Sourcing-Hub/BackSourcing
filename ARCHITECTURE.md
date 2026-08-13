# Architecture Backend SourcingHub (Django REST Framework)
Dernière mise à jour : 2026-08-13 (v1.2.0)

Ce document décrit l'architecture logicielle, la modélisation des données, les règles métier et la sécurité de l'API backend Django REST Framework développée pour SourcingHub.

---

## 1. Stack Technique

- **Framework principal** : Django 6.1
- **API Engine** : Django REST Framework (DRF)
- **Base de données** : SQLite (développement) / PostgreSQL (production)
- **Authentification** : JWT (JSON Web Tokens) via `djangorestframework-simplejwt`
- **Documentation API** : OpenAPI v3 / Swagger UI / ReDoc via `drf-spectacular`
- **Gestion des CORS** : `django-cors-headers` pour autoriser le frontend Vue.js 3

---

## 2. Découpage Modulaire (Applications Django)

L'architecture suit les principes de modularité de Django avec des applications indépendantes et hautement découplées :

### application `utilisateurs`
Gère l'authentification, les comptes utilisateurs et les autorisations.
- **Modèles** :
  - `Utilisateur` (Custom User Model) : Hérite de `AbstractUser`, stocke le téléphone, sexe, état de profil (`profilComplet`), état d'activation (`compteActive`) et le token d'activation.
  - `Role` : Définit les 5 rôles système (`Candidat`, `Administrateur`, `Évaluateur`, `Équipe Pédagogique`, `Équipe Gestion de Projet`).
- **Services** :
  - `emails.py` : Envoi d'invitations personnalisées par rôle avec description des responsabilités.
  - `permissions.py` : Contrôle d'accès basé sur les méthodes `est_admin()`, `est_equipe_pedagogique()`, etc.

### application `campagnes`
Gère les programmes de formation, les promotions et les campagnes de recrutement.
- **Modèles** :
  - `Formation` : Intitulé, description et dates de démarrage.
  - `Cohorte` : Liée à une formation (`ForeignKey`). Possède la contrainte d'unicité `unique_together = [('nom', 'formation')]`.
  - `Campagne` : Liée à une cohorte, gère le statut (`BROUILLON`, `OUVERTE`, `FERMEE`).
- **Logique Métier** :
  - Machine d'état `est_ouverte()`, `ouvrir()`, `fermer()`.
  - Empêche l'ouverture d'une campagne si aucun formulaire valide ne lui est associé.

### application `formulaires`
Le moteur de formulaires dynamiques paramétrables.
- **Modèles** :
  - `Formulaire` : Entête du formulaire rattaché à une campagne.
  - `ChampFormulaire` : Champ dynamique (type, ordre, obligatoire, règles JSON).
  - `OptionChamp` : Choix possibles pour les champs à sélections (listes, radios, cases à cocher).

### application `candidatures`
Réception, stockage et validation des dossiers de candidature.
- **Modèles** :
  - `Candidature` : Dossier unique avec numéro généré `CAND-AAAA-XXXX`.
  - `ReponseFormulaire` : Valeur saisie pour chaque champ dynamique.
  - `Document` : Fichiers joints avec validation du type MIME et de la taille maximale.

### application `evaluations`
Suivi du parcours d'évaluation et émargement des candidats.
- **Modèles** :
  - `Etape` : Étape de recrutement configurée par cohorte.
  - `ParticipationEtape` : Statut du candidat à une étape donnée.
- **Fonctionnalités** :
  - Génération de QR Code pour chaque candidat.
  - Endpoint de scan et d'émargement en direct.

### application `notifications`
Gestion des alertes système et notifications destinées aux candidats et évaluateurs.

---

## 3. Flux d'Authentification et Sécurité JWT

1. **Connexion** : Requête POST vers `/api/auth/connexion/` avec `username` (email) et `password`.
2. **Jeton JWT** : Le serveur émet un `access` token (durée 60 min) et un `refresh` token.
3. **Transmission** : Le client transmet le jeton dans le header HTTP `Authorization: Bearer <access_token>`.
4. **Activation de Compte** : Les comptes du personnel sont créés en état inactif (`is_active=False`). Un email contient un lien unique `/auth/activer/<token>` valide 48h.

---

## 4. Documentation des APIs

Le backend intègre `drf-spectacular` pour générer automatiquement la spécification OpenAPI v3 :
- **Swagger UI** : `http://127.0.0.1:8000/api/docs/swagger/`
- **ReDoc** : `http://127.0.0.1:8000/api/docs/redoc/`
- **Schéma OpenAPI JSON** : `http://127.0.0.1:8000/api/schema/`
