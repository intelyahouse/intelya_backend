# INTELYA HAVEN — Backend API

> Plateforme immobilière intelligente pour le Cameroun et l'Afrique.  
> Mise en relation agents, propriétaires et clients avec paiement Mobile Money intégré.

---

## Table des matières

1. [Présentation](#présentation)
2. [Architecture](#architecture)
3. [Prérequis](#prérequis)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Lancement](#lancement)
7. [API — Endpoints](#api--endpoints)
8. [Tests](#tests)
9. [Déploiement production](#déploiement-production)
10. [Sécurité](#sécurité)
11. [Structure du projet](#structure-du-projet)

---

## Présentation

INTELYA HAVEN est une API REST construite avec **Django 4.2** et **Django REST Framework**.  
Elle gère l'ensemble du cycle immobilier : inscription, recherche de biens, visites, contrats, paiements loyers et gestion locative.

**Stack technique :**

| Composant | Technologie |
|-----------|-------------|
| Framework | Django 4.2 + DRF 3.15 |
| Base de données | PostgreSQL + PostGIS (géolocalisation) |
| Cache | Redis + django-cachalot |
| Tâches async | Celery + Redis Broker + RedBeat |
| WebSocket | Django Channels + Redis |
| Authentification | JWT (SimpleJWT) + OAuth Google/Apple |
| Paiements | Campay (MTN Mobile Money + Orange Money) |
| Stockage fichiers | AWS S3 (production) |
| Notifications push | Firebase FCM |
| Monitoring | Sentry |
| Documentation API | Swagger (drf-spectacular) |

---

## Architecture

```
intelya-backend/
├── intelya/                  # Configuration principale
│   ├── settings/
│   │   ├── base.py           # Settings communs
│   │   ├── development.py    # Settings développement
│   │   └── production.py     # Settings production (HSTS, S3, Sentry)
│   ├── urls.py               # Routage principal
│   ├── celery.py             # Config Celery
│   └── asgi.py               # WebSocket (Channels)
│
├── apps/                     # Applications métier
│   ├── users/                # Authentification, profils, rôles
│   ├── agents/               # Profils agents, relations owner-agent
│   ├── owners/               # Profils propriétaires, comptes bancaires
│   ├── properties/           # Biens immobiliers, filtres, likes
│   ├── visits/               # Demandes de visites, planification GPS
│   ├── contracts/            # Contrats de location
│   ├── leases/               # Gestion locative, loyers, plaintes
│   ├── payments/             # Transactions, escrow, Mobile Money
│   ├── messaging/            # Messagerie temps réel (WebSocket)
│   ├── notifications/        # Notifications push (Firebase)
│   ├── reviews/              # Avis et notations
│   ├── disputes/             # Litiges et signalements
│   ├── boost/                # Mise en avant des annonces
│   └── referrals/            # Programme de parrainage
│
├── core/                     # Utilitaires partagés
│   ├── permissions.py        # IsAdmin, IsAgent, IsOwner, IsClient…
│   ├── middleware.py         # Sécurité, logging, blocage requêtes suspectes
│   ├── validators.py         # Validation téléphone camerounais, fichiers
│   ├── pagination.py         # Pagination standard
│   ├── throttles.py          # Rate limiting personnalisé
│   ├── exceptions.py         # Gestionnaire d'erreurs global
│   ├── utils.py              # Fonctions utilitaires
│   └── ai_match.py           # Matching IA bien/client
│
└── tests/                    # Suite de tests (123 tests)
    ├── conftest.py
    ├── test_auth.py
    ├── test_properties.py
    ├── test_security.py
    ├── test_visits.py
    ├── test_agents.py
    └── ...
```

---

## Prérequis

- Python 3.10+
- PostgreSQL 14+ avec extension **PostGIS**
- Redis 6+
- Node.js (optionnel, pour les outils frontend)

---

## Installation

### 1. Cloner le dépôt

```bash
git clone https://github.com/ton-user/intelya-backend.git
cd intelya-backend
```

### 2. Créer l'environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r requirements.txt
```

### 4. Configurer PostgreSQL avec PostGIS

```bash

```

```sql
CREATE DATABASE intelya_db;
CREATE USER intelya_user WITH PASSWORD 'Intelya123@';
GRANT ALL PRIVILEGES ON DATABASE intelya_db TO intelya_user;
ALTER USER intelya_user SUPERUSER;

\c intelya_db
CREATE EXTENSION IF NOT EXISTS postgis;
\q
```

### 5. Configurer les variables d'environnement

```bash
cp .env.example .env
nano .env
```

Remplir toutes les valeurs (voir section [Configuration](#configuration)).

### 6. Appliquer les migrations

```bash
export DJANGO_SETTINGS_MODULE=intelya.settings.development
python manage.py migrate
```

### 7. Créer un superadmin

```bash
python manage.py createsuperuser
```

### 8. Collecter les fichiers statiques

```bash
python manage.py collectstatic --noinput
```

---

## Configuration

Copie `.env.example` en `.env` et remplis ces valeurs :

```env
# Django
SECRET_KEY=une_cle_secrete_longue_et_aleatoire
DEBUG=True
DJANGO_SETTINGS_MODULE=intelya.settings.development
ALLOWED_HOSTS=localhost,127.0.0.1

# Base de données
DB_NAME=intelya_db
DB_USER=intelya_user
DB_PASSWORD=ton_mot_de_passe
DB_HOST=localhost
DB_PORT=5432

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# JWT
ACCESS_TOKEN_LIFETIME_MINUTES=30
REFRESH_TOKEN_LIFETIME_DAYS=7

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=ton@email.com
EMAIL_HOST_PASSWORD=ton_app_password

# Frontend
FRONTEND_URL=http://localhost:5173

# Paiements Campay (MTN + Orange Money)
CAMPAY_USERNAME=ton_username
CAMPAY_PASSWORD=ton_password
CAMPAY_WEBHOOK_SECRET=ton_secret
CAMPAY_API_URL=https://demo.campay.net/api   # sandbox
# CAMPAY_API_URL=https://campay.net/api      # production

# Firebase (notifications push)
FIREBASE_CREDENTIALS_PATH=firebase-credentials.json

# AWS S3 (production)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_STORAGE_BUCKET_NAME=intelya-haven-storage
AWS_S3_REGION_NAME=eu-west-1

# Google OAuth
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# SMS
SMS_API_KEY=
SMS_API_URL=
SMS_SENDER_NAME=INTELYA

# Sentry (production)
SENTRY_DSN=

# Plateforme
FREE_MODE=True
MAX_LOGIN_ATTEMPTS=5
OTP_EXPIRY_MINUTES=15
VISIT_GPS_RADIUS_METERS=200
PLATFORM_COMMISSION_PERCENT=2
```

---

## Lancement

### Serveur de développement

```bash
# Terminal 1 — Django
export DJANGO_SETTINGS_MODULE=intelya.settings.development
python manage.py runserver

# Terminal 2 — Celery worker
celery -A intelya worker -l info

# Terminal 3 — Celery Beat (tâches planifiées)
celery -A intelya beat -l info

# Terminal 4 — Daphne WebSocket (optionnel)
daphne -b 0.0.0.0 -p 8001 intelya.asgi:application
```

### Avec Docker

```bash
docker-compose up --build
```

---

## API — Endpoints

Documentation interactive disponible sur :

- **Swagger UI** : `http://localhost:8000/api/docs/`
- **ReDoc** : `http://localhost:8000/api/redoc/`
- **Health check** : `http://localhost:8000/api/health/`

### Résumé des routes principales

| Groupe           | Préfixe                  | Description                               |
|------------------|--------------------------|-------------------------------------------|
| Authentification | `/api/v1/auth/`          | Inscription, connexion, OTP, mot de passe |
| Utilisateurs     | `/api/v1/users/`         | Profil, changement de rôle                |
| Agents           | `/api/v1/agents/`        | Profils agents, relations owner/client    |
| Propriétaires    | `/api/v1/owners/`        | Profils, comptes bancaires                |
| Biens            | `/api/v1/properties/`    | Liste, détail, filtres, likes, favoris    |
| Visites          | `/api/v1/visits/`        | Demandes, planification, confirmation GPS |
| Contrats         | `/api/v1/contracts/`     | Création, signature, expiration           |
| Gestion locative | `/api/v1/leases/`        | Loyers, plaintes, renouvellements         |
| Paiements        | `/api/v1/payments/`      | Transactions, escrow, Mobile Money        |
| Messagerie       | `/api/v1/messaging/`     | Conversations, messages (WebSocket)       |
| Notifications    | `/api/v1/notifications/` | Push Firebase                             |
| Avis             | `/api/v1/reviews/`       | Notations agents et propriétaires         |
| Litiges          | `/api/v1/disputes/`      | Signalements, résolution                  |
| Boost            | `/api/v1/boost/`         | Mise en avant des annonces                |
| Parrainage       | `/api/v1/referrals/`     | Codes de parrainage                       |
| Admin panel      | `/api/v1/admin-panel/`   | Gestion utilisateurs, stats               |

### Authentification

Toutes les routes protégées nécessitent un header :

```
Authorization: Bearer <access_token>
```

**Inscription :**
```bash
POST /api/v1/auth/register/
{
  "first_name": "Jean",
  "last_name": "Dupont",
  "email": "jean@example.com",
  "phone": "+237670000001",
  "password": "MotDePasse123!",
  "confirm_password": "MotDePasse123!"
}
```

**Connexion :**
```bash
POST /api/v1/auth/login/
{
  "email": "jean@example.com",
  "password": "MotDePasse123!"
}
# Retourne: { "access": "...", "refresh": "...", "user": {...} }
```

**Vérification OTP :**
```bash
POST /api/v1/auth/verify-otp/
{
  "phone": "+237670000001",
  "code": "123456"
}
```

---

## Tests

```bash
# Tous les tests
python3 -m pytest tests/ -v --tb=short

# Un fichier spécifique
python3 -m pytest tests/test_auth.py -v

# Avec couverture de code
python3 -m pytest tests/ --cov=apps --cov-report=html
# Rapport HTML dans htmlcov/index.html

# Tests rapides sans sortie verbose
python3 -m pytest tests/ -q
```

### Résultats actuels

```
115 passed / 123 total — 93.5% de réussite
```

### Organisation des tests

| Fichier | Ce qu'il teste |
|---------|----------------|
| `test_auth.py` | Inscription, connexion, OTP, profil, changement de rôle |
| `test_properties.py` | Liste, détail, filtres, création, likes |
| `test_security.py` | IDOR, injection SQL, XSS, mass assignment, permissions |
| `test_visits.py` | Demandes, planification, annulation |
| `test_agents.py` | Profils agents, relations |
| `test_owners.py` | Profils propriétaires |
| `test_referrals.py` | Codes de parrainage |
| `test_messaging.py` | Conversations |
| `test_boost.py` | Boosts d'annonces |
| `test_disputes.py` | Litiges |
| `test_health.py` | Health check |

---

## Déploiement production

### 1. Variables d'environnement

```bash
DJANGO_SETTINGS_MODULE=intelya.settings.production
DEBUG=False
ALLOWED_HOSTS=intelya-haven.com,www.intelya-haven.com
```

### 2. Base de données

S'assurer que l'utilisateur PostgreSQL n'est **plus superuser** en production :

```sql
ALTER USER intelya_user NOSUPERUSER;
GRANT ALL PRIVILEGES ON DATABASE intelya_db TO intelya_user;
```

Et créer l'extension PostGIS en amont (en tant que postgres) :

```sql
\c intelya_db
CREATE EXTENSION IF NOT EXISTS postgis;
```

### 3. Gunicorn + Nginx

```bash
gunicorn intelya.wsgi:application \
  --workers 4 \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile logs/gunicorn_access.log \
  --error-logfile logs/gunicorn_error.log
```

### 4. Campay — basculer en production

Dans `.env` :
```env
CAMPAY_API_URL=https://campay.net/api
```

### 5. S3 pour les médias

```env
DEFAULT_FILE_STORAGE=storages.backends.s3boto3.S3Boto3Storage
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

### 6. Sauvegardes automatiques

```bash
# Sauvegarde manuelle
python manage.py dbbackup

# Restauration
python manage.py dbrestore
```

---

## Sécurité

INTELYA HAVEN implémente les protections suivantes :

| Protection | Mécanisme |
|-----------|-----------|
| Brute force | django-axes (blocage après 5 tentatives) |
| Rate limiting | django-ratelimit (3/min inscription, 5/min login) |
| JWT | Access token 30min, Refresh 7 jours avec blacklist |
| Headers sécurité | X-Frame-Options, X-Content-Type-Options, CSP, HSTS |
| Injection SQL | ORM Django, aucune requête raw |
| XSS | Validation serializers + bleach + CSP |
| CORS | Origines whitelistées uniquement |
| Upload fichiers | Validation type MIME + taille (10MB images, 20MB docs) |
| Audit trail | django-simple-history sur modèles sensibles |
| Logs | Audit log rotatif, Sentry en production |
| Blacklist | Blocage par numéro de téléphone et numéro CNI |
| HTTPS | HSTS 1 an avec preload en production |

### Rôles et permissions

| Rôle | Accès |
|------|-------|
| `admin` | Tout — gestion complète de la plateforme |
| `agent` | Gestion des biens, visites, clients liés (validé requis) |
| `owner` | Ses biens, ses locataires, paiements (validé requis) |
| `client` | Recherche biens, demandes de visites, messagerie |
| `tenant` | Gestion locative, paiements loyers |

---

## Tâches planifiées (Celery Beat)

| Tâche | Heure | Description |
|-------|-------|-------------|
| Vérification loyers | 08h00 | Détecte les impayés |
| Renouvellements baux | 09h00 | Propose le renouvellement |
| Blocage impayés | 10h00 | Bloque les comptes en retard |
| Expiration contrats | 07h00 | Notifie les expirations proches |
| Libération escrow | Toutes les heures | Libère les fonds retenus |
| Expiration boosts | 06h00 | Désactive les boosts expirés |
| Rapports mensuels | 1er du mois 06h00 | Génère les rapports propriétaires |

---

## Structure du projet complète

```
intelya-backend/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── manage.py
├── pytest.ini
├── requirements.txt
├── README.md
│
├── intelya/
│   ├── __init__.py
│   ├── asgi.py
│   ├── celery.py
│   ├── urls.py
│   ├── wsgi.py
│   └── settings/
│       ├── __init__.py
│       ├── base.py
│       ├── development.py
│       └── production.py
│
├── core/
│   ├── ai_match.py
│   ├── audit.py
│   ├── compression.py
│   ├── exceptions.py
│   ├── firebase.py
│   ├── health.py
│   ├── middleware.py
│   ├── pagination.py
│   ├── permissions.py
│   ├── throttles.py
│   ├── utils.py
│   └── validators.py
│
├── apps/
│   ├── users/
│   ├── agents/
│   ├── owners/
│   ├── properties/
│   ├── visits/
│   ├── contracts/
│   ├── leases/
│   ├── payments/
│   ├── messaging/
│   ├── notifications/
│   ├── reviews/
│   ├── disputes/
│   ├── boost/
│   └── referrals/
│
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_properties.py
│   ├── test_security.py
│   ├── test_visits.py
│   ├── test_agents.py
│   ├── test_owners.py
│   ├── test_referrals.py
│   ├── test_messaging.py
│   ├── test_boost.py
│   ├── test_disputes.py
│   └── test_health.py
│
└── logs/
    ├── audit.log
    └── errors.log
```

---

## Contacts & Support

Projet : **INTELYA HAVEN**  
Plateforme immobilière Cameroun / Afrique  
Email : contact@intelya-haven.com