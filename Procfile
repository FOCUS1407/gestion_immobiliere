release: python manage.py collectstatic --no-input && python manage.py migrate
web: gunicorn gestion_immobiliere.wsgi
