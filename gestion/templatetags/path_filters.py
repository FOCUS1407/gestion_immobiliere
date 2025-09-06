from django import template
from pathlib import Path

register = template.Library()

@register.filter
def to_path_uri(value):
    """
    Convertit un chemin de fichier système (ex: C:\\path\\to\\file.png)
    en un URI de fichier standard (ex: file:///C:/path/to/file.png)
    que WeasyPrint peut interpréter de manière fiable sur tous les systèmes.
    """
    if not value:
        return ""
    # Crée un objet Path, puis le convertit en URI.
    return Path(value).as_uri()