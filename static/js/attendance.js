/**
 * Attendance Management JavaScript for Punch Bot Management Interface
 */

/**
 * Initialize attendance page
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize date pickers
    initDatePickers();
    
    // Initialize form validation
    initFormValidation();
    
    // Initialize tooltips
    initTooltips();
    
    // Setup real-time updates
    setupRealTimeUpdates();
    
    // Setup filters
    setupFilters();
    
    // Initialize charts if on dashboard
    initAttendanceCharts();
});

/**
 * Initialize date pickers
 */
function initDatePickers() {
    const dateInputs = document.querySelectorAll('input[type="date"]');
    const datetimeInputs = document.querySelectorAll('input[type="datetime-local"]');
    
    // Set default values and constraints
    const today = new Date().toISOString().split('T')[0];
    
    dateInputs.forEach(input => {
        if (!input.value && input.name.includes('start')) {
            // Default start date to beginning of current month
            const firstDay = new Date();
            firstDay.setDate(1);
            input.value = firstDay.toISOString().split('T')[0];
        }
        
        if (!input.value && input.name.includes('end')) {
            input.value = today;
        }
        
        // Set max date to today for historical data
        if (input.name.includes('date')) {
            input.max = today;
        }
    });
    
    datetimeInputs.forEach(input => {
        if (!input.value) {
            // Default to current time
            const now = new Date();
            now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
            input.value = now.toISOString().slice(0, 16);
        }
    });
}

/**
 * Delete attendance record
 */
async function deleteRecord(recordId, confirmMessage = '確定要刪除這個打卡記錄嗎？') {
    if (!confirm(confirmMessage)) {
        return;
    }
    
    try {
        const response = await fetch(`/admin/attendance/${recordId}/delete`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            // Remove row from table
            const row = document.querySelector(`tr[data-record-id="${recordId}"]`);
            if (row) {
                row.style.transition = 'opacity 0.3s';
                row.style.opacity = '0';
                setTimeout(() => row.remove(), 300);
            }
            
            showAlert('打卡記錄已刪除', 'success');
        } else {
            throw new Error('Failed to delete record');
        }
    } catch (error) {
        console.error('Error deleting record:', error);
        showAlert('刪除失敗，請稍後再試', 'danger');
    }
}

/**
 * Quick punch for user (admin function)
 */
async function quickPunch(userId, action) {
    try {
        const response = await fetch('/admin/attendance/quick-punch', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_id: userId,
                action: action,
                timestamp: new Date().toISOString(),
                note: `管理員代理打卡 - ${action}`
            })
        });
        
        if (response.ok) {
            showAlert(`${action} 打卡成功`, 'success');
            
            // Refresh the page or update the UI
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            throw new Error('Failed to punch');
        }
    } catch (error) {
        console.error('Quick punch failed:', error);
        showAlert('代理打卡失敗', 'danger');
    }
}

/**
 * Export attendance records
 */
function exportRecords(format = 'csv') {
    const form = document.querySelector('form[method="GET"]');
    const searchParams = new URLSearchParams();
    
    if (form) {
        const formData = new FormData(form);
        for (let [key, value] of formData.entries()) {
            if (value) {
                searchParams.append(key, value);
            }
        }
    }
    
    searchParams.append('format', format);
    
    const exportUrl = `/admin/attendance/export/${format}?${searchParams.toString()}`;
    
    // Create download link
    const link = document.createElement('a');
    link.href = exportUrl;
    link.download = `attendance_records_${new Date().toISOString().split('T')[0]}.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showAlert(`正在匯出 ${format.toUpperCase()} 格式資料`, 'success');
}

/**
 * Setup real-time updates
 */
function setupRealTimeUpdates() {
    // Check if we're on the main attendance page
    if (window.location.pathname === '/admin/attendance') {
        // Refresh every 30 seconds
        setInterval(refreshAttendanceData, 30000);
    }
    
    // Setup WebSocket for real-time updates (if implemented)
    setupWebSocket();
}

/**
 * Refresh attendance data
 */
async function refreshAttendanceData() {
    try {
        // Get current filters
        const searchParams = new URLSearchParams(window.location.search);
        
        const response = await fetch(`/admin/attendance/api/recent?${searchParams.toString()}`);
        if (response.ok) {
            const data = await response.json();
            updateAttendanceTable(data.records);
            
            // Show subtle update indicator
            showUpdateIndicator();
        }
    } catch (error) {
        console.error('Failed to refresh attendance data:', error);
    }
}

/**
 * Update attendance table
 */
function updateAttendanceTable(records) {
    const tbody = document.querySelector('.attendance-table tbody');
    if (!tbody || !records) return;
    
    // Clear existing rows
    tbody.innerHTML = '';
    
    // Add new rows
    records.forEach(record => {
        const row = createAttendanceRow(record);
        tbody.appendChild(row);
    });
}

/**
 * Create attendance table row
 */
function createAttendanceRow(record) {
    const row = document.createElement('tr');
    row.setAttribute('data-record-id', record.id);
    
    const actionBadgeClass = {
        'in': 'bg-success',
        'out': 'bg-info',
        'break': 'bg-warning',
        'back': 'bg-primary'
    }[record.action] || 'bg-secondary';
    
    const actionText = {
        'in': '進入',
        'out': '離開',
        'break': '休息',
        'back': '回來'
    }[record.action] || record.action;
    
    row.innerHTML = `
        <td>
            <a href="/admin/users/${record.user.id}" class="text-decoration-none">
                ${record.user.internal_real_name}
            </a>
        </td>
        <td>
            <span class="badge bg-secondary">${record.user.department || '未分組'}</span>
        </td>
        <td>
            <span class="badge ${actionBadgeClass}">${actionText}</span>
        </td>
        <td>${formatDateTime(record.timestamp)}</td>
        <td>
            ${record.is_auto 
                ? '<i class="bi bi-robot text-warning" title="自動打卡"></i>' 
                : '<i class="bi bi-person text-success" title="手動打卡"></i>'
            }
        </td>
        <td>${record.note || '-'}</td>
        <td>
            <div class="btn-group btn-group-sm" role="group">
                <a href="/admin/attendance/${record.id}" class="btn btn-outline-info" title="查看詳情">
                    <i class="bi bi-eye"></i>
                </a>
                <a href="/admin/attendance/${record.id}/edit" class="btn btn-outline-warning" title="編輯">
                    <i class="bi bi-pencil"></i>
                </a>
                <button type="button" class="btn btn-outline-danger" title="刪除"
                        onclick="deleteRecord(${record.id})">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        </td>
    `;
    
    return row;
}

/**
 * Setup filters
 */
function setupFilters() {
    const filterForm = document.querySelector('.filter-form');
    if (!filterForm) return;
    
    // Auto-submit on filter change
    const filterInputs = filterForm.querySelectorAll('select, input[type="date"]');
    filterInputs.forEach(input => {
        input.addEventListener('change', function() {
            // Add a small delay to prevent too frequent requests
            setTimeout(() => {
                filterForm.submit();
            }, 300);
        });
    });
    
    // Quick date filters
    const quickFilters = document.querySelectorAll('.quick-date-filter');
    quickFilters.forEach(filter => {
        filter.addEventListener('click', function(e) {
            e.preventDefault();
            const range = this.getAttribute('data-range');
            applyDateRange(range);
        });
    });
}

/**
 * Apply quick date range filters
 */
function applyDateRange(range) {
    const startDateInput = document.querySelector('input[name="start_date"]');
    const endDateInput = document.querySelector('input[name="end_date"]');
    
    if (!startDateInput || !endDateInput) return;
    
    const today = new Date();
    let startDate, endDate;
    
    switch (range) {
        case 'today':
            startDate = endDate = today;
            break;
        case 'yesterday':
            startDate = endDate = new Date(today.getTime() - 24 * 60 * 60 * 1000);
            break;
        case 'this-week':
            startDate = new Date(today.setDate(today.getDate() - today.getDay()));
            endDate = new Date();
            break;
        case 'last-week':
            const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
            startDate = new Date(lastWeek.setDate(lastWeek.getDate() - lastWeek.getDay()));
            endDate = new Date(startDate.getTime() + 6 * 24 * 60 * 60 * 1000);
            break;
        case 'this-month':
            startDate = new Date(today.getFullYear(), today.getMonth(), 1);
            endDate = new Date();
            break;
        case 'last-month':
            startDate = new Date(today.getFullYear(), today.getMonth() - 1, 1);
            endDate = new Date(today.getFullYear(), today.getMonth(), 0);
            break;
        default:
            return;
    }
    
    startDateInput.value = startDate.toISOString().split('T')[0];
    endDateInput.value = endDate.toISOString().split('T')[0];
    
    // Submit form
    startDateInput.closest('form').submit();
}

/**
 * Setup WebSocket for real-time updates
 */
function setupWebSocket() {
    // This would be implemented if WebSocket support is added
    // for real-time attendance updates
    
    /*
    const ws = new WebSocket('ws://localhost:8000/ws/attendance');
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        if (data.type === 'attendance_update') {
            refreshAttendanceData();
        }
    };
    */
}

/**
 * Initialize attendance charts
 */
function initAttendanceCharts() {
    // Daily pattern chart
    const dailyPatternCtx = document.getElementById('dailyPatternChart');
    if (dailyPatternCtx) {
        createDailyPatternChart(dailyPatternCtx);
    }
    
    // Action distribution chart
    const actionDistCtx = document.getElementById('actionDistributionChart');
    if (actionDistCtx) {
        createActionDistributionChart(actionDistCtx);
    }
    
    // Hourly distribution chart
    const hourlyDistCtx = document.getElementById('hourlyDistributionChart');
    if (hourlyDistCtx) {
        createHourlyDistributionChart(hourlyDistCtx);
    }
}

/**
 * Create daily pattern chart
 */
function createDailyPatternChart(ctx) {
    fetch('/admin/attendance/api/daily-pattern')
        .then(response => response.json())
        .then(data => {
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: '打卡次數',
                        data: data.values,
                        borderColor: '#0d6efd',
                        backgroundColor: 'rgba(13, 110, 253, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Failed to load daily pattern chart:', error));
}

/**
 * Create action distribution chart
 */
function createActionDistributionChart(ctx) {
    fetch('/admin/attendance/api/action-distribution')
        .then(response => response.json())
        .then(data => {
            new Chart(ctx, {
                type: 'doughnut',
                data: {
                    labels: data.labels,
                    datasets: [{
                        data: data.values,
                        backgroundColor: [
                            '#198754', // in - green
                            '#0dcaf0', // out - info
                            '#ffc107', // break - warning
                            '#0d6efd'  // back - primary
                        ]
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false
                }
            });
        })
        .catch(error => console.error('Failed to load action distribution chart:', error));
}

/**
 * Create hourly distribution chart
 */
function createHourlyDistributionChart(ctx) {
    fetch('/admin/attendance/api/hourly-distribution')
        .then(response => response.json())
        .then(data => {
            new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: '打卡次數',
                        data: data.values,
                        backgroundColor: 'rgba(13, 110, 253, 0.8)',
                        borderColor: '#0d6efd',
                        borderWidth: 1
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            display: false
                        }
                    },
                    scales: {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Failed to load hourly distribution chart:', error));
}

/**
 * Show update indicator
 */
function showUpdateIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'update-indicator position-fixed';
    indicator.style.cssText = 'top: 70px; right: 20px; z-index: 1050;';
    indicator.innerHTML = `
        <div class="alert alert-success alert-dismissible fade show">
            <i class="bi bi-check-circle me-1"></i>
            資料已更新
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;
    
    document.body.appendChild(indicator);
    
    setTimeout(() => {
        if (indicator.parentNode) {
            indicator.remove();
        }
    }, 3000);
}

/**
 * Initialize form validation
 */
function initFormValidation() {
    const forms = document.querySelectorAll('.needs-validation');
    
    forms.forEach(form => {
        form.addEventListener('submit', function(event) {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            
            form.classList.add('was-validated');
        });
    });
    
    // Custom validation for datetime inputs
    const datetimeInputs = document.querySelectorAll('input[type="datetime-local"]');
    datetimeInputs.forEach(input => {
        input.addEventListener('change', function() {
            const selectedDate = new Date(this.value);
            const now = new Date();
            
            if (selectedDate > now) {
                this.setCustomValidity('不能選擇未來的時間');
            } else {
                this.setCustomValidity('');
            }
        });
    });
}

/**
 * Initialize tooltips
 */
function initTooltips() {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Show alert message
 */
function showAlert(message, type = 'info') {
    const alertContainer = document.getElementById('alertContainer') || createAlertContainer();
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    alertContainer.appendChild(alert);
    
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

/**
 * Create alert container
 */
function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alertContainer';
    container.style.cssText = 'position: fixed; top: 70px; right: 20px; z-index: 1050; max-width: 400px;';
    document.body.appendChild(container);
    return container;
}

/**
 * Format datetime for display
 */
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('zh-TW') + ' ' + date.toLocaleTimeString('zh-TW', {
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Format time duration
 */
function formatDuration(minutes) {
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;
    return `${hours}:${mins.toString().padStart(2, '0')}`;
}

// Global functions
window.deleteRecord = deleteRecord;
window.quickPunch = quickPunch;
window.exportRecords = exportRecords;