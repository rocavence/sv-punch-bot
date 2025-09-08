/**
 * Dashboard JavaScript for Punch Bot Management Interface
 */

let weeklyChart = null;

/**
 * Initialize weekly chart
 */
function initWeeklyChart(weekData) {
    const ctx = document.getElementById('weeklyChart').getContext('2d');
    
    weeklyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: weekData.map(item => item.day_name),
            datasets: [{
                label: '打卡記錄數',
                data: weekData.map(item => item.records),
                borderColor: '#0d6efd',
                backgroundColor: 'rgba(13, 110, 253, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointBackgroundColor: '#0d6efd',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    titleColor: 'white',
                    bodyColor: 'white',
                    borderColor: '#0d6efd',
                    borderWidth: 1,
                    callbacks: {
                        label: function(context) {
                            return `打卡記錄: ${context.parsed.y} 次`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#6c757d'
                    }
                },
                y: {
                    display: true,
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.1)',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#6c757d',
                        precision: 0
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });
}

/**
 * Refresh real-time statistics
 */
async function refreshStats() {
    try {
        const response = await fetch('/api/stats/realtime');
        const data = await response.json();
        
        if (data) {
            // Update statistics cards
            updateStatCard('totalUsers', data.total_users);
            updateStatCard('presentCount', data.present_count);
            updateStatCard('completedCount', data.completed_count);
            updateStatCard('anomalyCount', data.total_users - data.present_count);
            
            // Update last updated time
            const now = new Date();
            const timeStr = now.toLocaleTimeString('zh-TW', {
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            
            // Show a subtle update indicator
            showUpdateIndicator(`最後更新: ${timeStr}`);
        }
    } catch (error) {
        console.error('Failed to refresh stats:', error);
        showUpdateIndicator('更新失敗', 'error');
    }
}

/**
 * Update individual stat card
 */
function updateStatCard(elementId, newValue) {
    const element = document.getElementById(elementId);
    if (element && element.textContent !== newValue.toString()) {
        // Add animation effect
        element.classList.add('stat-updating');
        setTimeout(() => {
            element.textContent = newValue;
            element.classList.remove('stat-updating');
        }, 150);
    }
}

/**
 * Show update indicator
 */
function showUpdateIndicator(message, type = 'success') {
    // Remove existing indicator
    const existing = document.querySelector('.update-indicator');
    if (existing) {
        existing.remove();
    }
    
    // Create new indicator
    const indicator = document.createElement('div');
    indicator.className = `update-indicator alert alert-${type === 'error' ? 'danger' : 'success'} alert-dismissible fade show position-fixed`;
    indicator.style.cssText = 'top: 70px; right: 20px; z-index: 1050; min-width: 250px;';
    indicator.innerHTML = `
        <small>${message}</small>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(indicator);
    
    // Auto remove after 3 seconds
    setTimeout(() => {
        if (indicator.parentNode) {
            indicator.remove();
        }
    }, 3000);
}

/**
 * Update weekly chart data
 */
async function updateWeeklyChart() {
    try {
        const response = await fetch('/api/stats/weekly');
        const data = await response.json();
        
        if (data.week_data && weeklyChart) {
            weeklyChart.data.labels = data.week_data.map(item => item.day);
            weeklyChart.data.datasets[0].data = data.week_data.map(item => item.records);
            weeklyChart.update('active');
        }
    } catch (error) {
        console.error('Failed to update weekly chart:', error);
    }
}

/**
 * Format number with animation
 */
function animateNumber(element, start, end, duration = 1000) {
    const range = end - start;
    const minTimer = 50;
    let stepTime = Math.abs(Math.floor(duration / range));
    
    stepTime = Math.max(stepTime, minTimer);
    
    const startTime = new Date().getTime();
    const endTime = startTime + duration;
    let timer;

    function run() {
        const now = new Date().getTime();
        const remaining = Math.max((endTime - now) / duration, 0);
        const value = Math.round(end - (remaining * range));
        
        element.textContent = value;
        
        if (value === end) {
            clearInterval(timer);
        }
    }
    
    timer = setInterval(run, stepTime);
    run();
}

/**
 * Initialize dashboard tooltips
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Handle window resize for chart responsiveness
 */
function handleResize() {
    if (weeklyChart) {
        weeklyChart.resize();
    }
}

/**
 * Export dashboard data
 */
async function exportDashboardData(format = 'csv') {
    try {
        const response = await fetch(`/api/dashboard/export?format=${format}`);
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `dashboard_export_${new Date().toISOString().split('T')[0]}.${format}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            showUpdateIndicator('資料匯出成功');
        } else {
            throw new Error('Export failed');
        }
    } catch (error) {
        console.error('Export failed:', error);
        showUpdateIndicator('資料匯出失敗', 'error');
    }
}

/**
 * Print dashboard
 */
function printDashboard() {
    window.print();
}

/**
 * Toggle dark mode
 */
function toggleDarkMode() {
    document.body.classList.toggle('dark-mode');
    localStorage.setItem('darkMode', document.body.classList.contains('dark-mode'));
}

/**
 * Initialize dark mode from localStorage
 */
function initDarkMode() {
    if (localStorage.getItem('darkMode') === 'true') {
        document.body.classList.add('dark-mode');
    }
}

/**
 * Refresh page data
 */
async function refreshPage() {
    // Show loading indicator
    const refreshBtn = document.querySelector('[onclick="refreshStats()"]');
    if (refreshBtn) {
        refreshBtn.classList.add('loading');
        refreshBtn.disabled = true;
    }
    
    try {
        // Refresh stats and chart
        await Promise.all([
            refreshStats(),
            updateWeeklyChart()
        ]);
        
        // Optionally reload the page for fresh data
        // window.location.reload();
        
    } finally {
        // Remove loading indicator
        if (refreshBtn) {
            refreshBtn.classList.remove('loading');
            refreshBtn.disabled = false;
        }
    }
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initTooltips();
    
    // Initialize dark mode
    initDarkMode();
    
    // Handle window resize
    window.addEventListener('resize', handleResize);
    
    // Auto-refresh every 30 seconds
    setInterval(refreshStats, 30000);
    
    // Update weekly chart every 5 minutes
    setInterval(updateWeeklyChart, 300000);
});

// CSS animations
const style = document.createElement('style');
style.textContent = `
    .stat-updating {
        animation: pulse 0.3s ease-in-out;
        color: #0d6efd !important;
    }
    
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.05); }
        100% { transform: scale(1); }
    }
    
    .loading {
        position: relative;
        color: transparent !important;
    }
    
    .loading::after {
        content: '';
        position: absolute;
        width: 16px;
        height: 16px;
        top: 50%;
        left: 50%;
        margin-left: -8px;
        margin-top: -8px;
        border: 2px solid #f3f3f3;
        border-top: 2px solid #0d6efd;
        border-radius: 50%;
        animation: spin 1s linear infinite;
    }
    
    @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }
    
    .dark-mode {
        background-color: #1a1d23 !important;
        color: #e2e8f0 !important;
    }
    
    .dark-mode .card {
        background-color: #2d3748 !important;
        color: #e2e8f0 !important;
    }
    
    .dark-mode .sidebar {
        background-color: #2d3748 !important;
        border-color: #4a5568 !important;
    }
`;
document.head.appendChild(style);

// Global functions
window.refreshStats = refreshStats;
window.exportDashboardData = exportDashboardData;
window.printDashboard = printDashboard;
window.toggleDarkMode = toggleDarkMode;