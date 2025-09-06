import os
from pathlib import Path
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured


# Charger les variables d'environnement depuis le fichier .env pour tous les environnements
load_dotenv()

# Le chemin de base est maintenant 3 niveaux plus haut car ce fichier est dans settings/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# --- DIAGNOSTIC ---
# Nous forçons DEBUG à True pour nous assurer que le serveur de développement
# sert bien les fichiers statiques.
DEBUG = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.humanize',
    'django.contrib.staticfiles',
    'widget_tweaks',
    'gestion.apps.GestionConfig',
    
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'gestion.middleware.ForcePasswordChangeMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
]


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'], # Déjà correct, aucune modification nécessaire ici.
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'gestion.context_processors.notifications_processor',
            ],
        },
    },
]

WSGI_APPLICATION = 'gestion_immobiliere.wsgi.application'


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 10,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
    {
        'NAME': 'gestion.validators.CustomPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
    
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

# ==============================================================================
# CONFIGURATION DES FICHIERS MÉDIAS (TÉLÉVERSÉS PAR LES UTILISATEURS)
# ==============================================================================
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

ROOT_URLCONF = 'gestion_immobiliere.urls'  # Chemin vers le fichier urls.py principal

# Authentification
AUTH_USER_MODEL = 'gestion.CustomUser'  # Utilise votre modèle User personnalisé

# URLs
LOGIN_URL = 'gestion:connexion'
LOGIN_REDIRECT_URL = 'gestion:accueil'  # Redirige vers l'accueil, qui redirigera vers le bon tableau de bord
LOGOUT_REDIRECT_URL = 'gestion:accueil'

# Sessions
SESSION_COOKIE_AGE = 1209600  # 2 semaines en secondes
SESSION_SAVE_EVERY_REQUEST = True

# Sécurité (à activer en production avec HTTPS)
# CSRF_COOKIE_SECURE = True
# SESSION_COOKIE_SECURE = True

# Configuration des emails (pour le développement, les emails sont affichés dans la console)
# EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' # À commenter pour la production

# --- Configuration pour la production avec Gmail ---
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER') # Votre adresse Gmail
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD') # Votre mot de passe d'application

# L'email qui apparaîtra comme expéditeur
DEFAULT_FROM_EMAIL = f"RentSolution <{os.getenv('EMAIL_HOST_USER')}>"