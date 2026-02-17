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
    list.textContent = '';
    summaries.forEach(summary => {
        const card = document.createElement('div');
        card.className = 'summary-card';

        const h2 = document.createElement('h2');
        h2.className = 'text-xl font-semibold mb-2';
        h2.textContent = summary.title || 'Untitled Summary';
        card.appendChild(h2);

        const summaryP = document.createElement('p');
        summaryP.className = 'mb-4';
        summaryP.textContent = summary.summary;
        card.appendChild(summaryP);

        const flexDiv = document.createElement('div');
        flexDiv.className = 'flex justify-between items-center';

        const dateSpan = document.createElement('span');
        dateSpan.className = 'text-sm text-gray-500';
        dateSpan.textContent = new Date(summary.created_at).toLocaleDateString();
        flexDiv.appendChild(dateSpan);

        const buttonDiv = document.createElement('div');
        buttonDiv.className = 'flex gap-2';

        const downloadBtn = document.createElement('button');
        downloadBtn.dataset.action = 'download';
        downloadBtn.dataset.id = summary.id;
        downloadBtn.className = 'mr-2';
        downloadBtn.textContent = 'Download';
        buttonDiv.appendChild(downloadBtn);

        const deleteBtn = document.createElement('button');
        deleteBtn.dataset.action = 'delete';
        deleteBtn.dataset.id = summary.id;
        deleteBtn.className = 'text-red-400 hover:text-red-300';
        deleteBtn.textContent = 'Delete';
        buttonDiv.appendChild(deleteBtn);

        flexDiv.appendChild(buttonDiv);
        card.appendChild(flexDiv);

        const idP = document.createElement('p');
        idP.className = 'text-xs text-gray-500 mt-3';
        idP.textContent = 'ID: ' + summary.id;
        card.appendChild(idP);

        list.appendChild(card);
    });
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
