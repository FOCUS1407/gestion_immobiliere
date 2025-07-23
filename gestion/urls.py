from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = 'gestion'

urlpatterns = [
    # Authentification et pages principales
    path('', views.accueil, name='accueil'),
    path('connexion/', views.connexion, name='connexion'),
    path('deconnexion/', views.logout_view, name='logout'),
    path('register/', views.register, name='register'), # Utilise la vue et le formulaire modernes
    
    # Tableaux de bord
    path('agence/', views.tableau_de_bord_agence, name='tableau_de_bord_agence'),
    path('proprietaire/', views.tableau_de_bord_proprietaire, name='tableau_de_bord_proprietaire'),
    
    # Réinitialisation de mot de passe
    path('reinitialisation/', 
         auth_views.PasswordResetView.as_view(
             template_name='authentification/reinitialisation.html',
             email_template_name='authentification/emails/reinitialisation_email.html',
             subject_template_name='authentification/emails/reinitialisation_sujet.txt'
         ), 
         name='reinitialisation'),
    
    path('reinitialisation/envoye/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='authentification/reinitialisation_envoye.html'
         ), 
         name='password_reset_done'),
    
    path('reinitialisation/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='authentification/reinitialisation_confirmation.html'
         ), 
         name='password_reset_confirm'),
    
    path('reinitialisation/termine/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='authentification/reinitialisation_termine.html'
         ), 
         name='password_reset_complete'),
    
    # Profil utilisateur
    path('profil/', views.profil_utilisateur, name='profil'),
    path('bien/ajouter/', views.ajouter_bien, name='ajouter_bien'),
    path('bien/<int:pk>/', views.bien_detail, name='bien_detail'),
    path('bien/<int:pk>/modifier/', views.modifier_bien, name='modifier_bien'),
    path('bien/<int:pk>/supprimer/', views.supprimer_bien, name='supprimer_bien'),
    path('proprietaire/<int:pk>/', views.proprietaire_detail, name='proprietaire_detail'),
    path('proprietaire/ajouter/', views.ajouter_proprietaire, name='ajouter_proprietaire'),
    path('profil/changer-mdp/', 
         auth_views.PasswordChangeView.as_view(
             template_name='gestion/changer_mdp.html',
             success_url=reverse_lazy('gestion:password_change_done')
         ), 
         name='changer_mdp'),
    path('profil/changer-mdp/termine/', 
         auth_views.PasswordChangeDoneView.as_view(
             template_name='gestion/changer_mdp_termine.html'
         ), 
         name='password_change_done'),
]