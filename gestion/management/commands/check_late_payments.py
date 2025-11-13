import locale
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.urls import reverse
from dateutil.relativedelta import relativedelta
from gestion.models import Location, Notification, Paiement, Agence

class Command(BaseCommand):
    help = 'Vérifie les paiements en retard mois par mois et crée des notifications pour les agences.'

    def handle(self, *args, **options):
        self.stdout.write("Début de la vérification des paiements en retard...")

        # Définir la locale en français pour générer les noms de mois correctement
        try:
            locale.setlocale(locale.LC_TIME, 'fr_FR.UTF-8')
        except locale.Error:
            self.stdout.write(self.style.WARNING("Locale 'fr_FR.UTF-8' non trouvée. Utilisation de la locale par défaut."))
            locale.setlocale(locale.LC_TIME, '')

        locations_actives = Location.objects.filter(date_sortie__isnull=True).select_related(
            'chambre__immeuble__proprietaire__agence', 'locataire'
        )
        
        notifications_creees = 0
        today = timezone.now().date()

        for location in locations_actives:
            # Récupérer tous les mois déjà payés et validés pour cette location
            paid_months = set(
                Paiement.objects.filter(location=location, est_valide=True).values_list('mois_couvert', flat=True)
            )

            # Itérer du début de la location jusqu'au mois actuel
            cursor_date = location.date_entree
            
            # On ne vérifie pas le mois en cours si on est avant le 10 du mois (période de grâce)
            end_date_check = today
            if today.day < 10:
                end_date_check = today - relativedelta(months=1)

            while cursor_date <= end_date_check:
                month_str = cursor_date.strftime('%B %Y').capitalize()
                
                # Si le mois n'a pas été payé, il est en retard.
                if month_str not in paid_months:
                    agence = location.chambre.immeuble.proprietaire.agence
                    message = f"Paiement en retard pour {month_str} - Locataire: {location.locataire} ({location.chambre})."
                    
                    # Éviter de créer des doublons de notifications non lues pour le même arriéré
                    if not Notification.objects.filter(agence=agence, message=message, is_read=False).exists():
                        Notification.objects.create(
                            agence=agence, message=message,
                            link=reverse('gestion:chambre_detail', kwargs={'pk': location.chambre.pk})
                        )
                        notifications_creees += 1
                
                # Passer au mois suivant
                cursor_date += relativedelta(months=1)

        self.stdout.write(self.style.SUCCESS(f"Vérification terminée. {notifications_creees} nouvelles notifications de retard créées."))
