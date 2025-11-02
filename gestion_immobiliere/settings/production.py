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
# S'assurer que ALLOWED_HOSTS n'est jamais vide en production, sauf pendant la phase de construction.
if 'collectstatic' not in sys.argv:
    allowed_hosts_str = os.getenv('ALLOWED_HOSTS')
    if not allowed_hosts_str:
        raise ImproperlyConfigured("La variable d'environnement ALLOWED_HOSTS est requise en production.")
    
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_str.split(',')]
    
    # Railway injecte une variable d'environnement pour son domaine de service.
    # C'est une bonne pratique de l'ajouter si elle existe.
    railway_hostname = os.getenv('RAILWAY_PUBLIC_DOMAIN')
    if railway_hostname:
        ALLOWED_HOSTS.append(railway_hostname)
else:
    # Pendant la phase de build, la liste peut être vide.
    ALLOWED_HOSTS = []

# --- Configuration de la base de données ---
DATABASES = {
    'default': dj_database_url.config(conn_max_age=600, ssl_require=True, default='sqlite:///db.sqlite3')
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

# --- Configuration du stockage des fichiers MEDIA (téléversements utilisateurs) sur Amazon S3 ---

# Ne pas écraser les fichiers avec le même nom
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = 'public-read'

# Le backend de stockage par défaut pour les fichiers média
DEFAULT_FILE_STORAGE = 'storages.backends.s3.S3Storage'

# Configuration de l'accès à votre bucket S3 via les variables d'environnement
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = os.getenv('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = os.getenv('AWS_S3_REGION_NAME') # ex: 'eu-west-3'

# URL personnalisée pour servir les fichiers (meilleure performance)
AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com'

# S'assurer que les variables AWS sont définies si on n'est pas en train de build
if 'collectstatic' not in sys.argv and not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME, AWS_S3_REGION_NAME]):
    raise ImproperlyConfigured("Les variables d'environnement AWS pour le stockage S3 ne sont pas toutes définies.")