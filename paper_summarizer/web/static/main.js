// Mobile menu functionality
document.addEventListener('DOMContentLoaded', function() {
    const mobileMenuButton = document.querySelector('.mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');

    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');
            const expanded = mobileMenuButton.getAttribute('aria-expanded') === 'true';
            mobileMenuButton.setAttribute('aria-expanded', !expanded);
        });
    }
});

// Form submission handlers
document.addEventListener('DOMContentLoaded', function() {
    // Error handling function
    function showError(message) {
        const errorDiv = document.getElementById('error-message');
        errorDiv.textContent = message;
        errorDiv.style.display = 'block';
        setTimeout(() => {
            errorDiv.style.display = 'none';
        }, 5000);
    }

    // Show/hide loading spinner
    function setLoading(isLoading) {
        const spinner = document.getElementById('loading-spinner');
        const submitButtons = document.querySelectorAll('button[type="submit"]');
        spinner.style.display = isLoading ? 'block' : 'none';
        submitButtons.forEach(button => {
            button.disabled = isLoading;
        });
    }

    // Handle form submissions
    async function handleSubmit(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        
        try {
            setLoading(true);
            const response = await fetch('/summarize', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate summary');
            }
            
            document.getElementById('summary').textContent = data.summary;
            const resultDiv = document.getElementById('result');
            resultDiv.classList.remove('hidden');
            resultDiv.classList.add('visible');
        } catch (error) {
            showError(error.message);
            document.getElementById('result').classList.add('hidden');
        } finally {
            setLoading(false);
        }
    }

    // Add form submit handlers
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', handleSubmit);
    });

    // Tab functionality
    const tabButtons = document.querySelectorAll('.tab-button');
    const inputSections = document.querySelectorAll('.input-section');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const target = button.dataset.target;
            
            // Update active tab button
            tabButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');
            
            // Show/hide input sections
            inputSections.forEach(section => {
                if (section.id === target) {
                    section.classList.remove('hidden');
                } else {
                    section.classList.add('hidden');
                }
            });
        });
    });
});

// Export functionality
async function exportSummary() {
    const result = document.getElementById('result');
    const entryId = result.dataset.entryId;
    if (!entryId) {
        showError('No summary to export');
        return;
    }

    try {
        const response = await fetch(`/export/${entryId}`);
        if (!response.ok) {
            throw new Error('Failed to export summary');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `summary_${entryId}.txt`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        showError(error.message);
    }
}

// Load history on page load
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('history-view')) {
        loadHistory();
    }
});
