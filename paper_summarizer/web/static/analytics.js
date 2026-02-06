async function fetchAnalytics() {
    try {
        const response = await authFetch('/api/analytics');
        const data = await response.json();

        updateStatistics(data);
        createModelUsageChart(data.modelUsage || {});
        createLengthDistributionChart(data.lengthDistribution || {});
        createActivityChart(data.dailyActivity || {});
    } catch (error) {
        console.error('Failed to fetch analytics:', error);
    }
}

function updateStatistics(data) {
    document.getElementById('totalSummaries').textContent = data.totalSummaries;
    document.getElementById('avgLength').textContent = data.averageLength.toFixed(1);
    document.getElementById('modelsUsed').textContent = data.uniqueModels;
}

function createModelUsageChart(data) {
    const ctx = document.getElementById('modelUsageChart').getContext('2d');
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: Object.keys(data),
            datasets: [{
                data: Object.values(data),
                backgroundColor: [
                    '#ff6b4a',
                    '#4ade80',
                    '#60a5fa',
                    '#facc15',
                    '#fb7185'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

function createLengthDistributionChart(data) {
    const labels = Object.keys(data);
    const values = Object.values(data);
    if (!labels.length) {
        labels.push('N/A');
        values.push(0);
    }
    const ctx = document.getElementById('lengthDistChart').getContext('2d');
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Number of Summaries',
                data: values,
                backgroundColor: '#ff6b4a'
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

function createActivityChart(data) {
    const labels = Object.keys(data);
    const values = Object.values(data);
    if (!labels.length) {
        labels.push('N/A');
        values.push(0);
    }
    const ctx = document.getElementById('activityChart').getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                label: 'Summaries Created',
                data: values,
                borderColor: '#ff6b4a',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', fetchAnalytics);
