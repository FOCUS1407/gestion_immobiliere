from django import forms
from .models import CustomUser
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm, PasswordResetForm
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q
from .models import Agence, Proprietaire, Locataire, Location, Chambre, Immeuble, Paiement, MoyenPaiement, EtatDesLieux

User = get_user_model()

class ConnexionForm(AuthenticationForm):
    """
    Formulaire de connexion personnalisé qui hérite de l'AuthenticationForm de Django
    pour une gestion sécurisée de l'authentification.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update(
            {'class': 'form-control form-control-lg', 'placeholder': "Nom d'utilisateur"}
        )
        self.fields['password'].widget.attrs.update(
            {'class': 'form-control form-control-lg', 'placeholder': 'Mot de passe'}
        )

class AgenceRegistrationForm(forms.ModelForm):
    """
    Formulaire d'inscription spécifiquement pour les agences.
    Il ne demande que les informations nécessaires et gère la confirmation du mot de passe.
    """
    password = forms.CharField(
        label="Mot de passe",
        widget=forms.PasswordInput,
    )
    confirm_password = forms.CharField(
        label="Confirmer le mot de passe",
        widget=forms.PasswordInput,
    )

    class Meta:
        model = CustomUser
        # Champs demandés lors de l'inscription
        fields = ['first_name', 'last_name', 'email', 'telephone', 'addresse']

    def clean_confirm_password(self):
        """Vérifie que les deux mots de passe sont identiques."""
        password = self.cleaned_data.get("password")
        confirm_password = self.cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Les mots de passe ne correspondent pas.")
        return confirm_password

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['photo_profil', 'first_name', 'last_name', 'email', 'telephone', 'addresse']
        widgets = {
            'addresse': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # Appliquer la classe 'form-control' à tous les champs sauf les cases à cocher
            if not isinstance(field.widget, forms.CheckboxInput):
                cls = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{cls} form-control'.strip()

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control', 'placeholder': '••••••••'})
        self.fields['old_password'].label = "Ancien mot de passe"
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control', 'placeholder': '••••••••'})
        self.fields['new_password1'].label = "Nouveau mot de passe"
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control', 'placeholder': '••••••••'})
        self.fields['new_password2'].label = "Confirmation du nouveau mot de passe"

class CustomPasswordResetForm(PasswordResetForm):
    """
    Formulaire personnalisé pour permettre la réinitialisation par email ou téléphone.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].label = "Email ou numéro de téléphone"
        self.fields['email'].help_text = "Entrez l'adresse email ou le numéro de téléphone associé à votre compte."

    def get_users(self, email):
        """
        Surcharge la méthode pour trouver des utilisateurs par email OU téléphone.
        Le paramètre 'email' contient la saisie de l'utilisateur.
        """
        identifier = email
        return User._default_manager.filter(Q(email__iexact=identifier) | Q(telephone=identifier), is_active=True)

class MoyenPaiementForm(forms.ModelForm):
    """Formulaire pour ajouter un moyen de paiement."""
    class Meta:
        model = MoyenPaiement
        fields = ['designation']
        labels = {
            'designation': "Type de moyen de paiement"
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Utiliser un 'select' car le champ a des 'choices'
        self.fields['designation'].widget.attrs['class'] = 'form-select'

class PaiementForm(forms.ModelForm):
    """Formulaire pour enregistrer un nouveau paiement de loyer."""
    class Meta:
        model = Paiement
        # La 'location' sera définie dans la vue.
        fields = ['montant', 'date_paiement', 'mois_couvert', 'moyen_paiement', 'est_valide', 'preuve_paiement']
        widgets = {
            'date_paiement': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'montant': "Montant payé (Frcfa)",
            'date_paiement': "Date du paiement",
            'mois_couvert': "Mois du loyer couvert (ex: Août 2024)",
            'est_valide': "Marquer ce paiement comme validé/confirmé",
            'preuve_paiement': "Joindre une preuve de paiement (reçu, capture d'écran, etc.)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'
        
        # Amélioration pour Bootstrap 5 : utiliser form-select pour les listes déroulantes
        if 'moyen_paiement' in self.fields:
            self.fields['moyen_paiement'].widget.attrs['class'] = 'form-select'
            
        # Rendre le champ non obligatoire par défaut. La validation se fera dans la méthode clean().
        self.fields['preuve_paiement'].required = False
        self.fields['preuve_paiement'].help_text = "Formats autorisés : PDF, JPG, PNG. Taille maximale : 5 Mo."

    def clean(self):
        cleaned_data = super().clean()
        moyen_paiement = cleaned_data.get('moyen_paiement')
        preuve_paiement = cleaned_data.get('preuve_paiement') # Donnée du formulaire (fichier, None, ou False)

        if moyen_paiement:
            # Définir les moyens de paiement qui nécessitent une preuve
            requires_proof_designations = [MoyenPaiement.MOBILE, MoyenPaiement.VIREMENT, MoyenPaiement.DEPOT_ESPECES]
            
            if moyen_paiement.designation in requires_proof_designations:
                # Une preuve est considérée comme absente si :
                # 1. L'utilisateur coche "Effacer" (`preuve_paiement` est False).
                # 2. L'utilisateur ne téléverse rien (`preuve_paiement` est None) ET il n'y avait pas de fichier avant.
                has_existing_file = self.instance.pk and self.instance.preuve_paiement
                if preuve_paiement is False or (preuve_paiement is None and not has_existing_file):
                    self.add_error('preuve_paiement', "Une preuve de paiement est obligatoire pour ce moyen de paiement.")
        
        return cleaned_data

    def clean_preuve_paiement(self):
        """Valide le type et la taille du fichier de preuve de paiement."""
        preuve = self.cleaned_data.get('preuve_paiement', False)

        # La validation ne s'applique que si un nouveau fichier est téléversé.
        if preuve and hasattr(preuve, 'content_type'):
            # 1. Valider la taille du fichier (ex: limite de 5 Mo)
            if preuve.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Le fichier est trop volumineux. La taille maximale est de 5 Mo.")

            # 2. Valider le type de fichier (MIME type)
            allowed_types = ['application/pdf', 'image/jpeg', 'image/png']
            if preuve.content_type not in allowed_types:
                raise forms.ValidationError("Type de fichier non autorisé. Seuls les PDF et les images (JPG, PNG) sont acceptés.")
        
        return preuve
class EtatDesLieuxForm(forms.ModelForm):
    """Formulaire pour créer un état des lieux."""
    class Meta:
        model = EtatDesLieux
        fields = ['type_etat', 'date_etat', 'description', 'document_signe']
        widgets = {
            'date_etat': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 5}),
        }
        labels = {
            'type_etat': "Type d'état des lieux",
            'date_etat': "Date de l'état des lieux",
            'description': "Description de l'état (murs, sols, équipements, etc.)",
            'document_signe': "Document signé (PDF, Image)"
        }

class AgenceProfileForm(forms.ModelForm):
    class Meta:
        model = Agence
        fields = ['logo']
        labels = {
            'logo': "Logo de l'agence",
        
        }

class ProprietaireProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Proprietaire
        fields = ['taux_commission', 'date_debut_contrat', 'duree_contrat']
        labels = {
            'taux_commission': "Taux de commission (%)",
            'date_debut_contrat': "Date de début du contrat",
            'duree_contrat': "Durée du contrat (en mois)",
        }
        widgets = {
            'date_debut_contrat': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class ProprietaireCreationForm(forms.Form):
    # Champs pour le modèle CustomUser
    first_name = forms.CharField(label="Prénom du propriétaire", max_length=100)
    last_name = forms.CharField(label="Nom du propriétaire", max_length=100)
    email = forms.EmailField(label="Email")
    telephone = forms.CharField(label="Téléphone", max_length=20)
    addresse = forms.CharField(label="Adresse du propriétaire", widget=forms.Textarea(attrs={'rows': 3}))

    # Champs pour le modèle Proprietaire (contrat)
    taux_commission = forms.DecimalField(label="Taux de commission (%)", max_digits=5, decimal_places=2)
    date_debut_contrat = forms.DateField(label="Date de début du contrat", widget=forms.DateInput(attrs={'type': 'date'}))
    duree_contrat = forms.IntegerField(label="Durée du contrat (en mois)")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Appliquer les classes Bootstrap pour un meilleur style
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                cls = field.widget.attrs.get('class', '')
                field.widget.attrs['class'] = f'{cls} form-control'.strip()

    def clean_email(self):
        """Vérifie que l'email n'est pas déjà utilisé."""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un utilisateur avec cet email existe déjà.")
        return email

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['locataire', 'date_entree', 'moyen_paiement']
        widgets = {
            'date_entree': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        agence = kwargs.pop('agence', None)
        super().__init__(*args, **kwargs)

        # Commencer avec un queryset de base pour l'agence actuelle
        if agence:
            base_queryset = Locataire.objects.filter(agence=agence)
        else:
            base_queryset = Locataire.objects.none()

        # Exclure les locataires qui sont déjà dans une chambre
        occupied_tenants_ids = Chambre.objects.filter(locataire__isnull=False).values_list('locataire_id', flat=True)
        self.fields['locataire'].queryset = base_queryset.exclude(pk__in=occupied_tenants_ids)
        
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class LocataireForm(forms.ModelForm):
    """
    Formulaire optimisé pour la création et la modification d'un locataire.
    Hérite des contraintes du modèle et améliore l'expérience utilisateur.
    """
    class Meta:
        model = Locataire
        exclude = ['agence']
        labels = {
            'nom': "Nom de famille",
            'prenom': "Prénom(s)",
            'telephone': "Numéro de téléphone",
            'email': "Adresse e-mail (optionnel)",
            'raison_sociale': "Raison sociale (si entreprise)",
            'caution': "Montant de la caution (Frcfa)",
        }
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Ex: Dupont'}),
            'prenom': forms.TextInput(attrs={'placeholder': 'Ex: Marie'}),
            'telephone': forms.TextInput(attrs={'placeholder': 'Ex: 771234567'}),
            'email': forms.EmailInput(attrs={'placeholder': 'ex: marie.dupont@email.com'}),
            'raison_sociale': forms.TextInput(attrs={'placeholder': 'Ex: Entreprise SARL'}),
            'caution': forms.NumberInput(attrs={'placeholder': 'Ex: 100000'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            # Appliquer la classe 'form-control' à tous les champs
            cls = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f'{cls} form-control'.strip()
            
    def clean_telephone(self):
        """Nettoie et valide le numéro de téléphone pour ne garder que les chiffres."""
        telephone = self.cleaned_data.get('telephone')
        if telephone:
            # Supprime tous les caractères qui ne sont pas des chiffres
            cleaned_phone = ''.join(filter(str.isdigit, telephone))
            if not cleaned_phone:
                raise forms.ValidationError("Le numéro de téléphone doit contenir des chiffres.")
            return cleaned_phone
        return telephone


class ImmeubleForm(forms.ModelForm):
    """Formulaire pour créer ou modifier un immeuble."""
    class Meta:
        model = Immeuble
        # Le propriétaire sera défini automatiquement dans la vue
        fields = ['type_bien', 'addresse', 'superficie', 'nombre_chambres']
        widgets = {
            'addresse': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class ChambreForm(forms.ModelForm):
    """Formulaire pour créer ou modifier une unité locative (chambre)."""
    class Meta:
        model = Chambre
        # L'immeuble sera défini dans la vue et le locataire sera assigné plus tard
        fields = ['designation', 'superficie', 'prix_loyer', 'date_mise_en_location']
        widgets = {
            'date_mise_en_location': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
