async function loadSummaries() {
    const container = document.getElementById('summary-picker');
    const response = await authFetch('/api/summaries');
    if (!response.ok) {
        container.innerHTML = '<p class="text-gray-500">Failed to load summaries.</p>';
        return;
    }
    const data = await response.json();
    if (!data.summaries || data.summaries.length === 0) {
        container.innerHTML = '<p class="text-gray-500">No summaries available.</p>';
        return;
    }

    container.innerHTML = data.summaries.map(item => `
        <label class="summary-card flex items-start gap-3">
            <input type="checkbox" value="${item.id}" class="form-checkbox mt-1" />
            <div>
                <div class="font-semibold">${item.title || 'Untitled Summary'}</div>
                <div class="text-sm text-gray-500">ID: ${item.id}</div>
            </div>
        </label>
    `).join('');
}

async function runSynthesis() {
    const checks = Array.from(document.querySelectorAll('#summary-picker input[type="checkbox"]:checked'));
    const ids = checks.map(input => input.value);
    const output = document.getElementById('synthesis-output');
    const disagreements = document.getElementById('synthesis-disagreements');
    const citations = document.getElementById('synthesis-citations');
    if (!ids.length) {
        output.textContent = 'Select at least one summary.';
        return;
    }

    const response = await authFetch('/api/summaries/synthesize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ summary_ids: ids })
    });
    if (!response.ok) {
        output.textContent = 'Synthesis failed.';
        return;
    }
    const data = await response.json();
    output.textContent = data.consensus;
    disagreements.textContent = data.disagreements && data.disagreements.length
        ? data.disagreements.join('\n')
        : 'No major disagreements detected.';
    if (data.citations && data.citations.length) {
        citations.innerHTML = data.citations.map(item => `
            <div class="text-sm">[${item.summary_id.slice(0, 8)}] ${item.title || 'Untitled'} — ${item.excerpt}</div>
        `).join('');
    } else {
        citations.textContent = '';
    }
}

async function exportSynthesis(format = 'txt') {
    const output = document.getElementById('synthesis-output');
    if (!output || !output.textContent.trim()) {
        return;
    }
    const response = await authFetch(`/api/summaries/synthesize/export?format=${format}&consensus=${encodeURIComponent(output.textContent)}`);
    if (!response.ok) {
        return;
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    if (format === 'md') {
        a.download = 'synthesis.md';
    } else if (format === 'pdf') {
        a.download = 'synthesis.pdf';
    } else {
        a.download = 'synthesis.txt';
    }
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

document.addEventListener('DOMContentLoaded', () => {
    loadSummaries();
    const runButton = document.getElementById('runSynthesisButton');
    if (runButton) {
        runButton.addEventListener('click', runSynthesis);
    }
    document.querySelectorAll('[data-action="export"]').forEach(button => {
        button.addEventListener('click', () => exportSynthesis(button.dataset.format));
    });
});
