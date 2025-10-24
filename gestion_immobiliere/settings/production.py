import os
from .base import *  # Importe tous les paramètres communs
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Les paramètres ci-dessous sont spécifiques à l'environnement de PRODUCTION.

# SECURITY WARNING: keep the secret key used in production secret!
# DEBUG est déjà à False dans base.py, donc pas besoin de le redéfinir.

# Configurez les hôtes autorisés pour votre domaine de production.
# Ne PAS utiliser ['*'] en production !
# Railway fournit un domaine par défaut. On l'ajoute, ainsi que votre domaine personnalisé.
ALLOWED_HOSTS = set()

# Récupérer les hôtes depuis la variable d'environnement, s'ils existent.
allowed_hosts_str = os.getenv('ALLOWED_HOSTS')
if allowed_hosts_str:
    # Nettoie les espaces et ajoute les hôtes à un ensemble pour éviter les doublons
    hosts = [host.strip() for host in allowed_hosts_str.split(',')]
    ALLOWED_HOSTS.update(hosts)

# Railway injecte une variable d'environnement pour son domaine de service.
# C'est une bonne pratique de l'ajouter si elle existe.
railway_hostname = os.getenv('RAILWAY_PUBLIC_DOMAIN')
if railway_hostname:
    ALLOWED_HOSTS.add(railway_hostname)

ALLOWED_HOSTS = list(ALLOWED_HOSTS)
# Base de données pour la production
# Railway fournit une variable DATABASE_URL. dj-database-url la parse pour nous.
DATABASES = {
    'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
}

# Insérer WhiteNoiseMiddleware juste après SecurityMiddleware
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Paramètres de sécurité pour HTTPS
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True

# Configuration pour WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Le répertoire où `collectstatic` va rassembler tous les fichiers statiques.
# WhiteNoise utilisera ce répertoire pour servir les fichiers.
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Configuration des emails pour la production (déjà dans base.py, mais vérifiez les variables d'environnement)
if not os.getenv('EMAIL_HOST_USER') or not os.getenv('EMAIL_HOST_PASSWORD'):
    raise ImproperlyConfigured("Les variables d'environnement pour l'email ne sont pas configurées pour la production.")