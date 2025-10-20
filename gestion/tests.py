from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Agence, Proprietaire, Immeuble, TypeBien, Chambre, Locataire, Location, Paiement, MoyenPaiement, Notification, CustomUser

from django.core.exceptions import ValidationError
from .validators import CustomPasswordValidator
from decimal import Decimal
from django.core.management import call_command
from gestion.views import _get_financial_summary, _get_occupancy_stats
from unittest.mock import patch
from datetime import date

User = get_user_model()

class BaseTestCase(TestCase):
    """
    Une classe de base pour les tests qui configure un environnement commun.
    Crée une agence, un propriétaire, un type de bien et un immeuble.
    """
    @classmethod
    def setUpTestData(cls):
        # Créer les utilisateurs
        cls.agence_user = User.objects.create_user(
            username='agence_test', 
            password='password123', 
            user_type='AG',
            first_name='Agence',
            last_name='Test'
        )
        cls.proprietaire_user = User.objects.create_user(
            username='proprio_test', 
            password='password123', 
            user_type='PR',
            first_name='Proprio',
            last_name='Test'
        )
        
        # Créer le profil Agence
        cls.agence = Agence.objects.create(user=cls.agence_user)

        # Créer les profils associés
        cls.proprietaire = Proprietaire.objects.create(
            user=cls.proprietaire_user, 
            agence=cls.agence,
            taux_commission=5.0,
            date_debut_contrat='2023-01-01',
            duree_contrat=12
        )
        
        # Créer un TypeBien pour les immeubles
        cls.type_bien_res = TypeBien.objects.create(designation=TypeBien.RESIDENTIEL)

        # Créer un Immeuble pour le propriétaire
        cls.immeuble = Immeuble.objects.create(
            proprietaire=cls.proprietaire,
            type_bien=cls.type_bien_res,
            addresse="123 Rue de l'Exemple",
            superficie=100.0,
            nombre_chambres=5
        )

class DashboardViewsTest(BaseTestCase):
    """Teste l'accès aux différents tableaux de bord."""

    def test_agence_dashboard_view_acces_autorise(self):
        """Vérifie que l'agence peut accéder à son tableau de bord."""
        self.client.login(username='agence_test', password='password123')
        response = self.client.get(reverse('gestion:tableau_de_bord_agence'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/tableau_de_bord_agence.html')

    def test_proprietaire_dashboard_view_acces_autorise(self):
        """Vérifie que le propriétaire peut accéder à son tableau de bord."""
        self.client.login(username='proprio_test', password='password123')
        response = self.client.get(reverse('gestion:tableau_de_bord_proprietaire'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/tableau_de_bord_proprietaire.html')

    def test_acces_non_authentifie_redirige_vers_connexion(self):
        """Vérifie que les utilisateurs non connectés sont redirigés."""
        response = self.client.get(reverse('gestion:tableau_de_bord_agence'))
        self.assertRedirects(response, f"{reverse('gestion:connexion')}?next={reverse('gestion:tableau_de_bord_agence')}")

    def test_mauvais_type_utilisateur_est_redirige(self):
        """Vérifie qu'un propriétaire essayant d'accéder au TDB de l'agence est redirigé."""
        self.client.login(username='proprio_test', password='password123')
        response = self.client.get(reverse('gestion:tableau_de_bord_agence'))
        self.assertRedirects(response, reverse('gestion:tableau_de_bord_proprietaire'))

class ProprietaireManagementTest(BaseTestCase):
    """Teste la gestion des propriétaires par l'agence."""

    def test_vue_ajouter_proprietaire_post(self):
        """Teste la création d'un nouveau propriétaire via le formulaire."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:ajouter_proprietaire')
        
        data = {
            'first_name': 'Nouveau', 'last_name': 'Proprio',
            'email': 'nouveau@proprio.com', 'telephone': '0102030405',
            'addresse': 'Nouvelle Adresse', 'taux_commission': 7.5,
            'date_debut_contrat': '2024-01-01', 'duree_contrat': 24
        }
        response = self.client.post(url, data)
        
        self.assertTrue(User.objects.filter(email='nouveau@proprio.com').exists())
        new_user = User.objects.get(email='nouveau@proprio.com')
        self.assertTrue(Proprietaire.objects.filter(user=new_user).exists())
        
        # Vérifie la redirection vers la page de détail du nouveau propriétaire
        self.assertRedirects(response, reverse('gestion:proprietaire_detail', kwargs={'pk': new_user.pk}))

    def test_vue_detail_proprietaire(self):
        """Vérifie que les détails d'un propriétaire et de ses immeubles s'affichent."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:proprietaire_detail', kwargs={'pk': self.proprietaire_user.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.proprietaire_user.first_name)
        self.assertContains(response, self.immeuble.addresse)

class ImmeubleManagementTest(BaseTestCase):
    """Teste la gestion des immeubles."""

    def test_vue_ajouter_immeuble_post(self):
        """Teste l'ajout d'un immeuble à un propriétaire."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:ajouter_immeuble', kwargs={'pk': self.proprietaire_user.pk})
        
        data = {
            'type_bien': self.type_bien_res.pk, 'addresse': '456 Avenue Test',
            'superficie': 250.50, 'nombre_chambres': 10
        }
        response = self.client.post(url, data)
        
        self.assertTrue(Immeuble.objects.filter(addresse='456 Avenue Test').exists())
        self.assertRedirects(response, reverse('gestion:proprietaire_detail', kwargs={'pk': self.proprietaire_user.pk}))

    def test_acces_detail_immeuble_par_proprietaire_et_agence(self):
        """Vérifie que l'agence et le propriétaire peuvent voir les détails de l'immeuble."""
        # Accès par l'agence
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:immeuble_detail', kwargs={'pk': self.immeuble.pk})
        response_agence = self.client.get(url)
        self.assertEqual(response_agence.status_code, 200)

        # Se déconnecter pour garantir un test propre
        self.client.logout()

        # Accès par le propriétaire
        self.client.login(username='proprio_test', password='password123')
        response_proprio = self.client.get(url)
        self.assertEqual(response_proprio.status_code, 200)

class AuthenticationFlowsTest(BaseTestCase):
    """Teste les flux d'authentification comme le changement de mot de passe."""

    def test_password_change_flow(self):
        """
        Vérifie le processus complet de changement de mot de passe pour un utilisateur.
        1. Connexion avec l'ancien mot de passe.
        2. Soumission du formulaire de changement.
        3. Vérification de la redirection.
        4. Déconnexion.
        5. Échec de la connexion avec l'ancien mot de passe.
        6. Succès de la connexion avec le nouveau mot de passe.
        """
        old_password = 'password123'
        new_password = 'un_nouveau_mot_de_passe_securise_456'

        # 1. Connexion avec l'ancien mot de passe
        self.assertTrue(self.client.login(username=self.agence_user.username, password=old_password))

        # 2. Soumission du formulaire de changement
        change_url = reverse('gestion:changer_mdp')
        response = self.client.post(change_url, {
            'old_password': old_password,
            'new_password1': new_password,
            'new_password2': new_password,
        })

        # 3. Vérification de la redirection vers la page de succès
        self.assertRedirects(response, reverse('gestion:changer_mdp_done'))

        # 4. Déconnexion pour tester la nouvelle connexion
        self.client.logout()

        # 5. Échec de la connexion avec l'ancien mot de passe
        login_failed = self.client.login(username=self.agence_user.username, password=old_password)
        self.assertFalse(login_failed, "La connexion avec l'ancien mot de passe aurait dû échouer.")

        # 6. Succès de la connexion avec le nouveau mot de passe
        login_succeeded = self.client.login(username=self.agence_user.username, password=new_password)
        self.assertTrue(login_succeeded, "La connexion avec le nouveau mot de passe a échoué.")

class MiddlewareAndForcePasswordChangeTest(BaseTestCase):
    """
    Teste le middleware et le flux de changement de mot de passe forcé.
    """
    @classmethod
    def setUpTestData(cls):
        # On appelle la méthode parente pour avoir l'environnement de base
        super().setUpTestData()
        # On crée un utilisateur spécifique qui DOIT changer son mot de passe
        cls.user_must_change = User.objects.create_user(
            username='testuser_changepw',
            password='password123',
            user_type='PR',
            must_change_password=True
        )
        Proprietaire.objects.create(
            user=cls.user_must_change,
            agence=cls.agence,
            taux_commission=5.0,
            date_debut_contrat='2023-01-01',
            duree_contrat=12
        )

    def test_middleware_redirects_if_password_change_required(self):
        """
        Vérifie que le middleware redirige un utilisateur qui doit changer son mot de passe
        lorsqu'il tente d'accéder à une page non autorisée (ex: son tableau de bord).
        """
        self.client.login(username='testuser_changepw', password='password123')
        response = self.client.get(reverse('gestion:tableau_de_bord_proprietaire'))
        self.assertRedirects(response, reverse('gestion:changer_mdp'))

    def test_middleware_allows_access_to_change_password_page(self):
        """
        Vérifie que le middleware autorise l'accès à la page de changement de mot de passe.
        """
        self.client.login(username='testuser_changepw', password='password123')
        response = self.client.get(reverse('gestion:changer_mdp'))
        self.assertEqual(response.status_code, 200)

    def test_password_change_disables_flag_and_allows_access(self):
        """
        Vérifie que le changement de mot de passe réussi désactive l'indicateur
        `must_change_password` et autorise l'accès au site.
        """
        self.client.login(username='testuser_changepw', password='password123')
        
        new_password = 'new_secure_password'
        self.client.post(reverse('gestion:changer_mdp'), {
            'old_password': 'password123', 'new_password1': new_password, 'new_password2': new_password,
        })

        self.user_must_change.refresh_from_db()
        self.assertFalse(self.user_must_change.must_change_password, "L'indicateur must_change_password aurait dû être désactivé.")

        self.client.login(username='testuser_changepw', password=new_password)
        response_after_change = self.client.get(reverse('gestion:tableau_de_bord_proprietaire'))
        self.assertEqual(response_after_change.status_code, 200)

class CustomPasswordValidatorTest(TestCase):
    """
    Teste le validateur de mot de passe personnalisé de manière isolée.
    """
    def setUp(self):
        """Initialise le validateur pour chaque test."""
        self.validator = CustomPasswordValidator()

    def test_password_is_valid(self):
        """
        Vérifie qu'un mot de passe avec un chiffre et un symbole est valide.
        """
        try:
            # Ce mot de passe devrait passer la validation sans lever d'erreur.
            self.validator.validate('Password123!')
        except ValidationError:
            self.fail("Le validateur a levé une ValidationError de manière inattendue pour un mot de passe valide.")

    def test_password_missing_digit_is_invalid(self):
        """
        Vérifie qu'un mot de passe sans chiffre est invalide et lève la bonne exception.
        """
        with self.assertRaisesMessage(ValidationError, "Le mot de passe doit contenir au moins un chiffre (0-9)."):
            self.validator.validate('PasswordWithoutDigit!')

    def test_password_missing_symbol_is_invalid(self):
        """
        Vérifie qu'un mot de passe sans symbole est invalide et lève la bonne exception.
        """
        with self.assertRaisesMessage(ValidationError, "Le mot de passe doit contenir au moins un symbole (ex: !@#$%)."):
            self.validator.validate('PasswordWithoutSymbol123')

class CheckLatePaymentsCommandTest(BaseTestCase):
    """
    Teste la commande de gestion `check_late_payments` pour la détection des retards.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.locataire = Locataire.objects.create(agence=cls.agence, nom="Test", prenom="Locataire")
        cls.chambre = Chambre.objects.create(immeuble=cls.immeuble, designation="Unité Test", prix_loyer=1000)
        cls.moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.VIREMENT)

    @patch('django.utils.timezone.now')
    def test_creates_notification_for_past_due_payment(self, mock_now):
        """
        Vérifie qu'une notification est créée pour un mois passé qui n'a pas été payé.
        """
        # On simule être le 15 Mars 2024
        mock_now.return_value.date.return_value = date(2024, 3, 15)
        
        # La location a commencé en Janvier
        location = Location.objects.create(
            chambre=self.chambre, locataire=self.locataire, date_entree='2024-01-01', moyen_paiement=self.moyen_paiement
        )
        # Le paiement de Janvier a été fait, mais pas celui de Février
        Paiement.objects.create(location=location, montant=1000, date_paiement='2024-01-05', mois_couvert='Janvier 2024', est_valide=True)

        call_command('check_late_payments')

        self.assertEqual(Notification.objects.count(), 1)
        notification = Notification.objects.first()
        self.assertIn("Paiement en retard pour Février 2024", notification.message)

    @patch('django.utils.timezone.now')
    def test_no_notification_during_grace_period(self, mock_now):
        """
        Vérifie qu'aucune notification n'est créée pour le mois en cours si on est dans la période de grâce (avant le 10).
        """
        # On simule être le 5 Mars 2024
        mock_now.return_value.date.return_value = date(2024, 3, 5)
        
        Location.objects.create(
            chambre=self.chambre, locataire=self.locataire, date_entree='2024-03-01', moyen_paiement=self.moyen_paiement
        )

        call_command('check_late_payments')

        self.assertEqual(Notification.objects.count(), 0)

    @patch('django.utils.timezone.now')
    def test_notification_after_grace_period(self, mock_now):
        """
        Vérifie qu'une notification est créée pour le mois en cours si la période de grâce est passée.
        """
        # On simule être le 15 Mars 2024
        mock_now.return_value.date-return_value = date(2024, 3, 15)
        
        Location.objects.create(
            chambre=self.chambre, locataire=self.locataire, date_entree='2024-03-01', moyen_paiement=self.moyen_paiement
        )

        call_command('check_late_payments')

        self.assertEqual(Notification.objects.count(), 1)
        self.assertIn("Paiement en retard pour Mars 2024", Notification.objects.first().message)

    def test_no_duplicate_unread_notification(self):
        """
        Vérifie que la commande ne crée pas de doublon si une notification non lue pour le même problème existe déjà.
        """
        location = Location.objects.create(
            chambre=self.chambre, locataire=self.locataire, date_entree='2023-01-01', moyen_paiement=self.moyen_paiement
        )
        
        # Exécuter la commande une première fois
        call_command('check_late_payments')
        self.assertGreater(Notification.objects.count(), 0, "Au moins une notification aurait dû être créée.")
        count_after_first_run = Notification.objects.count()

        # Exécuter la commande une seconde fois
        call_command('check_late_payments')
        self.assertEqual(Notification.objects.count(), count_after_first_run, "Aucune nouvelle notification n'aurait dû être créée.")

class PaiementManagementTest(BaseTestCase):
    """Teste la gestion des paiements par l'agence."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Créer les objets nécessaires pour un paiement
        cls.locataire = Locataire.objects.create(
            agence=cls.agence, nom="Durand", prenom="Jean", telephone="0600000000", caution=50000
        )
        cls.chambre = Chambre.objects.create(
            immeuble=cls.immeuble, designation="Appartement 101", superficie=50, prix_loyer=50000
        )
        cls.moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.ESPECES)
        cls.location = Location.objects.create(
            chambre=cls.chambre, locataire=cls.locataire, date_entree='2024-01-01', moyen_paiement=cls.moyen_paiement
        )
        cls.chambre.locataire = cls.locataire
        cls.chambre.save()
        cls.paiement = Paiement.objects.create(
            location=cls.location, montant=50000, date_paiement='2024-08-01',
            mois_couvert='Août 2024', moyen_paiement=cls.moyen_paiement, est_valide=True
        )

    def test_supprimer_paiement_get_page(self):
        """Vérifie que la page de confirmation de suppression s'affiche correctement."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:supprimer_paiement', kwargs={'pk': self.paiement.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/paiement_confirm_delete.html')
        self.assertContains(response, "Confirmer la suppression")

    def test_supprimer_paiement_post(self):
        """Vérifie que la suppression d'un paiement via POST fonctionne et redirige."""
        self.client.login(username='agence_test', password='password123')
        
        paiement_count_before = Paiement.objects.count()
        self.assertEqual(paiement_count_before, 1)

        url = reverse('gestion:supprimer_paiement', kwargs={'pk': self.paiement.pk})
        response = self.client.post(url)

        # Vérifier la redirection vers la page de détail de l'unité
        self.assertRedirects(response, reverse('gestion:chambre_detail', kwargs={'pk': self.chambre.pk}))

        # Vérifier que le paiement a bien été supprimé de la base de données
        self.assertEqual(Paiement.objects.count(), 0)

        # Vérifier que le message de succès est affiché après la redirection
        response_redirected = self.client.get(reverse('gestion:chambre_detail', kwargs={'pk': self.chambre.pk}))
        self.assertContains(response_redirected, "Le paiement a été supprimé avec succès.")

    def test_supprimer_paiement_permission_denied_for_proprietaire(self):
        """Vérifie qu'un utilisateur non-agence (ex: propriétaire) ne peut pas supprimer un paiement."""
        self.client.login(username='proprio_test', password='password123')
        url = reverse('gestion:supprimer_paiement', kwargs={'pk': self.paiement.pk})
        response = self.client.post(url)
        # Le décorateur @login_required et la vérification de permission doivent renvoyer un 403 Forbidden
        self.assertEqual(response.status_code, 403)
        # S'assurer que le paiement n'a pas été supprimé
        self.assertTrue(Paiement.objects.filter(pk=self.paiement.pk).exists())

class ChambreManagementTest(BaseTestCase):
    """Teste la gestion des unités (chambres) par l'agence."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Créer une chambre pour les tests
        cls.chambre = Chambre.objects.create(
            immeuble=cls.immeuble,
            designation="Appartement A1",
            superficie="45.50",
            prix_loyer="50000.00",
            date_mise_en_location='2024-01-01'
        )

    def test_get_modifier_chambre_page(self):
        """Vérifie que la page de modification d'une unité s'affiche correctement."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:modifier_chambre', kwargs={'pk': self.chambre.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/modifier_chambre.html')
        self.assertContains(response, "Modifier l'unité locative")
        self.assertContains(response, self.chambre.designation)

    def test_post_modifier_chambre_success(self):
        """Vérifie que la modification d'une unité via POST fonctionne."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:modifier_chambre', kwargs={'pk': self.chambre.pk})
        
        new_data = {
            'designation': 'Studio Rénové A1',
            'superficie': '48.00',
            'prix_loyer': '55000.00',
            'date_mise_en_location': '2024-02-01'
        }
        
        response = self.client.post(url, new_data)
        self.assertRedirects(response, reverse('gestion:immeuble_detail', kwargs={'pk': self.immeuble.pk}))
        
        self.chambre.refresh_from_db()
        self.assertEqual(self.chambre.designation, new_data['designation'])
        self.assertEqual(str(self.chambre.superficie), new_data['superficie'])
        self.assertEqual(str(self.chambre.prix_loyer), new_data['prix_loyer'])
        self.assertEqual(self.chambre.date_mise_en_location.strftime('%Y-%m-%d'), new_data['date_mise_en_location'])

    def test_modifier_chambre_permission_denied_for_proprietaire(self):
        """Vérifie qu'un propriétaire ne peut pas modifier une unité."""
        self.client.login(username='proprio_test', password='password123')
        url = reverse('gestion:modifier_chambre', kwargs={'pk': self.chambre.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_get_supprimer_chambre_page(self):
        """Vérifie que la page de confirmation de suppression s'affiche."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:supprimer_chambre', kwargs={'pk': self.chambre.pk})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/chambre_confirm_delete.html')
        self.assertContains(response, "Confirmer la suppression")

    def test_post_supprimer_chambre_success(self):
        """Vérifie que la suppression d'une unité via POST fonctionne."""
        self.client.login(username='agence_test', password='password123')
        
        chambre_count_before = Chambre.objects.count()
        
        url = reverse('gestion:supprimer_chambre', kwargs={'pk': self.chambre.pk})
        response = self.client.post(url)
        
        self.assertRedirects(response, reverse('gestion:immeuble_detail', kwargs={'pk': self.immeuble.pk}))
        self.assertEqual(Chambre.objects.count(), chambre_count_before - 1)
        
        # Suivre la redirection pour vérifier le message de succès
        response_redirected = self.client.get(reverse('gestion:immeuble_detail', kwargs={'pk': self.immeuble.pk}))
        self.assertContains(response_redirected, "L'unité 'Appartement A1' a été supprimée avec succès.")

    def test_supprimer_chambre_permission_denied_for_proprietaire(self):
        """Vérifie qu'un propriétaire ne peut pas supprimer une unité."""
        self.client.login(username='proprio_test', password='password123')
        url = reverse('gestion:supprimer_chambre', kwargs={'pk': self.chambre.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Chambre.objects.filter(pk=self.chambre.pk).exists())

class FinancialReportTest(BaseTestCase):
    """Teste les vues de rapport financier."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Créer des données pour le rapport
        cls.locataire = Locataire.objects.create(agence=cls.agence, nom="Payeur", prenom="Bon")
        cls.chambre = Chambre.objects.create(
            immeuble=cls.immeuble, designation="Unité A", prix_loyer=Decimal('100000')
        )
        cls.moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.ESPECES)
        cls.location = Location.objects.create(
            chambre=cls.chambre, locataire=cls.locataire, date_entree='2024-01-01', moyen_paiement=cls.moyen_paiement
        )
        cls.chambre.locataire = cls.locataire
        cls.chambre.save()
        
        # Créer un paiement pour un mois spécifique
        Paiement.objects.create(
            location=cls.location, montant=Decimal('100000'), date_paiement='2024-08-05',
            mois_couvert='Août 2024', moyen_paiement=cls.moyen_paiement, est_valide=True
        )

    def test_rapport_financier_view_loads_correctly(self):
        """Vérifie que la vue du rapport financier s'affiche avec les bonnes données."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:rapport_financier') + '?mois=2024-08'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/rapport_financier.html')
        
        # Vérifier que les données du rapport sont bien dans le contexte après la correction
        self.assertIn('report_details', response.context)
        self.assertEqual(response.context['grand_total_paye'], Decimal('100000'))

    def test_generer_rapport_financier_pdf_with_owner_filter(self):
        """Vérifie que la génération du PDF du rapport financier fonctionne et que le nom du fichier est correct."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:generer_rapport_financier_pdf') + f'?mois=2024-08&proprietaire_id={self.proprietaire.pk}'
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Le nom du propriétaire est "Proprio Test"
        expected_filename = 'rapport_financier_Proprio_Test_2024-08.pdf'
        self.assertIn(f'attachment; filename="{expected_filename}"', response['Content-Disposition'])

    @patch('gestion.views.HTML')
    def test_rapport_financier_pdf_content_shows_filtered_owner(self, mock_html):
        """Vérifie que le nom du propriétaire filtré apparaît dans le contenu HTML du PDF."""
        mock_html.return_value.write_pdf.return_value = b'fake-pdf-content'

        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:generer_rapport_financier_pdf') + f'?mois=2024-08&proprietaire_id={self.proprietaire.pk}'
        self.client.get(url)

        # Récupérer le HTML qui aurait été rendu en PDF
        html_content = mock_html.call_args[1]['string']

        # Vérifier que le nom du propriétaire est bien présent dans le titre
        self.assertIn(f"Rapport pour le propriétaire : {self.proprietaire_user.get_full_name()}", html_content)

    @patch('gestion.views.HTML')
    def test_rapport_financier_pdf_content_no_owner_filter(self, mock_html):
        """Vérifie que le nom du propriétaire n'apparaît pas si aucun filtre n'est appliqué."""
        mock_html.return_value.write_pdf.return_value = b'fake-pdf-content'

        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:generer_rapport_financier_pdf') + '?mois=2024-08'
        self.client.get(url)

        html_content = mock_html.call_args[1]['string']

        # Vérifier que la mention du propriétaire est absente
        self.assertNotIn("Rapport pour le propriétaire", html_content)

    @patch('gestion.views.HTML')
    def test_rapport_financier_pdf_content_adapts_when_filtered(self, mock_html):
        """Vérifie que les titres du PDF s'adaptent lorsqu'un filtre propriétaire est appliqué."""
        mock_html.return_value.write_pdf.return_value = b'fake-pdf-content'

        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:generer_rapport_financier_pdf') + f'?mois=2024-08&proprietaire_id={self.proprietaire.pk}'
        self.client.get(url)

        html_content = mock_html.call_args[1]['string']

        # Le titre h2 de la section propriétaire doit être absent car redondant
        self.assertNotIn(f"<h2>Propriétaire : {self.proprietaire_user.get_full_name()}</h2>", html_content)
        # La section de résumé général doit être absente car les totaux sont déjà dans le tableau principal
        self.assertNotIn('<div class="grand-total-section">', html_content)

    @patch('gestion.views.HTML')
    def test_rapport_financier_pdf_content_shows_all_titles_when_not_filtered(self, mock_html):
        """Vérifie que les titres par défaut sont présents quand aucun filtre n'est appliqué."""
        mock_html.return_value.write_pdf.return_value = b'fake-pdf-content'

        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:generer_rapport_financier_pdf') + '?mois=2024-08'
        self.client.get(url)

        html_content = mock_html.call_args[1]['string']

        # Le titre h2 de la section propriétaire doit être présent car il n'y a pas de filtre global
        self.assertIn(f"<h2>Propriétaire : {self.proprietaire_user.get_full_name()}</h2>", html_content)
        # La section de résumé général doit être présente
        self.assertIn('<div class="grand-total-section">', html_content)

class HistoriquePaiementLocataireTest(BaseTestCase):
    """
    Teste les vues liées à l'historique des paiements d'un locataire.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.locataire = Locataire.objects.create(agence=cls.agence, nom="Dupont", prenom="Marie")
        cls.chambre = Chambre.objects.create(immeuble=cls.immeuble, designation="C101", prix_loyer=Decimal('75000'))
        cls.moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.ESPECES)
        cls.location = Location.objects.create(
            chambre=cls.chambre, locataire=cls.locataire, date_entree='2024-01-01', moyen_paiement=cls.moyen_paiement
        )
        cls.paiement = Paiement.objects.create(
            location=cls.location, montant=Decimal('75000'), date_paiement='2024-03-05',
            mois_couvert='Mars 2024', moyen_paiement=cls.moyen_paiement, est_valide=True
        )

    def test_historique_paiement_locataire_mois_view_with_payment(self):
        """
        Vérifie que la vue affiche correctement les détails d'un mois où un paiement a été effectué.
        """
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:historique_paiement_locataire_mois', args=[self.locataire.pk, 2024, 3])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/historique_paiement_locataire_mois.html')
        self.assertContains(response, "Paiement de Marie Dupont pour Mars 2024")
        self.assertContains(response, "75000") # Montant du paiement
        self.assertIn('paiement', response.context)
        self.assertEqual(response.context['paiement'], self.paiement)

    def test_historique_paiement_locataire_mois_view_without_payment(self):
        """
        Vérifie que la vue gère un mois où aucun paiement n'a été effectué.
        """
        self.client.login(username='agence_test', password='password123')
        # Février 2024 n'a pas de paiement enregistré
        url = reverse('gestion:historique_paiement_locataire_mois', args=[self.locataire.pk, 2024, 2])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Paiement de Marie Dupont pour Février 2024")
        self.assertContains(response, "Aucun paiement enregistré pour ce mois.")
        self.assertIsNone(response.context['paiement'])

    def test_historique_paiement_locataire_mois_permission_denied(self):
        """
        Vérifie qu'un propriétaire ne peut pas accéder à la vue.
        """
        self.client.login(username='proprio_test', password='password123')
        url = reverse('gestion:historique_paiement_locataire_mois', args=[self.locataire.pk, 2024, 3])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_historique_paiement_locataire_mois_invalid_date(self):
        """
        Vérifie que la vue redirige avec une erreur si la date est invalide (ex: mois 13).
        """
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:historique_paiement_locataire_mois', args=[self.locataire.pk, 2024, 13])
        response = self.client.get(url)
        self.assertRedirects(response, reverse('gestion:gerer_locataires'))

class FinancialSummaryHelperTest(BaseTestCase):
    """
    Teste la fonction d'aide `_get_financial_summary` pour garantir l'exactitude des calculs.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Propriétaire 2 avec un taux de commission différent
        cls.proprietaire_user_2 = User.objects.create_user(username='proprio2', password='password123', user_type='PR')
        cls.proprietaire_2 = Proprietaire.objects.create(
            user=cls.proprietaire_user_2, agence=cls.agence, taux_commission=Decimal('10.0')
        )

        # Immeubles et Chambres
        cls.immeuble_1 = cls.immeuble # Réutiliser l'immeuble du propriétaire 1
        cls.immeuble_2 = Immeuble.objects.create(proprietaire=cls.proprietaire_2, type_bien=cls.type_bien_res, addresse="456 Rue Test")

        cls.chambre_1 = Chambre.objects.create(immeuble=cls.immeuble_1, designation="A101", prix_loyer=Decimal('50000'))
        cls.chambre_2 = Chambre.objects.create(immeuble=cls.immeuble_1, designation="A102", prix_loyer=Decimal('60000')) # Location inactive
        cls.chambre_3 = Chambre.objects.create(immeuble=cls.immeuble_2, designation="B201", prix_loyer=Decimal('75000'))

        # Locataires et Locations
        cls.locataire_1 = Locataire.objects.create(agence=cls.agence, nom="Locataire", prenom="Un")
        cls.locataire_2 = Locataire.objects.create(agence=cls.agence, nom="Locataire", prenom="Deux")
        cls.locataire_3 = Locataire.objects.create(agence=cls.agence, nom="Locataire", prenom="Trois")

        cls.moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.ESPECES)

        # Location 1 (active)
        cls.location_1 = Location.objects.create(chambre=cls.chambre_1, locataire=cls.locataire_1, date_entree='2024-01-01', moyen_paiement=cls.moyen_paiement)
        # Location 2 (inactive)
        cls.location_2 = Location.objects.create(chambre=cls.chambre_2, locataire=cls.locataire_2, date_entree='2024-01-01', date_sortie='2024-06-30', moyen_paiement=cls.moyen_paiement)
        # Location 3 (active)
        cls.location_3 = Location.objects.create(chambre=cls.chambre_3, locataire=cls.locataire_3, date_entree='2024-02-01', moyen_paiement=cls.moyen_paiement)

        # Paiements pour "Août 2024"
        cls.month_str = "Août 2024"
        # Paiement valide pour la location 1
        Paiement.objects.create(location=cls.location_1, montant=Decimal('50000'), date_paiement='2024-08-05', mois_couvert=cls.month_str, est_valide=True, moyen_paiement=cls.moyen_paiement)
        # Paiement valide pour la location 3
        Paiement.objects.create(location=cls.location_3, montant=Decimal('70000'), date_paiement='2024-08-03', mois_couvert=cls.month_str, est_valide=True, moyen_paiement=cls.moyen_paiement)
        # Paiement non valide
        Paiement.objects.create(location=cls.location_1, montant=Decimal('50000'), date_paiement='2024-07-05', mois_couvert="Juillet 2024", est_valide=False, moyen_paiement=cls.moyen_paiement)
        # Paiement pour un autre mois
        Paiement.objects.create(location=cls.location_1, montant=Decimal('50000'), date_paiement='2024-07-05', mois_couvert="Juillet 2024", est_valide=True, moyen_paiement=cls.moyen_paiement)

    def test_get_financial_summary_calculates_correctly(self):
        """
        Vérifie que la fonction calcule correctement le total attendu, payé et la commission.
        """
        summary = _get_financial_summary(self.agence, self.month_str)

        # 1. Total attendu : somme des loyers des locations ACTIVES uniquement
        # chambre_1 (50000) + chambre_3 (75000) = 125000
        # chambre_2 (60000) est ignorée car sa location est inactive.
        self.assertEqual(summary['total_attendu'], Decimal('125000.00'))

        # 2. Total payé : somme des paiements VALIDES pour le mois "Août 2024"
        # paiement location 1 (50000) + paiement location 3 (70000) = 120000
        self.assertEqual(summary['total_paye'], Decimal('120000.00'))

        # 3. Commission : calculée sur les paiements valides du mois
        # Commission proprio 1 (taux 5%): 50000 * 0.05 = 2500
        # Commission proprio 2 (taux 10%): 70000 * 0.10 = 7000
        # Total commission = 2500 + 7000 = 9500
        self.assertEqual(summary['commission'], Decimal('9500.00'))

    def test_get_financial_summary_no_payments(self):
        """
        Vérifie que la fonction retourne des zéros pour les paiements et la commission si aucun paiement n'a été fait pour le mois.
        """
        summary = _get_financial_summary(self.agence, "Septembre 2024")

        # Le total attendu reste le même car il dépend des locations actives, pas des paiements.
        self.assertEqual(summary['total_attendu'], Decimal('125000.00'))
        self.assertEqual(summary['total_paye'], Decimal('0.00'))
        self.assertEqual(summary['commission'], Decimal('0.00'))

    def test_get_financial_summary_no_agence_profil(self):
        """
        Vérifie que la fonction retourne des zéros si aucun profil d'agence n'est fourni.
        """
        summary = _get_financial_summary(None, self.month_str)

        self.assertEqual(summary['total_attendu'], Decimal('0.00'))
        self.assertEqual(summary['total_paye'], Decimal('0.00'))
        self.assertEqual(summary['commission'], Decimal('0.00'))

    def test_get_financial_summary_no_active_locations(self):
        """
        Vérifie que la fonction retourne des zéros si l'agence n'a aucune location active.
        """
        # Créer une nouvelle agence sans aucune donnée
        other_agence_user = CustomUser.objects.create_user(username='agence_vide', password='password123', user_type='AG')
        other_agence = Agence.objects.create(user=other_agence_user)

        summary = _get_financial_summary(other_agence, self.month_str)

        self.assertEqual(summary['total_attendu'], Decimal('0.00'))
        self.assertEqual(summary['total_paye'], Decimal('0.00'))
        self.assertEqual(summary['commission'], Decimal('0.00'))

class OccupancyStatsHelperTest(BaseTestCase):
    """
    Teste la fonction d'aide `_get_occupancy_stats` pour garantir l'exactitude des statistiques d'occupation.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Créer des unités et des locations pour les tests
        cls.chambre_occupee = Chambre.objects.create(immeuble=cls.immeuble, designation="OCC-101", prix_loyer=1)
        cls.chambre_libre = Chambre.objects.create(immeuble=cls.immeuble, designation="LIB-102", prix_loyer=1)
        cls.chambre_liberee = Chambre.objects.create(immeuble=cls.immeuble, designation="LIB-103", prix_loyer=1)
        cls.chambre_autre_proprio = Chambre.objects.create(immeuble=cls.immeuble, designation="OCC-104", prix_loyer=1)

        locataire1 = Locataire.objects.create(agence=cls.agence, nom="Occupant", prenom="Un")
        locataire2 = Locataire.objects.create(agence=cls.agence, nom="Ancien", prenom="Occupant")
        locataire3 = Locataire.objects.create(agence=cls.agence, nom="Occupant", prenom="Deux")
        moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.ESPECES)

        # Location active pour chambre_occupee
        Location.objects.create(chambre=cls.chambre_occupee, locataire=locataire1, date_entree='2024-01-01', moyen_paiement=moyen_paiement)
        # Location active pour chambre_autre_proprio
        Location.objects.create(chambre=cls.chambre_autre_proprio, locataire=locataire3, date_entree='2024-01-01', moyen_paiement=moyen_paiement)
        # Location terminée pour chambre_liberee
        Location.objects.create(chambre=cls.chambre_liberee, locataire=locataire2, date_entree='2023-01-01', date_sortie='2023-12-31', moyen_paiement=moyen_paiement)

    def test_get_occupancy_stats_calculates_correctly(self):
        """
        Vérifie que les statistiques sont calculées correctement avec un mélange d'unités.
        """
        # L'agence gère 4 chambres au total pour ce propriétaire.
        # 2 sont occupées (chambre_occupee, chambre_autre_proprio)
        # 2 sont libres (chambre_libre, chambre_liberee)
        stats = _get_occupancy_stats(self.agence)

        self.assertEqual(stats['total_units'], 4)
        self.assertEqual(stats['occupied_units'], 2)
        self.assertEqual(stats['free_units'], 2)
        self.assertAlmostEqual(stats['occupancy_rate'], 50.0)

    def test_get_occupancy_stats_no_agence(self):
        """
        Vérifie que la fonction retourne des zéros si aucun profil d'agence n'est fourni.
        """
        stats = _get_occupancy_stats(None)
        self.assertEqual(stats['total_units'], 0)
        self.assertEqual(stats['occupied_units'], 0)
        self.assertEqual(stats['free_units'], 0)
        self.assertEqual(stats['occupancy_rate'], 0)

    def test_get_occupancy_stats_no_units(self):
        """
        Vérifie que la fonction retourne des zéros pour une agence sans aucune unité.
        """
        new_agence_user = User.objects.create_user(username='agence_neuve', password='password123', user_type='AG')
        new_agence = Agence.objects.create(user=new_agence_user)
        stats = _get_occupancy_stats(new_agence)
        self.assertEqual(stats['total_units'], 0)
        self.assertEqual(stats['occupied_units'], 0)
        self.assertEqual(stats['free_units'], 0)
        self.assertEqual(stats['occupancy_rate'], 0)

    def test_proprietaire_can_download_own_report(self):
        """Vérifie qu'un propriétaire connecté peut télécharger son propre rapport PDF."""
        # Connexion en tant que propriétaire
        self.client.login(username='proprio_test', password='password123')
        
        # L'URL n'a pas besoin de paramètres, la vue identifie l'utilisateur
        url = reverse('gestion:generer_rapport_financier_pdf')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        
        # Vérifier que le nom du fichier est correct pour le propriétaire connecté
        expected_filename = 'rapport_historique_Proprio_Test.pdf'
        self.assertIn(f'attachment; filename="{expected_filename}"', response['Content-Disposition'])

class TableauDeBordAgenceViewTest(BaseTestCase):
    """
    Teste la vue `tableau_de_bord_agence`, en particulier les filtres, la recherche et la pagination.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Créer des données supplémentaires pour tester les filtres et la pagination
        
        # Propriétaire 2
        cls.proprio_user_2 = User.objects.create_user(username='proprio_unique', password='password123', user_type='PR', first_name="Zoe", last_name="Unique")
        cls.proprio_2 = Proprietaire.objects.create(user=cls.proprio_user_2, agence=cls.agence, taux_commission=10)

        # Immeuble pour propriétaire 2
        cls.immeuble_2 = Immeuble.objects.create(proprietaire=cls.proprio_2, type_bien=cls.type_bien_res, addresse="789 Rue Filtrage")

        # Créer plusieurs chambres pour tester la pagination et les filtres
        cls.chambre_occupee = Chambre.objects.create(immeuble=cls.immeuble, designation="OCC-01", prix_loyer=1)
        cls.chambre_libre_1 = Chambre.objects.create(immeuble=cls.immeuble, designation="LIB-01", prix_loyer=1)
        cls.chambre_libre_2 = Chambre.objects.create(immeuble=cls.immeuble, designation="LIB-02", prix_loyer=1)
        cls.chambre_libre_3 = Chambre.objects.create(immeuble=cls.immeuble, designation="LIB-03", prix_loyer=1)
        cls.chambre_libre_4 = Chambre.objects.create(immeuble=cls.immeuble, designation="LIB-04", prix_loyer=1)
        cls.chambre_libre_5 = Chambre.objects.create(immeuble=cls.immeuble, designation="LIB-05", prix_loyer=1)
        cls.chambre_proprio_2 = Chambre.objects.create(immeuble=cls.immeuble_2, designation="FILTRE-P2", prix_loyer=1)

        # Créer une location pour la chambre occupée
        locataire = Locataire.objects.create(agence=cls.agence, nom="Test", prenom="Occupant")
        moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.VIREMENT)
        Location.objects.create(chambre=cls.chambre_occupee, locataire=locataire, date_entree='2024-01-01', moyen_paiement=moyen_paiement)

        cls.url = reverse('gestion:tableau_de_bord_agence')

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_view_loads_correctly(self):
        """Vérifie que la page du tableau de bord se charge correctement."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/tableau_de_bord_agence.html')

    def test_chambres_pagination(self):
        """Vérifie que la pagination des unités est appliquée (5 par page)."""
        response = self.client.get(self.url)
        self.assertIn('chambres', response.context)
        # Nous avons 7 chambres au total, la première page doit en contenir 5.
        self.assertEqual(len(response.context['chambres']), 5)

    def test_filter_chambres_by_status_occupees(self):
        """Vérifie que le filtre 'statut=occupees' ne retourne que les unités occupées."""
        response = self.client.get(self.url, {'statut': 'occupees'})
        self.assertEqual(response.status_code, 200)
        chambres_list = response.context['chambres']
        self.assertEqual(len(chambres_list), 1)
        self.assertEqual(chambres_list[0], self.chambre_occupee)

    def test_filter_chambres_by_status_libres(self):
        """Vérifie que le filtre 'statut=libres' ne retourne que les unités libres."""
        response = self.client.get(self.url, {'statut': 'libres'})
        self.assertEqual(response.status_code, 200)
        chambres_list = response.context['chambres']
        # Nous avons 6 chambres libres au total, la pagination en affiche 5.
        self.assertEqual(len(chambres_list), 5)
        self.assertNotIn(self.chambre_occupee, chambres_list)

    def test_search_chambres_by_designation(self):
        """Vérifie que la recherche par désignation d'unité ('q_unite') fonctionne."""
        response = self.client.get(self.url, {'q_unite': 'OCC-01'})
        self.assertEqual(response.status_code, 200)
        chambres_list = response.context['chambres']
        self.assertEqual(len(chambres_list), 1)
        self.assertEqual(chambres_list[0].designation, 'OCC-01')

    def test_filter_chambres_by_proprietaire(self):
        """Vérifie que le filtre par propriétaire sur les unités fonctionne."""
        response = self.client.get(self.url, {'unite_proprietaire_id': self.proprio_2.pk})
        self.assertEqual(response.status_code, 200)
        chambres_list = response.context['chambres']
        self.assertEqual(len(chambres_list), 1)
        self.assertEqual(chambres_list[0], self.chambre_proprio_2)

    def test_search_proprietaires_by_name(self):
        """Vérifie que la recherche par nom de propriétaire ('q_proprietaire') fonctionne."""
        response = self.client.get(self.url, {'q_proprietaire': 'Unique'})
        self.assertEqual(response.status_code, 200)
        proprietaires_list = response.context['proprietaires_page']
        self.assertEqual(len(proprietaires_list), 1)
        self.assertEqual(proprietaires_list[0].user, self.proprio_user_2)

    # --- Tests pour les requêtes HTMX ---

    def test_htmx_request_for_chambres_returns_partial(self):
        """Vérifie qu'une requête HTMX pour filtrer les chambres retourne le bon partiel."""
        headers = {'HTTP_HX-Request': 'true'}
        response = self.client.get(self.url, {'statut': 'libres'}, **headers)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/partials/_unit_status_wrapper.html')
        # Le template de base ne doit pas être utilisé
        self.assertTemplateNotUsed(response, 'gestion/tableau_de_bord_agence.html')

    def test_htmx_request_for_proprietaires_returns_partial(self):
        """Vérifie qu'une requête HTMX pour rechercher un propriétaire retourne le bon partiel."""
        headers = {'HTTP_HX-Request': 'true'}
        response = self.client.get(self.url, {'q_proprietaire': 'Unique'}, **headers)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/partials/_proprietaires_list.html')
        self.assertTemplateNotUsed(response, 'gestion/tableau_de_bord_agence.html')

    def test_htmx_request_for_financial_report_returns_partial(self):
        """Vérifie qu'une requête HTMX pour le rapport financier retourne le bon partiel."""
        headers = {'HTTP_HX-Request': 'true'}
        response = self.client.get(self.url, {'source': 'financial_report', 'mois': '2024-08'}, **headers)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/partials/_financial_report_table.html')
        self.assertTemplateNotUsed(response, 'gestion/tableau_de_bord_agence.html')

class RapportDetailleLoyersViewTest(BaseTestCase):
    """
    Teste la vue `rapport_detaille_loyers` pour vérifier les permissions, les filtres et l'exactitude des données.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Propriétaire 2
        cls.proprio_user_2 = User.objects.create_user(username='proprio2_rapport', password='password123', user_type='PR', first_name="Alice", last_name="Martin")
        cls.proprio_2 = Proprietaire.objects.create(user=cls.proprio_user_2, agence=cls.agence, taux_commission=10)
        cls.immeuble_2 = Immeuble.objects.create(proprietaire=cls.proprio_2, type_bien=cls.type_bien_res, addresse="101 Rue du Rapport")

        # Unités
        cls.chambre_p1 = Chambre.objects.create(immeuble=cls.immeuble, designation="P1-A1", prix_loyer=Decimal('100000'))
        cls.chambre_p2 = Chambre.objects.create(immeuble=cls.immeuble_2, designation="P2-B1", prix_loyer=Decimal('150000'))
        cls.chambre_p1_impaye = Chambre.objects.create(immeuble=cls.immeuble, designation="P1-A2", prix_loyer=Decimal('50000'))

        # Locataires et Locations
        locataire1 = Locataire.objects.create(agence=cls.agence, nom="Payeur", prenom="Total")
        locataire2 = Locataire.objects.create(agence=cls.agence, nom="Payeur", prenom="Autre")
        locataire3 = Locataire.objects.create(agence=cls.agence, nom="Debiteur", prenom="Partiel")
        moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.VIREMENT)

        loc1 = Location.objects.create(chambre=cls.chambre_p1, locataire=locataire1, date_entree='2024-01-01', moyen_paiement=moyen_paiement)
        loc2 = Location.objects.create(chambre=cls.chambre_p2, locataire=locataire2, date_entree='2024-01-01', moyen_paiement=moyen_paiement)
        loc3 = Location.objects.create(chambre=cls.chambre_p1_impaye, locataire=locataire3, date_entree='2024-01-01', moyen_paiement=moyen_paiement)

        # Paiements pour "Août 2024"
        Paiement.objects.create(location=loc1, montant=Decimal('100000'), date_paiement='2024-08-05', mois_couvert='Août 2024', est_valide=True, moyen_paiement=moyen_paiement)
        Paiement.objects.create(location=loc2, montant=Decimal('150000'), date_paiement='2024-08-03', mois_couvert='Août 2024', est_valide=True, moyen_paiement=moyen_paiement)
        # Pas de paiement pour loc3 en Août

        cls.url = reverse('gestion:rapport_detaille_loyers')

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_permission_denied_for_proprietaire(self):
        """Vérifie qu'un propriétaire ne peut pas accéder à cette vue."""
        self.client.login(username='proprio_test', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_view_loads_with_all_owners_data(self):
        """Vérifie que la vue se charge avec les données de tous les propriétaires pour le mois sélectionné."""
        response = self.client.get(self.url, {'mois': '2024-08'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/rapport_detaille_loyers.html')

        # Doit contenir les 3 locations actives
        self.assertEqual(len(response.context['monthly_rent_details']), 3)
        # Vérifier les totaux globaux
        self.assertEqual(response.context['totals']['attendu'], Decimal('300000')) # 100k + 150k + 50k
        self.assertEqual(response.context['totals']['paye'], Decimal('250000')) # 100k + 150k
        self.assertEqual(response.context['totals']['impaye'], Decimal('50000'))

    def test_filter_by_proprietaire(self):
        """Vérifie que le filtre par propriétaire fonctionne correctement."""
        # On filtre sur le propriétaire 1 (celui de BaseTestCase)
        response = self.client.get(self.url, {'mois': '2024-08', 'proprietaire_id': self.proprietaire_user.pk})
        self.assertEqual(response.status_code, 200)

        # Doit contenir uniquement les 2 locations du propriétaire 1
        self.assertEqual(len(response.context['monthly_rent_details']), 2)
        self.assertContains(response, "P1-A1") # Chambre du proprio 1
        self.assertContains(response, "P1-A2") # Chambre du proprio 1
        self.assertNotContains(response, "P2-B1") # Chambre du proprio 2

        # Vérifier les totaux pour le propriétaire 1
        self.assertEqual(response.context['totals']['attendu'], Decimal('150000')) # 100k + 50k
        self.assertEqual(response.context['totals']['paye'], Decimal('100000')) # 100k
        self.assertEqual(response.context['totals']['impaye'], Decimal('50000'))

    def test_empty_state_for_no_locations(self):
        """Vérifie que la vue affiche un message si aucun résultat ne correspond aux filtres."""
        # Un mois où il n'y a aucune location
        response = self.client.get(self.url, {'mois': '2020-01'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['monthly_rent_details']), 0)
        self.assertContains(response, "Aucune location active à afficher pour les filtres sélectionnés.")

class ChambreDetailViewTest(BaseTestCase):
    """
    Teste la vue `chambre_detail` pour les permissions, l'affichage conditionnel et les actions POST.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Chambre libre
        cls.chambre_libre = Chambre.objects.create(immeuble=cls.immeuble, designation="LIB-1", prix_loyer=100)
        
        # Chambre occupée
        cls.chambre_occupee = Chambre.objects.create(immeuble=cls.immeuble, designation="OCC-1", prix_loyer=200)
        cls.locataire_actuel = Locataire.objects.create(agence=cls.agence, nom="Actuel", prenom="Occupant")
        cls.moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.VIREMENT)
        cls.location_active = Location.objects.create(
            chambre=cls.chambre_occupee, locataire=cls.locataire_actuel, date_entree='2024-01-01', moyen_paiement=cls.moyen_paiement
        )
        cls.chambre_occupee.locataire = cls.locataire_actuel
        cls.chambre_occupee.save()

        # Locataire disponible pour une nouvelle location
        cls.locataire_disponible = Locataire.objects.create(agence=cls.agence, nom="Disponible", prenom="Candidat")

        # Utilisateur propriétaire d'une autre agence pour tester les permissions
        cls.autre_agence_user = User.objects.create_user(username='autre_agence', password='password123', user_type='AG')
        cls.autre_agence = Agence.objects.create(user=cls.autre_agence_user)

    def test_managing_agence_can_access(self):
        """Vérifie que l'agence qui gère l'immeuble peut accéder à la vue."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:chambre_detail', kwargs={'pk': self.chambre_libre.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/chambre_detail.html')

    def test_owner_can_access(self):
        """Vérifie que le propriétaire de l'immeuble peut accéder à la vue."""
        self.client.login(username='proprio_test', password='password123')
        url = reverse('gestion:chambre_detail', kwargs={'pk': self.chambre_libre.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_other_agence_is_denied(self):
        """Vérifie qu'une autre agence ne peut pas accéder à la vue."""
        self.client.login(username='autre_agence', password='password123')
        url = reverse('gestion:chambre_detail', kwargs={'pk': self.chambre_libre.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_view_for_free_chambre_shows_location_form(self):
        """Vérifie que pour une chambre libre, le formulaire d'assignation est présent."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:chambre_detail', kwargs={'pk': self.chambre_libre.pk})
        response = self.client.get(url)
        self.assertIsNone(response.context['location_active'])
        self.assertIn('location_form', response.context)
        self.assertContains(response, "Assigner un locataire")

    def test_view_for_occupied_chambre_shows_details(self):
        """Vérifie que pour une chambre occupée, les détails de la location sont présents."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:chambre_detail', kwargs={'pk': self.chambre_occupee.pk})
        response = self.client.get(url)
        self.assertEqual(response.context['location_active'], self.location_active)
        self.assertIsNone(response.context['location_form'])
        self.assertContains(response, "Occupant Actuel")
        self.assertContains(response, "Libérer l'unité")

    def test_assign_locataire_success(self):
        """Teste l'assignation réussie d'un locataire à une chambre libre."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:chambre_detail', kwargs={'pk': self.chambre_libre.pk})
        post_data = {
            'locataire': self.locataire_disponible.pk,
            'date_entree': '2024-09-01',
            'moyen_paiement': self.moyen_paiement.pk,
            'submit_location': '' # Nom du bouton de soumission
        }
        response = self.client.post(url, post_data)
        self.assertRedirects(response, url)
        
        self.chambre_libre.refresh_from_db()
        self.assertEqual(self.chambre_libre.locataire, self.locataire_disponible)
        self.assertTrue(Location.objects.filter(chambre=self.chambre_libre, locataire=self.locataire_disponible).exists())

    def test_liberer_chambre_success(self):
        """Teste la libération réussie d'une chambre occupée."""
        self.client.login(username='agence_test', password='password123')
        url = reverse('gestion:liberer_chambre', kwargs={'pk': self.chambre_occupee.pk})
        response = self.client.post(url)
        
        self.assertRedirects(response, reverse('gestion:chambre_detail', kwargs={'pk': self.chambre_occupee.pk}))
        
        self.chambre_occupee.refresh_from_db()
        self.location_active.refresh_from_db()
        
        self.assertIsNone(self.chambre_occupee.locataire)
        self.assertIsNotNone(self.location_active.date_sortie)

class LocataireDetailViewTest(BaseTestCase):
    """
    Teste la vue `locataire_detail` pour les permissions et l'exactitude des données.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Locataire géré par l'agence principale
        cls.locataire_gere = Locataire.objects.create(agence=cls.agence, nom="Géré", prenom="Locataire")
        
        # Locataire avec une location active et une ancienne
        chambre_active = Chambre.objects.create(immeuble=cls.immeuble, designation="ACT-1", prix_loyer=1)
        chambre_ancienne = Chambre.objects.create(immeuble=cls.immeuble, designation="ANC-1", prix_loyer=1)
        moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.VIREMENT)
        
        cls.location_active = Location.objects.create(chambre=chambre_active, locataire=cls.locataire_gere, date_entree='2024-01-01', moyen_paiement=moyen_paiement)
        cls.location_ancienne = Location.objects.create(chambre=chambre_ancienne, locataire=cls.locataire_gere, date_entree='2023-01-01', date_sortie='2023-12-31', moyen_paiement=moyen_paiement)

        # Locataire non géré par l'agence principale
        autre_agence_user = User.objects.create_user(username='autre_agence', password='password123', user_type='AG')
        autre_agence = Agence.objects.create(user=autre_agence_user)
        cls.locataire_non_gere = Locataire.objects.create(agence=autre_agence, nom="NonGéré", prenom="Locataire")

        cls.url_gere = reverse('gestion:locataire_detail', kwargs={'pk': cls.locataire_gere.pk})
        cls.url_non_gere = reverse('gestion:locataire_detail', kwargs={'pk': cls.locataire_non_gere.pk})

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_view_loads_correctly_for_managed_locataire(self):
        """Vérifie que la vue se charge avec les bonnes données pour un locataire géré."""
        response = self.client.get(self.url_gere)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/locataire_detail.html')
        
        # Vérifier le contexte
        self.assertEqual(response.context['locataire'], self.locataire_gere)
        self.assertEqual(response.context['location_active'], self.location_active)
        self.assertEqual(len(response.context['locations_history']), 2)
        self.assertIn(self.location_active, response.context['locations_history'])
        self.assertIn(self.location_ancienne, response.context['locations_history'])

        # Vérifier le contenu HTML
        self.assertContains(response, "Locataire Géré")
        self.assertContains(response, "Location Actuelle")
        self.assertContains(response, "ACT-1") # Désignation de la chambre active
        self.assertContains(response, "Historique des locations")
        self.assertContains(response, "ANC-1") # Désignation de la chambre ancienne

    def test_permission_denied_for_unmanaged_locataire(self):
        """Vérifie qu'une agence ne peut pas voir les détails d'un locataire qu'elle ne gère pas."""
        response = self.client.get(self.url_non_gere)
        self.assertEqual(response.status_code, 403)

    def test_permission_denied_for_proprietaire(self):
        """Vérifie qu'un propriétaire ne peut pas accéder à la vue."""
        self.client.login(username='proprio_test', password='password123')
        response = self.client.get(self.url_gere)
        self.assertEqual(response.status_code, 403)

class ModifierLocataireViewTest(BaseTestCase):
    """
    Teste la vue `modifier_locataire` pour les permissions et la logique de formulaire.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Locataire géré par l'agence de test
        cls.locataire_a_modifier = Locataire.objects.create(
            agence=cls.agence, nom="AncienNom", prenom="AncienPrenom", telephone="111111"
        )

        # Agence et locataire non liés pour tester les permissions
        autre_agence_user = User.objects.create_user(username='autre_agence_2', password='password123', user_type='AG')
        autre_agence = Agence.objects.create(user=autre_agence_user)
        cls.locataire_autre_agence = Locataire.objects.create(
            agence=autre_agence, nom="Autre", prenom="Locataire", telephone="222222"
        )

        cls.url = reverse('gestion:modifier_locataire', kwargs={'pk': cls.locataire_a_modifier.pk})

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_permission_denied_for_other_agence(self):
        """Vérifie qu'une agence ne peut pas modifier un locataire qu'elle ne gère pas."""
        url_autre_locataire = reverse('gestion:modifier_locataire', kwargs={'pk': self.locataire_autre_agence.pk})
        response = self.client.get(url_autre_locataire)
        self.assertEqual(response.status_code, 403)

    def test_get_form_is_prefilled(self):
        """Vérifie que le formulaire est bien pré-rempli avec les données du locataire."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/modifier_locataire.html')
        self.assertContains(response, 'value="AncienNom"')
        self.assertContains(response, 'value="AncienPrenom"')

    def test_successful_post_updates_locataire_and_redirects(self):
        """Vérifie qu'une soumission valide met à jour le locataire et redirige."""
        post_data = {'nom': 'NouveauNom', 'prenom': 'NouveauPrenom', 'telephone': '999999', 'caution': 1000}
        response = self.client.post(self.url, post_data)

        # Vérifier la redirection vers la page de détail
        self.assertRedirects(response, reverse('gestion:locataire_detail', kwargs={'pk': self.locataire_a_modifier.pk}))

        # Vérifier que les données ont été mises à jour
        self.locataire_a_modifier.refresh_from_db()
        self.assertEqual(self.locataire_a_modifier.nom, 'NouveauNom')
        self.assertEqual(self.locataire_a_modifier.telephone, '999999')

    def test_invalid_post_rerenders_form_with_errors(self):
        """Vérifie qu'une soumission invalide (champ requis manquant) ré-affiche le formulaire avec des erreurs."""
        post_data = {'nom': '', 'prenom': 'NouveauPrenom', 'telephone': '999999', 'caution': 1000} # Nom manquant
        response = self.client.post(self.url, post_data)

        self.assertEqual(response.status_code, 200) # Pas de redirection
        self.assertFormError(response, 'form', 'nom', 'Ce champ est obligatoire.')

class SupprimerLocataireViewTest(BaseTestCase):
    """
    Teste la vue `supprimer_locataire` pour les permissions et la logique de suppression.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Locataire géré par l'agence, sans location active
        cls.locataire_libre = Locataire.objects.create(agence=cls.agence, nom="Libre", prenom="Candidat")

        # Locataire géré par l'agence, AVEC une location active
        cls.locataire_occupe = Locataire.objects.create(agence=cls.agence, nom="Occupant", prenom="Actif")
        chambre = Chambre.objects.create(immeuble=cls.immeuble, designation="Test-Occupe", prix_loyer=100)
        moyen_paiement = MoyenPaiement.objects.create(designation=MoyenPaiement.VIREMENT)
        Location.objects.create(chambre=chambre, locataire=cls.locataire_occupe, date_entree='2024-01-01', moyen_paiement=moyen_paiement)

        # Locataire d'une autre agence
        autre_agence_user = User.objects.create_user(username='autre_agence_3', password='password123', user_type='AG')
        autre_agence = Agence.objects.create(user=autre_agence_user)
        cls.locataire_autre_agence = Locataire.objects.create(agence=autre_agence, nom="Autre", prenom="Locataire")

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_permission_denied_for_proprietaire(self):
        """Vérifie qu'un propriétaire ne peut pas accéder à la page de suppression."""
        self.client.login(username='proprio_test', password='password123')
        url = reverse('gestion:supprimer_locataire', kwargs={'pk': self.locataire_libre.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_permission_denied_for_other_agence(self):
        """Vérifie qu'une agence ne peut pas supprimer un locataire qu'elle ne gère pas."""
        url = reverse('gestion:supprimer_locataire', kwargs={'pk': self.locataire_autre_agence.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_get_page_shows_warning_for_occupied_locataire(self):
        """Vérifie que la page de confirmation affiche un avertissement si le locataire est actif."""
        url = reverse('gestion:supprimer_locataire', kwargs={'pk': self.locataire_occupe.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_occupant'])
        self.assertContains(response, "Attention, ce locataire occupe actuellement une unité.")

    def test_successful_post_deletes_locataire_and_redirects(self):
        """Vérifie qu'une soumission valide supprime le locataire et redirige."""
        locataire_pk = self.locataire_libre.pk
        self.assertTrue(Locataire.objects.filter(pk=locataire_pk).exists())

        url = reverse('gestion:supprimer_locataire', kwargs={'pk': locataire_pk})
        response = self.client.post(url)

        self.assertRedirects(response, reverse('gestion:gerer_locataires'))
        self.assertFalse(Locataire.objects.filter(pk=locataire_pk).exists())

        # Vérifier le message de succès sur la page de redirection
        response_redirected = self.client.get(reverse('gestion:gerer_locataires'))
        self.assertContains(response_redirected, "Le locataire 'Candidat Libre' a été supprimé avec succès.")

class AjouterLocataireViewTest(BaseTestCase):
    """
    Teste la vue `ajouter_locataire` pour les permissions et la logique de formulaire.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.url = reverse('gestion:ajouter_locataire')
        cls.valid_data = {
            'nom': 'Durand',
            'prenom': 'Paul',
            'telephone': '0123456789',
            'email': 'paul.durand@test.com',
            'caution': '100000',
        }
        cls.invalid_data = {
            'nom': '', # Champ requis manquant
            'prenom': 'Paul',
            'telephone': '0123456789',
            'caution': '100000',
        }

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_permission_denied_for_proprietaire(self):
        """Vérifie qu'un propriétaire ne peut pas accéder à la vue."""
        self.client.login(username='proprio_test', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_view_loads_correctly(self):
        """Vérifie que la page de création de locataire se charge correctement pour une agence."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/ajouter_locataire.html')
        self.assertIn('form', response.context)

    def test_successful_post_creates_locataire(self):
        """Vérifie qu'une soumission valide crée un nouveau locataire et redirige."""
        locataire_count_before = Locataire.objects.count()
        response = self.client.post(self.url, self.valid_data)
        self.assertRedirects(response, reverse('gestion:gerer_locataires'))
        self.assertEqual(Locataire.objects.count(), locataire_count_before + 1)
        self.assertTrue(Locataire.objects.filter(email='paul.durand@test.com', agence=self.agence).exists())

    def test_invalid_post_rerenders_form(self):
        """Vérifie qu'une soumission invalide ré-affiche le formulaire avec des erreurs."""
        locataire_count_before = Locataire.objects.count()
        response = self.client.post(self.url, self.invalid_data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Locataire.objects.count(), locataire_count_before)
        self.assertFormError(response, 'form', 'nom', 'Ce champ est obligatoire.')

from .forms import LocataireForm

class LocataireFormTest(TestCase):
    """
    Teste le formulaire `LocataireForm` de manière isolée pour valider sa logique.
    """
    def test_form_is_valid_with_all_data(self):
        """Vérifie que le formulaire est valide lorsque toutes les données sont correctes."""
        form_data = {
            'nom': 'Test', 'prenom': 'Valide', 'telephone': '771234567',
            'email': 'valide@test.com', 'caution': 100000
        }
        form = LocataireForm(data=form_data)
        self.assertTrue(form.is_valid())

    def test_form_is_invalid_if_required_field_is_missing(self):
        """Vérifie que le formulaire est invalide si un champ requis est manquant."""
        # Test avec 'nom' manquant
        form_data = {'prenom': 'Invalide', 'telephone': '771112233', 'caution': 50000}
        form = LocataireForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('nom', form.errors)

        # Test avec 'caution' manquante
        form_data = {'nom': 'Invalide', 'prenom': 'Test', 'telephone': '771112233'}
        form = LocataireForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('caution', form.errors)

    def test_telephone_is_cleaned(self):
        """Vérifie que la méthode clean_telephone nettoie bien le numéro."""
        form_data = {
            'nom': 'Test', 'prenom': 'Nettoyage', 'telephone': '+221 77 123 45-67', 'caution': 100000
        }
        form = LocataireForm(data=form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['telephone'], '221771234567')

class GererLocatairesViewTest(BaseTestCase):
    """
    Teste la vue `gerer_locataires` pour les permissions, l'affichage et la recherche.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Locataires pour l'agence principale
        cls.locataire1 = Locataire.objects.create(agence=cls.agence, nom="Martin", prenom="Alice")
        cls.locataire2 = Locataire.objects.create(agence=cls.agence, nom="Durand", prenom="Bob")

        # Locataire pour une autre agence (pour tester l'isolation des données)
        autre_agence_user = User.objects.create_user(username='autre_agence_4', password='password123', user_type='AG')
        autre_agence = Agence.objects.create(user=autre_agence_user)
        cls.locataire_autre = Locataire.objects.create(agence=autre_agence, nom="Externe", prenom="Charles")

        cls.url = reverse('gestion:gerer_locataires')

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_permission_denied_for_proprietaire(self):
        """Vérifie qu'un propriétaire ne peut pas accéder à la vue."""
        self.client.login(username='proprio_test', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_view_lists_correct_locataires(self):
        """Vérifie que la vue liste uniquement les locataires de l'agence connectée."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/gerer_locataires.html')
        self.assertContains(response, "Alice Martin")
        self.assertContains(response, "Bob Durand")
        self.assertNotContains(response, "Charles Externe")

    def test_search_functionality(self):
        """Vérifie que la recherche filtre correctement les locataires."""
        response = self.client.get(self.url, {'q': 'Martin'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Martin")
        self.assertNotContains(response, "Bob Durand")

        # Vérifier que le champ de recherche est pré-rempli
        self.assertIn('search_query', response.context)
        self.assertEqual(response.context['search_query'], 'Martin')

class ProprietaireDetailViewTest(BaseTestCase):
    """
    Teste la vue `proprietaire_detail` pour les permissions et l'affichage des données.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Créer une autre agence et un propriétaire qui lui est associé
        cls.autre_agence_user = User.objects.create_user(username='autre_agence', password='password123', user_type='AG')
        cls.autre_agence = Agence.objects.create(user=cls.autre_agence_user)
        cls.autre_proprietaire_user = User.objects.create_user(username='autre_proprio', password='password123', user_type='PR')
        cls.autre_proprietaire = Proprietaire.objects.create(
            user=cls.autre_proprietaire_user, agence=cls.autre_agence, taux_commission=10,
            date_debut_contrat='2024-01-01', duree_contrat=12
        )

        cls.url = reverse('gestion:proprietaire_detail', kwargs={'pk': cls.proprietaire_user.pk})

    def test_permission_denied_for_non_agence_user(self):
        """Vérifie qu'un utilisateur non-agence (ex: un autre propriétaire) ne peut pas accéder à la vue."""
        self.client.login(username='autre_proprio', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_permission_denied_for_unrelated_agence(self):
        """Vérifie qu'une agence ne peut pas voir les détails d'un propriétaire qu'elle ne gère pas."""
        # L'agence de test (agence_test) essaie de voir le propriétaire de autre_agence
        self.client.login(username='agence_test', password='password123')
        url_autre_proprio = reverse('gestion:proprietaire_detail', kwargs={'pk': self.autre_proprietaire_user.pk})
        response = self.client.get(url_autre_proprio)
        self.assertEqual(response.status_code, 403)

    def test_view_loads_correctly_for_managing_agence(self):
        """Vérifie que la vue se charge correctement pour l'agence qui gère le propriétaire."""
        self.client.login(username='agence_test', password='password123')
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/proprietaire_detail.html')

        # Vérifier que les bonnes données sont dans le contexte
        self.assertEqual(response.context['proprietaire_user'], self.proprietaire_user)
        self.assertEqual(response.context['proprietaire_profil'], self.proprietaire)
        self.assertIn(self.immeuble, response.context['immeubles'])

        # Vérifier que les données sont affichées dans le template
        self.assertContains(response, "Proprio Test") # Nom du propriétaire
        self.assertContains(response, "123 Rue de l'Exemple") # Adresse de l'immeuble

class AjouterImmeubleViewTest(BaseTestCase):
    """
    Teste la vue `ajouter_immeuble` pour les permissions et la logique de formulaire.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # URL pour ajouter un immeuble au propriétaire de test
        cls.url = reverse('gestion:ajouter_immeuble', kwargs={'pk': cls.proprietaire_user.pk})

        # Créer une autre agence et un propriétaire non lié pour les tests de permission
        autre_agence_user = User.objects.create_user(username='autre_agence_5', password='password123', user_type='AG')
        autre_agence = Agence.objects.create(user=autre_agence_user)
        cls.autre_proprio_user = User.objects.create_user(username='autre_proprio_5', password='password123', user_type='PR')
        Proprietaire.objects.create(user=cls.autre_proprio_user, agence=autre_agence, taux_commission=5, date_debut_contrat='2024-01-01', duree_contrat=12)
        
        cls.valid_data = {
            'type_bien': cls.type_bien_res.pk, 'addresse': '10 Rue du Test',
            'superficie': 120.50, 'nombre_chambres': 4,
        }
        cls.invalid_data = {
            'type_bien': cls.type_bien_res.pk, 'addresse': '', # Adresse manquante
            'superficie': 120.50, 'nombre_chambres': 4,
        }

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_permission_denied_for_proprietaire(self):
        """Vérifie qu'un propriétaire ne peut pas accéder à la vue."""
        self.client.login(username='proprio_test', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_permission_denied_for_unrelated_agence(self):
        """Vérifie qu'une agence ne peut pas ajouter un immeuble à un propriétaire qu'elle ne gère pas."""
        url_autre_proprio = reverse('gestion:ajouter_immeuble', kwargs={'pk': self.autre_proprio_user.pk})
        response = self.client.get(url_autre_proprio)
        self.assertEqual(response.status_code, 403)

    def test_successful_post_creates_immeuble(self):
        """Vérifie qu'une soumission valide crée un nouvel immeuble et redirige."""
        immeuble_count_before = Immeuble.objects.count()
        response = self.client.post(self.url, self.valid_data)
        
        self.assertRedirects(response, reverse('gestion:proprietaire_detail', kwargs={'pk': self.proprietaire_user.pk}))
        self.assertEqual(Immeuble.objects.count(), immeuble_count_before + 1)
        
        new_immeuble = Immeuble.objects.get(addresse='10 Rue du Test')
        self.assertEqual(new_immeuble.proprietaire, self.proprietaire)

    def test_invalid_post_rerenders_form_with_errors(self):
        """Vérifie qu'une soumission invalide ré-affiche le formulaire avec des erreurs."""
        response = self.client.post(self.url, self.invalid_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'addresse', 'Ce champ est obligatoire.')

class ModifierImmeubleViewTest(BaseTestCase):
    """
    Teste la vue `modifier_immeuble` pour les permissions et la logique de formulaire.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Immeuble à modifier, appartenant à l'agence de test
        cls.immeuble_a_modifier = cls.immeuble
        cls.url = reverse('gestion:modifier_immeuble', kwargs={'pk': cls.immeuble_a_modifier.pk})

        # Créer une autre agence et un immeuble non lié pour les tests de permission
        autre_agence_user = User.objects.create_user(username='autre_agence_6', password='password123', user_type='AG')
        autre_agence = Agence.objects.create(user=autre_agence_user)
        autre_proprio_user = User.objects.create_user(username='autre_proprio_6', password='password123', user_type='PR')
        autre_proprio = Proprietaire.objects.create(user=autre_proprio_user, agence=autre_agence, taux_commission=5, date_debut_contrat='2024-01-01', duree_contrat=12)
        cls.immeuble_autre_agence = Immeuble.objects.create(proprietaire=autre_proprio, type_bien=cls.type_bien_res, addresse="Adresse Intouchable", superficie=100, nombre_chambres=1)

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_permission_denied_for_unrelated_agence(self):
        """Vérifie qu'une agence ne peut pas modifier un immeuble qu'elle ne gère pas."""
        url_autre_immeuble = reverse('gestion:modifier_immeuble', kwargs={'pk': self.immeuble_autre_agence.pk})
        response = self.client.get(url_autre_immeuble)
        self.assertEqual(response.status_code, 403)

    def test_get_form_is_prefilled(self):
        """Vérifie que le formulaire est bien pré-rempli avec les données de l'immeuble."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/modifier_immeuble.html')
        self.assertContains(response, self.immeuble_a_modifier.addresse)

    def test_successful_post_updates_immeuble(self):
        """Vérifie qu'une soumission valide met à jour l'immeuble et redirige."""
        post_data = {
            'type_bien': self.type_bien_res.pk,
            'addresse': 'Nouvelle Adresse Modifiée',
            'superficie': 150.75,
            'nombre_chambres': 6,
        }
        response = self.client.post(self.url, post_data)

        self.assertRedirects(response, reverse('gestion:immeuble_detail', kwargs={'pk': self.immeuble_a_modifier.pk}))
        
        self.immeuble_a_modifier.refresh_from_db()
        self.assertEqual(self.immeuble_a_modifier.addresse, 'Nouvelle Adresse Modifiée')
        self.assertEqual(self.immeuble_a_modifier.nombre_chambres, 6)

    def test_invalid_post_rerenders_form_with_errors(self):
        """Vérifie qu'une soumission invalide ré-affiche le formulaire avec des erreurs."""
        post_data = {
            'type_bien': self.type_bien_res.pk, 'addresse': '', 'superficie': 150, 'nombre_chambres': 6
        }
        response = self.client.post(self.url, post_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'addresse', 'Ce champ est obligatoire.')

class SupprimerImmeubleViewTest(BaseTestCase):
    """
    Teste la vue `supprimer_immeuble` pour les permissions et la logique de suppression.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # Immeuble à supprimer, appartenant à l'agence de test
        cls.immeuble_a_supprimer = cls.immeuble
        cls.url = reverse('gestion:supprimer_immeuble', kwargs={'pk': cls.immeuble_a_supprimer.pk})

        # Créer une autre agence et un immeuble non lié pour les tests de permission
        autre_agence_user = User.objects.create_user(username='autre_agence_7', password='password123', user_type='AG')
        autre_agence = Agence.objects.create(user=autre_agence_user)
        autre_proprio_user = User.objects.create_user(username='autre_proprio_7', password='password123', user_type='PR')
        autre_proprio = Proprietaire.objects.create(user=autre_proprio_user, agence=autre_agence, taux_commission=5, date_debut_contrat='2024-01-01', duree_contrat=12)
        cls.immeuble_autre_agence = Immeuble.objects.create(proprietaire=autre_proprio, type_bien=cls.type_bien_res, addresse="Adresse Intouchable", superficie=100, nombre_chambres=1)

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_permission_denied_for_proprietaire(self):
        """Vérifie qu'un propriétaire ne peut pas supprimer un immeuble."""
        self.client.login(username='proprio_test', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_permission_denied_for_unrelated_agence(self):
        """Vérifie qu'une agence ne peut pas supprimer un immeuble qu'elle ne gère pas."""
        url_autre_immeuble = reverse('gestion:supprimer_immeuble', kwargs={'pk': self.immeuble_autre_agence.pk})
        response = self.client.get(url_autre_immeuble)
        self.assertEqual(response.status_code, 403)

    def test_get_confirmation_page(self):
        """Vérifie que la page de confirmation s'affiche correctement."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/immeuble_confirm_delete.html')
        self.assertContains(response, self.immeuble_a_supprimer.addresse)

    def test_successful_post_deletes_immeuble_and_redirects(self):
        """Vérifie qu'une soumission valide supprime l'immeuble et redirige."""
        immeuble_pk = self.immeuble_a_supprimer.pk
        proprietaire_pk = self.immeuble_a_supprimer.proprietaire.user.pk
        self.assertTrue(Immeuble.objects.filter(pk=immeuble_pk).exists())

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('gestion:proprietaire_detail', kwargs={'pk': proprietaire_pk}))
        self.assertFalse(Immeuble.objects.filter(pk=immeuble_pk).exists())

class AjouterChambreViewTest(BaseTestCase):
    """
    Teste la vue `ajouter_chambre` pour les permissions et la logique de formulaire.
    """
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        # URL pour ajouter une chambre à l'immeuble de test
        cls.url = reverse('gestion:ajouter_chambre', kwargs={'immeuble_id': cls.immeuble.pk})

        # Données valides et invalides pour le formulaire
        cls.valid_data = {
            'designation': 'Unité C1', 'superficie': 35.50,
            'prix_loyer': 75000, 'date_mise_en_location': '2024-10-01',
        }
        cls.invalid_data = {
            'designation': '', 'superficie': 35.50, # Designation manquante
            'prix_loyer': 75000, 'date_mise_en_location': '2024-10-01',
        }

    def setUp(self):
        self.client.login(username='agence_test', password='password123')

    def test_permission_denied_for_proprietaire(self):
        """Vérifie qu'un propriétaire ne peut pas accéder à la vue."""
        self.client.login(username='proprio_test', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_view_loads_correctly(self):
        """Vérifie que la page de création de chambre se charge correctement pour l'agence."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/ajouter_chambre.html')
        self.assertIn('form', response.context)

    def test_successful_post_creates_chambre(self):
        """Vérifie qu'une soumission valide crée une nouvelle chambre et redirige."""
        chambre_count_before = Chambre.objects.count()
        response = self.client.post(self.url, self.valid_data)
        self.assertRedirects(response, reverse('gestion:immeuble_detail', kwargs={'pk': self.immeuble.pk}))
        self.assertEqual(Chambre.objects.count(), chambre_count_before + 1)
        self.assertTrue(Chambre.objects.filter(designation='Unité C1', immeuble=self.immeuble).exists())

    def test_invalid_post_rerenders_form_with_errors(self):
        """Vérifie qu'une soumission invalide ré-affiche le formulaire avec des erreurs."""
        response = self.client.post(self.url, self.invalid_data)
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'designation', 'Ce champ est obligatoire.')
