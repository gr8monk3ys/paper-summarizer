async function loadSummaries() {
    const container = document.getElementById('summary-picker');
    const response = await authFetch('/api/summaries');
    if (!response.ok) {
        container.textContent = '';
        const failP = document.createElement('p');
        failP.className = 'text-gray-500';
        failP.textContent = 'Failed to load summaries.';
        container.appendChild(failP);
        return;
    }
    const data = await response.json();
    if (!data.summaries || data.summaries.length === 0) {
        container.textContent = '';
        const emptyP = document.createElement('p');
        emptyP.className = 'text-gray-500';
        emptyP.textContent = 'No summaries available.';
        container.appendChild(emptyP);
        return;
    }

    container.textContent = '';
    data.summaries.forEach(item => {
        const label = document.createElement('label');
        label.className = 'summary-card flex items-start gap-3';

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = item.id;
        checkbox.className = 'form-checkbox mt-1';
        label.appendChild(checkbox);

        const div = document.createElement('div');

        const titleDiv = document.createElement('div');
        titleDiv.className = 'font-semibold';
        titleDiv.textContent = item.title || 'Untitled Summary';
        div.appendChild(titleDiv);

        const idDiv = document.createElement('div');
        idDiv.className = 'text-sm text-gray-500';
        idDiv.textContent = 'ID: ' + item.id;
        div.appendChild(idDiv);

        label.appendChild(div);
        container.appendChild(label);
    });
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
        citations.textContent = '';
        data.citations.forEach(item => {
            const div = document.createElement('div');
            div.className = 'text-sm';
            div.textContent = '[' + item.summary_id.slice(0, 8) + '] ' + (item.title || 'Untitled') + ' \u2014 ' + item.excerpt;
            citations.appendChild(div);
        });
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
