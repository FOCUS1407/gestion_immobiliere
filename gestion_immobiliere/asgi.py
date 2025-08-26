"""
ASGI config for gestion_immobiliere project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

# En production, vous changerez peut-être ceci pour 'gestion_immobiliere.settings.production'
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestion_immobiliere.settings.development')

application = get_asgi_application()
