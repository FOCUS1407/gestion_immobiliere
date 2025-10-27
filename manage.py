#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from dotenv import load_dotenv

def main():
    """Run administrative tasks."""
    # Charger les variables d'environnement depuis le fichier .env.
    # Ceci doit être fait AVANT d'accéder à os.environ.
    load_dotenv()

    # En production, DJANGO_SETTINGS_MODULE sera fourni par Gunicorn ou une variable d'environnement.
    # En développement, il est défini dans le fichier .env ou par votre IDE.
    # Nous n'avons plus besoin de `setdefault` ici, ce qui rend le code plus propre et moins sujet aux erreurs.
    # Assurez-vous que votre .env local contient : DJANGO_SETTINGS_MODULE=gestion_immobiliere.settings.development

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
