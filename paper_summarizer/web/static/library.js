async function fetchSummaries() {
    try {
        const response = await authFetch('/api/summaries');
        const data = await response.json();
        if (data.summaries && data.summaries.length > 0) {
            displaySummaries(data.summaries);
        } else {
            document.getElementById('emptyState').classList.remove('hidden');
        }
    } catch (error) {
        console.error('Failed to fetch summaries:', error);
    }
}

function displaySummaries(summaries) {
    const list = document.getElementById('summaryList');
    list.innerHTML = summaries.map(summary => `
        <div class="summary-card">
            <h2 class="text-xl font-semibold mb-2">${summary.title || 'Untitled Summary'}</h2>
            <p class="mb-4">${summary.summary}</p>
            <div class="flex justify-between items-center">
                <span class="text-sm text-gray-500">${new Date(summary.created_at).toLocaleDateString()}</span>
                <div class="flex gap-2">
                    <button data-action="download" data-id="${summary.id}" class="mr-2">Download</button>
                    <button data-action="delete" data-id="${summary.id}" class="text-red-400 hover:text-red-300">Delete</button>
                </div>
            </div>
            <p class="text-xs text-gray-500 mt-3">ID: ${summary.id}</p>
        </div>
    `).join('');
}

async function downloadSummary(id, format = 'txt') {
    const response = await authFetch(`/export/${id}?format=${format}`);
    if (!response.ok) {
        console.error('Failed to download summary');
        return;
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = format === 'md' ? `summary_${id}.md` : format === 'pdf' ? `summary_${id}.pdf` : `summary_${id}.txt`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

async function deleteSummary(id) {
    const response = await authFetch(`/api/summaries/${id}`, { method: 'DELETE' });
    if (!response.ok) {
        console.error('Failed to delete summary');
        return;
    }
    fetchSummaries();
}

document.addEventListener('DOMContentLoaded', () => {
    const list = document.getElementById('summaryList');
    if (list) {
        list.addEventListener('click', event => {
            const button = event.target.closest('button[data-action]');
            if (!button) {
                return;
            }
            const action = button.dataset.action;
            const summaryId = button.dataset.id;
            if (action === 'download') {
                downloadSummary(summaryId, 'txt');
            }
            if (action === 'delete') {
                deleteSummary(summaryId);
            }
        });
    }
    fetchSummaries();
});
