from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import transaction
import string
import random
from .forms import RegisterForm, LoginForm, BienForm, ProprietaireCreationForm, UserUpdateForm, AgenceProfileForm, ProprietaireProfileUpdateForm
from .models import Bien, Proprietaire, Agence, Immeuble, Chambre
from django.core.exceptions import PermissionDenied

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
        return redirect('gestion:accueil')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Bienvenue, {user.username} !")
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

@login_required
def ajouter_bien(request):
    """
    Gère l'ajout d'une nouvelle propriété.
    """
    if request.method == 'POST':
        form = BienForm(request.POST, user=request.user)
        if form.is_valid():
            bien = form.save(commit=False)
            if request.user.user_type == 'PR':
                # Si l'utilisateur est un propriétaire, il est le propriétaire du bien
                bien.proprietaire = request.user
            elif request.user.user_type == 'AG':
                # Si l'utilisateur est une agence, elle gère le bien
                bien.agence = request.user
            
            bien.save()
            messages.success(request, "Le bien a été ajouté avec succès.")
            
            # Rediriger vers le tableau de bord approprié
            return redirect('gestion:tableau_de_bord_proprietaire' if request.user.user_type == 'PR' else 'gestion:tableau_de_bord_agence')
    else:
        form = BienForm(user=request.user)

    return render(request, 'gestion/ajouter_bien.html', {'form': form})

@login_required
def modifier_bien(request, pk):
    """
    Gère la modification d'un bien existant.
    """
    bien = get_object_or_404(Bien, pk=pk)

    # Vérification des permissions (seul le propriétaire ou l'agence peut modifier)
    is_proprietaire = (request.user.user_type == 'PR' and bien.proprietaire == request.user)
    is_agence = (request.user.user_type == 'AG' and bien.agence == request.user)

    if not (is_proprietaire or is_agence):
        raise PermissionDenied("Vous n'avez pas la permission de modifier ce bien.")

    if request.method == 'POST':
        # On passe 'instance=bien' pour indiquer au formulaire qu'il s'agit d'une mise à jour
        form = BienForm(request.POST, user=request.user, instance=bien)
        if form.is_valid():
            form.save()
            messages.success(request, f"Le bien '{bien.nom}' a été mis à jour avec succès.")
            return redirect('gestion:bien_detail', pk=bien.pk)
    else:
        # On passe 'instance=bien' pour pré-remplir le formulaire avec les données existantes
        form = BienForm(user=request.user, instance=bien)

    return render(request, 'gestion/modifier_bien.html', {'form': form, 'bien': bien})

@login_required
def supprimer_bien(request, pk):
    """
    Gère la suppression d'un bien, avec confirmation.
    """
    bien = get_object_or_404(Bien, pk=pk)

    # Vérification des permissions
    is_proprietaire = (request.user.user_type == 'PR' and bien.proprietaire == request.user)
    is_agence = (request.user.user_type == 'AG' and bien.agence == request.user)

    if not (is_proprietaire or is_agence):
        raise PermissionDenied("Vous n'avez pas la permission de supprimer ce bien.")

    if request.method == 'POST':
        bien_nom = bien.nom
        bien.delete()
        messages.success(request, f"Le bien '{bien_nom}' a été supprimé avec succès.")
        # Rediriger vers le tableau de bord approprié
        if request.user.user_type == 'AG':
            return redirect('gestion:tableau_de_bord_agence')
        else:
            return redirect('gestion:tableau_de_bord_proprietaire')

    return render(request, 'gestion/bien_confirm_delete.html', {'bien': bien})

@login_required
def bien_detail(request, pk):
    """
    Affiche les détails d'un bien spécifique.
    Vérifie que l'utilisateur a le droit de voir ce bien.
    """
    bien = get_object_or_404(Bien, pk=pk)

    # Vérification des permissions
    is_proprietaire = (request.user.user_type == 'PR' and bien.proprietaire == request.user)
    is_agence = (request.user.user_type == 'AG' and bien.agence == request.user)

    if not (is_proprietaire or is_agence):
        raise PermissionDenied("Vous n'avez pas la permission de voir ce bien.")

    context = {
        'bien': bien
    }
    return render(request, 'gestion/bien_detail.html', context)

# Vues de placeholder pour éviter les erreurs
@login_required
def tableau_de_bord_agence(request):
    # Récupère uniquement les biens gérés par l'agence connectée
    biens_geres = Bien.objects.filter(agence=request.user)
    nombre_biens = biens_geres.count()
    
    proprietaires_geres = Proprietaire.objects.none()
    nombre_proprietaires = 0
    
    # Récupère les propriétaires gérés par l'agence
    try:
        # On s'assure que l'utilisateur a un profil Agence avant de l'utiliser.
        agence_profil = request.user.agence
        # On utilise select_related('user') pour optimiser la requête
        # en récupérant les informations de l'utilisateur en même temps.
        proprietaires_geres = Proprietaire.objects.filter(agence=agence_profil).select_related('user')
        nombre_proprietaires = proprietaires_geres.count()
    except User.agence.RelatedObjectDoesNotExist:
        # Gère le cas où un utilisateur de type Agence n'a pas encore de profil Agence créé.
        # Ce n'est pas une erreur bloquante pour le tableau de bord, on affiche juste un avertissement.
        proprietaires_geres = Proprietaire.objects.none()
        nombre_proprietaires = 0
        messages.warning(request, "Votre profil d'agence n'est pas complet. Certaines informations peuvent manquer.")
    
    # --- Calcul du Taux d'Occupation ---
    # On se base sur les modèles détaillés (Immeuble -> Chambre) pour un calcul précis.
    
    # 1. Récupérer tous les immeubles des propriétaires gérés
    immeubles_geres = Immeuble.objects.filter(proprietaire__in=proprietaires_geres)
    
    # 2. Récupérer toutes les unités (chambres) de ces immeubles
    total_chambres = Chambre.objects.filter(immeuble__in=immeubles_geres)
    total_units = total_chambres.count()
    
    # 3. Compter les unités occupées (celles avec un locataire assigné)
    occupied_units = total_chambres.filter(locataire__isnull=False).count()
    
    # 4. Calculer le taux
    occupancy_rate = 0
    if total_units > 0:
        occupancy_rate = (occupied_units / total_units) * 100

    context = {
        'biens': biens_geres,
        'nombre_biens': nombre_biens,
        'proprietaires': proprietaires_geres,
        'nombre_proprietaires': nombre_proprietaires,
        'occupancy_rate': occupancy_rate,
    }
    return render(request, 'gestion/tableau_de_bord_agence.html', context)

@login_required
def tableau_de_bord_proprietaire(request):
    # Récupère uniquement les biens appartenant au propriétaire connecté
    biens_proprietaire = Bien.objects.filter(proprietaire=request.user)
    nombre_biens = biens_proprietaire.count()

    context = {
        'biens': biens_proprietaire,
        'nombre_biens': nombre_biens,
    }
    return render(request, 'gestion/tableau_de_bord_proprietaire.html', context)

@login_required
def profil_utilisateur(request):
    """
    Affiche et gère la mise à jour du profil de l'utilisateur
    et de son profil Agence si applicable.
    """
    user = request.user
    agence_profil = None
    if user.user_type == 'AG':
        agence_profil, created = Agence.objects.get_or_create(user=user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=user)
        agence_form = None
        if user.user_type == 'AG':
            agence_form = AgenceProfileForm(request.POST, instance=agence_profil)

        if user_form.is_valid() and (agence_form is None or agence_form.is_valid()):
            user_form.save()
            if agence_form:
                agence_form.save()
            messages.success(request, "Votre profil a été mis à jour avec succès.")
            return redirect('gestion:profil')
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        user_form = UserUpdateForm(instance=user)
        agence_form = None
        if user.user_type == 'AG':
            agence_form = AgenceProfileForm(instance=agence_profil)

    context = {
        'user_form': user_form,
        'agence_form': agence_form
    }
    return render(request, 'gestion/profil.html', context)

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
                    
                    password = User.objects.make_random_password()

                    proprietaire_user = User.objects.create_user(
                        username=username,
                        password=password,
                        email=cd['email'],
                        first_name=cd['first_name'],
                        last_name=cd['last_name'],
                        telephone=cd['telephone'],
                        addresse=cd['addresse'],
                        user_type='PR'
                    )

                    # 2. Créer le profil Proprietaire (contrat)
                    Proprietaire.objects.create(
                        user=proprietaire_user,
                        agence=agence_profil, # Utilise le profil Agence vérifié
                        taux_commission=cd['taux_commission'],
                        date_debut_contrat=cd['date_debut_contrat'],
                        duree_contrat=cd['duree_contrat']
                    )

                    # 3. Créer le Bien immobilier
                    Bien.objects.create(
                        proprietaire=proprietaire_user,
                        agence=request.user, # Lien vers le compte Agence de l'utilisateur connecté
                        nom=cd['bien_nom'],
                        adresse=cd['bien_adresse'],
                        description=cd['bien_description']
                    )

                messages.success(request, f"Le propriétaire {proprietaire_user.get_full_name()} a été ajouté avec succès. Son mot de passe temporaire est : {password}")
                return redirect('gestion:tableau_de_bord_agence')

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

    # Récupère les biens de ce propriétaire
    biens_du_proprietaire = Bien.objects.filter(proprietaire=proprietaire_user)

    context = {
        'proprietaire_user': proprietaire_user,
        'proprietaire_profil': proprietaire_profil,
        'biens': biens_du_proprietaire,
    }
    return render(request, 'gestion/proprietaire_detail.html', context)