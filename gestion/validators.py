import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class CustomPasswordValidator:
    """
    Valide que le mot de passe contient au moins un chiffre et un symbole.
    """
    def __init__(self, symbols="!@#$%^&*(),.?\":{}|<>"):
        self.symbols = symbols

    def validate(self, password, user=None):
        if not re.search(r'\d', password):
            raise ValidationError(
                _("Le mot de passe doit contenir au moins un chiffre (0-9)."),
                code='password_no_digit',
            )
        if not any(char in self.symbols for char in password):
            raise ValidationError(
                _("Le mot de passe doit contenir au moins un symbole (ex: !@#$%%)."),
                code='password_no_symbol',
            )

    def get_help_text(self):
        return _(
            "Votre mot de passe doit contenir au moins un chiffre et un symbole."
        )