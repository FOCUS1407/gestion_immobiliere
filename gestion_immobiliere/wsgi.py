"""
WSGI config for gestion_immobiliere project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

# En production, vous changerez peut-être ceci pour 'gestion_immobiliere.settings.production'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_immobiliere.settings.development')

application = get_wsgi_application()
