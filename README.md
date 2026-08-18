# SourcingHub — Backend Application (Django REST Framework)

[![Python](https://img.shields.io/badge/Python-3.13-blue?style=flat-square&logo=python)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-092E20?style=flat-square&logo=django)](https://www.djangoproject.com/)
[![DRF](https://img.shields.io/badge/DRF-REST_Framework-red?style=flat-square)](https://www.django-rest-framework.org/)
[![Swagger](https://img.shields.io/badge/OpenAPI-drf--spectacular-85EA2D?style=flat-square&logo=swagger)](https://github.com/tfranzel/drf-spectacular)

**SourcingHub Backend** est l'application serveur RESTful développée avec **Django 6.1** et **Django REST Framework (DRF)**. Elle gère la logique métier centrale du système de recrutement SourcingHub : authentification JWT, gestion fine des rôles et permissions, moteur de formulaires dynamiques, cycle de vie des campagnes, traitement des candidatures et suivi d'émargement via QR Code.

---

## Table des Matières

1. [Architecture des Applications Django](#architecture-des-applications-django)
2. [Stack Technique](#stack-technique)
3. [Documentation OpenAPI et Swagger](#documentation-openapi-et-swagger)
4. [Structure du Projet](#structure-du-projet)
5. [Installation et Configuration](#installation-et-configuration)
6. [Commandes de Gestion (CLI)](#commandes-de-gestion-cli)
7. [Sécurité et Permissions](#sécurité-et-permissions)
8. [Documentation de l'Architecture](#documentation-de-larchitecture)

---

## Architecture des Applications Django

Le backend est structuré en 6 applications Django spécialisées et indépendantes :

- **utilisateurs** : Custom User Model, rôles (Candidat, Admin, Équipe Pédagogique, Équipe Gestion de Projet, Évaluateur), authentification JWT, tokens d'activation et envoi d'emails d'invitation personnalisés.
- **campagnes** : Gestion des formations, des cohortes (avec contrainte d'unicité `unique_together` par formation) et des campagnes de recrutement avec leur machine à états (Brouillon, Ouverte, Fermée).
- **formulaires** : Moteur de formulaires dynamiques paramétrables avec types de champs avancés (texte, email, téléphone, date, liste, fichier avec validation MIME/taille).
- **candidatures** : Traitement des candidatures (anonymes ou connectées), génération du numéro unique `CAND-AAAA-XXXX`, stockage des réponses et fichiers joints.
- **evaluations** : Gestion des étapes de recrutement, notation par critère et suivi des présences via scan de QR Code.
- **notifications** : Gestion des alertes et rappels envoyés aux candidats et membres du personnel.

---

## Stack Technique

- **Langage** : Python 3.13
- **Framework Web** : Django 6.1
- **API Engine** : Django REST Framework (DRF)
- **Authentification** : JWT (JSON Web Token) via `djangorestframework-simplejwt`
- **Documentation API** : `drf-spectacular` (OpenAPI v3, Swagger UI, ReDoc)
- **Base de données** : SQLite (développement) / PostgreSQL (production)
- **Gestion des CORS** : `django-cors-headers`

---

## Documentation OpenAPI et Swagger

En environnement de développement, l'API génère automatiquement la documentation interactive OpenAPI v3 :

- **Swagger UI** : `http://127.0.0.1:8000/api/docs/swagger/`
- **ReDoc UI** : `http://127.0.0.1:8000/api/docs/redoc/`
- **Schéma OpenAPI JSON** : `http://127.0.0.1:8000/api/schema/`

---

## Structure du Projet

```text
BacSourcing/
├── me/
├── utilisateurs/         # App Auth & Utilisateurs
│   ├── management/       # Commandes CLI (creer_roles)
│   ├── models.py         # Modèles Utilisateur & Role
│   ├── permissions.py    # Classes de permissions personnalisées
│   ├── serializers.py    # Sérialiseurs DRF
│   ├── views.py          # Endpoints API
│   └── emails.py         # Templates d'invitation par rôle
├── campagnes/            # App Formations, Cohortes & Campagnes
├── formulaires/          # App Formulaires dynamiques & Champs
├── candidatures/         # App Soumissions & Réponses
├── evaluations/          # App Étapes de sélection & QR Code
├── notifications/        # App Notifications système
├── sourcing_backend/     # Configuration globale Django (settings, urls)
├── db.sqlite3            # Base de données locale de développement
├── manage.py             # Script CLI Django
├── requirements.txt      # Dépendances Python
└── ARCHITECTURE.md       # Spécification technique détaillée
```

---

## Installation et Configuration

### 1. Création de l'environnement virtuel

```bash
python -m venv venv
# Sur Windows :
venv\Scripts\activate
# Sur Linux/macOS :
source venv/bin/activate
```

### 2. Installation des dépendances

```bash
pip install -r requirements.txt
```

### 3. Application des migrations et initialisation

```bash
python manage.py migrate
python manage.py creer_roles
```

### 4. Lancement du serveur de développement

```bash
python manage.py runserver 8000
```
> L'API backend sera accessible sur `http://127.0.0.1:8000/api/`.

---

## Commandes de Gestion (CLI)

- **Initialisation des 5 rôles par défaut** :
  ```bash
  python manage.py creer_roles
  ```

- **Création d'un superutilisateur administrateur** :
  ```bash
  python manage.py createsuperuser
  ```

---

## Sécurité et Permissions

Chaque endpoint de l'API est sécurisé par des classes de permissions dédiées dans `utilisateurs/permissions.py` :

- `EstAdministrateur` : Réservé aux administrateurs de la plateforme.
- `EstEquipePedagogique` : Réservé aux membres de l'Équipe Pédagogique.
- `EstEquipeGestionProjet` : Réservé aux membres de l'Équipe Gestion de Projet.
- `IsStaffOrAdmin` : Accès combiné pour Admin, Pédagogie et Gestion de Projet.

---

## Documentation de l'Architecture

Pour consulter la description détaillée de la modélisation des données, des règles de gestion métier et de la sécurité des endpoints, référez-vous au document :
[ARCHITECTURE.md](file:///C:/Users/dell/Documents/SourcingHub/BacSourcing/ARCHITECTURE.md)
