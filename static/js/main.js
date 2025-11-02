// Attend que le contenu de la page soit entièrement chargé avant d'exécuter le script.
// C'est la méthode la plus robuste et moderne.
document.addEventListener('DOMContentLoaded', function () {

    // La fonction qui gère le basculement de la visibilité
    function togglePasswordVisibility(button) {
        const inputGroup = button.closest('.input-group');
        if (!inputGroup) {
            console.error("Password toggle button is not inside an .input-group");
            return;
        }

        const input = inputGroup.querySelector('input');
        if (!input) {
            console.error("No input field found inside the .input-group");
            return;
        }

        const icon = button.querySelector('i');

        if (input.type === 'password') {
            input.type = 'text';
            icon.classList.remove('fa-eye-slash');
            icon.classList.add('fa-eye');
        } else {
            input.type = 'password';
            icon.classList.remove('fa-eye');
            icon.classList.add('fa-eye-slash');
        }
    }

    // Sélectionne TOUS les boutons qui ont la classe 'js-password-toggle'
    const toggleButtons = document.querySelectorAll('.js-password-toggle');

    // Pour chaque bouton trouvé, on ajoute un écouteur d'événement 'click'
    toggleButtons.forEach(function (button) {
        button.addEventListener('click', function () {
            togglePasswordVisibility(this);
        });
    });

});
