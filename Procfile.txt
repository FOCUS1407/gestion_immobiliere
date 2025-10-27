release: python manage.py migrate --no-input
web: echo "LD_LIBRARY_PATH is: $LD_LIBRARY_PATH" && python manage.py collectstatic --no-input && gunicorn gestion_immobiliere.wsgi