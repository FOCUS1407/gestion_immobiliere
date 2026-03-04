import os
from .base import * # Importe tous les paramètres communs

# Les paramètres ci-dessous sont spécifiques à l'environnement de DÉVELOPPEMENT.

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# Pas besoin de CSRF_TRUSTED_ORIGINS en développement local avec DEBUG=True

# --- Base de données pour le développement ---
# Lève une erreur claire si les variables d'environnement ne sont pas trouvées.
try:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ['DB_NAME'],
            'USER': os.environ['DB_USER'],
            'PASSWORD': os.environ['DB_PASSWORD'],
            'HOST': os.getenv('DB_HOST', 'localhost'), # getenv garde une valeur par défaut
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
except KeyError as e:
    from django.core.exceptions import ImproperlyConfigured
    raise ImproperlyConfigured(
        f"La variable d'environnement {e} est manquante. Assurez-vous qu'elle est définie dans votre fichier .env."
    ) from e

# En développement, il est plus simple d'afficher les emails dans la console
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'