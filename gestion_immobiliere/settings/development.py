import os
from .base import * # Importe tous les paramètres communs

# Les paramètres ci-dessous sont spécifiques à l'environnement de DÉVELOPPEMENT.

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Pas besoin de CSRF_TRUSTED_ORIGINS en développement local avec DEBUG=True

# Base de données pour le développement
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST', 'localhost'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# En développement, il est plus simple d'afficher les emails dans la console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'