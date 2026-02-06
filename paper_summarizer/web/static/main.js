function showError(message) {
    const errorDiv = document.getElementById('error-message');
    if (!errorDiv) {
        return;
    }
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

function setLoading(isLoading) {
    const spinner = document.getElementById('loading-spinner');
    const submitButtons = document.querySelectorAll('button[type="submit"]');
    if (spinner) {
        spinner.style.display = isLoading ? 'block' : 'none';
    }
    submitButtons.forEach(button => {
        button.disabled = isLoading;
    });
}

// Form submission handlers
document.addEventListener('DOMContentLoaded', function() {
    const mobileMenuButton = document.querySelector('.mobile-menu-button');
    const mobileMenu = document.getElementById('mobile-menu');
    if (mobileMenuButton && mobileMenu) {
        mobileMenuButton.addEventListener('click', () => {
            mobileMenu.classList.toggle('hidden');
            const expanded = mobileMenuButton.getAttribute('aria-expanded') === 'true';
            mobileMenuButton.setAttribute('aria-expanded', String(!expanded));
        });
    }

    const commonOptionsTemplate = document.getElementById('common-options-template');
    if (commonOptionsTemplate) {
        document.querySelectorAll('.common-options').forEach(container => {
            container.appendChild(commonOptionsTemplate.content.cloneNode(true));
        });
    }

    // Handle form submissions
    async function handleSubmit(event) {
        event.preventDefault();
        const form = event.target;
        const formData = new FormData(form);
        
        try {
            setLoading(true);
            const response = await authFetch('/summarize', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate summary');
            }
            
            document.getElementById('summary').textContent = data.summary;
            const resultDiv = document.getElementById('result');
            resultDiv.dataset.entryId = data.summary_id || '';
            resultDiv.classList.remove('hidden');
            resultDiv.classList.add('visible');
            loadEvidence();
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

            if (target === 'history-view') {
                loadHistory();
            }
        });
    });

    const generateEvidenceButton = document.getElementById('generateEvidenceButton');
    if (generateEvidenceButton) {
        generateEvidenceButton.addEventListener('click', generateEvidence);
    }
    const addEvidenceButton = document.getElementById('addEvidenceButton');
    if (addEvidenceButton) {
        addEvidenceButton.addEventListener('click', addEvidence);
    }
    const exportMenuToggle = document.getElementById('exportMenuToggle');
    if (exportMenuToggle) {
        exportMenuToggle.addEventListener('click', toggleExportMenu);
    }
    document.querySelectorAll('[data-action=\"export-summary\"]').forEach(button => {
        button.addEventListener('click', () => exportSummary(button.dataset.format));
    });
    const runSynthesisButton = document.getElementById('runSynthesisButton');
    if (runSynthesisButton) {
        runSynthesisButton.addEventListener('click', runSynthesis);
    }
    document.querySelectorAll('[data-action=\"export-synthesis\"]').forEach(button => {
        button.addEventListener('click', () => exportSynthesis(button.dataset.format));
    });

    const evidenceList = document.getElementById('evidence-list');
    if (evidenceList) {
        evidenceList.addEventListener('click', event => {
            const button = event.target.closest('button[data-action]');
            if (!button) {
                return;
            }
            const action = button.dataset.action;
            const evidenceId = button.dataset.id;
            if (action === 'edit') {
                startEditEvidence(evidenceId);
            } else if (action === 'delete') {
                deleteEvidence(evidenceId);
            } else if (action === 'save') {
                saveEvidence(evidenceId);
            } else if (action === 'cancel') {
                cancelEditEvidence(evidenceId);
            }
        });
    }
});

// Export functionality
async function exportSummary(format = 'txt') {
    const result = document.getElementById('result');
    const entryId = result.dataset.entryId;
    if (!entryId) {
        showError('No summary to export');
        return;
    }

    try {
        const response = await authFetch(`/export/${entryId}?format=${format}`);
        if (!response.ok) {
            throw new Error('Failed to export summary');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        if (format === 'md') {
            a.download = `summary_${entryId}.md`;
        } else if (format === 'pdf') {
            a.download = `summary_${entryId}.pdf`;
        } else {
            a.download = `summary_${entryId}.txt`;
        }
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    } catch (error) {
        showError(error.message);
    }
}

async function loadEvidence() {
    const result = document.getElementById('result');
    const entryId = result.dataset.entryId;
    const evidenceList = document.getElementById('evidence-list');
    if (!entryId || !evidenceList) {
        return;
    }

    const response = await authFetch(`/api/summaries/${entryId}/evidence`);
    if (!response.ok) {
        evidenceList.innerHTML = '<p class="text-gray-500">Failed to load evidence.</p>';
        return;
    }
    const data = await response.json();
    if (!data.items || data.items.length === 0) {
        evidenceList.innerHTML = '<p class="text-gray-500">No evidence items yet.</p>';
        return;
    }
    evidenceList.innerHTML = data.items.map(item => `
        <div class="summary-card">
            <div class="flex justify-between items-start gap-3">
                <div class="flex-1">
                    <h4 class="font-semibold mb-2">${item.claim}</h4>
                    <p>${item.evidence}</p>
                    ${item.location ? `<p class="text-xs text-gray-500 mt-2">${item.location}</p>` : ''}
                </div>
                <div class="flex gap-2">
                    <button class="text-xs text-gray-400 hover:text-gray-200" data-action="edit" data-id="${item.id}">Edit</button>
                    <button class="text-xs text-red-400 hover:text-red-300" data-action="delete" data-id="${item.id}">Delete</button>
                </div>
            </div>
            <div id="evidence-edit-${item.id}" class="hidden mt-3 space-y-2">
                <input class="form-input" id="claim-${item.id}" value="${item.claim}" />
                <input class="form-input" id="evidence-${item.id}" value="${item.evidence}" />
                <input class="form-input" id="location-${item.id}" value="${item.location || ''}" />
                <div class="flex gap-2">
                    <button class="submit-button" data-action="save" data-id="${item.id}">Save</button>
                    <button class="submit-button" data-action="cancel" data-id="${item.id}">Cancel</button>
                </div>
            </div>
        </div>
    `).join('');
}

async function generateEvidence() {
    const result = document.getElementById('result');
    const entryId = result.dataset.entryId;
    if (!entryId) {
        showError('Generate a summary first.');
        return;
    }
    const response = await authFetch(`/api/summaries/${entryId}/evidence/generate`, {
        method: 'POST'
    });
    if (!response.ok) {
        showError('Failed to generate evidence.');
        return;
    }
    loadEvidence();
}

async function addEvidence() {
    const result = document.getElementById('result');
    const entryId = result.dataset.entryId;
    if (!entryId) {
        showError('Generate a summary first.');
        return;
    }
    const claim = document.getElementById('evidence-claim').value.trim();
    const evidence = document.getElementById('evidence-evidence').value.trim();
    const location = document.getElementById('evidence-location').value.trim();
    if (!claim || !evidence) {
        showError('Claim and evidence are required.');
        return;
    }

    const response = await authFetch(`/api/summaries/${entryId}/evidence`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim, evidence, location: location || null })
    });
    if (!response.ok) {
        showError('Failed to add evidence.');
        return;
    }
    document.getElementById('evidence-claim').value = '';
    document.getElementById('evidence-evidence').value = '';
    document.getElementById('evidence-location').value = '';
    loadEvidence();
}

function startEditEvidence(id) {
    const edit = document.getElementById(`evidence-edit-${id}`);
    if (edit) {
        edit.classList.remove('hidden');
    }
}

function cancelEditEvidence(id) {
    const edit = document.getElementById(`evidence-edit-${id}`);
    if (edit) {
        edit.classList.add('hidden');
    }
}

async function saveEvidence(id) {
    const result = document.getElementById('result');
    const entryId = result.dataset.entryId;
    const claim = document.getElementById(`claim-${id}`).value.trim();
    const evidence = document.getElementById(`evidence-${id}`).value.trim();
    const location = document.getElementById(`location-${id}`).value.trim();
    if (!claim || !evidence) {
        showError('Claim and evidence are required.');
        return;
    }

    const response = await authFetch(`/api/summaries/${entryId}/evidence/${id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ claim, evidence, location: location || null })
    });
    if (!response.ok) {
        showError('Failed to update evidence.');
        return;
    }
    loadEvidence();
}

async function deleteEvidence(id) {
    const result = document.getElementById('result');
    const entryId = result.dataset.entryId;
    const response = await authFetch(`/api/summaries/${entryId}/evidence/${id}`, {
        method: 'DELETE'
    });
    if (!response.ok) {
        showError('Failed to delete evidence.');
        return;
    }
    loadEvidence();
}

async function runSynthesis() {
    const input = document.getElementById('synthesis-ids');
    const output = document.getElementById('synthesis-output');
    if (!input || !output) {
        return;
    }
    const ids = input.value.split(',').map(id => id.trim()).filter(Boolean);
    if (!ids.length) {
        output.textContent = 'Provide at least one summary ID.';
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
}

async function exportSynthesis(format = 'txt') {
    const output = document.getElementById('synthesis-output');
    if (!output || !output.textContent.trim()) {
        showError('Run synthesis first.');
        return;
    }
    const response = await authFetch(`/api/summaries/synthesize/export?format=${format}&consensus=${encodeURIComponent(output.textContent)}`);
    if (!response.ok) {
        showError('Failed to export synthesis.');
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

function toggleExportMenu() {
    const menu = document.getElementById('export-menu');
    if (!menu) {
        return;
    }
    menu.classList.toggle('hidden');
}

// History loading
async function loadHistory() {
    const historyList = document.getElementById('history-list');
    if (!historyList) {
        return;
    }
    try {
        const response = await authFetch('/api/summaries');
        const data = await response.json();
        historyList.innerHTML = '';

        if (!data.summaries || data.summaries.length === 0) {
            historyList.innerHTML = '<p class="text-gray-500">No summaries yet.</p>';
            return;
        }

        data.summaries.slice(0, 5).forEach(summary => {
            const card = document.createElement('div');
            card.className = 'summary-card';
            card.innerHTML = `
                <h3 class="font-semibold mb-2">${summary.title || 'Untitled Summary'}</h3>
                <p>${summary.summary}</p>
            `;
            historyList.appendChild(card);
        });
    } catch (error) {
        historyList.innerHTML = '<p class="text-gray-500">Failed to load history.</p>';
    }
}

// Load history on page load
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('history-view')) {
        loadHistory();
    }
});
