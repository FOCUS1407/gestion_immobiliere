# Utilisez une image de base Python officielle.
# Choisissez une version de Python qui correspond à celle de votre environnement de développement.
# Par exemple, python:3.10-slim-buster pour Debian 10 (Buster) ou python:3.11-slim-bullseye pour Debian 11 (Bullseye).
# L'image 'slim' est plus légère et contient le strict minimum.
FROM python:3.11-slim-bullseye

# Définir l'encodage pour éviter les problèmes de locale
ENV LANG C.UTF-8
ENV PYTHONUNBUFFERED 1

# Définir le répertoire de travail dans le conteneur
WORKDIR /app

# Installer les dépendances système nécessaires pour WeasyPrint et d'autres outils.
# libgobject-2.0-0 est inclus via gir1.2-gtk-3.0 et libgirepository-1.0-1.
# Les autres sont pour Pango, Cairo, et les formats d'image.
# build-essential est utile pour compiler certaines dépendances Python si nécessaire.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
    # Dépendances pour psycopg (PostgreSQL)
    libpq-dev postgresql-client \
    build-essential \
    dos2unix \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    gir1.2-gtk-3.0 \
    libgirepository-1.0-1 \
    && rm -rf /var/lib/apt/lists/*

# Copier les fichiers de dépendances Python et les installer
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copier le reste du code de l'application
COPY . /app/

# Lancer collectstatic pour rassembler tous les fichiers statiques
# La variable d'environnement DJANGO_SETTINGS_MODULE est nécessaire pour que manage.py sache quels paramètres utiliser.
ENV DJANGO_SETTINGS_MODULE=gestion_immobiliere.settings.production
RUN python manage.py collectstatic --noinput

# Exposer le port sur lequel Django s'exécute (par défaut 8000)
EXPOSE 8000

# Commande pour démarrer l'application Django avec Gunicorn
# Assurez-vous que Gunicorn est dans votre requirements.txt
# Utilisez le fichier wsgi.py de votre projet

# Copier le script d'entrée et le rendre exécutable
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
# Utiliser dos2unix pour s'assurer que les fins de ligne sont correctes (LF)
RUN dos2unix /app/docker-entrypoint.sh
# Rendre le script exécutable
RUN chmod +x /app/docker-entrypoint.sh
CMD ["/app/docker-entrypoint.sh"]