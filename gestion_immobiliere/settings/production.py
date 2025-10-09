import os
from .base import *  # Importe tous les paramètres communs
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Les paramètres ci-dessous sont spécifiques à l'environnement de PRODUCTION.

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ImproperlyConfigured("La variable d'environnement SECRET_KEY n'est pas définie pour la production.")

# DEBUG est déjà à False dans base.py, donc pas besoin de le redéfinir.

# Configurez les hôtes autorisés pour votre domaine de production.
# Ne PAS utiliser ['*'] en production !
# Railway fournit un domaine par défaut. On l'ajoute, ainsi que votre domaine personnalisé.
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# Base de données pour la production
# Railway fournit une variable DATABASE_URL. dj-database-url la parse pour nous.
DATABASES = {
    'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
}

# Paramètres de sécurité pour HTTPS
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

# Configuration pour WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Configuration des emails pour la production (déjà dans base.py, mais vérifiez les variables d'environnement)
if not os.getenv('EMAIL_HOST_USER') or not os.getenv('EMAIL_HOST_PASSWORD'):
    raise ImproperlyConfigured("Les variables d'environnement pour l'email ne sont pas configurées pour la production.")