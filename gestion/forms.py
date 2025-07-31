from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from .models import Agence, Proprietaire, Locataire, Location, Chambre, Immeuble, TypeBien, Paiement, MoyenPaiement

User = get_user_model()

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'form-control',
        'placeholder': "Nom d'utilisateur"
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'form-control',
        'placeholder': 'Mot de passe'
    }))

class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        label="Email",
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    telephone = forms.CharField(
        max_length=20,
        required=True,
        label="Téléphone",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    user_type = forms.ChoiceField(
        choices=User.USER_TYPE_CHOICES,
        required=True,
        widget=forms.RadioSelect,
        label="Type de compte"
    )
    terms_accepted = forms.BooleanField(
        required=True,
        # Le label est défini dynamiquement dans __init__ pour éviter la dépendance circulaire.
        error_messages={'required': "Vous devez accepter les conditions pour continuer."}
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'telephone', 'user_type')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # On définit le label ici pour s'assurer que la résolution de l'URL
        # se fait au moment de l'exécution et non de l'importation.
        self.fields['terms_accepted'].label = format_html(
            "J'ai lu et j'accepte les <a href='#' data-bs-toggle='modal' data-bs-target='#termsModal'>Conditions d'Utilisation</a>"
        )
        self.fields['username'].widget.attrs.update({'class': 'form-control'})
        self.fields['password1'].widget.attrs.update({'class': 'form-control', 'placeholder': '••••••••'})
        self.fields['password1'].label = "Mot de passe"
        self.fields['password2'].widget.attrs.update({'class': 'form-control', 'placeholder': '••••••••'})
        self.fields['password2'].label = "Confirmer le mot de passe"

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.telephone = self.cleaned_data['telephone']
        user.user_type = self.cleaned_data['user_type']
        if commit:
            user.save()
        return user

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['photo_profil', 'first_name', 'last_name', 'email', 'telephone', 'addresse']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

class CustomPasswordChangeForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({'class': 'form-control', 'placeholder': '••••••••'})
        self.fields['old_password'].label = "Ancien mot de passe"
        self.fields['new_password1'].widget.attrs.update({'class': 'form-control', 'placeholder': '••••••••'})
        self.fields['new_password1'].label = "Nouveau mot de passe"
        self.fields['new_password2'].widget.attrs.update({'class': 'form-control', 'placeholder': '••••••••'})
        self.fields['new_password2'].label = "Confirmation du nouveau mot de passe"

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
        fields = ['montant', 'date_paiement', 'mois_couvert', 'moyen_paiement', 'est_valide']
        widgets = {
            'date_paiement': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'montant': "Montant payé (Frcfa)",
            'date_paiement': "Date du paiement",
            'mois_couvert': "Mois du loyer couvert (ex: Août 2024)",
            'est_valide': "Marquer ce paiement comme validé/confirmé"
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'

class AgenceProfileForm(forms.ModelForm):
    class Meta:
        model = Agence
        fields = ['siret']
        labels = {
            'siret': "Numéro de SIRET"
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
    class Meta:
        model = Locataire
        exclude = ['agence']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            field.required = False # Rendre tous les champs optionnels sauf si spécifié dans le modèle
        self.fields['nom'].required = True
        self.fields['prenom'].required = True
        self.fields['telephone'].required = True

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
