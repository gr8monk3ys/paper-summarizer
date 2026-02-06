document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('batch-form');
    if (!form) {
        return;
    }
    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const spinner = document.getElementById('loading-spinner');
        const results = document.getElementById('batch-results');
        const resultsList = document.getElementById('results-list');
        const errorMessage = document.getElementById('error-message');

        try {
            spinner.classList.remove('hidden');
            errorMessage.classList.add('hidden');
            results.classList.add('hidden');

            const response = await authFetch('/batch', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to process files');
            }

            resultsList.innerHTML = '';
            data.summaries.forEach(result => {
                const resultDiv = document.createElement('div');
                resultDiv.className = 'summary-card';
                resultDiv.innerHTML = `
                    <h3 class="font-semibold mb-2">${result.filename}</h3>
                    <p>${result.summary}</p>
                `;
                resultsList.appendChild(resultDiv);
            });

            results.classList.remove('hidden');
        } catch (error) {
            errorMessage.textContent = error.message;
            errorMessage.classList.remove('hidden');
        } finally {
            spinner.classList.add('hidden');
        }
    });
});
