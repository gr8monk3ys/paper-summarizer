async function loadModels() {
    try {
        const response = await authFetch('/models');
        const data = await response.json();

        const select = document.getElementById('defaultModel');
        Object.entries(data).forEach(([provider, models]) => {
            const group = document.createElement('optgroup');
            group.label = provider === 'together_ai' ? 'Cloud Models' : 'Local Models';

            models.forEach(model => {
                const option = document.createElement('option');
                option.value = model.id;
                option.text = `${model.name} - ${model.description}`;
                group.appendChild(option);
            });

            select.appendChild(group);
        });
    } catch (error) {
        console.error('Failed to load models:', error);
    }
}

async function loadSettings() {
    try {
        const response = await authFetch('/api/settings');
        const settings = await response.json();

        document.getElementById('defaultModel').value = settings.defaultModel;
        document.getElementById('apiKey').value = settings.apiKey || '';
        document.getElementById('summaryLength').value = settings.summaryLength;
        document.getElementById('summaryLengthValue').textContent = `${settings.summaryLength} sentences`;
        document.querySelector(`input[name="citations"][value="${settings.citationHandling}"]`).checked = true;
        document.getElementById('autoSave').checked = settings.autoSave;
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

function setupSlider() {
    const slider = document.getElementById('summaryLength');
    const value = document.getElementById('summaryLengthValue');

    slider.addEventListener('input', function() {
        value.textContent = `${this.value} sentences`;
    });
}

function toggleApiKey() {
    const input = document.getElementById('apiKey');
    const button = document.getElementById('toggleApiKeyButton');

    if (input.type === 'password') {
        input.type = 'text';
        button.textContent = 'Hide';
    } else {
        input.type = 'password';
        button.textContent = 'Show';
    }
}

async function saveSettings() {
    const settings = {
        defaultModel: document.getElementById('defaultModel').value,
        apiKey: document.getElementById('apiKey').value,
        summaryLength: parseInt(document.getElementById('summaryLength').value, 10),
        citationHandling: document.querySelector('input[name="citations"]:checked').value,
        autoSave: document.getElementById('autoSave').checked
    };

    try {
        const response = await authFetch('/api/settings', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        });

        if (response.ok) {
            alert('Settings saved successfully');
        } else {
            throw new Error('Failed to save settings');
        }
    } catch (error) {
        console.error('Failed to save settings:', error);
        alert('Failed to save settings. Please try again.');
    }
}

function confirmClearData() {
    if (confirm('Are you sure you want to clear all saved summaries? This action cannot be undone.')) {
        clearData();
    }
}

async function clearData() {
    try {
        const response = await fetch('/api/clear-data', {
            method: 'POST'
        });

        if (response.ok) {
            alert('All data cleared successfully');
        } else {
            throw new Error('Failed to clear data');
        }
    } catch (error) {
        console.error('Failed to clear data:', error);
        alert('Failed to clear data. Please try again.');
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadModels();
    loadSettings();
    setupSlider();

    const toggleButton = document.getElementById('toggleApiKeyButton');
    const clearButton = document.getElementById('clearDataButton');
    const saveButton = document.getElementById('saveSettingsButton');

    if (toggleButton) {
        toggleButton.addEventListener('click', toggleApiKey);
    }
    if (clearButton) {
        clearButton.addEventListener('click', confirmClearData);
    }
    if (saveButton) {
        saveButton.addEventListener('click', saveSettings);
    }
});
