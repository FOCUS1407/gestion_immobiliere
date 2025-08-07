from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Agence, Proprietaire, Immeuble, TypeBien, Chambre, Locataire, Location, Paiement, MoyenPaiement, Notification

from django.core.exceptions import ValidationError
from .validators import CustomPasswordValidator
from decimal import Decimal
from django.core.management import call_command 
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
