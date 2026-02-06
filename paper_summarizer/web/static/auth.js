function getAuthToken() {
    return localStorage.getItem('auth_token');
}

function setAuthToken(token) {
    localStorage.setItem('auth_token', token);
}

function clearAuthToken() {
    localStorage.removeItem('auth_token');
}

function isLoginPage() {
    return window.location.pathname === '/login';
}

function enforceAuth() {
    if (!getAuthToken() && !isLoginPage()) {
        window.location.href = '/login';
    }
}

async function authFetch(url, options = {}) {
    const token = getAuthToken();
    const headers = options.headers ? { ...options.headers } : {};
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    return fetch(url, { ...options, headers });
}

function setupAuthButton() {
    const buttons = [
        document.getElementById('auth-action-desktop'),
        document.getElementById('auth-action-mobile'),
    ].filter(Boolean);

    const token = getAuthToken();
    buttons.forEach(button => {
        if (token) {
            button.textContent = 'Logout';
            button.onclick = () => {
                clearAuthToken();
                window.location.href = '/login';
            };
        } else {
            button.textContent = 'Login';
            button.onclick = () => {
                window.location.href = '/login';
            };
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    setupAuthButton();
    enforceAuth();
});

window.authFetch = authFetch;
