from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from .models import Agence, Proprietaire, Bien

User = get_user_model()

class AjouterProprietaireViewTest(TestCase):
    """Test suite for the `ajouter_proprietaire` view."""

    def setUp(self):
        """
        Initial setup for each test.
        Creates necessary users and data.
        """
        # 1. Create an Agency user with a complete profile
        self.agence_user = User.objects.create_user(
            username='agence_test',
            password='password123',
            user_type='AG'
        )
        self.agence_profil = Agence.objects.create(
            user=self.agence_user,
            siret='12345678901234'
        )

        # 2. Create an Owner user for permission tests
        self.proprietaire_user = User.objects.create_user(
            username='proprio_test',
            password='password123',
            user_type='PR'
        )

        # 3. URL of the view to test
        self.url = reverse('gestion:ajouter_proprietaire')

        # 4. Valid data for the form
        self.valid_data = {
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'telephone': '0123456789',
            'addresse': '123 Rue Test',
            'bien_nom': 'Villa de John',
            'bien_adresse': '456 Avenue Test',
            'bien_description': 'Une belle villa.',
            'taux_commission': 10.5,
            'date_debut_contrat': '2024-01-01',
            'duree_contrat': 12,
        }

    def test_get_request_as_authenticated_agence(self):
        """Tests that an authenticated agency can access the form page."""
        self.client.login(username='agence_test', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'gestion/ajouter_proprietaire.html')

    def test_get_request_as_proprietaire_is_forbidden(self):
        """Tests that an owner cannot access the page (receives a 403 Forbidden)."""
        self.client.login(username='proprio_test', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_get_request_unauthenticated_user_is_redirected(self):
        """Tests that an unauthenticated user is redirected to the login page."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('gestion:connexion')}?next={self.url}")

    def test_agence_without_profile_is_redirected(self):
        """Tests that an agency without a profile is redirected to their profile page."""
        agence_sans_profil = User.objects.create_user(username='agence_no_profile', password='password123', user_type='AG')
        self.client.login(username='agence_no_profile', password='password123')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('gestion:profil'))

    def test_successful_post_request_creates_objects(self):
        """Tests that a valid submission creates a CustomUser, a Proprietaire, and a Bien."""
        self.client.login(username='agence_test', password='password123')
        
        # Check the state before submission
        self.assertEqual(User.objects.filter(user_type='PR').count(), 1)
        self.assertEqual(Proprietaire.objects.count(), 0)
        self.assertEqual(Bien.objects.count(), 0)

        response = self.client.post(self.url, self.valid_data)

        # Check the state after submission
        self.assertEqual(User.objects.filter(user_type='PR').count(), 2)
        self.assertEqual(Proprietaire.objects.count(), 1)
        self.assertEqual(Bien.objects.count(), 1)

        # Check the details of the created objects
        new_user = User.objects.get(email='john.doe@example.com')
        self.assertEqual(new_user.first_name, 'John')
        
        new_proprietaire_profile = Proprietaire.objects.get(user=new_user)
        self.assertEqual(new_proprietaire_profile.agence, self.agence_profil)

        new_bien = Bien.objects.get(proprietaire=new_user)
        self.assertEqual(new_bien.agence, self.agence_user)

        # Check the redirection and success message
        self.assertRedirects(response, reverse('gestion:tableau_de_bord_agence'))
        
        # Check that the password in the message is correct
        response_redirected = self.client.get(response.url, follow=True)
        messages = list(get_messages(response_redirected.wsgi_request))
        self.assertEqual(len(messages), 1)
        message_text = str(messages[0])
        password_from_message = message_text.split("est : ")[-1]
        self.assertTrue(new_user.check_password(password_from_message))

    def test_invalid_post_request_does_not_create_objects(self):
        """Tests that an invalid submission (duplicate email) does not create any objects."""
        User.objects.create_user(username='existing_user', email='john.doe@example.com', password='password123')
        self.client.login(username='agence_test', password='password123')

        response = self.client.post(self.url, self.valid_data)

        # The page should be re-rendered with errors, without redirection
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response, 'form', 'email', 'Un utilisateur avec cet email existe déjà.')
        
        # No objects should have been created
        self.assertEqual(Proprietaire.objects.count(), 0)
        self.assertEqual(Bien.objects.count(), 0)