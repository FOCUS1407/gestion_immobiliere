import os
from .base import *  # Importe tous les paramètres communs
import sys
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# ==============================================================================
# CONFIGURATION DE PRODUCTION
# ==============================================================================

# --- Détection du contexte de déploiement ---
# Cette variable est cruciale. Elle est True uniquement pendant la phase de `build`.
IS_COLLECTSTATIC = 'collectstatic' in sys.argv

# --- Configuration de la base de données ---
DATABASES = {
    'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
}
# Pendant la phase de build, on utilise une base de données factice pour que `collectstatic` ne plante pas.
if IS_COLLECTSTATIC:
    DATABASES['default'] = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}

# --- Configuration des fichiers statiques avec WhiteNoise ---
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
# Le répertoire où `collectstatic` va rassembler tous les fichiers statiques.
# WhiteNoise utilisera ce répertoire pour servir les fichiers.
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# --- Configuration des fichiers médias avec Amazon S3 ---
DEFAULT_FILE_STORAGE = 'storages.backends.s3.S3Storage'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = 'public-read'
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME')
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

# --- Configuration de la sécurité ---

# Hôtes autorisés
ALLOWED_HOSTS = []
if not IS_COLLECTSTATIC:
    # On récupère les domaines publics depuis les variables d'environnement
    public_hosts_str = os.getenv('ALLOWED_HOSTS', '')
    ALLOWED_HOSTS.extend([host.strip() for host in public_hosts_str.split(',') if host.strip()])

    # On ajoute les domaines de service de Railway (public et privé)
    railway_public = os.getenv('RAILWAY_PUBLIC_DOMAIN')
    if railway_public and railway_public not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(railway_public)
    
    railway_private = os.getenv('RAILWAY_PRIVATE_DOMAIN')
    if railway_private and railway_private not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(railway_private)

    # Vérification finale : la liste ne doit pas être vide en production
    if not ALLOWED_HOSTS:
        raise ImproperlyConfigured("ALLOWED_HOSTS ne peut pas être vide en production.")

# Configuration pour le reverse proxy (Railway)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Redirection HTTPS
SECURE_SSL_REDIRECT = True

# Exempter le health check de la redirection SSL
SECURE_REDIRECT_EXEMPT = [r'^healthz/?$']

# Cookies sécurisés
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Origines de confiance pour les requêtes POST en HTTPS
# CORRECTION : Définir CSRF_TRUSTED_ORIGINS de manière conditionnelle.
if IS_COLLECTSTATIC:
    CSRF_TRUSTED_ORIGINS = []
else:
    CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS]

# --- Configuration des Middlewares ---

# Position recommandée pour WhiteNoise : juste après SecurityMiddleware
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

# --- Vérifications de configuration finale ---

# On s'assure que les clés AWS sont bien définies, sauf pendant le build
if not IS_COLLECTSTATIC:
    aws_vars = [
        AWS_ACCESS_KEY_ID,
        AWS_SECRET_ACCESS_KEY,
        AWS_STORAGE_BUCKET_NAME,
        AWS_S3_REGION_NAME
    ]
    if not all(aws_vars):
        raise ImproperlyConfigured(
            "Toutes les variables d'environnement AWS (ACCESS_KEY, SECRET_KEY, BUCKET_NAME, REGION) "
            "doivent être définies en production."
        )