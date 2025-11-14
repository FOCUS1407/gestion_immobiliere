from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.views import PasswordChangeDoneView
from django.contrib.auth import get_user_model, models as auth_models
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import transaction, IntegrityError, models
from django.db.models import Sum, Count, Q, F, DecimalField, OuterRef, Exists
from django.db.models.functions import Coalesce
from django.db.models.functions import TruncMonth
from django.template.loader import render_to_string
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.http import HttpResponse
from datetime import datetime, timedelta
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from .models import Locataire # Assurez-vous d'importer vos modèles
import locale
import string
import random
from django.urls import reverse
import csv
from gestion.forms import AgenceProfileForm, AgenceRegistrationForm, ChambreForm, ConnexionForm, EtatDesLieuxForm, ImmeubleForm, LocataireForm, LocationForm, MoyenPaiementForm, PaiementForm, ProprietaireCreationForm, ProprietaireProfileUpdateForm, UserUpdateForm
from gestion.models import Agence, CustomUser, EtatDesLieux, Locataire, Location, MoyenPaiement, Notification, Paiement, Proprietaire, Immeuble,Chambre

try:
    from weasyprint import HTML
except ImportError:
    HTML = None # Gère le cas où WeasyPrint n'est pas installé

from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

User = get_user_model()

def health_check(request):
    """
    Vue dédiée pour les vérifications de santé (health checks).
    Renvoie une réponse simple avec un statut 200 OK.
    """
    return HttpResponse("OK", status=200)

def accueil(request):
    """
    Vue pour la page d'accueil.
    - Répond avec un statut 200 OK pour les vérifications de santé (health checks).
    - Redirige les utilisateurs authentifiés ou non vers la page de connexion.
    """
    # Si la requête est une vérification de santé (souvent avec un User-Agent spécifique),
    # Pour tous les visiteurs, on redirige simplement vers la page de connexion.
    return redirect('gestion:connexion')

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
        form = ConnexionForm(request, data=request.POST)
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
        form = ConnexionForm()
    return render(request, 'gestion/connexion.html', {'form': form})

def logout_view(request):
    """
    Déconnecte l'utilisateur.
    """
    logout(request)
    messages.info(request, "Vous avez été déconnecté avec succès.")
    return redirect('gestion:accueil')

@transaction.atomic # Assure que la création de l'utilisateur et de l'agence se fait en une seule fois
def register_view(request):
    """
    Gère l'inscription des nouvelles agences avec un formulaire simplifié.
    Le nom d'utilisateur est généré automatiquement à partir de l'email.
    """
    if request.user.is_authenticated:
        if request.user.user_type == 'AG':
            return redirect('gestion:tableau_de_bord_agence')
        return redirect('gestion:tableau_de_bord_proprietaire')

    if request.method == 'POST':
        form = AgenceRegistrationForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save(commit=False)
                
                # --- Génération automatique du nom d'utilisateur ---
                # On utilise l'email comme nom d'utilisateur, car il est unique.
                user.username = form.cleaned_data['email']
                
                user.user_type = CustomUser.AGENCE
                user.set_password(form.cleaned_data['password'])
                user.save()

                Agence.objects.create(user=user)

            messages.success(request, "Votre compte agence a été créé avec succès !")

            # --- Envoi de l'email de bienvenue ---
            try:
                subject = render_to_string('gestion/email/welcome_user_subject.txt').strip()
                login_url = request.build_absolute_uri(reverse('gestion:connexion'))
                
                email_context = { 'user': user, 'login_url': login_url }
                html_body = render_to_string('gestion/email/welcome_user_body.html', email_context)

                send_mail(
                    subject=subject, message='', from_email=None,
                    recipient_list=[user.email], html_message=html_body,
                    fail_silently=False,
                )
            except Exception as email_error:
                messages.warning(request, f"Votre compte a été créé, mais l'envoi de l'email de bienvenue a échoué : {email_error}")

            login(request, user)
            return redirect('gestion:tableau_de_bord_agence')
    else:
        form = AgenceRegistrationForm()
    
    return render(request, 'gestion/register.html', {'form': form})


def terms_of_service_view(request):
    """Affiche la page des conditions d'utilisation."""
    return render(request, 'gestion/terms_of_service.html')

def privacy_policy_view(request):
    """Affiche la page de la politique de confidentialité."""
    return render(request, 'gestion/privacy_policy.html')

def _get_financial_summary(agence_profil, month_str):
    """Calcule le résumé financier pour un mois donné en optimisant les requêtes."""
    if not agence_profil:
        return {
            'total_attendu': Decimal('0.00'),
            'total_paye': Decimal('0.00'),
            'commission': Decimal('0.00'),
        }

    # Loyer total attendu pour les chambres occupées (1 requête)
    # AMÉLIORATION : Se baser sur les locations actives pour le loyer attendu
    total_attendu = Location.objects.filter(
        chambre__immeuble__proprietaire__agence=agence_profil,
        date_sortie__isnull=True # Location active
    ).select_related('chambre').aggregate(
        # Sum sur le prix_loyer de la chambre liée à la location active
        # Coalesce pour gérer le cas où il n'y a pas de locations actives
        total=Coalesce(Sum('chambre__prix_loyer'), Decimal('0.00'))
    )['total']

    # Paiements validés et commission pour le mois en cours (1 requête)
    paiements_summary = Paiement.objects.filter(
        location__chambre__immeuble__proprietaire__agence=agence_profil,
        mois_couvert=month_str,
        est_valide=True
    ).aggregate(
        total_paye=Coalesce(Sum('montant'), Decimal('0.00')),
        total_commission=Coalesce(Sum(
            F('montant') * F('location__chambre__immeuble__proprietaire__taux_commission') / Decimal('100.0'),
            output_field=DecimalField()
        ), Decimal('0.00'))
    )

    return {
        'total_attendu': total_attendu,
        'total_paye': paiements_summary['total_paye'],
        'commission': paiements_summary['total_commission'],
    }

def _get_occupancy_stats(agence_profil):
    """Calcule les statistiques d'occupation pour l'agence en une seule requête, en utilisant la source de vérité (Location)."""
    if not agence_profil:
        return {
            'total_units': 0,
            'occupied_units': 0,
            'free_units': 0,
            'occupancy_rate': 0,
        }

    # Utilise une seule requête d'agrégation pour plus d'efficacité
    # La logique est maintenant cohérente avec le filtrage du tableau de bord.
    stats = Chambre.objects.filter(
        immeuble__proprietaire__agence=agence_profil
    ).aggregate(
        total_units=Count('id', distinct=True),
        occupied_units=Count('id', filter=Q(locations__date_sortie__isnull=True), distinct=True)
    )
    
    total_units = stats.get('total_units', 0)
    occupied_units = stats.get('occupied_units', 0)
    free_units = total_units - occupied_units

    occupancy_rate = (occupied_units / total_units) * 100 if total_units > 0 else 0

    return {
        'total_units': total_units,
        'occupied_units': occupied_units,
        'free_units': free_units,
        'occupancy_rate': occupancy_rate,
    }

def _get_financial_report_context(agence, selected_owner_id, selected_month_str):
    """
    Fonction d'aide UNIQUE pour calculer les données du rapport financier.
    Calcule les totaux par immeuble et les agrège par propriétaire.
    Utilisée par le tableau de bord et le rapport détaillé.
    """
    try:
        selected_month_date = datetime.strptime(selected_month_str, '%Y-%m')
    except (ValueError, TypeError):
        selected_month_date = datetime.now()

    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')
    mois_couvert_str = selected_month_date.strftime('%B %Y').capitalize()

    # --- Récupération des données (Optimisée) ---
    proprietaires_qs = Proprietaire.objects.filter(agence=agence).select_related('user')
    proprietaire_filtre = None
    if selected_owner_id and selected_owner_id.isdigit():
        proprietaires_qs = proprietaires_qs.filter(pk=selected_owner_id)
        proprietaire_filtre = proprietaires_qs.first()

    # 1. Obtenir tous les loyers attendus pour les propriétaires concernés, groupés par immeuble
    # AMÉLIORATION : Utiliser les locations actives comme source de vérité pour le loyer attendu.
    expected_rents = Location.objects.filter(
        chambre__immeuble__proprietaire__in=proprietaires_qs,
        date_sortie__isnull=True  # Uniquement les locations actives
    ).values(
        'chambre__immeuble_id'  # Grouper par immeuble
    ).annotate(total=Sum('chambre__prix_loyer'))
    expected_by_immeuble = {item['chambre__immeuble_id']: item['total'] for item in expected_rents}

    # 2. Obtenir tous les loyers payés pour les propriétaires concernés pour le mois sélectionné, groupés par immeuble
    paid_rents = Paiement.objects.filter(
        location__chambre__immeuble__proprietaire__in=proprietaires_qs,
        mois_couvert=mois_couvert_str,
        est_valide=True
    ).values('location__chambre__immeuble_id').annotate(total=Sum('montant'))
    paid_by_immeuble = {item['location__chambre__immeuble_id']: item['total'] for item in paid_rents}

    # 3. Obtenir tous les immeubles pour les propriétaires concernés pour les grouper
    all_immeubles = Immeuble.objects.filter(proprietaire__in=proprietaires_qs).select_related('proprietaire')

    # --- Traitement des données ---
    report_details = []
    grand_total_attendu = Decimal('0.00')
    grand_total_paye = Decimal('0.00')

    # Grouper les immeubles par propriétaire pour structurer le rapport
    immeubles_by_owner = {}
    for immeuble in all_immeubles:
        immeubles_by_owner.setdefault(immeuble.proprietaire, []).append(immeuble)

    for proprietaire, immeubles_list in immeubles_by_owner.items():
        owner_total_attendu = Decimal('0.00')
        owner_total_paye = Decimal('0.00')
        immeubles_data = []

        for immeuble in immeubles_list:
            loyer_attendu_immeuble = expected_by_immeuble.get(immeuble.id, Decimal('0.00'))
            loyer_paye_immeuble = paid_by_immeuble.get(immeuble.id, Decimal('0.00'))

            immeubles_data.append({
                'immeuble': immeuble, 'total_attendu': loyer_attendu_immeuble,
                'total_paye': loyer_paye_immeuble, 'total_impaye': loyer_attendu_immeuble - loyer_paye_immeuble,
            })
            owner_total_attendu += loyer_attendu_immeuble
            owner_total_paye += loyer_paye_immeuble

        commission = owner_total_paye * (proprietaire.taux_commission / Decimal('100.0'))
        report_details.append({
            'proprietaire': proprietaire,
            'immeubles_data': immeubles_data, # Pour le rapport détaillé
            'owner_total_attendu': owner_total_attendu, # Pour le tableau de bord
            'owner_total_paye': owner_total_paye, # Pour le tableau de bord
            'owner_total_impaye': owner_total_attendu - owner_total_paye, # Pour le tableau de bord
            'commission': commission, # Pour le tableau de bord
        })
        grand_total_attendu += owner_total_attendu
        grand_total_paye += owner_total_paye

    grand_total_impaye = grand_total_attendu - grand_total_paye
    grand_total_commission = sum(item['commission'] for item in report_details)

    return {
        'report_details': report_details, 'mois_couvert_str': mois_couvert_str, 'proprietaire_filtre': proprietaire_filtre,
        'grand_total_attendu': grand_total_attendu, 'grand_total_paye': grand_total_paye, 'grand_total_impaye': grand_total_impaye,
        'grand_total_commission': grand_total_commission,
    }

def _check_agence_permission(user, chambre):
    """
    Fonction d'aide pour vérifier si un utilisateur est une agence 
    et si elle gère bien la chambre spécifiée.
    """
    if user.user_type != 'AG':
        return False
    try:
        return chambre.immeuble.proprietaire.agence == user.agence
    except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
        return False

def _get_monthly_financial_report(agence, proprietaire_id=None, num_months=12):
    """
    Calcule un rapport financier agrégé par mois pour les X derniers mois.
    Peut être filtré par propriétaire.
    """
    proprietaires_qs = Proprietaire.objects.filter(agence=agence)
    proprietaire_filtre = None
    # Condition pour filtrer par propriétaire, gérant à la fois les ID entiers (depuis le profil)
    # et les chaînes de caractères numériques (depuis les requêtes GET).
    should_filter = False
    if isinstance(proprietaire_id, int):
        should_filter = True
    elif isinstance(proprietaire_id, str) and proprietaire_id.isdigit():
        should_filter = True

    if should_filter:
        proprietaires_qs = proprietaires_qs.filter(pk=proprietaire_id)
        proprietaire_filtre = proprietaires_qs.first()

    if not proprietaires_qs.exists() and proprietaire_id:
        return [], None # Retourne une liste vide si le filtre ne trouve personne

    report_data = []
    today = timezone.now().date()

    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')

    for i in range(num_months - 1, -1, -1):
        target_date = today - relativedelta(months=i)
        start_of_month = target_date.replace(day=1)
        end_of_month = start_of_month + relativedelta(months=1, days=-1)
        
        month_label = start_of_month.strftime('%B %Y').capitalize()

        # Locations actives durant ce mois pour les propriétaires sélectionnés
        active_locations = Location.objects.filter(
            Q(chambre__immeuble__proprietaire__in=proprietaires_qs) &
            Q(date_entree__lte=end_of_month) &
            (Q(date_sortie__isnull=True) | Q(date_sortie__gte=start_of_month))
        ).distinct()
        
        total_expected = active_locations.aggregate(
            total=Coalesce(Sum('chambre__prix_loyer'), Decimal('0.00'))
        )['total']

        # Paiements pour ces locations, pour ce mois
        paiements_summary = Paiement.objects.filter(
            location__in=active_locations,
            mois_couvert=month_label,
            est_valide=True
        ).aggregate(
            total_paye=Coalesce(Sum('montant'), Decimal('0.00')),
            total_commission=Coalesce(Sum(
                F('montant') * F('location__chambre__immeuble__proprietaire__taux_commission') / Decimal('100.0'),
                output_field=DecimalField()
            ), Decimal('0.00'))
        )
        
        total_paye = paiements_summary['total_paye']
        commission = paiements_summary['total_commission']
        
        # Calcul du taux de commission effectif pour le mois
        commission_rate = (commission / total_paye * 100) if total_paye > 0 else Decimal('0.00')
        
        report_data.append({
            'month_str': month_label, 'total_attendu': total_expected, 'total_paye': total_paye,
            'total_impaye': total_expected - total_paye, 'commission': commission,
            'commission_rate': commission_rate,
        })

    return report_data, proprietaire_filtre

@login_required
def tableau_de_bord_agence(request):
    """Affiche le tableau de bord principal pour l'agence."""
    if request.user.user_type != 'AG':
        return redirect('gestion:tableau_de_bord_proprietaire')
    
    agence_profil = None
    try:
        agence_profil = request.user.agence
    except User.agence.RelatedObjectDoesNotExist:
        messages.warning(request, "Votre profil d'agence n'est pas complet. Certaines informations peuvent manquer.")
    
    # --- Liste des propriétaires gérés (avec pagination) ---
    all_proprietaires_list = Proprietaire.objects.filter(
        agence=agence_profil
    ).select_related('user').annotate(
        nombre_immeubles_proprietaire=Count('immeubles__id', distinct=True)
    ).order_by('user__last_name', 'user__first_name')
    
    # Ajout de la fonctionnalité de recherche pour les propriétaires
    q_proprietaire = request.GET.get('q_proprietaire', '')
    if q_proprietaire:
        all_proprietaires_list = all_proprietaires_list.filter(
            Q(user__first_name__icontains=q_proprietaire) |
            Q(user__last_name__icontains=q_proprietaire) |
            Q(user__username__icontains=q_proprietaire)
        )
    
    paginator_proprietaires = Paginator(all_proprietaires_list, 10)
    page_number_prop = request.GET.get('page')
    proprietaires_page = paginator_proprietaires.get_page(page_number_prop)

    # --- Données pour les widgets et statistiques ---
    now = timezone.now()
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')
    current_month_display = now.strftime('%B %Y').capitalize()

    # Utilisation des fonctions d'aide pour des calculs optimisés
    financial_summary = _get_financial_summary(agence_profil, current_month_display)
    occupancy_stats = _get_occupancy_stats(agence_profil)

    # --- Liste des chambres (avec pagination) ---
    all_chambres_list = Chambre.objects.filter(
        immeuble__proprietaire__agence=agence_profil
    ).select_related('immeuble').order_by('immeuble__addresse', 'identifiant')

    # NOUVEAU : Appliquer le filtre par recherche textuelle sur les unités
    q_unite = request.GET.get('q_unite', '')
    if q_unite:
        all_chambres_list = all_chambres_list.filter(
            Q(identifiant__icontains=q_unite) |
            Q(immeuble__addresse__icontains=q_unite)
        )

    # NOUVEAU : Appliquer le filtre par propriétaire pour la liste des unités
    unite_proprietaire_id = request.GET.get('unite_proprietaire_id')
    if unite_proprietaire_id and unite_proprietaire_id.isdigit():
        all_chambres_list = all_chambres_list.filter(immeuble__proprietaire__id=unite_proprietaire_id)

    # --- OPTIMISATION : Pré-charger les locations actives pour éviter les requêtes N+1 ---
    # 1. Récupérer toutes les locations actives pour l'agence en une seule requête
    active_locations = Location.objects.filter(
        chambre__immeuble__proprietaire__agence=agence_profil,
        date_sortie__isnull=True
    ).select_related('locataire')

    # 2. Créer un dictionnaire pour un accès rapide : {chambre_id: location_object}
    location_map = {location.chambre_id: location for location in active_locations}

    # Appliquer le filtre de statut en utilisant location_map
    statut_filtre = request.GET.get('statut', 'toutes')
    if statut_filtre == 'libres':
        chambres_occupees_ids = location_map.keys()
        filtered_chambres_list = all_chambres_list.exclude(id__in=chambres_occupees_ids)
    elif statut_filtre == 'occupees':
        chambres_occupees_ids = location_map.keys()
        filtered_chambres_list = all_chambres_list.filter(id__in=chambres_occupees_ids)
    else: # 'toutes'
        filtered_chambres_list = all_chambres_list

    # 3. Paginer la liste des chambres (maintenant filtrée)
    paginator_chambres = Paginator(filtered_chambres_list, 5)
    chambres_page_number = request.GET.get('chambres_page')
    # Utilisation de .get_page() pour une gestion robuste et sécurisée des erreurs de pagination.
    # Cela évite les erreurs EmptyPage lorsque la liste filtrée est vide.
    chambres_page = paginator_chambres.get_page(chambres_page_number)
    # 4. Attacher la location active à chaque chambre de la page courante
    #    On synchronise aussi `chambre.locataire` avec la source de vérité (la location active)
    #    pour corriger les incohérences d'affichage, car le template utilise probablement ce champ.
    for chambre in chambres_page:
        active_location = location_map.get(chambre.id)
        chambre.active_location = active_location
        if active_location:
            # Si une location active existe, on s'assure que le bon locataire est assigné.
            chambre.locataire = active_location.locataire
        else:
            # Si aucune location active n'existe, on s'assure que la chambre est bien marquée comme libre.
            chambre.locataire = None

    # Calcul du total impayé
    total_impaye_mois = financial_summary['total_attendu'] - financial_summary['total_paye']

    context = {
        # Données des propriétaires
        'proprietaires_page': proprietaires_page,
        'nombre_proprietaires': paginator_proprietaires.count,
        'all_proprietaires': all_proprietaires_list, # Pour les filtres, si nécessaire
        'q_proprietaire': q_proprietaire, # Pour pré-remplir le champ de recherche
        'q_unite': q_unite, # Pour pré-remplir le champ de recherche des unités

        # Données des chambres
        'chambres': chambres_page,
        'page_obj': chambres_page,
        # Données financières
        'current_month_display': current_month_display,
        'total_attendu_mois': financial_summary['total_attendu'],
        'total_paye_mois': financial_summary['total_paye'],
        'commission_mois': financial_summary['commission'],
        'total_impaye_mois': total_impaye_mois,
        'total_commission_agence': financial_summary['commission'],
        # Statistiques d'occupation
        **occupancy_stats,
        'statut_filter': statut_filtre, # Pour l'état actif des boutons
        'selected_unite_proprietaire_id': int(unite_proprietaire_id) if unite_proprietaire_id and unite_proprietaire_id.isdigit() else '',
        'today': timezone.now(),
    }

    # --- Nouveau: Données pour le rapport financier détaillé ---
    # On récupère les filtres spécifiques à ce rapport
    selected_owner_id = request.GET.get('proprietaire_id')
    selected_month_str = request.GET.get('mois', now.strftime('%Y-%m'))
    
    # On appelle la fonction helper UNIQUE et on ajoute son résultat au contexte
    financial_report_context = _get_financial_report_context(agence_profil, selected_owner_id, selected_month_str)
    context.update(financial_report_context)
    context['selected_owner_id'] = int(selected_owner_id) if selected_owner_id and selected_owner_id.isdigit() else ''
    context['selected_month_str'] = selected_month_str

    # Si la requête est une requête HTMX, on ne renvoie que le fragment de template
    if request.headers.get('HX-Request'):
        source = request.GET.get('source')

        # Logique de robustesse : si des filtres spécifiques aux unités sont présents
        # (statut ou pagination des chambres), on déduit que la source est la liste 
        # des unités, même si le paramètre 'source' est manquant.
        if not source and ('statut' in request.GET or 'chambres_page' in request.GET or 'unite_proprietaire_id' in request.GET or 'q_unite' in request.GET):
            source = 'chambres'

        if source == 'financial_report':
            return render(request, 'gestion/partials/_financial_report_table.html', context)
        elif source == 'chambres':
            # Le contexte est maintenant correct pour le partiel des chambres
            # Il contient 'chambres', 'page_obj', et 'today'.
            # Et chaque 'chambre' a l'attribut 'active_location'.
            return render(request, 'gestion/partials/_unit_status_wrapper.html', context)
        # Par défaut (ou si source == 'proprietaires'), on met à jour la table des propriétaires
        else:
            # On renvoie le partiel qui ne contient que les lignes (<tr>) du tableau,
            # comme pour le chargement initial, pour éviter de dupliquer les en-têtes.
            return render(request, 'gestion/partials/_proprietaires_list.html', context)

    return render(request, 'gestion/tableau_de_bord_agence.html', context)

def _get_detailed_rent_report_context(agence_profil, proprietaire_id, selected_month_str):
    """
    Fonction d'aide pour récupérer et calculer les données du rapport détaillé des loyers.
    Cette logique est partagée entre la vue HTML et la vue d'export PDF pour garantir la cohérence.
    """
    try:
        # On s'assure que la date est au bon format, sinon on prend le mois actuel.
        selected_month_date = datetime.strptime(selected_month_str, '%Y-%m')
    except (ValueError, TypeError):
        selected_month_date = datetime.now()

    # Définir la locale pour afficher le nom du mois en français
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')
    mois_couvert_str = selected_month_date.strftime('%B %Y').capitalize()

    # --- Filtrage des données ---
    end_of_month = selected_month_date.replace(day=1) + relativedelta(months=1, days=-1)
    start_of_month = selected_month_date.replace(day=1)

    locations_actives = Location.objects.filter(
        models.Q(date_sortie__isnull=True) | models.Q(date_sortie__gte=start_of_month),
        chambre__immeuble__proprietaire__agence=agence_profil,
        date_entree__lte=end_of_month
    ).select_related('chambre', 'locataire', 'chambre__immeuble', 'chambre__immeuble__proprietaire__user')

    # Appliquer le filtre par propriétaire si un ID est fourni
    proprietaire_filtre = None
    if proprietaire_id and proprietaire_id.isdigit():
        proprietaire_id_int = int(proprietaire_id)
        locations_actives = locations_actives.filter(chambre__immeuble__proprietaire__user__id=proprietaire_id_int)
        proprietaire_filtre = Proprietaire.objects.filter(user__id=proprietaire_id_int).select_related('user').first()
    # --- Calcul du rapport et des totaux ---
    monthly_rent_details = []
    total_attendu = Decimal('0.00')
    total_paye = Decimal('0.00')
    commission_totale = Decimal('0.00')

    # --- CORRECTION : Gérer les variations de locale pour 'mois_couvert' ---
    # Générer le nom du mois en français
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
        mois_couvert_fr = selected_month_date.strftime('%B %Y').capitalize()
    except locale.Error:
        mois_couvert_fr = None # Ne sera pas utilisé si la locale échoue
    
    # Générer le nom du mois avec la locale par défaut du système (souvent l'anglais)
    locale.setlocale(locale.LC_TIME, '')
    mois_couvert_default = selected_month_date.strftime('%B %Y').capitalize()

    # Créer une liste des chaînes à rechercher. On enlève les doublons si les locales sont identiques.
    mois_couvert_options = list(set(filter(None, [mois_couvert_fr, mois_couvert_default])))

    paiements_du_mois = Paiement.objects.filter(
        location__in=locations_actives,
        mois_couvert__in=mois_couvert_options, # On cherche l'une ou l'autre des chaînes
        est_valide=True
    ).select_related('location__chambre__immeuble__proprietaire')
    paiements_map = {p.location_id: p for p in paiements_du_mois}

    for location in locations_actives:
        loyer_a_payer = location.chambre.prix_loyer
        paiement = paiements_map.get(location.id)
        loyer_paye = paiement.montant if paiement else Decimal('0.00')
        reste_a_payer = loyer_a_payer - loyer_paye

        monthly_rent_details.append({
            'locataire': location.locataire,
            'chambre': location.chambre,
            'loyer_a_payer': loyer_a_payer,
            'loyer_paye': loyer_paye,
            'reste_a_payer': reste_a_payer,
            'date_paiement': paiement.date_paiement if paiement else None,
        })
        total_attendu += loyer_a_payer
        total_paye += loyer_paye

        # Calcul de la commission sur le loyer payé
        commission_rate = location.chambre.immeuble.proprietaire.taux_commission
        commission_totale += loyer_paye * (commission_rate / Decimal('100.0'))

    total_impaye = total_attendu - total_paye

    return {
        'monthly_rent_details': monthly_rent_details,
        'proprietaire_filtre': proprietaire_filtre,
        'mois_couvert_str': mois_couvert_str,
        'selected_month_str': selected_month_date.strftime('%Y-%m'),
        'totals': {
            'attendu': total_attendu,
            'paye': total_paye,
            'impaye': total_impaye,
        }
    }

@login_required
def rapport_detaille_loyers(request):
    """
    Affiche le rapport détaillé des loyers pour le mois en cours,
    filtrable par propriétaire.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent accéder à ce rapport.")

    try:
        agence_profil = request.user.agence
    except Agence.DoesNotExist:
        messages.error(request, "Votre profil d'agence est incomplet.")
        return redirect('gestion:profil')

    # --- Gestion du mois et du filtre propriétaire ---
    proprietaires_agence = Proprietaire.objects.filter(agence=agence_profil).select_related('user').order_by('user__last_name', 'user__first_name')
    selected_proprietaire_id = request.GET.get('proprietaire_id')
    selected_month_str = request.GET.get('mois', datetime.now().strftime('%Y-%m'))

    # Utiliser la fonction d'aide pour obtenir les données du rapport
    context = _get_detailed_rent_report_context(agence_profil, selected_proprietaire_id, selected_month_str)

    # Ajouter les éléments spécifiques à la vue HTML (non nécessaires pour le PDF)
    context.update({
        'page_title': 'Détail des Loyers Mensuels',
        'proprietaires_agence': proprietaires_agence,
        'selected_proprietaire_id': int(selected_proprietaire_id) if selected_proprietaire_id and selected_proprietaire_id.isdigit() else None,
    })

    return render(request, 'gestion/rapport_detaille_loyers.html', context)

@login_required
def locataire_detail(request, pk):
    """
    Affiche les détails d'un locataire, y compris sa location actuelle et son historique.
    """
    locataire = get_object_or_404(Locataire, pk=pk)

    # Vérification de permission : l'agence connectée gère-t-elle ce locataire ?
    is_managing_agence = False
    try:
        if request.user.user_type == 'AG' and locataire.agence == request.user.agence:
            is_managing_agence = True
    except (User.agence.RelatedObjectDoesNotExist, AttributeError):
        pass # L'utilisateur n'est pas une agence ou le locataire n'a pas d'agence

    if not is_managing_agence:
        raise PermissionDenied("Vous n'avez pas la permission de voir les détails de ce locataire.")

    # Trouver la location active actuelle pour ce locataire (optimisé)
    location_active = Location.objects.filter(
        locataire=locataire,
        date_sortie__isnull=True
    ).select_related('chambre', 'chambre__immeuble').first()

    # Historique des locations (passées et présentes)
    locations_history = Location.objects.filter(
        locataire=locataire
    ).select_related('chambre', 'chambre__immeuble').order_by('-date_entree')

    context = {
        'locataire': locataire,
        'location_active': location_active,
        'locations_history': locations_history,
    }
    return render(request, 'gestion/locataire_detail.html', context)

@login_required
def tableau_de_bord_proprietaire(request):
    """
    Affiche le tableau de bord pour un utilisateur de type Propriétaire,
    listant ses immeubles et un résumé financier.
    """
    if request.user.user_type != 'PR':
        raise PermissionDenied("Seuls les propriétaires peuvent accéder à cette page.")

    # Initialisation des variables pour le contexte
    immeubles_proprietaire = Immeuble.objects.none()
    nombre_immeubles = 0
    total_attendu_mois = Decimal('0.00')
    total_paye_mois = Decimal('0.00')
    commission_mois = Decimal('0.00')
    monthly_rent_details = []
    
    try:
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
    except locale.Error:
        locale.setlocale(locale.LC_TIME, '')
    current_month_display = timezone.now().strftime('%B %Y').capitalize()
    now = timezone.now()
    start_of_month = now.date().replace(day=1)
    end_of_month = start_of_month + relativedelta(months=1, days=-1)

    try:
        proprietaire_profil = request.user.proprietaire
        immeubles_proprietaire = Immeuble.objects.filter(proprietaire=proprietaire_profil)
        nombre_immeubles = immeubles_proprietaire.count()

        # --- Calcul du résumé financier et du rapport détaillé pour le mois en cours ---
        if proprietaire_profil and nombre_immeubles > 0:
            # 1. Récupérer toutes les locations actives pour ce propriétaire PENDANT le mois en cours
            locations_actives = Location.objects.filter(
                Q(chambre__immeuble__proprietaire=proprietaire_profil) &
                Q(date_entree__lte=end_of_month) &
                (Q(date_sortie__isnull=True) | Q(date_sortie__gte=start_of_month))
            ).select_related('chambre', 'locataire')

            # Calcul du total attendu basé sur les locations actives
            total_attendu_mois = locations_actives.aggregate(
                total=Coalesce(Sum('chambre__prix_loyer'), Decimal('0.00'))
            )['total']
            # 2. Récupérer les paiements du mois pour ces locations
            paiements_du_mois = Paiement.objects.filter(
                location__in=locations_actives,
                mois_couvert=current_month_display,
                est_valide=True
            )
            paiements_map = {p.location_id: p for p in paiements_du_mois}

            # 3. Itérer sur les locations pour construire le rapport et calculer les totaux
            for location in locations_actives:
                paiement = paiements_map.get(location.id)

                if paiement:
                    loyer_paye = paiement.montant
                    date_paiement = paiement.date_paiement
                else:
                    loyer_paye = Decimal('0.00')
                    date_paiement = None

                reste_a_payer = location.chambre.prix_loyer - loyer_paye

                monthly_rent_details.append({
                    'locataire': location.locataire,
                    'chambre': location.chambre,
                    'loyer_a_payer': location.chambre.prix_loyer,
                    'loyer_paye': loyer_paye,
                    'reste_a_payer': reste_a_payer,
                    'date_paiement': date_paiement,
                })
                # Mettre à jour les totaux
                total_paye_mois += loyer_paye

            # 4. Calculer la commission
            if proprietaire_profil.taux_commission > 0:
                commission_mois = total_paye_mois * (proprietaire_profil.taux_commission / Decimal('100.0'))

    except Proprietaire.DoesNotExist:
        messages.warning(request, "Votre profil de propriétaire n'est pas complet ou n'a pas été trouvé.")

    total_impaye_mois = total_attendu_mois - total_paye_mois

    context = {
        'immeubles': immeubles_proprietaire, 'nombre_immeubles': nombre_immeubles,
        'current_month_display': current_month_display, 'total_attendu_mois': total_attendu_mois,
        'total_paye_mois': total_paye_mois, 'total_impaye_mois': total_impaye_mois, 'commission_mois': commission_mois,
        'monthly_rent_details': monthly_rent_details,
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
                return redirect('gestion:tableau_de_bord_proprietaire') # CORRECTION : Ajout du namespace 'gestion:'
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
                    # 1. Créer l'utilisateur à partir du ModelForm, mais ne pas encore le sauvegarder.
                    proprietaire_user = form.save(commit=False)
                    
                    # Générer un nom d'utilisateur unique et un mot de passe temporaire
                    base_username = f"{form.cleaned_data['first_name'].lower()}.{form.cleaned_data['last_name'].lower().replace(' ', '')}"
                    username = base_username
                    counter = 1
                    # Boucle pour garantir un nom d'utilisateur unique
                    while User.objects.filter(username=username).exists():
                        username = f"{base_username}{counter}"
                        counter += 1
                    proprietaire_user.username = username
                    
                    password = get_random_string(length=12, allowed_chars='ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*')
                    proprietaire_user.set_password(password)
                    proprietaire_user.user_type = 'PR'
                    proprietaire_user.must_change_password = True
                    proprietaire_user.save() # Sauvegarder l'utilisateur

                    # 2. Créer le profil Proprietaire (contrat)
                    cd = form.cleaned_data
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
                        fail_silently=False, # fail_silently=False est important pour voir les erreurs dans les logs
                    )
                    messages.info(request, f"Un email de bienvenue a été envoyé à {proprietaire_user.email} avec ses identifiants.")
                except Exception as email_error:
                    messages.warning(request, f"Le propriétaire a été créé, mais l'envoi de l'email de bienvenue a échoué. L'erreur est : {email_error}")

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
        user_form = UserUpdateForm(request.POST, request.FILES, instance=proprietaire_user)
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
    Affiche la liste des locataires des biens gérés par l'agence, avec une fonction de recherche.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent gérer les locataires.")

    try:
        agence_profil = request.user.agence
        # Requête de base pour les locataires de l'agence
        locataires_list = Locataire.objects.filter(agence=agence_profil).order_by('nom', 'prenom')
        
        # Fonctionnalité de recherche
        search_query = request.GET.get('q', '')
        if search_query:
            locataires_list = locataires_list.filter(
                Q(nom__icontains=search_query) | Q(prenom__icontains=search_query)
            )

    except User.agence.RelatedObjectDoesNotExist:
        locataires_list = Locataire.objects.none()
        messages.error(request, "Votre profil d'agence est incomplet.")

    context = {
        'locataires': locataires_list,
        'search_query': search_query,
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
def historique_paiement_locataire(request, locataire_id):
    """
    Affiche l'historique complet de tous les paiements pour un locataire, avec pagination.
    """
    # 1. Vérification de sécurité : l'utilisateur doit être une agence
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent accéder à cette page.")

    # 2. Récupération des objets et vérification des permissions
    locataire = get_object_or_404(Locataire, pk=locataire_id)
    try:
        if locataire.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce locataire.")
    except User.agence.RelatedObjectDoesNotExist:
        raise PermissionDenied("Votre profil d'agence est incomplet.")

    # 3. Récupérer tous les paiements pour toutes les locations de ce locataire
    paiements_list = Paiement.objects.filter(
        location__locataire=locataire
    ).select_related(
        'location__chambre__immeuble',
        'moyen_paiement'
    ).order_by('-date_paiement') # Les plus récents en premier

    # 4. Pagination
    paginator = Paginator(paiements_list, 15) # 15 paiements par page
    page_number = request.GET.get('page')
    paiements_page = paginator.get_page(page_number)

    context = {
        'locataire': locataire,
        'paiements_page': paiements_page,
        'page_title': f"Historique des paiements de {locataire}",
    }
    return render(request, 'gestion/historique_paiement_locataire.html', context)

@login_required
def historique_paiement_locataire_mois(request, locataire_id, year, month):
    """
    Affiche le détail du paiement d'un locataire pour un mois et une année spécifiques.
    """
    # 1. Vérification de sécurité : l'utilisateur doit être une agence
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent accéder à cette page.")

    # 2. Récupération des objets et vérification des permissions
    locataire = get_object_or_404(Locataire, pk=locataire_id)
    try:
        if locataire.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce locataire.")
    except User.agence.RelatedObjectDoesNotExist:
        raise PermissionDenied("Votre profil d'agence est incomplet.")

    # 3. Déterminer le mois et construire la chaîne 'mois_couvert'
    try:
        target_date = datetime(year, month, 1)
        locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
        mois_couvert_str = target_date.strftime('%B %Y').capitalize()
    except (ValueError, locale.Error):
        messages.error(request, "Date invalide.")
        return redirect('gestion:gerer_locataires')

    # 4. Trouver la location active durant ce mois
    start_of_month = target_date.date()
    end_of_month = (start_of_month + relativedelta(months=1, days=-1))
    
    location = Location.objects.filter(
        Q(locataire=locataire) &
        Q(date_entree__lte=end_of_month) &
        (Q(date_sortie__isnull=True) | Q(date_sortie__gte=start_of_month))
    ).select_related('chambre__immeuble').first()

    # 5. Trouver le paiement pour cette location et ce mois
    paiement = None
    if location:
        paiement = Paiement.objects.filter(
            location=location,
            mois_couvert=mois_couvert_str
        ).first()

    context = {
        'locataire': locataire,
        'location': location,
        'paiement': paiement,
        'mois_couvert_str': mois_couvert_str,
        'page_title': f"Paiement de {locataire} pour {mois_couvert_str}",
    }
    return render(request, 'gestion/historique_paiement_locataire_mois.html', context)

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
def telecharger_paiements_locataire(request, locataire_id):
    """
    Génère un fichier CSV de l'historique des paiements pour un locataire donné.
    """
    # --- Vérifications de sécurité ---
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent effectuer cette action.")

    locataire = get_object_or_404(Locataire, pk=locataire_id)
    
    try:
        if locataire.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce locataire.")
    except User.agence.RelatedObjectDoesNotExist:
        raise PermissionDenied("Votre profil d'agence est incomplet.")

    # Définir le nom du fichier de sortie
    filename = f"historique_paiements_{locataire.nom}_{locataire.prenom}.csv".replace(" ", "_")

    # Créer la réponse HTTP avec les en-têtes corrects pour un fichier CSV
    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
    response.write(u'\ufeff'.encode('utf8')) # BOM pour Excel

    writer = csv.writer(response, delimiter=';')

    # Écrire la ligne d'en-tête
    writer.writerow(['Date de Paiement', 'Montant (Frcfa)', 'Période Concernée', 'Bien Concerné', 'Méthode de Paiement'])

    # Récupérer tous les paiements pour ce locataire (source de vérité : via Location)
    paiements = Paiement.objects.filter(
        location__locataire=locataire
    ).select_related(
        'location__chambre__immeuble', 
        'moyen_paiement'
    ).order_by('date_paiement')

    # Écrire chaque paiement
    for paiement in paiements:
        writer.writerow([
            paiement.date_paiement,
            paiement.montant,
            paiement.mois_couvert,
            f"{paiement.location.chambre} ({paiement.location.chambre.immeuble.addresse})",
            paiement.moyen_paiement.get_designation_display() if paiement.moyen_paiement else "-",
        ])

    return response

@login_required
def telecharger_paiements_locataire_pdf(request, locataire_id):
    """
    Génère un fichier PDF de l'historique des paiements pour un locataire donné.
    """
    if HTML is None:
        messages.error(request, "La génération de PDF n'est pas disponible. Veuillez contacter l'administrateur.")
        return redirect('gestion:locataire_detail', pk=locataire_id)

    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent effectuer cette action.")

    locataire = get_object_or_404(Locataire, pk=locataire_id)
    try:
        agence = request.user.agence
        if locataire.agence != agence:
            raise PermissionDenied("Vous ne gérez pas ce locataire.")
    except User.agence.RelatedObjectDoesNotExist:
        raise PermissionDenied("Votre profil d'agence est incomplet.")

    paiements = Paiement.objects.filter(location__locataire=locataire).select_related('location__chambre__immeuble', 'moyen_paiement').order_by('date_paiement')
    total_paye = paiements.aggregate(total=Coalesce(Sum('montant'), Decimal('0.00')))['total']

    context = {
        'locataire': locataire,
        'paiements': paiements,
        'agence': agence,
        'total_paye': total_paye,
        'date_generation': timezone.now().date(),
    }
    html_string = render_to_string('gestion/historique_paiements_locataire_pdf.html', context)
    
    # CORRECTION : On passe l'URL de base à WeasyPrint pour qu'il puisse charger
    # les fichiers CSS externes (comme Bootstrap) et les images locales.
    # `base_url` aide à résoudre les chemins relatifs dans le HTML.
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    filename = f"historique_paiements_{locataire.nom}_{locataire.prenom}.pdf".replace(" ", "_")
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@login_required
def supprimer_locataire(request, pk):
    """
    Gère la suppression d'un locataire.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent supprimer des locataires.")

    locataire = get_object_or_404(Locataire, pk=pk)

    # Vérification de sécurité
    try: # Vérifie si l'agence connectée gère ce locataire
        if locataire.agence != request.user.agence:
            raise PermissionDenied("Vous ne gérez pas ce locataire.")
    except User.agence.RelatedObjectDoesNotExist:
        raise PermissionDenied("Votre profil d'agence est incomplet.")

    if request.method == 'POST':
        locataire_nom = str(locataire)
        locataire.delete()
        messages.success(request, f"Le locataire '{locataire_nom}' a été supprimé avec succès.")
        return redirect('gestion:gerer_locataires')

    # Vérifie si le locataire a des locations actives (source de vérité)
    is_occupant = Location.objects.filter(locataire=locataire, date_sortie__isnull=True).exists()

    context = {
        'locataire': locataire,
        'is_occupant': is_occupant,
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
    immeuble = get_object_or_404(Immeuble.objects.select_related('proprietaire__user'), pk=pk)

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

    # AMÉLIORATION : Ne pas select_related('locataire') ici, on va le gérer via Location
    chambres = Chambre.objects.filter(immeuble=immeuble)

    # --- OPTIMISATION : Pré-charger les locations actives pour éviter les requêtes N+1 ---

    # --- Calculs pour les statistiques de l'immeuble ---
    total_units = chambres.count()
    occupied_units = chambres.filter(locataire__isnull=False).count()
    
    occupancy_rate = 0
    if total_units > 0:
        occupancy_rate = (occupied_units / total_units) * 100

    # 1. Récupérer toutes les locations actives pour les chambres de cet immeuble
    active_locations = Location.objects.filter(
        chambre__in=chambres, # Filtre sur les chambres de cet immeuble
        date_sortie__isnull=True
    ).select_related('locataire') # Pré-charger le locataire

    # 2. Créer un dictionnaire pour un accès rapide : {chambre_id: location_object}
    location_map = {location.chambre_id: location for location in active_locations}

    # 3. Attacher la location active et le locataire à chaque chambre
    #    On crée une nouvelle liste pour ne pas modifier le queryset original pendant l'itération
    chambres_with_status = []
    for chambre in chambres:
        active_location = location_map.get(chambre.id)
        chambre.active_location = active_location # Pour le template
        chambre.locataire_actuel = active_location.locataire if active_location else None # Pour le template
        chambres_with_status.append(chambre)

    # Recalculer les statistiques d'occupation et le loyer total en se basant sur les locations actives
    occupied_units = len(active_locations)
    total_rent = sum(loc.chambre.prix_loyer for loc in active_locations)
    occupancy_rate = (occupied_units / total_units) * 100 if total_units > 0 else 0

    context = {
        'immeuble': immeuble,
        'chambres': chambres_with_status, # Utiliser la liste enrichie
        'occupancy_rate': occupancy_rate,
        'total_rent': total_rent,
        'is_managing_agence': is_managing_agence,
        'occupied_units': occupied_units,
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
            chambre.save() # La méthode __str__ est maintenant "Type identifiant"
            messages.success(request, f"L'unité '{chambre}' a été ajoutée avec succès.")
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
            messages.success(request, f"L'unité '{chambre}' a été mise à jour avec succès.")
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
        designation = str(chambre) # Utilise la méthode __str__
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
    chambre = get_object_or_404(Chambre.objects.select_related('immeuble__proprietaire'), pk=pk)

    # Vérification de permission : l'utilisateur est-il l'agence qui gère ou le propriétaire ?
    is_managing_agence = _check_agence_permission(request.user, chambre)
    is_owner = (request.user.user_type == 'PR' and chambre.immeuble.proprietaire.user == request.user)

    if not (is_managing_agence or is_owner):
        raise PermissionDenied("Vous n'avez pas la permission de voir cette unité.")

    # --- Récupération des données liées à la location active ---
    location_active = Location.objects.filter(chambre=chambre, date_sortie__isnull=True).first()
    etats_des_lieux = EtatDesLieux.objects.none()
    if location_active:
        etats_des_lieux = location_active.etats_des_lieux.all()

    if request.method == 'POST':
        if not is_managing_agence:
            raise PermissionDenied("Seule l'agence peut effectuer cette action.")

        # Gère l'assignation d'un nouveau locataire
        if 'submit_location' in request.POST: # Assignation d'un nouveau locataire
            if location_active: # Vérifie s'il y a déjà une location active
                messages.error(request, "Cette chambre est déjà occupée.")
                return redirect('gestion:chambre_detail', pk=pk)

            location_form = LocationForm(request.POST, agence=request.user.agence)
            if location_form.is_valid():
                with transaction.atomic():
                    location = location_form.save(commit=False)
                    location.chambre = chambre
                    location.save()
                    chambre.locataire = location.locataire
                    chambre.save() # La méthode __str__ est maintenant "Type identifiant"
                messages.success(request, f"Le locataire {chambre.locataire} a été assigné à l'unité {chambre}.")
                return redirect('gestion:chambre_detail', pk=pk)
            else:
                # Si le formulaire n'est pas valide, on affiche un message d'erreur.
                # Le formulaire avec les erreurs sera automatiquement passé au contexte.
                messages.error(request, "Veuillez corriger les erreurs dans le formulaire d'assignation.")

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

    else: # Requête GET
        location_form = None
        etat_des_lieux_form = None
        if is_managing_agence:
            if not location_active: # Si l'unité est libre, on prépare le formulaire d'assignation
                location_form = LocationForm(agence=request.user.agence)
            else: # Si l'unité est occupée, on prépare le formulaire d'état des lieux
                etat_des_lieux_form = EtatDesLieuxForm()

    # --- Construction de l'historique complet des paiements (payés et arriérés) ---
    payment_history = []
    if location_active: # L'historique des paiements est lié à la location active
        if location_active:
            # Récupérer tous les paiements (validés ou non) et les mapper par mois pour un accès rapide
            # CORRECTION : On cherche tous les paiements faits par le locataire actuel POUR CETTE CHAMBRE,
            # en pré-chargeant le moyen de paiement associé pour optimiser la requête.
            payments_queryset = Paiement.objects.filter(
                location__chambre=chambre, location__locataire=location_active.locataire
            ).select_related('moyen_paiement')

            all_payments = {
                p.mois_couvert: p for p in payments_queryset.order_by('date_paiement')
            }
            
            # Définir la locale en français pour générer les noms de mois correctement
            # CORRECTION : Rendre la définition de la locale plus robuste pour éviter les crashs sur les serveurs de production
            # où la locale 'fr_FR.UTF-8' n'est pas forcément installée.
            try:
                locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
            except locale.Error:
                try:
                    locale.setlocale(locale.LC_TIME, '') # Fallback sur la locale système par défaut
                except locale.Error:
                    # Si même la locale par défaut échoue, on continue sans planter.
                    # Les noms de mois seront probablement en anglais.
                    pass

            # Itérer du début de la location jusqu'au mois actuel
            cursor_date = location_active.date_entree
            end_date = timezone.now().date()

            while cursor_date.year < end_date.year or (cursor_date.year == end_date.year and cursor_date.month <= end_date.month):
                month_str = cursor_date.strftime('%B %Y').capitalize()
                payment_obj = all_payments.get(month_str)
                
                if payment_obj:
                    if payment_obj.est_valide:
                        status = 'paid'
                    else:
                        status = 'pending'
                    payment_history.append({'month': month_str, 'status': status, 'payment': payment_obj})
                else:
                    payment_history.append({'month': month_str, 'status': 'unpaid', 'payment': None})
                
                cursor_date += relativedelta(months=1)
            
            # Inverser la liste pour afficher les mois les plus récents en premier
            payment_history.reverse()

    context = {
        'chambre': chambre,
        'location_form': location_form,
        'locataire_actuel': location_active.locataire if location_active else None, # Passer le locataire actuel au template
        'etat_des_lieux_form': etat_des_lieux_form,
        'etats_des_lieux': etats_des_lieux,
        'location_active': location_active,
        'payment_history': payment_history,
        'is_managing_agence': is_managing_agence,
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
def generer_etat_des_lieux_pdf(request, pk):
    """
    Génère un document PDF pour un état des lieux.
    """
    if HTML is None:
        return HttpResponse("La bibliothèque WeasyPrint est requise pour générer des PDF. Veuillez l'installer avec 'pip install WeasyPrint'.", status=501)

    etat = get_object_or_404(EtatDesLieux, pk=pk)
    chambre = etat.location.chambre
    agence = None

    # Vérification de sécurité : Seule l'agence peut générer le document.
    is_managing_agence = False
    if request.user.user_type == 'AG':
        try:
            agence = request.user.agence
            if chambre.immeuble.proprietaire.agence == agence:
                is_managing_agence = True
        except (User.agence.RelatedObjectDoesNotExist, Proprietaire.DoesNotExist):
            pass

    if not is_managing_agence:
        raise PermissionDenied("Seules les agences peuvent générer ce document.")

    context = {
        'etat': etat,
        'location': etat.location,
        'chambre': chambre,
        'locataire': etat.location.locataire,
        'immeuble': chambre.immeuble,
        'proprietaire': chambre.immeuble.proprietaire,
        'agence': agence,
        'date_generation': timezone.now().date(),
    }

    html_string = render_to_string('gestion/etat_des_lieux_pdf.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    locataire_name_safe = "".join([c for c in str(etat.location.locataire) if c.isalpha() or c.isdigit() or c.isspace()]).rstrip()
    filename = f"etat_des_lieux_{etat.type_etat}_{locataire_name_safe.replace(' ', '_')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

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
        # AMÉLIORATION : Se baser sur la présence d'une location active (source de vérité)
        # plutôt que sur le champ dénormalisé `chambre.locataire`.
        location_active = Location.objects.filter(chambre=chambre, date_sortie__isnull=True).first()
        
        if location_active:
            locataire_nom = str(location_active.locataire)
            
            with transaction.atomic():
                # Marque la date de sortie sur la location active pour la terminer.
                location_active.date_sortie = timezone.now().date()
                location_active.save()
                
                # Met à jour le champ dénormalisé pour la cohérence.
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
        form = PaiementForm(request.POST, request.FILES)
        if form.is_valid():
            # Vérification pour éviter les doublons
            mois_couvert = form.cleaned_data['mois_couvert']
            if Paiement.objects.filter(location=location, mois_couvert=mois_couvert).exists():
                messages.error(request, f"Un paiement pour le mois de '{mois_couvert}' existe déjà pour cette location.")
            else:
                paiement = form.save(commit=False)
                paiement.location = location
                paiement.save() # La sauvegarde du formulaire gère l'upload du fichier
                messages.success(request, f"Le paiement de {paiement.montant} Frcfa a été enregistré avec succès.")
                return redirect('gestion:chambre_detail', pk=chambre.pk)
    else:
        # Définir la locale pour générer le nom du mois correctement, assurant la cohérence
        # avec la façon dont les rapports lisent cette donnée.
        try:
            locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
        except locale.Error:
            locale.setlocale(locale.LC_TIME, '') # Fallback sur la locale système

        # Pré-remplir le formulaire pour plus de commodité
        # Utilise le paramètre 'mois' de l'URL s'il est fourni (pour les arriérés)
        initial_data = {
            'montant': chambre.prix_loyer,
            'date_paiement': timezone.now().date(),
            'mois_couvert': request.GET.get('mois', timezone.now().strftime('%B %Y').capitalize()),
        }
        form = PaiementForm(initial=initial_data)

    # Récupérer les PK des moyens de paiement qui nécessitent une preuve pour le JS du template
    pks_require_proof = list(MoyenPaiement.objects.filter(
        designation__in=[MoyenPaiement.MOBILE, MoyenPaiement.VIREMENT, MoyenPaiement.DEPOT_ESPECES]
    ).values_list('pk', flat=True))

    context = {
        'form': form,
        'chambre': chambre,
        'location': location,
        'pks_require_proof': pks_require_proof,
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
        form = PaiementForm(request.POST, request.FILES, instance=paiement)
        if form.is_valid():
            form.save() # La sauvegarde du formulaire gère l'upload du fichier
            messages.success(request, "Le paiement a été mis à jour avec succès.")
            return redirect('gestion:chambre_detail', pk=chambre.pk)
    else:
        form = PaiementForm(instance=paiement)

    # Récupérer les PK des moyens de paiement qui nécessitent une preuve pour le JS du template
    pks_require_proof = list(MoyenPaiement.objects.filter(
        designation__in=[MoyenPaiement.MOBILE, MoyenPaiement.VIREMENT, MoyenPaiement.DEPOT_ESPECES]
    ).values_list('pk', flat=True))

    context = {
        'form': form,
        'paiement': paiement,
        'chambre': chambre,
        'pks_require_proof': pks_require_proof,
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
def exporter_paiements_pdf(request):
    """
    Exporte la liste de tous les paiements gérés par l'agence en fichier PDF.
    """
    if HTML is None:
        return HttpResponse("La bibliothèque WeasyPrint est requise pour générer des PDF. Veuillez l'installer avec 'pip install WeasyPrint'.", status=501)

    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent exporter des données.")

    try:
        agence = request.user.agence
        paiements = Paiement.objects.filter(
            location__chambre__immeuble__proprietaire__agence=agence
        ).select_related(
            'location__chambre__immeuble',
            'location__locataire',
            'moyen_paiement'
        ).order_by('-date_paiement')
    except CustomUser.agence.RelatedObjectDoesNotExist:
        messages.error(request, "Votre profil d'agence est incomplet.")
        return redirect('gestion:profil')

    context = {
        'paiements': paiements,
        'agence': agence,
        'date_generation': timezone.now().date(),
    }

    html_string = render_to_string('gestion/paiements_export_pdf.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="export_tous_les_paiements.pdf"'
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
    Affiche un rapport financier historique sur 12 mois, filtrable par propriétaire.
    Gère également la demande de téléchargement PDF.
    """
    if request.user.user_type != 'AG':
        raise PermissionDenied("Seuls les utilisateurs de type agence peuvent accéder à ce rapport.")

    try:
        agence = request.user.agence
    except Agence.DoesNotExist:
        messages.error(request, "Votre profil d'agence est incomplet.")
        return redirect('gestion:profil')

    # Si le bouton de téléchargement a été cliqué, on appelle directement la vue de génération PDF.
    if 'download_pdf' in request.GET:
        return generer_rapport_financier_pdf(request)

    # --- Get filters from request ---
    proprietaires_agence = Proprietaire.objects.filter(agence=agence).select_related('user').order_by('user__last_name')
    selected_owner_id = request.GET.get('proprietaire_id')

    # --- Generate report data using the new monthly report function ---
    monthly_report_data, proprietaire_filtre = _get_monthly_financial_report(agence, selected_owner_id)
    
    # Calculate grand totals
    grand_total_attendu = sum(item['total_attendu'] for item in monthly_report_data)
    grand_total_paye = sum(item['total_paye'] for item in monthly_report_data)
    grand_total_impaye = sum(item['total_impaye'] for item in monthly_report_data)
    grand_total_commission = sum(item['commission'] for item in monthly_report_data)

    # Calcul du taux de commission global effectif
    grand_total_commission_rate = (grand_total_commission / grand_total_paye * 100) if grand_total_paye > 0 else Decimal('0.00')

    context = {
        'proprietaires_agence': proprietaires_agence,
        'selected_owner_id': int(selected_owner_id) if selected_owner_id and selected_owner_id.isdigit() else None,
        'proprietaire_filtre': proprietaire_filtre,
        'page_title': 'Rapport Financier Historique',
        'report_data': monthly_report_data,
        'grand_total_attendu': grand_total_attendu,
        'grand_total_paye': grand_total_paye,
        'grand_total_impaye': grand_total_impaye,
        'grand_total_commission': grand_total_commission,
        'grand_total_commission_rate': grand_total_commission_rate,
    }
    return render(request, 'gestion/rapport_financier.html', context)

@login_required
def generer_rapport_financier_pdf(request):
    """
    Génère un rapport financier PDF, basé sur l'historique mensuel.
    Accessible par l'agence (avec filtre) et par le propriétaire (pour lui-même).
    """
    if HTML is None:
        return HttpResponse("La bibliothèque WeasyPrint est requise pour générer des PDF. Veuillez l'installer avec 'pip install WeasyPrint'.", status=501)

    if request.user.user_type == 'AG':
        try:
            agence = request.user.agence
            selected_owner_id = request.GET.get('proprietaire_id')
        except Agence.DoesNotExist:
            messages.error(request, "Votre profil d'agence est incomplet.")
            return redirect('gestion:profil')
    elif request.user.user_type == 'PR':
        try:
            proprietaire_profil = request.user.proprietaire
            agence = proprietaire_profil.agence
            selected_owner_id = proprietaire_profil.id
        except Proprietaire.DoesNotExist:
            messages.error(request, "Votre profil de propriétaire est introuvable.")
            return redirect('gestion:tableau_de_bord_proprietaire')
    else:
        # Si le type d'utilisateur n'est ni AG ni PR, on refuse l'accès.
        raise PermissionDenied("Vous n'êtes pas autorisé à générer ce rapport.")
    
    # Utiliser la nouvelle fonction pour obtenir les données mensuelles
    monthly_report_data, proprietaire_filtre = _get_monthly_financial_report(agence, selected_owner_id)
    
    # Calculer les totaux pour le PDF
    grand_total_attendu = sum(item['total_attendu'] for item in monthly_report_data)
    grand_total_paye = sum(item['total_paye'] for item in monthly_report_data)
    grand_total_impaye = sum(item['total_impaye'] for item in monthly_report_data)
    grand_total_commission = sum(item['commission'] for item in monthly_report_data)

    # Calcul du taux de commission global effectif pour le PDF
    grand_total_commission_rate = (grand_total_commission / grand_total_paye * 100) if grand_total_paye > 0 else Decimal('0.00')

    context = {
        'agence': agence,
        'date_generation': timezone.now().date(),
        'report_data': monthly_report_data,
        'proprietaire_filtre': proprietaire_filtre,
        'grand_total_attendu': grand_total_attendu,
        'grand_total_paye': grand_total_paye,
        'grand_total_impaye': grand_total_impaye,
        'grand_total_commission': grand_total_commission,
        'grand_total_commission_rate': grand_total_commission_rate,
    }
    html_string = render_to_string('gestion/rapport_financier_pdf.html', context)
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    response = HttpResponse(pdf_file, content_type='application/pdf')
    
    # Amélioration du nom de fichier pour inclure le nom du propriétaire si filtré
    filename = "rapport_financier_historique"
    if proprietaire_filtre:
        owner_name_safe = "".join([c for c in proprietaire_filtre.user.get_full_name() if c.isalnum() or c.isspace()]).replace(' ', '_')
        filename = f"rapport_historique_{owner_name_safe}"
    response['Content-Disposition'] = f'attachment; filename="{filename}.pdf"'
    return response

@login_required
def exporter_rapport_detaille_pdf(request):
    """
    Génère un rapport PDF détaillé des loyers, en utilisant les mêmes filtres
    que la page de rapport HTML.
    """
    if HTML is None:
        return HttpResponse("La bibliothèque WeasyPrint est requise pour générer des PDF. Veuillez l'installer avec 'pip install WeasyPrint'.", status=501)

    if request.user.user_type != 'AG':
        raise PermissionDenied("Seules les agences peuvent générer ce rapport PDF.")

    try:
        agence = request.user.agence
    except Agence.DoesNotExist:
        messages.error(request, "Votre profil d'agence est incomplet.")
        return redirect('gestion:profil')

    # Récupérer les filtres depuis l'URL
    selected_proprietaire_id = request.GET.get('proprietaire_id')
    selected_month_str = request.GET.get('mois', datetime.now().strftime('%Y-%m'))

    # Utiliser la fonction d'aide pour obtenir les données du rapport
    context = _get_detailed_rent_report_context(agence, selected_proprietaire_id, selected_month_str)

    # Ajouter les éléments spécifiques au contexte du PDF
    context.update({
        'agence': agence,
        'date_generation': timezone.now().date(),
    })

    html_string = render_to_string('gestion/rapport_detaille_pdf.html', context)
    html = HTML(string=html_string, base_url=request.build_absolute_uri())
    pdf = html.write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f"rapport_loyers_{context['mois_couvert_str'].replace(' ', '_')}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response