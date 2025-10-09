release: python manage.py migrate --settings=gestion_immobiliere.settings.production
web: gunicorn gestion_immobiliere.wsgi --settings=gestion_immobiliere.settings.production