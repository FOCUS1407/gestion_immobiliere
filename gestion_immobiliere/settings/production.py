import os
from .base import *  # Importe tous les paramètres communs
import sys
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

# S'assurer que ALLOWED_HOSTS n'est jamais vide en production, sauf pendant la phase de construction.
if 'collectstatic' not in sys.argv:
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("La liste ALLOWED_HOSTS ne peut pas être vide en production. Définissez la variable d'environnement ALLOWED_HOSTS ou RAILWAY_PUBLIC_DOMAIN.")

# --- Configuration de la base de données ---
# Si nous sommes en train d'exécuter `collectstatic`, nous n'avons pas besoin de la base de données.
# Cela permet à la construction Docker de fonctionner sans les secrets de production.
if 'collectstatic' in sys.argv:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'db.sqlite3'}}
else:
    DATABASE_URL = os.getenv('DATABASE_URL')
    if not DATABASE_URL:
        raise ImproperlyConfigured("La variable d'environnement DATABASE_URL n'est pas définie pour la production.")

    DATABASES = {
        'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
    }

# --- Configuration pour le Reverse Proxy (Railway) ---
# Indique à Django de faire confiance à l'en-tête X-Forwarded-Proto envoyé par Railway.
# C'est essentiel pour que SECURE_SSL_REDIRECT fonctionne correctement.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Insérer WhiteNoiseMiddleware juste après SecurityMiddleware
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Paramètres de sécurité pour HTTPS
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
# Redirige tout le trafic HTTP vers HTTPS.
SECURE_SSL_REDIRECT = True

# Domaines de confiance pour les requêtes CSRF (connexion, formulaires, etc.)
if 'collectstatic' not in sys.argv:
    CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]
else:
    # Pendant collectstatic, on peut le laisser vide car il ne sera pas utilisé.
    # Django 4.0+ lève une ImproperlyConfigured si CSRF_TRUSTED_ORIGINS est vide et CSRF_COOKIE_SECURE est True en non-DEBUG.
    CSRF_TRUSTED_ORIGINS = []

# Configuration pour WhiteNoise
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Le répertoire où `collectstatic` va rassembler tous les fichiers statiques.
# WhiteNoise utilisera ce répertoire pour servir les fichiers.
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')