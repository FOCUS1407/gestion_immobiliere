from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from .models import (
    CustomUser, Agence, Proprietaire, TypeBien, Immeuble, 
    Locataire, MoyenPaiement, Chambre, Location, Paiement, EtatDesLieux
)
from django.db.models import Count

# Forms for CustomUserAdmin to handle custom fields
class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'user_type', 'telephone', 'addresse')

class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = '__all__'

# Configuration pour le modèle User personnalisé
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser

    list_display = ('username', 'email', 'user_type', 'telephone', 'is_active')
    list_filter = ('user_type', 'is_active')
    search_fields = ('username', 'email', 'telephone')
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Informations personnelles', {'fields': ('first_name', 'last_name', 'email', 'telephone', 'addresse')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions', 'user_type')}),
        ('Dates importantes', {'fields': ('last_login', 'date_joined')}),
    )


# Configuration pour les agences
@admin.register(Agence)
class AgenceAdmin(admin.ModelAdmin):
    list_display = ('user', 'rccm', 'nif', 'date_creation')
    search_fields = ('user__username', 'rccm', 'nif')
    raw_id_fields = ('user',)

# Configuration pour les propriétaires
@admin.register(Proprietaire)
class ProprietaireAdmin(admin.ModelAdmin):
    list_display = ('user', 'agence', 'get_nombre_immeubles', 'taux_commission', 'date_debut_contrat', 'duree_contrat')
    list_filter = ('agence',)
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user', 'agence')

    def get_queryset(self, request):
        """Optimize the queryset by annotating the count of properties."""
        queryset = super().get_queryset(request)
        queryset = queryset.annotate(
            _nombre_immeubles=Count('immeubles')
        )
        return queryset

    def get_nombre_immeubles(self, obj):
        """Return the annotated count."""
        return obj._nombre_immeubles
    get_nombre_immeubles.admin_order_field = '_nombre_immeubles'  # Allows column sorting
    get_nombre_immeubles.short_description = 'Nombre d\'immeubles'  # Sets column header

# Configuration pour les types de bien
@admin.register(TypeBien)
class TypeBienAdmin(admin.ModelAdmin):
    list_display = ('designation',)
    search_fields = ('designation',)

# Configuration pour les immeubles
@admin.register(Immeuble)
class ImmeubleAdmin(admin.ModelAdmin):
    list_display = ('proprietaire', 'type_bien', 'addresse', 'superficie', 'nombre_chambres', 'date_ajout')
    list_filter = ('type_bien', 'proprietaire')
    search_fields = ('addresse',)
    raw_id_fields = ('proprietaire',)
    list_per_page = 20

# Configuration pour les locataires
@admin.register(Locataire)
class LocataireAdmin(admin.ModelAdmin):
    list_display = ('nom', 'prenom', 'telephone', 'email', 'caution', 'date_inscription')
    search_fields = ('nom', 'prenom', 'telephone', 'email')
    list_per_page = 20

# Configuration pour les moyens de paiement
@admin.register(MoyenPaiement)
class MoyenPaiementAdmin(admin.ModelAdmin):
    list_display = ('designation',)
    search_fields = ('designation',)

# Configuration pour les chambres
@admin.register(Chambre)
class ChambreAdmin(admin.ModelAdmin):
    list_display = ('immeuble', 'designation', 'superficie', 'prix_loyer', 'locataire_actuel')
    list_filter = ('immeuble',)
    search_fields = ('designation', 'immeuble__adresse')
    raw_id_fields = ('immeuble', 'locataire')
    
    def locataire_actuel(self, obj):
        return obj.locataire if obj.locataire else "Libre"
    locataire_actuel.short_description = 'Locataire actuel'

# Configuration pour les locations
@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ('chambre', 'locataire', 'date_entree', 'date_sortie', 'moyen_paiement')
    list_filter = ('moyen_paiement',)
    search_fields = ('chambre__designation', 'locataire__nom')
    raw_id_fields = ('chambre', 'locataire')
    list_per_page = 20

# Configuration pour les paiements
@admin.register(Paiement)
class PaiementAdmin(admin.ModelAdmin):
    list_display = ('location', 'montant', 'date_paiement', 'mois_couvert', 'moyen_paiement', 'est_valide')
    list_filter = ('est_valide', 'moyen_paiement')
    search_fields = ('location__chambre__designation', 'location__locataire__nom')
    list_editable = ('est_valide',)
    raw_id_fields = ('location',)
    date_hierarchy = 'date_paiement'
    list_per_page = 30

# Configuration pour les états des lieux
@admin.register(EtatDesLieux)
class EtatDesLieuxAdmin(admin.ModelAdmin):
    list_display = ('location', 'type_etat', 'date_etat', 'document_signe')
    list_filter = ('type_etat', 'date_etat')
    search_fields = ('location__chambre__designation', 'location__locataire__nom')
    raw_id_fields = ('location',)