from django import template

register = template.Library()

@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    """
    Prend les paramètres de la requête GET actuelle et les met à jour
    avec les nouveaux paramètres fournis.
    """
    query = context['request'].GET.copy()
    for key, value in kwargs.items():
        # On s'assure de ne pas ajouter de valeurs None à l'URL.
        if value is not None:
            query[key] = value
        # Si la nouvelle valeur est None et que la clé existe, on la retire.
        elif key in query:
            del query[key]
    return query.urlencode()