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

            resultsList.textContent = '';
            data.summaries.forEach(result => {
                const resultDiv = document.createElement('div');
                resultDiv.className = 'summary-card';

                const h3 = document.createElement('h3');
                h3.className = 'font-semibold mb-2';
                h3.textContent = result.filename;
                resultDiv.appendChild(h3);

                const p = document.createElement('p');
                p.textContent = result.summary;
                resultDiv.appendChild(p);

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
