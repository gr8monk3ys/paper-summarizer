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
        evidenceList.textContent = '';
        const failP = document.createElement('p');
        failP.className = 'text-gray-500';
        failP.textContent = 'Failed to load evidence.';
        evidenceList.appendChild(failP);
        return;
    }
    const data = await response.json();
    if (!data.items || data.items.length === 0) {
        evidenceList.textContent = '';
        const emptyP = document.createElement('p');
        emptyP.className = 'text-gray-500';
        emptyP.textContent = 'No evidence items yet.';
        evidenceList.appendChild(emptyP);
        return;
    }
    evidenceList.textContent = '';
    data.items.forEach(item => {
        const card = document.createElement('div');
        card.className = 'summary-card';

        const flexOuter = document.createElement('div');
        flexOuter.className = 'flex justify-between items-start gap-3';

        const contentDiv = document.createElement('div');
        contentDiv.className = 'flex-1';

        const claimH4 = document.createElement('h4');
        claimH4.className = 'font-semibold mb-2';
        claimH4.textContent = item.claim;
        contentDiv.appendChild(claimH4);

        const evidenceP = document.createElement('p');
        evidenceP.textContent = item.evidence;
        contentDiv.appendChild(evidenceP);

        if (item.location) {
            const locationP = document.createElement('p');
            locationP.className = 'text-xs text-gray-500 mt-2';
            locationP.textContent = item.location;
            contentDiv.appendChild(locationP);
        }

        flexOuter.appendChild(contentDiv);

        const actionDiv = document.createElement('div');
        actionDiv.className = 'flex gap-2';

        const editBtn = document.createElement('button');
        editBtn.className = 'text-xs text-gray-400 hover:text-gray-200';
        editBtn.dataset.action = 'edit';
        editBtn.dataset.id = item.id;
        editBtn.textContent = 'Edit';
        actionDiv.appendChild(editBtn);

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'text-xs text-red-400 hover:text-red-300';
        deleteBtn.dataset.action = 'delete';
        deleteBtn.dataset.id = item.id;
        deleteBtn.textContent = 'Delete';
        actionDiv.appendChild(deleteBtn);

        flexOuter.appendChild(actionDiv);
        card.appendChild(flexOuter);

        const editDiv = document.createElement('div');
        editDiv.id = 'evidence-edit-' + item.id;
        editDiv.className = 'hidden mt-3 space-y-2';

        const claimInput = document.createElement('input');
        claimInput.className = 'form-input';
        claimInput.id = 'claim-' + item.id;
        claimInput.value = item.claim;
        editDiv.appendChild(claimInput);

        const evidenceInput = document.createElement('input');
        evidenceInput.className = 'form-input';
        evidenceInput.id = 'evidence-' + item.id;
        evidenceInput.value = item.evidence;
        editDiv.appendChild(evidenceInput);

        const locationInput = document.createElement('input');
        locationInput.className = 'form-input';
        locationInput.id = 'location-' + item.id;
        locationInput.value = item.location || '';
        editDiv.appendChild(locationInput);

        const editActionDiv = document.createElement('div');
        editActionDiv.className = 'flex gap-2';

        const saveBtn = document.createElement('button');
        saveBtn.className = 'submit-button';
        saveBtn.dataset.action = 'save';
        saveBtn.dataset.id = item.id;
        saveBtn.textContent = 'Save';
        editActionDiv.appendChild(saveBtn);

        const cancelBtn = document.createElement('button');
        cancelBtn.className = 'submit-button';
        cancelBtn.dataset.action = 'cancel';
        cancelBtn.dataset.id = item.id;
        cancelBtn.textContent = 'Cancel';
        editActionDiv.appendChild(cancelBtn);

        editDiv.appendChild(editActionDiv);
        card.appendChild(editDiv);

        evidenceList.appendChild(card);
    });
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
        historyList.textContent = '';

        if (!data.summaries || data.summaries.length === 0) {
            const noSummP = document.createElement('p');
            noSummP.className = 'text-gray-500';
            noSummP.textContent = 'No summaries yet.';
            historyList.appendChild(noSummP);
            return;
        }

        data.summaries.slice(0, 5).forEach(summary => {
            const card = document.createElement('div');
            card.className = 'summary-card';

            const h3 = document.createElement('h3');
            h3.className = 'font-semibold mb-2';
            h3.textContent = summary.title || 'Untitled Summary';
            card.appendChild(h3);

            const p = document.createElement('p');
            p.textContent = summary.summary;
            card.appendChild(p);

            historyList.appendChild(card);
        });
    } catch (error) {
        historyList.textContent = '';
        const histFailP = document.createElement('p');
        histFailP.className = 'text-gray-500';
        histFailP.textContent = 'Failed to load history.';
        historyList.appendChild(histFailP);
    }
}

// Load history on page load
document.addEventListener('DOMContentLoaded', function() {
    if (document.getElementById('history-view')) {
        loadHistory();
    }
});
