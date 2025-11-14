#!/bin/sh

# Arrête le script si une commande échoue
set -e

# Appliquer les migrations de la base de données
echo "Applying database migrations..."
python manage.py migrate
echo "Database migrations applied successfully."

# Collecter tous les fichiers statiques dans le répertoire STATIC_ROOT
echo "Collecting static files..."
python manage.py collectstatic --no-input
echo "Static files collected successfully."

# Démarrer le serveur Gunicorn
# 'exec' remplace le processus shell par Gunicorn, ce qui est une bonne pratique.
echo "Starting Gunicorn server with Gunicorn..."
# Utilisation de --log-level info pour des logs plus concis en production
# Les autres options sont conservées pour la performance et la robustesse
# --workers 3 : Nombre de processus pour gérer les requêtes.
# --timeout 120 : Augmente le délai d'attente à 120 secondes pour donner à l'application le temps de démarrer.
exec gunicorn gestion_immobiliere.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120


# --- Fin du script d'entrée (ne devrait pas être atteint si Gunicorn démarre) ---
