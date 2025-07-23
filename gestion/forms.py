from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth import get_user_model
from django.utils.html import format_html

from .models import Bien, Agence, Proprietaire

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

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'telephone', 'user_type')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
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

class BienForm(forms.ModelForm):
    class Meta:
        model = Bien
        # Exclure 'agence' qui sera défini automatiquement si l'utilisateur est une agence
        fields = ['nom', 'adresse', 'description', 'proprietaire']

    def __init__(self, *args, **kwargs):
        # Récupérer l'utilisateur passé depuis la vue
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Appliquer les classes Bootstrap à tous les champs
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'

        if user:
            if user.user_type == 'AG':
                # L'agence doit sélectionner un propriétaire
                self.fields['proprietaire'].queryset = User.objects.filter(user_type='PR')
                self.fields['proprietaire'].label = "Propriétaire du bien"
            elif user.user_type == 'PR':
                # Pour un propriétaire, le champ est inutile, il sera défini dans la vue
                # On le retire du formulaire pour ne pas l'afficher
                del self.fields['proprietaire']

class UserUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'telephone', 'addresse']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
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

    # Champs pour le modèle Bien
    bien_nom = forms.CharField(label="Désignation du bien immobilier", max_length=200, help_text="Ex: Villa Duplex - Cité des Palmiers")
    bien_adresse = forms.CharField(label="Adresse du bien", max_length=255)
    bien_description = forms.CharField(label="Description du bien", widget=forms.Textarea(attrs={'rows': 3}), required=False)

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
