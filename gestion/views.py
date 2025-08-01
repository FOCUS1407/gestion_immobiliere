from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.views import PasswordChangeDoneView
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction, IntegrityError, models
from django.db.models import Sum, Count, Q
from django.db.models.functions import TruncMonth
from django.template.loader import render_to_string
from django.utils import timezone
from django.http import HttpResponse
from datetime import datetime, timedelta
from decimal import Decimal
from dateutil.relativedelta import relativedelta
import locale
import string
import random
from django.urls import reverse
import csv

from gestion.forms import AgenceProfileForm, ChambreForm, EtatDesLieuxForm, ImmeubleForm, LocataireForm, LocationForm, LoginForm, MoyenPaiementForm, PaiementForm, ProprietaireCreationForm, ProprietaireProfileUpdateForm, RegisterForm, UserUpdateForm
from gestion.models import Agence, CustomUser, EtatDesLieux, Locataire, Location, MoyenPaiement, Notification, Paiement, Proprietaire, Immeuble,Chambre

try:
    from weasyprint import HTML
except ImportError:
    HTML = None # Gère le cas où WeasyPrint n'est pas installé

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

User = get_user_model()

def accueil(request):
    """
    Affiche la page d'accueil.
    Redirige les utilisateurs déjà connectés vers leur tableau de bord.
    """
    if request.user.is_authenticated:
        if request.user.user_type == 'AG':
            return redirect('gestion:tableau_de_bord_agence')
        else: # 'PR'
            return redirect('gestion:tableau_de_bord_proprietaire')
            
    return render(request, 'gestion/accueil.html')

def connexion(request):
    """
    Gère la connexion des utilisateurs et redirige selon le type de compte.
    """
    if request.user.is_authenticated:
        # Si l'utilisateur est déjà connecté, on le redirige vers son tableau de bord
        if request.user.user_type == 'AG':
            return redirect('gestion:tableau_de_bord_agence')
        else: # 'PR'
            return redirect('gestion:tableau_de_bord_proprietaire')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # messages.success(request, f"Bienvenue, {user.username} !") # Message de bienvenue supprimé.
            # Redirection vers le tableau de bord approprié
            if user.user_type == 'AG':
                return redirect('gestion:tableau_de_bord_agence')
            else:
                return redirect('gestion:tableau_de_bord_proprietaire')
        else:
            messages.error(request, "Nom d'utilisateur ou mot de passe incorrect.")
    else:
        form = LoginForm()
    return render(request, 'gestion/connexion.html', {'form': form})

def logout_view(request):
    """
    Déconnecte l'utilisateur.
    """
    logout(request)
    messages.info(request, "Vous avez été déconnecté avec succès.")
    return redirect('gestion:accueil')

def register(request):
    """
    Gère l'inscription des utilisateurs avec un formulaire Django.
    """
    if request.user.is_authenticated:
        return redirect('gestion:accueil')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Votre compte a été créé avec succès !")
            if user.user_type == 'AG':
                return redirect('gestion:tableau_de_bord_agence')
            else:
                return redirect('gestion:tableau_de_bord_proprietaire')
    else:
        form = RegisterForm()
    return render(request, 'gestion/register.html', {'form': form})

def terms_of_service_view(request):
    """Affiche la page des conditions d'utilisation."""
    return render(request, 'gestion/terms_of_service.html')

# Vues de placeholder pour éviter les erreurs
@login_required
def tableau_de_bord_agence(request):
    # Vérification de permission : un propriétaire ne peut pas accéder à ce tableau de bord.
    # S'il essaie, il est redirigé vers son propre tableau de bord.
    if request.user.user_type != 'AG':
        return redirect('gestion:tableau_de_bord_proprietaire')
    
    proprietaires_geres = Proprietaire.objects.none()
    nombre_proprietaires = 0
    
    # Récupère les propriétaires gérés par l'agence
    try:
        # On s'assure que l'utilisateur a un profil Agence avant de l'utiliser.
        agence_profil = None # Initialisation
        agence_profil = request.user.agence
        # Récupère TOUS les propriétaires gérés et annote avec le nombre d'immeubles pour optimiser.
        all_proprietaires_list = Proprietaire.objects.filter(
            agence=agence_profil
        ).select_related('user').annotate(
            nombre_immeubles_proprietaire=Count('immeubles')
        ).order_by('user__last_name', 'user__first_name')
        nombre_proprietaires = all_proprietaires_list.count()
    except User.agence.RelatedObjectDoesNotExist:
        # Gère le cas où un utilisateur de type Agence n'a pas encore de profil Agence créé.
        # Ce n'est pas une erreur bloquante pour le tableau de bord, on affiche juste un avertissement.
        all_proprietaires_list = Proprietaire.objects.none()
        nombre_proprietaires = 0
        messages.warning(request, "Votre profil d'agence n'est pas complet. Certaines informations peuvent manquer.")
    
    # --- Calcul du résumé financier pour le mois en cours ---
    now = timezone.now()
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')
    current_month_display = now.strftime('%B %Y').capitalize()
    
    total_attendu_mois = Decimal('0.00')
    total_paye_mois = Decimal('0.00')
    commission_mois = Decimal('0.00')

    if agence_profil:
        # Loyer total attendu pour le mois en cours pour les chambres occupées
        total_attendu_mois = Chambre.objects.filter(
            immeuble__proprietaire__agence=agence_profil,
            locataire__isnull=False
        ).aggregate(total=Sum('prix_loyer'))['total'] or Decimal('0.00')

        # Paiements validés pour le mois en cours
        paiements_mois = Paiement.objects.filter(
            location__chambre__immeuble__proprietaire__agence=agence_profil,
            mois_couvert=current_month_display,
            est_valide=True
        ).select_related('location__chambre__immeuble__proprietaire')

        total_paye_mois = paiements_mois.aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
        
        for p in paiements_mois:
            commission_rate = p.location.chambre.immeuble.proprietaire.taux_commission
            commission_mois += p.montant * (commission_rate / Decimal('100.0'))

    total_impaye_mois = total_attendu_mois - total_paye_mois

    # --- Pagination pour la liste des propriétaires ---
    paginator = Paginator(all_proprietaires_list, 10) # 10 propriétaires par page
    page_number = request.GET.get('page')
    try:
        proprietaires_page = paginator.page(page_number)
    except PageNotAnInteger:
        # Si la page n'est pas un entier, afficher la première page.
        proprietaires_page = paginator.page(1)
    except EmptyPage:
        # Si la page est hors limites, afficher la dernière page.
        proprietaires_page = paginator.page(paginator.num_pages)

    # --- Logique de filtrage pour les données (stats, graphique, listes) ---
    selected_proprietaire_id = request.GET.get('proprietaire_id')
    
    # Le queryset de base inclut tous les immeubles de l'agence
    immeubles_geres = Immeuble.objects.filter(proprietaire__agence=agence_profil).select_related('proprietaire__user', 'type_bien')

    if selected_proprietaire_id and selected_proprietaire_id.isdigit():
        # Si un propriétaire est sélectionné, on filtre le queryset des immeubles
        immeubles_geres = immeubles_geres.filter(proprietaire_id=selected_proprietaire_id)
        selected_proprietaire_id = int(selected_proprietaire_id)
    else:
        selected_proprietaire_id = None

    nombre_immeubles = immeubles_geres.count()
    
    # 2. Récupérer toutes les unités (chambres) de ces immeubles
    total_chambres_list = Chambre.objects.filter(immeuble__in=immeubles_geres).select_related('immeuble', 'locataire').order_by('immeuble__addresse', 'designation')
    total_units = total_chambres_list.count()
    
    # 3. Compter les unités occupées (celles avec un locataire assigné)
    occupied_units = total_chambres_list.filter(locataire__isnull=False).count()
    
    # 4. Calculer le taux
    occupancy_rate = 0
    if total_units > 0:
        occupancy_rate = (occupied_units / total_units) * 100

    # --- Pagination pour les chambres ---
    chambres_paginator = Paginator(total_chambres_list, 5) # 5 chambres par page
    chambres_page_number = request.GET.get('chambres_page')
    try:
        chambres_page = chambres_paginator.page(chambres_page_number)
    except PageNotAnInteger:
        chambres_page = chambres_paginator.page(1)
    except EmptyPage:
        chambres_page = chambres_paginator.page(chambres_paginator.num_pages)

    # --- Calcul des revenus mensuels pour le graphique ---
    # On filtre les paiements validés pour les immeubles gérés par l'agence
    # et on les groupe par mois sur les 12 derniers mois.
    douze_mois_avant = timezone.now().date() - timedelta(days=365)
    revenus_par_mois = Paiement.objects.filter(
        location__chambre__immeuble__in=immeubles_geres,
        est_valide=True,
        date_paiement__gte=douze_mois_avant
    ).annotate(
        month=TruncMonth('date_paiement')  # Tronque la date au premier jour du mois
    ).values(
        'month'  # Groupe par mois
    ).annotate(
        total=Sum('montant')  # Calcule la somme des montants pour ce mois
    ).values('month', 'total').order_by('month')

    # Formatter les données pour Chart.js
    revenue_dict = {item['month'].strftime('%Y-%m'): float(item['total']) for item in revenus_par_mois}
    
    chart_labels = []
    chart_data = []
    current_date = timezone.now().date()
    for i in range(12):
        # Formatage du label (ex: "août 24")
        month_label = current_date.strftime("%b %y").lower().capitalize()
        month_key = current_date.strftime('%Y-%m')
        
        chart_labels.insert(0, month_label)
        chart_data.insert(0, revenue_dict.get(month_key, 0))
        
        # Aller au mois précédent
        premier_jour_mois_courant = current_date.replace(day=1)
        dernier_jour_mois_precedent = premier_jour_mois_courant - timedelta(days=1)
        current_date = dernier_jour_mois_precedent

    context = {
        'immeubles': immeubles_geres,
        'nombre_immeubles': nombre_immeubles,
        'proprietaires_page': proprietaires_page,
        'nombre_proprietaires': nombre_proprietaires,
        'occupancy_rate': occupancy_rate,
        'chambres_page': chambres_page,
        'total_units': total_units,
        'all_proprietaires': all_proprietaires_list,
        'selected_proprietaire_id': selected_proprietaire_id,
        'chart_labels': chart_labels,
        'chart_data': chart_data,
        'current_month_display': current_month_display,
        'total_attendu_mois': total_attendu_mois,
        'total_paye_mois': total_paye_mois,
        'total_impaye_mois': total_impaye_mois,
        'commission_mois': commission_mois,
    }
    return render(request, 'gestion/tableau_de_bord_agence.html', context)

@login_required
def tableau_de_bord_proprietaire(request):
    """
    Affiche le tableau de bord pour un utilisateur de type Propriétaire,
    listant ses immeubles.
    """
    if request.user.user_type != 'PR':
        raise PermissionDenied("Seuls les propriétaires peuvent accéder à cette page.")

    try:
        proprietaire_profil = request.user.proprietaire
        immeubles_proprietaire = Immeuble.objects.filter(proprietaire=proprietaire_profil).select_related('type_bien')
        nombre_immeubles = immeubles_proprietaire.count()
    except Proprietaire.DoesNotExist:
        immeubles_proprietaire = Immeuble.objects.none()
        nombre_immeubles = 0
        messages.warning(request, "Votre profil de propriétaire n'est pas complet ou n'a pas été trouvé.")

    context = {
        'immeubles': immeubles_proprietaire,
        'nombre_immeubles': nombre_immeubles,
    }
    return render(request, 'gestion/tableau_de_bord_proprietaire.html', context)

@login_required
def profil_utilisateur(request):
    """
    Affiche et gère la mise à jour du profil de l'utilisateur
    et de son profil Agence si applicable.
    """
    user = request.user
    agence_form = None
    agence_profile = None
    proprietaire_profile = None # Ajout pour le profil propriétaire

    if user.user_type == 'AG':
        agence_profile, created = Agence.objects.get_or_create(user=user)
    elif user.user_type == 'PR':
        try:
            proprietaire_profile = user.proprietaire
        except Proprietaire.DoesNotExist:
            # Ce cas ne devrait pas arriver dans un flux normal, mais on le gère.
            messages.warning(request, "Votre profil de contrat est introuvable. Veuillez contacter votre agence.")

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, request.FILES, instance=user)
        
        form_list = [user_form]
        if user.user_type == 'AG':
            # On passe aussi request.FILES pour gérer l'upload du logo
            agence_form = AgenceProfileForm(request.POST, request.FILES, instance=agence_profile)
            form_list.append(agence_form)
        # Note: Le propriétaire ne peut pas modifier son contrat ici. C'est géré par l'agence.
        # On ne traite donc que le user_form pour lui.

        # On vérifie si tous les formulaires sont valides
        if all(form.is_valid() for form in form_list):
            for form in form_list:
                form.save() # On sauvegarde chaque formulaire
            
            messages.success(request, 'Votre profil a été mis à jour avec succès.')
            # Rediriger vers le tableau de bord approprié après la mise à jour
            if user.user_type == 'AG':
                return redirect('gestion:tableau_de_bord_agence')
            else: # 'PR'
                return redirect('gestion:tableau_de_bord_proprietaire')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        # En méthode GET, on affiche les formulaires avec les données actuelles
        user_form = UserUpdateForm(instance=user)
        if user.user_type == 'AG':
            agence_form = AgenceProfileForm(instance=agence_profile)

    context = {
        'user_form': user_form,
        'agence_form': agence_form,
        'proprietaire_profile': proprietaire_profile, # On passe le profil au template
        'page_title': 'Modifier mon profil',
    }
    return render(request, 'gestion/profil.html', context)

class CustomPasswordChangeDoneView(PasswordChangeDoneView):
    """
    Vue affichée après un changement de mot de passe réussi.
    Elle désactive l'indicateur 'must_change_password'.
    """
    def get(self, request, *args, **kwargs):
        if request.user.must_change_password:
            request.user.must_change_password = False
            request.user.save()
        return super().get(request, *args, **kwargs)
@login_required
def ajouter_proprietaire(request):
    """
    Vue pour une agence pour ajouter un nouveau propriétaire, son bien et son contrat.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent ajouter des propriétaires.")

    try:
        # Vérification critique : l'agence doit avoir un profil pour pouvoir ajouter un propriétaire.
        agence_profil = request.user.agence
    except User.agence.RelatedObjectDoesNotExist:
        messages.error(request, "Action impossible : vous devez d'abord compléter votre profil d'agence.")
        return redirect('gestion:profil') # On redirige vers la page de profil pour la compléter

    if request.method == 'POST':
        form = ProprietaireCreationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    cd = form.cleaned_data
                    
                    # 1. Créer le compte utilisateur pour le propriétaire
                    # Générer un nom d'utilisateur unique et un mot de passe temporaire
                    base_username = f"{cd['first_name'].lower()}.{cd['last_name'].lower().replace(' ', '')}"
                    username = base_username
                    counter = 1
                    # Boucle pour garantir un nom d'utilisateur unique
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1
                    
                    password = User.objects.make_random_password(length=12, allowed_chars='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*')

                    proprietaire_user = User.objects.create_user(
                        username=username,
                        password=password,
                        email=cd['email'],
                        first_name=cd['first_name'],
                        last_name=cd['last_name'],
                        telephone=cd['telephone'],
                        addresse=cd['addresse'],
                        must_change_password=True, # Forcer le changement de mot de passe
                        user_type='PR'
                    )

                    # 2. Créer le profil Proprietaire (contrat)
                    proprietaire_profil = Proprietaire.objects.create(
                        user=proprietaire_user,
                        agence=agence_profil, # Utilise le profil Agence vérifié
                        taux_commission=cd['taux_commission'],
                        date_debut_contrat=cd['date_debut_contrat'],
                        duree_contrat=cd['duree_contrat']
                    )

                messages.success(request, f"Le propriétaire {proprietaire_user.get_full_name()} a été ajouté avec succès.")

                # --- Envoi de l'email de bienvenue ---
                try:
                    subject = render_to_string('gestion/email/welcome_proprietaire_subject.txt').strip()
                    login_url = request.build_absolute_uri(reverse('gestion:connexion'))
                    
                    email_context = {
                        'user': proprietaire_user,
                        'password': password,
                        'login_url': login_url,
                    }
                    
                    text_body = render_to_string('gestion/email/welcome_proprietaire_body.txt', email_context)
                    html_body = render_to_string('gestion/email/welcome_proprietaire_body.html', email_context)

                    send_mail(
                        subject=subject, message=text_body, from_email=None,
                        recipient_list=[proprietaire_user.email], html_message=html_body,
                        fail_silently=False,
                    )
                    messages.info(request, f"Un email de bienvenue a été envoyé à {proprietaire_user.email} avec ses identifiants.")
                except Exception as email_error:
                    messages.warning(request, f"Le propriétaire a été créé, mais l'envoi de l'email de bienvenue a échoué : {email_error}")

                # Rediriger vers la page de détail du nouveau propriétaire pour pouvoir lui ajouter des biens
                return redirect('gestion:proprietaire_detail', pk=proprietaire_user.pk)

            except Exception as e:
                messages.error(request, f"Une erreur est survenue : {e}")
    else:
        form = ProprietaireCreationForm()

    return render(request, 'gestion/ajouter_proprietaire.html', {'form': form})

@login_required
def proprietaire_detail(request, pk):
    """
    Affiche les détails d'un propriétaire spécifique géré par l'agence.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent voir les détails des propriétaires.")

    # Récupère le propriétaire et son profil
    proprietaire_user = get_object_or_404(User, pk=pk, user_type='PR')
    proprietaire_profil = get_object_or_404(Proprietaire, user=proprietaire_user)

    # Vérification de sécurité : l'agence connectée gère-t-elle bien ce propriétaire ?
    try:
        if proprietaire_profil.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce propriétaire.")
    except User.agence.RelatedObjectDoesNotExist:
        # Si l'agence n'a pas de profil, elle ne peut gérer personne.
        raise PermissionDenied("Votre profil d'agence est incomplet.")

    # Récupère les immeubles de ce propriétaire, en pré-chargeant les unités pour optimiser
    immeubles_du_proprietaire = Immeuble.objects.filter(proprietaire=proprietaire_profil).prefetch_related('chambres')

    context = {
        'proprietaire_user': proprietaire_user,
        'proprietaire_profil': proprietaire_profil,
        'immeubles': immeubles_du_proprietaire,
    }
    return render(request, 'gestion/proprietaire_detail.html', context)

@login_required
def modifier_proprietaire(request, pk):
    """
    Gère la modification des informations d'un propriétaire et de son contrat.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent modifier les propriétaires.")

    proprietaire_user = get_object_or_404(User, pk=pk, user_type='PR')
    proprietaire_profil = get_object_or_404(Proprietaire, user=proprietaire_user)

    # Vérification de sécurité : l'agence connectée gère-t-elle bien ce propriétaire ?
    try:
        if proprietaire_profil.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce propriétaire.")
    except User.agence.RelatedObjectDoesNotExist:
        raise PermissionDenied("Votre profil d'agence est incomplet.")

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=proprietaire_user)
        profile_form = ProprietaireProfileUpdateForm(request.POST, instance=proprietaire_profil)

        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            messages.success(request, f"Les informations de {proprietaire_user.get_full_name()} ont été mises à jour.")
            return redirect('gestion:proprietaire_detail', pk=proprietaire_user.pk)
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        user_form = UserUpdateForm(instance=proprietaire_user)
        profile_form = ProprietaireProfileUpdateForm(instance=proprietaire_profil)

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'proprietaire_user': proprietaire_user,
    }
    return render(request, 'gestion/modifier_proprietaire.html', context)

@login_required
def supprimer_proprietaire(request, pk):
    """
    Gère la suppression d'un propriétaire et de toutes ses données associées.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent supprimer des propriétaires.")

    proprietaire_user = get_object_or_404(User, pk=pk, user_type='PR')
    
    # Vérification de sécurité : l'agence connectée gère-t-elle bien ce propriétaire ?
    try:
        if proprietaire_user.proprietaire.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce propriétaire.")
    except (Proprietaire.DoesNotExist, User.agence.RelatedObjectDoesNotExist):
        raise PermissionDenied("Impossible de vérifier les permissions pour ce propriétaire.")

    if request.method == 'POST':
        proprietaire_nom = proprietaire_user.get_full_name()
        # La suppression en cascade (CASCADE) s'occupera des objets liés (Proprietaire, Bien, etc.)
        proprietaire_user.delete()
        messages.success(request, f"Le propriétaire '{proprietaire_nom}' et toutes ses données associées ont été supprimés.")
        return redirect('gestion:tableau_de_bord_agence')

    context = {
        'proprietaire_user': proprietaire_user
    }
    return render(request, 'gestion/proprietaire_confirm_delete.html', context)

@login_required
def gerer_locataires(request):
    """
    Affiche la liste des locataires des biens gérés par l'agence.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent gérer les locataires.")

    try:
        agence_profil = request.user.agence
        # Logique corrigée : récupère tous les locataires directement liés à l'agence.
        locataires = Locataire.objects.filter(agence=agence_profil).order_by('nom', 'prenom')
    except User.agence.RelatedObjectDoesNotExist:
        locataires = Locataire.objects.none()
        messages.error(request, "Votre profil d'agence est incomplet.")

    context = {
        'locataires': locataires
    }
    return render(request, 'gestion/gerer_locataires.html', context)

@login_required
def ajouter_locataire(request):
    """
    Gère l'ajout d'un nouveau locataire par une agence.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent ajouter des locataires.")

    try:
        agence_profil = request.user.agence
    except User.agence.RelatedObjectDoesNotExist:
        messages.error(request, "Action impossible : vous devez d'abord compléter votre profil d'agence.")
        return redirect('gestion:profil')

    if request.method == 'POST':
        form = LocataireForm(request.POST)
        if form.is_valid():
            locataire = form.save(commit=False)
            locataire.agence = agence_profil # Assigne l'agence connectée
            locataire.save()
            messages.success(request, "Le locataire a été ajouté avec succès.")
            return redirect('gestion:gerer_locataires')
    else:
        form = LocataireForm()

    return render(request, 'gestion/ajouter_locataire.html', {'form': form})

@login_required
def locataire_detail(request, pk):
    """
    Affiche les détails d'un locataire spécifique.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent voir les détails des locataires.")

    locataire = get_object_or_404(Locataire, pk=pk)

    # Permission check: Is this tenant managed by the current agency?
    try:
        if locataire.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce locataire.")
    except User.agence.RelatedObjectDoesNotExist:
         raise PermissionDenied("Votre profil d'agence est incomplet.")

    # Get all past and present locations for this tenant
    locations = Location.objects.filter(locataire=locataire).select_related('chambre__immeuble').order_by('-date_entree')

    context = {
        'locataire': locataire,
        'locations': locations,
    }
    return render(request, 'gestion/locataire_detail.html', context)

@login_required
def modifier_locataire(request, pk):
    """
    Gère la modification des informations d'un locataire.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent modifier les locataires.")

    locataire = get_object_or_404(Locataire, pk=pk)

    # Vérification de sécurité : l'agence connectée gère-t-elle bien ce locataire ?
    try:
        if locataire.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce locataire.")
    except User.agence.RelatedObjectDoesNotExist:
        raise PermissionDenied("Votre profil d'agence est incomplet.")

    if request.method == 'POST':
        form = LocataireForm(request.POST, instance=locataire)
        if form.is_valid():
            form.save()
            messages.success(request, f"Les informations du locataire {locataire} ont été mises à jour.")
            return redirect('gestion:locataire_detail', pk=locataire.pk)
    else:
        form = LocataireForm(instance=locataire)

    context = {
        'form': form,
        'locataire': locataire,
    }
    return render(request, 'gestion/modifier_locataire.html', context)

@login_required
def supprimer_locataire(request, pk):
    """
    Gère la suppression d'un locataire.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent supprimer des locataires.")

    locataire = get_object_or_404(Locataire, pk=pk)

    # Vérification de sécurité
    try:
        if locataire.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce locataire.")
    except User.agence.RelatedObjectDoesNotExist:
        raise PermissionDenied("Votre profil d'agence est incomplet.")

    if request.method == 'POST':
        locataire_nom = str(locataire)
        locataire.delete()
        messages.success(request, f"Le locataire '{locataire_nom}' a été supprimé avec succès.")
        return redirect('gestion:gerer_locataires')

    context = {
        'locataire': locataire,
        'is_occupant': locataire.chambres.exists(),
    }
    return render(request, 'gestion/locataire_confirm_delete.html', context)

@login_required
def ajouter_immeuble(request, pk):
    """
    Permet à une agence d'ajouter un immeuble pour un propriétaire spécifique.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent ajouter des immeubles.")

    proprietaire_user = get_object_or_404(User, pk=pk, user_type='PR')
    proprietaire_profil = get_object_or_404(Proprietaire, user=proprietaire_user)
    
    # Vérification de sécurité : l'agence actuelle gère-t-elle ce propriétaire ?
    try:
        if proprietaire_profil.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce propriétaire.")
    except User.agence.RelatedObjectDoesNotExist:
        raise PermissionDenied("Votre profil d'agence est incomplet.")

    if request.method == 'POST':
        form = ImmeubleForm(request.POST)
        if form.is_valid():
            immeuble = form.save(commit=False)
            immeuble.proprietaire = proprietaire_profil
            immeuble.save()
            messages.success(request, f"L'immeuble à l'adresse '{immeuble.addresse}' a été ajouté avec succès.")
            return redirect('gestion:proprietaire_detail', pk=proprietaire_user.pk)
    else:
        form = ImmeubleForm()

    context = {
        'form': form,
        'proprietaire_profil': proprietaire_profil
    }
    return render(request, 'gestion/ajouter_immeuble.html', context)

@login_required
def immeuble_detail(request, pk):
    """
    Affiche les détails d'un immeuble et la liste de ses unités (chambres).
    """
    immeuble = get_object_or_404(Immeuble.objects.select_related('proprietaire__user', 'type_bien'), pk=pk)

    # Vérification de sécurité : l'utilisateur est-il l'agence qui gère ou le propriétaire ?
    is_managing_agence = False
    # Seuls les utilisateurs de type 'AG' peuvent avoir un profil agence
    if request.user.user_type == 'AG':
        try:
            if immeuble.proprietaire.agence == request.user.agence:
                is_managing_agence = True
        except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
            pass # is_managing_agence reste False

    is_owner = (request.user.user_type == 'PR' and immeuble.proprietaire.user == request.user)

    if not (is_managing_agence or is_owner):
        raise PermissionDenied("Vous n'avez pas la permission de voir cet immeuble.")

    chambres = Chambre.objects.filter(immeuble=immeuble).select_related('locataire')

    # --- Calculs pour les statistiques de l'immeuble ---
    total_units = chambres.count()
    occupied_units = chambres.filter(locataire__isnull=False).count()
    
    occupancy_rate = 0
    if total_units > 0:
        occupancy_rate = (occupied_units / total_units) * 100
        
    total_rent = chambres.aggregate(total=Sum('prix_loyer'))['total'] or 0

    context = {
        'immeuble': immeuble,
        'chambres': chambres,
        'occupancy_rate': occupancy_rate,
        'total_rent': total_rent,
    }
    return render(request, 'gestion/immeuble_detail.html', context)

@login_required
def modifier_immeuble(request, pk):
    """
    Permet de modifier les informations d'un immeuble.
    """
    immeuble = get_object_or_404(Immeuble, pk=pk)

    # Vérification de sécurité
    try:
        if request.user.user_type != 'AG' or immeuble.proprietaire.agence != request.user.agence:
            raise PermissionDenied("Vous n'avez pas la permission de modifier cet immeuble.")
    except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
        raise PermissionDenied("Impossible de vérifier les permissions.")

    if request.method == 'POST':
        form = ImmeubleForm(request.POST, instance=immeuble)
        if form.is_valid():
            form.save()
            messages.success(request, "Les informations de l'immeuble ont été mises à jour.")
            return redirect('gestion:immeuble_detail', pk=immeuble.pk)
    else:
        form = ImmeubleForm(instance=immeuble)

    context = {
        'form': form,
        'immeuble': immeuble,
    }
    return render(request, 'gestion/modifier_immeuble.html', context)

@login_required
def supprimer_immeuble(request, pk):
    """
    Permet de supprimer un immeuble et ses unités associées.
    """
    immeuble = get_object_or_404(Immeuble, pk=pk)

    # Vérification de sécurité
    try:
        if request.user.user_type != 'AG' or immeuble.proprietaire.agence != request.user.agence:
            raise PermissionDenied("Vous n'avez pas la permission de supprimer cet immeuble.")
    except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
        raise PermissionDenied("Impossible de vérifier les permissions.")

    if request.method == 'POST':
        proprietaire_pk = immeuble.proprietaire.user.pk
        adresse = immeuble.addresse
        immeuble.delete()
        messages.success(request, f"L'immeuble à l'adresse '{adresse}' a été supprimé.")
        return redirect('gestion:proprietaire_detail', pk=proprietaire_pk)

    context = {
        'immeuble': immeuble
    }
    return render(request, 'gestion/immeuble_confirm_delete.html', context)

@login_required
def ajouter_chambre(request, immeuble_id):
    """
    Permet à une agence d'ajouter une unité (chambre) à un immeuble spécifique.
    """
    immeuble = get_object_or_404(Immeuble, pk=immeuble_id)

    # Vérification de sécurité
    try:
        if request.user.user_type != 'AG' or immeuble.proprietaire.agence != request.user.agence:
            raise PermissionDenied("Vous n'avez pas la permission d'ajouter une unité à cet immeuble.")
    except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
        raise PermissionDenied("Impossible de vérifier les permissions.")

    if request.method == 'POST':
        form = ChambreForm(request.POST)
        if form.is_valid():
            chambre = form.save(commit=False)
            chambre.immeuble = immeuble
            chambre.save()
            messages.success(request, f"L'unité '{chambre.designation}' a été ajoutée avec succès.")
            return redirect('gestion:immeuble_detail', pk=immeuble.pk)
    else:
        form = ChambreForm()

    context = {
        'form': form,
        'immeuble': immeuble
    }
    return render(request, 'gestion/ajouter_chambre.html', context)

@login_required
def modifier_chambre(request, pk):
    """
    Permet de modifier les informations d'une unité locative.
    """
    chambre = get_object_or_404(Chambre, pk=pk)
    immeuble = chambre.immeuble

    # Vérification de sécurité
    try:
        if request.user.user_type != 'AG' or immeuble.proprietaire.agence != request.user.agence:
            raise PermissionDenied("Vous n'avez pas la permission de modifier cette unité.")
    except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
        raise PermissionDenied("Impossible de vérifier les permissions.")

    if request.method == 'POST':
        form = ChambreForm(request.POST, instance=chambre)
        if form.is_valid():
            form.save()
            messages.success(request, f"L'unité '{chambre.designation}' a été mise à jour avec succès.")
            return redirect('gestion:immeuble_detail', pk=immeuble.pk)
    else:
        form = ChambreForm(instance=chambre)

    context = {
        'form': form,
        'chambre': chambre,
    }
    return render(request, 'gestion/modifier_chambre.html', context)

@login_required
def supprimer_chambre(request, pk):
    """
    Permet de supprimer une unité locative.
    """
    chambre = get_object_or_404(Chambre, pk=pk)
    immeuble = chambre.immeuble

    # Vérification de sécurité
    try:
        if request.user.user_type != 'AG' or immeuble.proprietaire.agence != request.user.agence:
            raise PermissionDenied("Vous n'avez pas la permission de supprimer cette unité.")
    except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
        raise PermissionDenied("Impossible de vérifier les permissions.")

    if request.method == 'POST':
        designation = chambre.designation
        chambre.delete()
        messages.success(request, f"L'unité '{designation}' a été supprimée avec succès.")
        return redirect('gestion:immeuble_detail', pk=immeuble.pk)

    context = {
        'chambre': chambre
    }
    return render(request, 'gestion/chambre_confirm_delete.html', context)

@login_required
def chambre_detail(request, pk):
    """
    Affiche les détails d'une chambre et permet d'assigner un locataire.
    """
    chambre = get_object_or_404(Chambre.objects.select_related('immeuble__proprietaire', 'locataire'), pk=pk)

    # Vérification de permission : l'utilisateur est-il l'agence qui gère ou le propriétaire ?
    is_managing_agence = False
    if request.user.user_type == 'AG':
        try:
            if chambre.immeuble.proprietaire.agence == request.user.agence:
                is_managing_agence = True
        except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
            pass

    is_owner = (request.user.user_type == 'PR' and chambre.immeuble.proprietaire.user == request.user)

    if not (is_managing_agence or is_owner):
        raise PermissionDenied("Vous n'avez pas la permission de voir cette unité.")

    # --- Récupération des données liées à la location active ---
    location_active = Location.objects.filter(chambre=chambre, date_sortie__isnull=True).first()
    etats_des_lieux = EtatDesLieux.objects.none()
    if location_active:
        etats_des_lieux = location_active.etats_des_lieux.all()

    # --- Initialisation des formulaires ---
    location_form = None
    etat_des_lieux_form = None

    if request.method == 'POST':
        if not is_managing_agence:
            raise PermissionDenied("Seule l'agence peut effectuer cette action.")

        # Gère l'assignation d'un nouveau locataire
        if 'submit_location' in request.POST:
            if chambre.locataire is not None:
                messages.error(request, "Cette chambre est déjà occupée.")
                return redirect('gestion:chambre_detail', pk=pk)

            location_form = LocationForm(request.POST, agence=request.user.agence)
            if location_form.is_valid():
                with transaction.atomic():
                    location = location_form.save(commit=False)
                    location.chambre = chambre
                    location.save()
                    chambre.locataire = location.locataire
                    chambre.save()
                messages.success(request, f"Le locataire {chambre.locataire} a été assigné à la chambre {chambre.designation}.")
                return redirect('gestion:chambre_detail', pk=pk)

        # Gère l'ajout d'un état des lieux
        elif 'submit_etat_des_lieux' in request.POST:
            if not location_active:
                messages.error(request, "Aucune location active pour ajouter un état des lieux.")
                return redirect('gestion:chambre_detail', pk=pk)
            
            etat_des_lieux_form = EtatDesLieuxForm(request.POST, request.FILES)
            if etat_des_lieux_form.is_valid():
                try:
                    etat = etat_des_lieux_form.save(commit=False)
                    etat.location = location_active
                    etat.save()
                    messages.success(request, "L'état des lieux a été ajouté avec succès.")
                    return redirect('gestion:chambre_detail', pk=pk)
                except IntegrityError:
                    messages.error(request, f"Un état des lieux de ce type existe déjà pour cette location.")

    else: # GET request
        if is_managing_agence:
            if chambre.locataire is None:
                location_form = LocationForm(agence=request.user.agence)
            if location_active:
                etat_des_lieux_form = EtatDesLieuxForm()

    # --- Construction de l'historique complet des paiements (payés et arriérés) ---
    payment_history = []
    if chambre.locataire:
        if location_active:
            # Récupérer tous les paiements validés et les mapper par mois pour un accès rapide
            paid_payments = {
                p.mois_couvert: p 
                for p in Paiement.objects.filter(location=location_active, est_valide=True).order_by('date_paiement')
            }
            
            # Définir la locale en français pour générer les noms de mois correctement
            try:
                locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
            except locale.Error:
                locale.setlocale(locale.LC_TIME, '') # Fallback sur la locale système

            # Itérer du début de la location jusqu'au mois actuel
            cursor_date = location_active.date_entree
            end_date = timezone.now().date()

            while cursor_date.year < end_date.year or (cursor_date.year == end_date.year and cursor_date.month <= end_date.month):
                month_str = cursor_date.strftime('%B %Y').capitalize()
                payment_obj = paid_payments.get(month_str)
                
                if payment_obj:
                    payment_history.append({'month': month_str, 'status': 'paid', 'payment': payment_obj})
                else:
                    payment_history.append({'month': month_str, 'status': 'unpaid', 'payment': None})
                
                cursor_date += relativedelta(months=1)
            
            # Inverser la liste pour afficher les mois les plus récents en premier
            payment_history.reverse()

    context = {
        'chambre': chambre,
        'location_form': location_form,
        'etat_des_lieux_form': etat_des_lieux_form,
        'etats_des_lieux': etats_des_lieux,
        'location_active': location_active,
        'payment_history': payment_history,
    }
    return render(request, 'gestion/chambre_detail.html', context)

@login_required
def modifier_etat_des_lieux(request, pk):
    """
    Gère la modification d'un état des lieux existant.
    """
    etat = get_object_or_404(EtatDesLieux, pk=pk)
    chambre = etat.location.chambre

    # Vérification de sécurité : Seule l'agence peut modifier.
    is_managing_agence = False
    if request.user.user_type == 'AG':
        try:
            if chambre.immeuble.proprietaire.agence == request.user.agence:
                is_managing_agence = True
        except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
            pass

    if not is_managing_agence:
        raise PermissionDenied("Seules les agences peuvent modifier un état des lieux.")

    if request.method == 'POST':
        form = EtatDesLieuxForm(request.POST, request.FILES, instance=etat)
        if form.is_valid():
            form.save()
            messages.success(request, "L'état des lieux a été mis à jour avec succès.")
            return redirect('gestion:chambre_detail', pk=chambre.pk)
    else:
        form = EtatDesLieuxForm(instance=etat)

    context = {
        'form': form,
        'etat': etat,
        'chambre': chambre,
    }
    return render(request, 'gestion/modifier_etat_des_lieux.html', context)

@login_required
def supprimer_etat_des_lieux(request, pk):
    """
    Gère la suppression d'un état des lieux.
    """
    etat = get_object_or_404(EtatDesLieux, pk=pk)
    chambre = etat.location.chambre

    # Vérification de sécurité : Seule l'agence peut supprimer.
    is_managing_agence = False
    if request.user.user_type == 'AG':
        try:
            if chambre.immeuble.proprietaire.agence == request.user.agence:
                is_managing_agence = True
        except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
            pass

    if not is_managing_agence:
        raise PermissionDenied("Seules les agences peuvent supprimer un état des lieux.")

    if request.method == 'POST':
        etat.delete()
        messages.success(request, "L'état des lieux a été supprimé avec succès.")
        return redirect('gestion:chambre_detail', pk=chambre.pk)

    context = {
        'etat': etat,
        'chambre': chambre,
    }
    return render(request, 'gestion/etat_des_lieux_confirm_delete.html', context)

@login_required
def liberer_chambre(request, pk):
    """
    Libère une unité en retirant le locataire et en marquant la date de sortie.
    """
    chambre = get_object_or_404(Chambre, pk=pk)

    # Vérification de sécurité : Seule l'agence peut libérer une chambre.
    is_managing_agence = False
    if request.user.user_type == 'AG':
        try:
            if chambre.immeuble.proprietaire.agence == request.user.agence:
                is_managing_agence = True
        except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
            pass

    if not is_managing_agence:
        raise PermissionDenied("Seules les agences peuvent libérer une unité.")

    if request.method == 'POST':
        if chambre.locataire:
            locataire_nom = str(chambre.locataire)
            
            with transaction.atomic():
                # Trouve la location active et définit la date de sortie
                location = Location.objects.filter(chambre=chambre, locataire=chambre.locataire, date_sortie__isnull=True).first()
                if location:
                    location.date_sortie = timezone.now().date()
                    location.save()
                
                # Libère la chambre
                chambre.locataire = None
                chambre.save()
            
            messages.info(request, f"L'unité est maintenant libre. L'ancien locataire, {locataire_nom}, a été retiré.")
        else:
            messages.warning(request, "Cette unité est déjà libre.")
    
    return redirect('gestion:chambre_detail', pk=chambre.pk)

@login_required
def ajouter_paiement(request, chambre_id):
    """
    Gère l'ajout d'un paiement pour une location active.
    """
    chambre = get_object_or_404(Chambre, pk=chambre_id)

    # Vérification de sécurité : Seule l'agence peut ajouter un paiement.
    is_managing_agence = False
    if request.user.user_type == 'AG':
        try:
            if chambre.immeuble.proprietaire.agence == request.user.agence:
                is_managing_agence = True
        except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
            pass

    if not is_managing_agence:
        raise PermissionDenied("Seules les agences peuvent ajouter un paiement.")


    # Trouver la location active pour cette chambre
    location = Location.objects.filter(chambre=chambre, date_sortie__isnull=True).first()
    if not location:
        messages.error(request, "Aucune location active trouvée pour cette unité. Impossible d'ajouter un paiement.")
        return redirect('gestion:chambre_detail', pk=chambre.pk)

    if request.method == 'POST':
        form = PaiementForm(request.POST)
        if form.is_valid():
            # Vérification pour éviter les doublons
            mois_couvert = form.cleaned_data['mois_couvert']
            if Paiement.objects.filter(location=location, mois_couvert=mois_couvert).exists():
                messages.error(request, f"Un paiement pour le mois de '{mois_couvert}' existe déjà pour cette location.")
            else:
                paiement = form.save(commit=False)
                paiement.location = location
                paiement.save()
                messages.success(request, f"Le paiement de {paiement.montant} Frcfa a été enregistré avec succès.")
                return redirect('gestion:chambre_detail', pk=chambre.pk)
    else:
        # Pré-remplir le formulaire pour plus de commodité
        # Utilise le paramètre 'mois' de l'URL s'il est fourni (pour les arriérés)
        initial_data = {
            'montant': chambre.prix_loyer,
            'date_paiement': timezone.now().date(),
            'mois_couvert': request.GET.get('mois', timezone.now().strftime('%B %Y')),
        }
        form = PaiementForm(initial=initial_data)

    context = {
        'form': form,
        'chambre': chambre,
        'location': location,
    }
    return render(request, 'gestion/ajouter_paiement.html', context)

@login_required
def modifier_paiement(request, pk):
    """
    Gère la modification d'un paiement existant.
    """
    paiement = get_object_or_404(Paiement, pk=pk)
    chambre = paiement.location.chambre

    # Vérification de sécurité : Seule l'agence peut modifier un paiement.
    is_managing_agence = False
    if request.user.user_type == 'AG':
        try:
            if chambre.immeuble.proprietaire.agence == request.user.agence:
                is_managing_agence = True
        except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
            pass

    if not is_managing_agence:
        raise PermissionDenied("Seules les agences peuvent modifier un paiement.")

    if request.method == 'POST':
        form = PaiementForm(request.POST, instance=paiement)
        if form.is_valid():
            form.save()
            messages.success(request, "Le paiement a été mis à jour avec succès.")
            return redirect('gestion:chambre_detail', pk=chambre.pk)
    else:
        form = PaiementForm(instance=paiement)

    context = {
        'form': form,
        'paiement': paiement,
        'chambre': chambre,
    }
    return render(request, 'gestion/modifier_paiement.html', context)

@login_required
def supprimer_paiement(request, pk):
    """
    Gère la suppression d'un paiement.
    """
    paiement = get_object_or_404(Paiement, pk=pk)
    chambre = paiement.location.chambre

    # Vérification de sécurité : Seule l'agence peut supprimer un paiement.
    is_managing_agence = False
    if request.user.user_type == 'AG':
        try:
            if chambre.immeuble.proprietaire.agence == request.user.agence:
                is_managing_agence = True
        except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
            pass

    if not is_managing_agence:
        raise PermissionDenied("Seules les agences peuvent supprimer un paiement.")

    if request.method == 'POST':
        paiement.delete()
        messages.success(request, "Le paiement a été supprimé avec succès.")
        return redirect('gestion:chambre_detail', pk=chambre.pk)

    context = {
        'paiement': paiement,
        'chambre': chambre,
    }
    return render(request, 'gestion/paiement_confirm_delete.html', context)

@login_required
def exporter_paiements_csv(request):
    """
    Exporte la liste de tous les paiements gérés par l'agence en fichier CSV.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent exporter des données.")

    # Créer la réponse HTTP avec l'en-tête CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="export_paiements.csv"'
    # Ajout du BOM pour une meilleure compatibilité avec Excel
    response.write(u'\ufeff'.encode('utf8'))

    writer = csv.writer(response, delimiter=';')
    # Écrire l'en-tête du fichier CSV
    writer.writerow([
        'Date de Paiement',
        'Montant (Frcfa)',
        'Locataire',
        'Immeuble',
        'Unité (Chambre)',
        'Mois Couvert',
        'Statut',
        'Moyen de Paiement'
    ])

    # Récupérer les paiements à exporter
    try:
        agence_profil = request.user.agence
        paiements = Paiement.objects.filter(
            location__chambre__immeuble__proprietaire__agence=agence_profil
        ).select_related(
            'location__chambre__immeuble',
            'location__locataire',
            'moyen_paiement'
        ).order_by('-date_paiement')

        for paiement in paiements:
            writer.writerow([
                paiement.date_paiement.strftime('%d/%m/%Y'),
                paiement.montant,
                str(paiement.location.locataire),
                paiement.location.chambre.immeuble.addresse.replace('\n', ' ').replace('\r', ''),
                str(paiement.location.chambre.designation),
                paiement.mois_couvert,
                "Validé" if paiement.est_valide else "En attente",
                str(paiement.moyen_paiement)
            ])
    except CustomUser.agence.RelatedObjectDoesNotExist:
        pass # Si l'agence n'a pas de profil, ne rien faire.

    return response

@login_required
def gerer_moyens_paiement(request):
    """
    Affiche la liste des moyens de paiement et permet d'en ajouter.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seule une agence peut gérer les moyens de paiement.")

    if request.method == 'POST':
        form = MoyenPaiementForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Le nouveau moyen de paiement a été ajouté.")
                return redirect('gestion:gerer_moyens_paiement')
            except IntegrityError: # Gère le cas où le choix existe déjà (unique=True)
                messages.error(request, "Ce moyen de paiement existe déjà.")
    else:
        form = MoyenPaiementForm()

    moyens_paiement = MoyenPaiement.objects.all()
    context = {
        'form': form,
        'moyens_paiement': moyens_paiement,
    }
    return render(request, 'gestion/gerer_moyens_paiement.html', context)

@login_required
def supprimer_moyen_paiement(request, pk):
    """
    Supprime un moyen de paiement.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seule une agence peut gérer les moyens de paiement.")
    
    moyen = get_object_or_404(MoyenPaiement, pk=pk)
    
    # Vérifie si le moyen de paiement est utilisé avant de le supprimer (à cause de on_delete=PROTECT)
    if Paiement.objects.filter(moyen_paiement=moyen).exists() or Location.objects.filter(moyen_paiement=moyen).exists():
        messages.error(request, f"Impossible de supprimer '{moyen.get_designation_display()}' car il est utilisé dans des paiements ou des locations existantes.")
    elif request.method == 'POST':
        designation = moyen.get_designation_display()
        moyen.delete()
        messages.success(request, f"Le moyen de paiement '{designation}' a été supprimé.")
    
    return redirect('gestion:gerer_moyens_paiement')

@login_required
def generer_quittance_pdf(request, pk):
    """
    Génère une quittance de loyer en PDF pour un paiement validé.
    """
    if HTML is None:
        return HttpResponse("La bibliothèque WeasyPrint est requise pour générer des PDF. Veuillez l'installer avec 'pip install WeasyPrint'.", status=501)

    paiement = get_object_or_404(Paiement, pk=pk)
    
    # Vérifications de sécurité et de logique
    if not paiement.est_valide:
        messages.error(request, "Une quittance ne peut être générée que pour un paiement validé.")
        return redirect('gestion:chambre_detail', pk=paiement.location.chambre.pk)

    # Vérification de sécurité : Seule l'agence peut générer une quittance.
    is_managing_agence = False
    agence = None
    if request.user.user_type == 'AG':
        try:
            agence = request.user.agence
            if paiement.location.chambre.immeuble.proprietaire.agence == agence:
                is_managing_agence = True
        except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
            pass
    if not is_managing_agence:
        raise PermissionDenied("Seules les agences peuvent générer une quittance.")
    # Rassembler toutes les informations nécessaires pour la quittance
    context = {
        'paiement': paiement,
        'location': paiement.location,
        'chambre': paiement.location.chambre,
        'locataire': paiement.location.locataire,
        'immeuble': paiement.location.chambre.immeuble,
        'proprietaire': paiement.location.chambre.immeuble.proprietaire,
        'agence': agence,
        'date_generation': timezone.now().date(),
    }

    # Rendre le template HTML en une chaîne de caractères
    html_string = render_to_string('gestion/quittance_pdf.html', context)

    # Générer le PDF
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    # Créer la réponse HTTP
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="quittance_{paiement.mois_couvert.replace(" ", "_")}_{paiement.location.locataire}.pdf"'

    return response

@login_required
def notification_list(request):
    """
    Affiche toutes les notifications pour l'agence connectée et les marque comme lues.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seuls les utilisateurs de type agence peuvent voir les notifications.")

    try:
        agence = request.user.agence
        # On récupère toutes les notifications pour l'agence
        all_notifications = Notification.objects.filter(agence=agence)

        # Pagination
        paginator = Paginator(all_notifications, 15) # 15 notifications par page
        page_number = request.GET.get('page')
        notifications_page = paginator.get_page(page_number)

        # On marque toutes les notifications non lues comme lues
        Notification.objects.filter(agence=agence, is_read=False).update(is_read=True)

    except Agence.DoesNotExist:
        notifications_page = None
        messages.warning(request, "Votre profil d'agence est incomplet.")

    context = {
        'notifications_page': notifications_page,
    }
    return render(request, 'gestion/notification_list.html', context)

@login_required
def rapport_financier(request):
    """
    Génère un rapport financier sur les loyers attendus, payés, impayés et les commissions,
    filtrable par propriétaire et par mois.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seuls les utilisateurs de type agence peuvent accéder à ce rapport.")

    try:
        agence = request.user.agence
    except Agence.DoesNotExist:
        messages.error(request, "Votre profil d'agence est incomplet.")
        return redirect('gestion:profil')

    # --- Gestion des filtres ---
    proprietaires_agence = Proprietaire.objects.filter(agence=agence).select_related('user').order_by('user__last_name')
    selected_owner_id = request.GET.get('proprietaire_id')
    selected_month_str = request.GET.get('mois', datetime.now().strftime('%Y-%m'))

    try:
        selected_month_date = datetime.strptime(selected_month_str, '%Y-%m')
    except ValueError:
        selected_month_date = datetime.now()
        selected_month_str = selected_month_date.strftime('%Y-%m')

    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')
    mois_couvert_str = selected_month_date.strftime('%B %Y').capitalize()

    proprietaires_a_traiter = proprietaires_agence
    if selected_owner_id and selected_owner_id.isdigit():
        proprietaires_a_traiter = proprietaires_a_traiter.filter(pk=selected_owner_id)

    # --- Calcul des données ---
    report_details = []
    grand_total_attendu = Decimal('0.00')
    grand_total_paye = Decimal('0.00')

    for proprietaire in proprietaires_a_traiter:
        owner_total_attendu = Decimal('0.00')
        owner_total_paye = Decimal('0.00')
        immeubles_data = []

        immeubles = Immeuble.objects.filter(proprietaire=proprietaire)
        for immeuble in immeubles:
            chambres = Chambre.objects.filter(immeuble=immeuble)
            loyer_attendu_immeuble = chambres.filter(locataire__isnull=False).aggregate(total=Sum('prix_loyer'))['total'] or Decimal('0.00')
            loyer_paye_immeuble = Paiement.objects.filter(
                location__chambre__in=chambres,
                mois_couvert=mois_couvert_str,
                est_valide=True
            ).aggregate(total=Sum('montant'))['total'] or Decimal('0.00')

            immeubles_data.append({
                'immeuble': immeuble, 'total_attendu': loyer_attendu_immeuble,
                'total_paye': loyer_paye_immeuble, 'total_impaye': loyer_attendu_immeuble - loyer_paye_immeuble,
            })
            owner_total_attendu += loyer_attendu_immeuble
            owner_total_paye += loyer_paye_immeuble

        commission = owner_total_paye * (proprietaire.taux_commission / Decimal('100.0'))
        report_details.append({
            'proprietaire': proprietaire,
            'immeubles_data': immeubles_data,
            'owner_total_attendu': owner_total_attendu,
            'owner_total_paye': owner_total_paye,
            'owner_total_impaye': owner_total_attendu - owner_total_paye,
            'commission': commission,
        })
        grand_total_attendu += owner_total_attendu
        grand_total_paye += owner_total_paye

    grand_total_impaye = grand_total_attendu - grand_total_paye
    grand_total_commission = sum(item['commission'] for item in report_details)

    context = {
        'report_details': report_details,
        'proprietaires_agence': proprietaires_agence,
        'selected_owner_id': int(selected_owner_id) if selected_owner_id and selected_owner_id.isdigit() else None,
        'selected_month_str': selected_month_str,
        'mois_couvert_str': mois_couvert_str,
        'grand_total_attendu': grand_total_attendu,
        'grand_total_paye': grand_total_paye,
        'grand_total_impaye': grand_total_impaye,
        'grand_total_commission': grand_total_commission,
        'page_title': 'Rapport Financier Mensuel',
    }
    return render(request, 'gestion/rapport_financier.html', context)

@login_required
def generer_rapport_financier_pdf(request):
    """
    Génère le rapport financier en PDF.
    Reprend la logique de la vue `rapport_financier`.
    """
    if HTML is None:
        return HttpResponse("La bibliothèque WeasyPrint est requise pour générer des PDF. Veuillez l'installer avec 'pip install WeasyPrint'.", status=501)

    if request.user.user_type != 'AG':
        raise PermissionDenied("Seuls les utilisateurs de type agence peuvent accéder à ce rapport.")

    try:
        agence = request.user.agence
    except Agence.DoesNotExist:
        messages.error(request, "Votre profil d'agence est incomplet.")
        return redirect('gestion:profil')

    # --- Reprise de la logique de filtrage et de calcul de `rapport_financier` ---
    proprietaires_agence = Proprietaire.objects.filter(agence=agence).select_related('user').order_by('user__last_name')
    selected_owner_id = request.GET.get('proprietaire_id')
    selected_month_str = request.GET.get('mois', datetime.now().strftime('%Y-%m'))

    try:
        selected_month_date = datetime.strptime(selected_month_str, '%Y-%m')
    except ValueError:
        selected_month_date = datetime.now()
        selected_month_str = selected_month_date.strftime('%Y-%m')

    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')
    mois_couvert_str = selected_month_date.strftime('%B %Y').capitalize()

    proprietaires_a_traiter = proprietaires_agence
    proprietaire_filtre = None
    if selected_owner_id and selected_owner_id.isdigit():
        proprietaires_a_traiter = proprietaires_a_traiter.filter(pk=selected_owner_id)
        proprietaire_filtre = proprietaires_agence.filter(pk=selected_owner_id).first()

    report_details = []
    grand_total_attendu = Decimal('0.00')
    grand_total_paye = Decimal('0.00')

    for proprietaire in proprietaires_a_traiter:
        # ... (La logique de calcul est identique à la vue rapport_financier) ...
        owner_total_attendu = Decimal('0.00')
        owner_total_paye = Decimal('0.00')
        immeubles_data = []

        immeubles = Immeuble.objects.filter(proprietaire=proprietaire)
        for immeuble in immeubles:
            chambres = Chambre.objects.filter(immeuble=immeuble)
            loyer_attendu_immeuble = chambres.filter(locataire__isnull=False).aggregate(total=Sum('prix_loyer'))['total'] or Decimal('0.00')
            loyer_paye_immeuble = Paiement.objects.filter(location__chambre__in=chambres, mois_couvert=mois_couvert_str, est_valide=True).aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
            immeubles_data.append({'immeuble': immeuble, 'total_attendu': loyer_attendu_immeuble, 'total_paye': loyer_paye_immeuble, 'total_impaye': loyer_attendu_immeuble - loyer_paye_immeuble})
            owner_total_attendu += loyer_attendu_immeuble
            owner_total_paye += loyer_paye_immeuble

        commission = owner_total_paye * (proprietaire.taux_commission / Decimal('100.0'))
        report_details.append({'proprietaire': proprietaire, 'immeubles_data': immeubles_data, 'owner_total_attendu': owner_total_attendu, 'owner_total_paye': owner_total_paye, 'owner_total_impaye': owner_total_attendu - owner_total_paye, 'commission': commission})
        grand_total_attendu += owner_total_attendu
        grand_total_paye += owner_total_paye

    grand_total_impaye = grand_total_attendu - grand_total_paye
    grand_total_commission = sum(item['commission'] for item in report_details)

    context = {
        'report_details': report_details, 'mois_couvert_str': mois_couvert_str, 'proprietaire_filtre': proprietaire_filtre,
        'grand_total_attendu': grand_total_attendu, 'grand_total_paye': grand_total_paye, 'grand_total_impaye': grand_total_impaye,
        'grand_total_commission': grand_total_commission, 'agence': agence, 'date_generation': timezone.now().date(),
    }

    html_string = render_to_string('gestion/rapport_financier_pdf.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="rapport_financier_{selected_month_str}.pdf"'
    return response
