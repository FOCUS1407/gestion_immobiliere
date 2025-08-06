from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from gestion.models import Agence, Proprietaire

User = get_user_model()

class ModifierProprietaireViewTest(TestCase):
    """
    Tests pour la vue `modifier_proprietaire`.
    """

    @classmethod
    def setUpTestData(cls):
        """
        Crée les données initiales nécessaires pour tous les tests de cette classe.
        Nous créons deux agences et un propriétaire pour tester les permissions.
        """
        # Agence 1 et son propriétaire
        cls.agence_user_1 = User.objects.create_user(username='agence1', password='password123', user_type='AG')
        cls.agence_1 = Agence.objects.create(user=cls.agence_user_1)
        
        cls.proprietaire_user = User.objects.create_user(
            username='proprio1', password='password123', user_type='PR',
            first_name="Jean", last_name="Dupont", email="jean.dupont@test.com"
        )
        cls.proprietaire_profil = Proprietaire.objects.create(
            user=cls.proprietaire_user,
            agence=cls.agence_1,
            taux_commission=5.0,
            date_debut_contrat='2023-01-01',
            duree_contrat=12
        )

        # Agence 2 (pour tester les accès non autorisés)
        cls.agence_user_2 = User.objects.create_user(username='agence2', password='password123', user_type='AG')
        cls.agence_2 = Agence.objects.create(user=cls.agence_user_2)

        # URL de la vue à tester
        cls.url = reverse('gestion:modifier_proprietaire', kwargs={'pk': cls.proprietaire_user.pk})

    def setUp(self):
        """
        Crée un client de test pour chaque test.
        """
        self.client = Client()

    # --- Tests de Permissions ---

    def test_unauthenticated_user_is_redirected(self):
        """Vérifie qu'un utilisateur non connecté est redirigé vers la page de connexion."""
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('gestion:connexion')}?next={self.url}")

    def test_proprietaire_cannot_access_view(self):
        """Vérifie qu'un propriétaire ne peut pas accéder à la page (reçoit une erreur 403)."""
        self.client.login(username='proprio1', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403) # 403 Forbidden

    def test_other_agence_cannot_access_view(self):
        """Vérifie qu'une autre agence ne peut pas modifier un propriétaire qui ne lui appartient pas."""
        self.client.login(username='agence2', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403) # 403 Forbidden

    # --- Tests de la requête GET ---

    def test_view_accessible_by_correct_agence(self):
        """Vérifie que la bonne agence peut accéder à la page (reçoit un statut 200 OK)."""
        self.client.login(username='agence1', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/modifier_proprietaire.html')

    def test_view_uses_correct_template(self):
        """Vérifie que la vue utilise le bon template."""
        self.client.login(username='agence1', password='password123')
        response = self.client.get(self.url)
        self.assertTemplateUsed(response, 'gestion/modifier_proprietaire.html')

    def test_forms_are_prefilled_with_data(self):
        """Vérifie que les formulaires sont pré-remplis avec les données du propriétaire."""
        self.client.login(username='agence1', password='password123')
        response = self.client.get(self.url)
        # On vérifie que le nom du propriétaire est bien présent dans le HTML de la réponse
        self.assertContains(response, 'value="Jean"')
        self.assertContains(response, 'value="Dupont"')
        self.assertContains(response, 'value="5.0"') # Taux de commission

    # --- Tests de la requête POST ---

    def test_successful_post_updates_data_and_redirects(self):
        """Vérifie qu'une soumission valide met à jour les données et redirige."""
        self.client.login(username='agence1', password='password123')
        
        post_data = {
            'first_name': 'Jean-Claude',
            'last_name': 'Van Damme',
            'email': 'jc.vandamme@test.com',
            'telephone': '0102030405',
            'addresse': '123 Rue de la Forme',
            'taux_commission': '7.5',
            'date_debut_contrat': '2023-01-01',
            'duree_contrat': '24',
        }

        response = self.client.post(self.url, data=post_data)

        # 1. Vérifier la redirection vers la page de détail
        expected_redirect_url = reverse('gestion:proprietaire_detail', kwargs={'pk': self.proprietaire_user.pk})
        self.assertRedirects(response, expected_redirect_url)

        # 2. Rafraîchir les objets depuis la base de données pour vérifier les changements
        self.proprietaire_user.refresh_from_db()
        self.proprietaire_profil.refresh_from_db()

        # 3. Vérifier que les données ont bien été mises à jour
        self.assertEqual(self.proprietaire_user.first_name, 'Jean-Claude')
        self.assertEqual(self.proprietaire_profil.taux_commission, 7.5)

        # 4. Vérifier que le message de succès est affiché après la redirection
        response_redirected = self.client.get(expected_redirect_url)
        self.assertContains(response_redirected, "Les informations de Jean-Claude Van Damme ont été mises à jour.")

    def test_invalid_post_rerenders_form_with_errors(self):
        """Vérifie qu'une soumission invalide (ex: email incorrect) ne met pas à jour les données et affiche une erreur."""
        self.client.login(username='agence1', password='password123')

        post_data = {
            'first_name': 'Jean',
            'last_name': 'Dupont',
            'email': 'email-invalide', # Email incorrect
            'telephone': '0102030405',
            'addresse': '123 Rue de la Forme',
            'taux_commission': '5.0',
            'date_debut_contrat': '2023-01-01',
            'duree_contrat': '12',
        }

        response = self.client.post(self.url, data=post_data)

        # La page ne doit pas rediriger, elle doit ré-afficher le formulaire
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/modifier_proprietaire.html')
        # Vérifier que le message d'erreur de l'email est bien présent
        self.assertContains(response, "Saisissez une adresse e-mail valide.")

