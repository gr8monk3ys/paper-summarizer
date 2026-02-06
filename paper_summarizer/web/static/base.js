document.addEventListener('DOMContentLoaded', () => {
    const button = document.getElementById('mobileMenuButton');
    const menu = document.getElementById('mobileMenu');
    if (!button || !menu) {
        return;
    }
    button.addEventListener('click', () => {
        const isExpanded = menu.classList.contains('hidden');
        menu.classList.toggle('hidden');
        button.setAttribute('aria-expanded', String(isExpanded));
    });
});
