import os
from .base import *  # Importe tous les paramètres communs
import sys
# CORRECTION : Importer dj_database_url pour pouvoir l'utiliser.
# Il était utilisé mais pas importé, ce qui aurait pu causer une NameError.
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

# Les paramètres ci-dessous sont spécifiques à l'environnement de PRODUCTION.

# SECURITY WARNING: keep the secret key used in production secret!
# DEBUG est déjà à False dans base.py, donc pas besoin de le redéfinir.
# CORRECTION : Détecter si la commande 'collectstatic' est en cours d'exécution.
IS_COLLECTSTATIC = 'collectstatic' in sys.argv

# Configurez les hôtes autorisés pour votre domaine de production.
# Ne PAS utiliser ['*'] en production !

# CORRECTION : Simplifier et sécuriser la configuration de ALLOWED_HOSTS.
# On récupère la variable d'environnement, avec une chaîne vide par défaut.
if IS_COLLECTSTATIC:
    # Pendant le build, on autorise tout pour éviter les erreurs.
    ALLOWED_HOSTS = ["*"]
else:
    allowed_hosts_str = os.getenv('ALLOWED_HOSTS', '')
    ALLOWED_HOSTS = [host.strip() for host in allowed_hosts_str.split(',') if host.strip()]

    # CORRECTION : Toujours ajouter le domaine de service de l'hébergeur s'il existe.
    # C'est crucial pour que les vérifications de santé (health checks) fonctionnent.
    service_hostname = os.getenv('RAILWAY_PUBLIC_DOMAIN') or os.getenv('HEROKU_HOSTNAME')
    if service_hostname:
        # On s'assure de ne pas l'ajouter en double
        if service_hostname not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(service_hostname)
            
    # CORRECTION : Ajouter le domaine privé de Railway pour les health checks internes.
    # C'est souvent la cause des échecs de health check.
    private_hostname = os.getenv('RAILWAY_PRIVATE_DOMAIN')
    if private_hostname:
        if private_hostname not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(private_hostname)

    # Vérification de sécurité : si on est en production (DEBUG=False) et que la liste est vide, on lève une erreur.
    if not DEBUG and not ALLOWED_HOSTS:
        raise ImproperlyConfigured("La variable d'environnement ALLOWED_HOSTS ne peut pas être vide en production.")

# --- Configuration de la base de données ---
# Par défaut, on exige la variable DATABASE_URL.
# L'absence de 'default' dans dj_database_url.config() fera échouer le démarrage
# si la variable est manquante, ce qui est le comportement souhaité.
DATABASES = {
    'default': dj_database_url.config(conn_max_age=600, ssl_require=True)
}

# CORRECTION : Si on est en train de construire les fichiers statiques, on remplace la configuration
# de la base de données par une base de données factice pour éviter les erreurs de connexion.
if IS_COLLECTSTATIC:
    DATABASES['default'] = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}

# --- Configuration pour le Reverse Proxy (Railway) ---
# Indique à Django de faire confiance à l'en-tête X-Forwarded-Proto envoyé par Railway.
# C'est essentiel pour que SECURE_SSL_REDIRECT fonctionne correctement.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
 
# CORRECTION : Placer WhiteNoiseMiddleware en PREMIÈRE position, avant SecurityMiddleware.
# Cela lui permet de servir les fichiers statiques efficacement sans interférer
# avec la logique de redirection ou d'autres middlewares de sécurité pour les URLs dynamiques.
MIDDLEWARE.insert(0, 'whitenoise.middleware.WhiteNoiseMiddleware')

# Paramètres de sécurité pour HTTPS
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
# Redirige tout le trafic HTTP vers HTTPS.
SECURE_SSL_REDIRECT = True
# CORRECTION : Exempter le point de contrôle de santé de la redirection SSL.
# Les vérifications de santé internes sont souvent en HTTP simple. Sans cette exception,
# Django renverrait une redirection 301, ce qui ferait échouer la vérification.
SECURE_REDIRECT_EXEMPT = [r'^healthz/?$']


# CORRECTION : Définir CSRF_TRUSTED_ORIGINS de manière conditionnelle pour éviter les erreurs pendant le build.
if IS_COLLECTSTATIC:
    CSRF_TRUSTED_ORIGINS = []
else:
    # En exécution normale, on dérive les origines de confiance de ALLOWED_HOSTS.
    CSRF_TRUSTED_ORIGINS = [f"https://{host}" for host in ALLOWED_HOSTS if host != "*"]

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

# Vérification de sécurité : si on est en production, les clés AWS sont obligatoires.
# CORRECTION : On ne fait cette vérification que si on n'est PAS en train d'exécuter `collectstatic`.
if not IS_COLLECTSTATIC and not DEBUG and not all([AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_STORAGE_BUCKET_NAME, AWS_S3_REGION_NAME]):
    raise ImproperlyConfigured("Les variables d'environnement AWS pour le stockage S3 ne sont pas toutes définies.")