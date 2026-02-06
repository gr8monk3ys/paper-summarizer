async function submitAuth(endpoint) {
    const email = document.getElementById('auth-email').value.trim();
    const password = document.getElementById('auth-password').value.trim();
    const error = document.getElementById('auth-error');
    if (!email || !password) {
        error.textContent = 'Email and password are required.';
        return;
    }
    error.textContent = '';
    const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });
    if (!response.ok) {
        const data = await response.json();
        error.textContent = data.error || 'Authentication failed.';
        return;
    }
    const data = await response.json();
    localStorage.setItem('auth_token', data.access_token);
    window.location.href = '/';
}

document.addEventListener('DOMContentLoaded', () => {
    const loginButton = document.getElementById('loginButton');
    const registerButton = document.getElementById('registerButton');
    if (loginButton) {
        loginButton.addEventListener('click', () => submitAuth('/auth/login'));
    }
    if (registerButton) {
        registerButton.addEventListener('click', () => submitAuth('/auth/register'));
    }
});
