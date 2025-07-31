from django.urls import reverse
from django.shortcuts import redirect
from django.contrib import messages

class ForcePasswordChangeMiddleware:
    """
    Middleware qui vérifie si un utilisateur doit changer son mot de passe.
    Si c'est le cas, il le redirige vers la page de changement de mot de passe,
    sauf s'il essaie déjà d'y accéder ou de se déconnecter.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Le middleware ne s'applique qu'aux utilisateurs authentifiés
        if request.user.is_authenticated and request.user.must_change_password:
            
            # Liste des URLs autorisées pendant ce processus
            allowed_urls = [
                reverse('gestion:changer_mdp'),
                reverse('gestion:changer_mdp_done'),
                reverse('gestion:logout')
            ]

            if request.path not in allowed_urls:
                messages.warning(request, "Pour des raisons de sécurité, vous devez changer votre mot de passe temporaire avant de continuer.")
                return redirect('gestion:changer_mdp')

        response = self.get_response(request)
        return response