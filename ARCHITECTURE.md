# Architecture du Backend SourcingHub

Ce document décrit l'architecture et les choix techniques du backend Django (REST Framework) développé pour SourcingHub.

## 1. Stack Technique
- **Framework** : Django 6.1
- **API** : Django REST Framework (DRF)
- **Base de données** : SQLite (par défaut pour le développement)
- **Authentification** : JWT (JSON Web Tokens) via `djangorestframework-simplejwt`
- **Documentation API** : Swagger/ReDoc via `drf-spectacular`
- **CORS** : `django-cors-headers` pour autoriser les requêtes du frontend Vue.js

## 2. Découpage Modulaire (Applications Django)

L'architecture suit les principes de modularité de Django avec des "Apps" indépendantes :

### `utilisateurs`
Gère l'authentification et les permissions.
- **Modèles** : `Utilisateur` (Custom User Model), `Role` (Candidat, Admin, Evaluateur, etc.)
- **Logique** : Authentification par JWT, activation de compte par email, permissions personnalisées pour restreindre l'accès aux APIs.

### `campagnes`
Gère la définition des sessions de recrutement.
- **Modèles** : `Formation`, `Cohorte` (liée à une formation), `Campagne` (liée à une cohorte, possède des dates et un statut).
- **Logique** : API pour le CRUD et machines d'état (Ouvrir, Fermer, Archiver une campagne).

### `formulaires`
Le constructeur de formulaires dynamiques.
- **Modèles** : 
  - `Formulaire` : Entête du document.
  - `ChampFormulaire` : Entité dynamique (Texte, Liste déroulante, Fichier). Contient les règles de validation en JSON.
  - `OptionChamp` : Choix possibles pour les champs de type liste.
- **Logique** : Configuration des champs via Drag&Drop coté front, avec des types natifs et des métadonnées (taille max, extensions pour les fichiers).

### `candidatures` *(En cours)*
Réception des réponses aux formulaires dynamiques.
- Stockage clé/valeur pour les réponses dynamiques associées aux candidats.

### `evaluations` *(En cours)*
- Workflow pour l'équipe pédagogique et les évaluateurs pour noter les candidatures.

## 3. Flux d'Authentification (Sécurité)
1. Le Frontend envoie l'email/mot de passe au endpoint `/api/auth/connexion/`.
2. Le Backend génère un **Access Token (JWT)**. Le token contient en claims les infos utiles (ID, Nom, Prénom, Rôle) pour éviter des requêtes inutiles.
3. Toutes les requêtes sensibles du Frontend doivent inclure le header `Authorization: Bearer <token>`.
4. Le Backend valide le jeton et applique les règles définies dans `permissions.py` (Ex: Seul un Administrateur peut créer une campagne).

## 4. Documentation des APIs
Toutes les routes API sont auto-documentées avec Swagger.
- **Swagger UI** : `http://127.0.0.1:8000/api/docs/swagger/`
- **ReDoc** : `http://127.0.0.1:8000/api/docs/redoc/`
