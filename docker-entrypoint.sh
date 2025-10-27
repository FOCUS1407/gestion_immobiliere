#!/bin/sh

# Arrête le script si une commande échoue
set -e

# Afficher les variables d'environnement pour le débogage (ATTENTION : ne pas laisser en production avec des secrets)
# --- Début du script d'entrée ---
echo "--- Début de docker-entrypoint.sh ---"

# Afficher les variables d'environnement pour le débogage
echo "--- Variables d'environnement au démarrage ---"
env
echo "--- Fin des variables d'environnement ---"

# Appliquer les migrations de la base de données
echo "Applying database migrations..."
python manage.py migrate
echo "Database migrations applied successfully."

# Démarrer le serveur Gunicorn
# 'exec' remplace le processus shell par Gunicorn, ce qui est une bonne pratique.
echo "Starting Gunicorn server with Gunicorn..."
# Ajout de --log-level debug pour plus de détails dans les logs
# Ajout de --timeout pour éviter un arrêt prématuré si le démarrage est lent
# Ajout de --workers pour une meilleure performance (ajuster selon les ressources)
# Ajout de --chdir /app pour s'assurer que Gunicorn s'exécute dans le bon répertoire
exec gunicorn --chdir /app gestion_immobiliere.wsgi:application --bind 0.0.0.0:8000 --log-level debug --timeout 120 --workers 2

# --- Fin du script d'entrée (ne devrait pas être atteint si Gunicorn démarre) ---
echo "--- Fin inattendue de docker-entrypoint.sh ---"
