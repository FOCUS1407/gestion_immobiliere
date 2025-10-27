#!/bin/sh

# Arrête le script si une commande échoue
set -e

# Appliquer les migrations de la base de données
echo "Applying database migrations..."
python manage.py migrate
echo "Database migrations applied successfully."

# Démarrer le serveur Gunicorn
# 'exec' remplace le processus shell par Gunicorn, ce qui est une bonne pratique.
echo "Starting Gunicorn server with Gunicorn..."
# Utilisation de --log-level info pour des logs plus concis en production
# Les autres options sont conservées pour la performance et la robustesse
exec gunicorn --chdir /app gestion_immobiliere.wsgi:application --bind 0.0.0.0:$PORT --log-level info --timeout 120 --workers 2

# --- Fin du script d'entrée (ne devrait pas être atteint si Gunicorn démarre) ---
