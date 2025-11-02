from django import forms
from django.utils.safestring import mark_safe

class PasswordToggleWidget(forms.PasswordInput):
    """
    Un widget de champ de mot de passe qui inclut un bouton pour basculer la visibilité.
    """
    def __init__(self, attrs=None):
        # S'assure que les attributs par défaut sont fusionnés avec ceux fournis.
        default_attrs = {'class': 'form-control'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)

    def render(self, name, value, attrs=None, renderer=None):
        # Obtenir le rendu HTML du champ de mot de passe de base
        # CORRECTION : On s'assure que les attributs définis dans __init__ sont bien utilisés
        # en les fusionnant avec ceux potentiellement passés à la méthode render.
        final_attrs = self.build_attrs(self.attrs, attrs)
        input_html = super().render(name, value, final_attrs)

        # Ajouter le bouton "œil" à côté du champ
        # Le JavaScript nécessaire sera dans un fichier statique global.
        toggle_html = """
        <button class="btn btn-outline-secondary js-password-toggle" type="button" style="border-top-left-radius: 0; border-bottom-left-radius: 0;">
            <i class="fas fa-eye-slash"></i>
        </button>
        """

        # Envelopper le champ et le bouton dans un groupe pour qu'ils soient côte à côte
        return mark_safe(f'<div class="input-group">{input_html}{toggle_html}</div>')