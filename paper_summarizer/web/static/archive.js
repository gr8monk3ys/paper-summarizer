async function exportAll() {
    const status = document.getElementById('archive-status');
    const response = await authFetch('/api/summaries/export');
    if (!response.ok) {
        status.textContent = 'Export failed.';
        return;
    }
    const data = await response.json();
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'paper_summaries.json';
    document.body.appendChild(a);
    a.click();
    URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

async function importAll() {
    const status = document.getElementById('archive-status');
    const fileInput = document.getElementById('importFile');
    if (!fileInput.files.length) {
        status.textContent = 'Select a JSON file first.';
        return;
    }
    const file = fileInput.files[0];
    const text = await file.text();
    let payload;
    try {
        payload = JSON.parse(text);
    } catch (err) {
        status.textContent = 'Invalid JSON file.';
        return;
    }

    const response = await authFetch('/api/summaries/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) {
        status.textContent = 'Import failed.';
        return;
    }
    const result = await response.json();
    status.textContent = `Imported ${result.count} summaries.`;
}

document.addEventListener('DOMContentLoaded', () => {
    const exportButton = document.getElementById('exportArchiveButton');
    const importButton = document.getElementById('importArchiveButton');
    if (exportButton) {
        exportButton.addEventListener('click', exportAll);
    }
    if (importButton) {
        importButton.addEventListener('click', importAll);
    }
});
