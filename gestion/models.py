from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator

def user_profile_pic_path(instance, filename):
    """Génère un chemin de fichier unique pour la photo de profil."""
    # Le fichier sera uploadé dans MEDIA_ROOT/profile_pics/user_<id>/<filename>
    return f'profile_pics/user_{instance.id}/{filename}'

class CustomUser(AbstractUser):
    AGENCE = 'AG'
    PROPRIETAIRE = 'PR'
    USER_TYPE_CHOICES = [
        (AGENCE, 'Agence Immobilière'),
        (PROPRIETAIRE, 'Propriétaire'),
    ]
    user_type = models.CharField(max_length=2, choices=USER_TYPE_CHOICES)
    telephone = models.CharField(max_length=20)
    addresse = models.TextField()
    photo_profil = models.ImageField(upload_to=user_profile_pic_path, null=True, blank=True, verbose_name="Photo de profil")
    must_change_password = models.BooleanField(default=False, verbose_name="Doit changer le mot de passe")

    class Meta:
        db_table = 'gestion_customuser'

    def __str__(self):
        return self.username

class Agence(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    siret = models.CharField(max_length=14, unique=True)
    date_creation = models.DateField(auto_now_add=True)


    def __str__(self):
        return f"{self.user.get_full_name()} (Agence)"

class Proprietaire(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    agence = models.ForeignKey(Agence, on_delete=models.CASCADE, related_name='proprietaires')
    taux_commission = models.DecimalField(max_digits=5, decimal_places=2)
    date_debut_contrat = models.DateField()
    duree_contrat = models.PositiveIntegerField()  # en mois

    def __str__(self):
        return f"{self.user.get_full_name()}"

class TypeBien(models.Model):
    RESIDENTIEL = 'RES'
    COMMERCIAL = 'COM'
    TYPE_CHOICES = [
        (RESIDENTIEL, 'Résidentiel'),
        (COMMERCIAL, 'Commercial'),
    ]
    designation = models.CharField(max_length=3, choices=TYPE_CHOICES, unique=True)

    def __str__(self):
        return self.get_designation_display()

class Immeuble(models.Model):
    proprietaire = models.ForeignKey(Proprietaire, on_delete=models.CASCADE, related_name='immeubles')
    type_bien = models.ForeignKey(TypeBien, on_delete=models.PROTECT)
    addresse = models.TextField()
    superficie = models.DecimalField(max_digits=10, decimal_places=2)  # en m²
    nombre_chambres = models.PositiveIntegerField()
    date_ajout = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Immeuble {self.id} - {self.addresse[:20]}..."

class Locataire(models.Model):
    agence = models.ForeignKey(Agence, on_delete=models.CASCADE, related_name='locataires')
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    telephone = models.CharField(max_length=20)
    raison_sociale = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    caution = models.DecimalField(max_digits=10, decimal_places=2)
    date_inscription = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.prenom} {self.nom}"

class MoyenPaiement(models.Model):
    MOBILE = 'MOB'
    ESPECES = 'ESP'
    VIREMENT = 'VIR'
    TYPE_CHOICES = [
        (MOBILE, 'Mobile Money'),
        (ESPECES, 'Espèces'),
        (VIREMENT, 'Virement Bancaire'),
    ]
    designation = models.CharField(max_length=3, choices=TYPE_CHOICES, unique=True)

    def __str__(self):
        return self.get_designation_display()

class Chambre(models.Model):
    immeuble = models.ForeignKey(Immeuble, on_delete=models.CASCADE, related_name='chambres')
    designation = models.CharField(max_length=100)
    superficie = models.DecimalField(max_digits=6, decimal_places=2)  # en m²
    prix_loyer = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    locataire = models.ForeignKey(Locataire, on_delete=models.SET_NULL, null=True, blank=True, related_name='chambres')
    date_mise_en_location = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"Chambre {self.designation}"

class Location(models.Model):
    chambre = models.ForeignKey(Chambre, on_delete=models.CASCADE, related_name='locations')
    locataire = models.ForeignKey(Locataire, on_delete=models.CASCADE, related_name='locations')
    date_entree = models.DateField()
    date_sortie = models.DateField(null=True, blank=True)
    moyen_paiement = models.ForeignKey(MoyenPaiement, on_delete=models.PROTECT)

    def __str__(self):
        return f"Location {self.chambre} - {self.locataire}"

class Paiement(models.Model):
    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='paiements')
    montant = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    date_paiement = models.DateField()
    mois_couvert = models.CharField(max_length=20)  # Format "MM-YYYY"
    moyen_paiement = models.ForeignKey(MoyenPaiement, on_delete=models.PROTECT)
    est_valide = models.BooleanField(default=False)

    class Meta:
        unique_together = ('location', 'mois_couvert')

    def __str__(self):
        return f"Paiement {self.montant}frcfa - {self.location}"

class Notification(models.Model):
    agence = models.ForeignKey(Agence, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    link = models.URLField(blank=True, null=True, help_text="Lien optionnel vers la ressource concernée")

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Notif pour {self.agence.user.username} - {self.message[:30]}"
