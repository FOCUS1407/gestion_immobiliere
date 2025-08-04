from django.urls import path, reverse_lazy
from . import views, forms
from django.contrib.auth import views as auth_views

app_name = 'gestion'

urlpatterns = [
    # URLs générales et d'authentification
    path('', views.accueil, name='accueil'),
    path('connexion/', views.connexion, name='connexion'),
    path('deconnexion/', views.logout_view, name='logout'),
    path('inscription/', views.register, name='register'),
    path('cgu/', views.terms_of_service_view, name='terms_of_service'),
    path('profil/', views.profil_utilisateur, name='profil'),

    # URLs de changement de mot de passe
    path('profil/changer-mot-de-passe/',
         auth_views.PasswordChangeView.as_view(
             template_name='gestion/changer_mdp.html',
             success_url=reverse_lazy('gestion:changer_mdp_done'),
             form_class=forms.CustomPasswordChangeForm
         ),
         name='changer_mdp'),
    path('profil/changer-mot-de-passe/done/',
         views.CustomPasswordChangeDoneView.as_view(template_name='gestion/changer_mdp_done.html'),
         name='changer_mdp_done'),

    # URLs de réinitialisation de mot de passe
    path('reinitialisation/', 
         auth_views.PasswordResetView.as_view(
             template_name='gestion/password_reset_form.html',
             email_template_name='gestion/email/password_reset_email.html',
             html_email_template_name='gestion/email/password_reset_email.html',
             subject_template_name='gestion/password_reset_subject.txt',
             success_url=reverse_lazy('gestion:password_reset_done'),
             form_class=forms.CustomPasswordResetForm
         ), 
         name='reinitialisation'),
    path('reinitialisation/envoye/', 
         auth_views.PasswordResetDoneView.as_view(
             template_name='gestion/password_reset_done.html'
         ), 
         name='password_reset_done'),
    path('reinitialisation/confirmer/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='gestion/password_reset_confirm.html',
             success_url=reverse_lazy('gestion:password_reset_complete')
         ), 
         name='password_reset_confirm'),
    path('reinitialisation/complet/', 
         auth_views.PasswordResetCompleteView.as_view(
             template_name='gestion/password_reset_complete.html'
         ), 
         name='password_reset_complete'),

    # Tableaux de bord
    path('tableau-de-bord/agence/', views.tableau_de_bord_agence, name='tableau_de_bord_agence'),
    path('tableau-de-bord/proprietaire/', views.tableau_de_bord_proprietaire, name='tableau_de_bord_proprietaire'),

    # Gestion des Propriétaires (par l'agence)
    path('proprietaires/ajouter/', views.ajouter_proprietaire, name='ajouter_proprietaire'),
    path('proprietaires/<int:pk>/', views.proprietaire_detail, name='proprietaire_detail'),
    path('proprietaires/<int:pk>/modifier/', views.modifier_proprietaire, name='modifier_proprietaire'),
    path('proprietaires/<int:pk>/supprimer/', views.supprimer_proprietaire, name='supprimer_proprietaire'),

    # Gestion des Immeubles (par l'agence)
    path('proprietaires/<int:pk>/immeubles/ajouter/', views.ajouter_immeuble, name='ajouter_immeuble'),
    path('immeubles/<int:pk>/', views.immeuble_detail, name='immeuble_detail'),
    path('immeubles/<int:pk>/modifier/', views.modifier_immeuble, name='modifier_immeuble'),
    path('immeubles/<int:pk>/supprimer/', views.supprimer_immeuble, name='supprimer_immeuble'),
    
    # Gestion des Unités/Chambres (par l'agence)
    path('immeubles/<int:immeuble_id>/chambres/ajouter/', views.ajouter_chambre, name='ajouter_chambre'),
    path('chambres/<int:pk>/', views.chambre_detail, name='chambre_detail'),
    path('chambres/<int:pk>/modifier/', views.modifier_chambre, name='modifier_chambre'),
    path('chambres/<int:pk>/supprimer/', views.supprimer_chambre, name='supprimer_chambre'),
    path('chambres/<int:pk>/liberer/', views.liberer_chambre, name='liberer_chambre'),

    # Gestion des Locataires (par l'agence)
    path('locataires/', views.gerer_locataires, name='gerer_locataires'),
    path('locataires/ajouter/', views.ajouter_locataire, name='ajouter_locataire'),
    path('locataires/<int:pk>/', views.locataire_detail, name='locataire_detail'),
    path('locataires/<int:pk>/modifier/', views.modifier_locataire, name='modifier_locataire'),
    path('locataires/<int:pk>/supprimer/', views.supprimer_locataire, name='supprimer_locataire'),

    # Gestion des Paiements (par l'agence)
    path('chambres/<int:chambre_id>/paiements/ajouter/', views.ajouter_paiement, name='ajouter_paiement'),
    path('paiements/<int:pk>/modifier/', views.modifier_paiement, name='modifier_paiement'),
    path('paiements/<int:pk>/supprimer/', views.supprimer_paiement, name='supprimer_paiement'),
    path('paiements/<int:pk>/quittance/', views.generer_quittance_pdf, name='generer_quittance_pdf'),

    # Gestion des États des Lieux
    path('etats-des-lieux/<int:pk>/modifier/', views.modifier_etat_des_lieux, name='modifier_etat_des_lieux'),
    path('etats-des-lieux/<int:pk>/supprimer/', views.supprimer_etat_des_lieux, name='supprimer_etat_des_lieux'),
    path('etats-des-lieux/<int:pk>/pdf/', views.generer_etat_des_lieux_pdf, name='generer_etat_des_lieux_pdf'),

    # Paramètres et Exports
    path('parametres/moyens-paiement/', views.gerer_moyens_paiement, name='gerer_moyens_paiement'),
    path('parametres/moyens-paiement/<int:pk>/supprimer/', views.supprimer_moyen_paiement, name='supprimer_moyen_paiement'),
    path('export/paiements/csv/', views.exporter_paiements_csv, name='exporter_paiements_csv'),
    path('rapports/financier/', views.rapport_financier, name='rapport_financier'),
    path('rapports/financier/pdf/', views.generer_rapport_financier_pdf, name='generer_rapport_financier_pdf'),

    # Notifications
    path('notifications/', views.notification_list, name='notification_list'),
]
