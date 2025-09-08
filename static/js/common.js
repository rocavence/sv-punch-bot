/**
 * Common JavaScript utilities for Punch Bot Management Interface
 */

/**
 * Initialize common functionality
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap components
    initBootstrapComponents();
    
    // Setup CSRF token for AJAX requests
    setupCSRFToken();
    
    // Setup common event listeners
    setupEventListeners();
    
    // Initialize theme
    initTheme();
});

/**
 * Initialize Bootstrap components
 */
function initBootstrapComponents() {
    // Initialize all tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl, {
            delay: { show: 500, hide: 100 }
        });
    });
    
    // Initialize all popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        if (!alert.querySelector('.btn-close')) {
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.classList.add('fade');
                    alert.classList.remove('show');
                    setTimeout(() => alert.remove(), 150);
                }
            }, 5000);
        }
    });
}

/**
 * Setup CSRF token for AJAX requests
 */
function setupCSRFToken() {
    // Get CSRF token from meta tag or cookie
    const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') ||
                     getCookie('csrf_token');
    
    if (csrfToken) {
        // Set default headers for fetch requests
        const originalFetch = window.fetch;
        window.fetch = function(url, options = {}) {
            options.headers = {
                ...options.headers,
                'X-CSRFToken': csrfToken
            };
            return originalFetch(url, options);
        };
    }
}

/**
 * Setup common event listeners
 */
function setupEventListeners() {
    // Confirm delete buttons
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn-delete') || e.target.closest('.btn-delete')) {
            const button = e.target.classList.contains('btn-delete') ? e.target : e.target.closest('.btn-delete');
            const confirmMessage = button.getAttribute('data-confirm') || '確定要執行此操作嗎？';
            
            if (!confirm(confirmMessage)) {
                e.preventDefault();
                e.stopPropagation();
            }
        }
    });
    
    // Auto-save forms
    const autoSaveForms = document.querySelectorAll('.auto-save');
    autoSaveForms.forEach(form => {
        let saveTimeout;
        
        form.addEventListener('input', function() {
            clearTimeout(saveTimeout);
            saveTimeout = setTimeout(() => {
                autoSaveForm(form);
            }, 2000);
        });
    });
    
    // Copy to clipboard functionality
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('copy-btn') || e.target.closest('.copy-btn')) {
            const button = e.target.classList.contains('copy-btn') ? e.target : e.target.closest('.copy-btn');
            const text = button.getAttribute('data-copy') || button.textContent;
            
            copyToClipboard(text).then(() => {
                showToast('已複製到剪貼簿', 'success');
            }).catch(() => {
                showToast('複製失敗', 'error');
            });
        }
    });
    
    // Loading button states
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('btn-loading') || e.target.closest('.btn-loading')) {
            const button = e.target.classList.contains('btn-loading') ? e.target : e.target.closest('.btn-loading');
            setLoadingState(button, true);
        }
    });
    
    // Sidebar toggle for mobile
    const sidebarToggle = document.getElementById('sidebarToggle');
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            document.body.classList.toggle('sidebar-toggled');
        });
    }
}

/**
 * Initialize theme
 */
function initTheme() {
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.body.classList.add('dark-theme');
    }
    
    // Theme toggle button
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
}

/**
 * Toggle theme
 */
function toggleTheme() {
    const isDark = document.body.classList.toggle('dark-theme');
    localStorage.setItem('theme', isDark ? 'dark' : 'light');
    
    // Update theme toggle icon
    const themeIcon = document.querySelector('#themeToggle i');
    if (themeIcon) {
        themeIcon.className = isDark ? 'bi bi-sun' : 'bi bi-moon';
    }
}

/**
 * Get cookie value
 */
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

/**
 * Copy text to clipboard
 */
async function copyToClipboard(text) {
    if (navigator.clipboard) {
        return await navigator.clipboard.writeText(text);
    } else {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            document.execCommand('copy');
            textArea.remove();
            return Promise.resolve();
        } catch (err) {
            textArea.remove();
            return Promise.reject(err);
        }
    }
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info', duration = 3000) {
    // Remove existing toast container
    const existingContainer = document.getElementById('toast-container');
    if (existingContainer) {
        existingContainer.remove();
    }
    
    // Create toast container
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed top-0 end-0 p-3';
    container.style.zIndex = '1060';
    
    // Create toast
    const toast = document.createElement('div');
    toast.className = `toast align-items-center text-white bg-${getBootstrapColorClass(type)} border-0`;
    toast.setAttribute('role', 'alert');
    toast.innerHTML = `
        <div class="d-flex">
            <div class="toast-body">
                <i class="bi bi-${getToastIcon(type)} me-2"></i>
                ${message}
            </div>
            <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
        </div>
    `;
    
    container.appendChild(toast);
    document.body.appendChild(container);
    
    // Initialize and show toast
    const bsToast = new bootstrap.Toast(toast, {
        autohide: true,
        delay: duration
    });
    
    bsToast.show();
    
    // Remove container after toast is hidden
    toast.addEventListener('hidden.bs.toast', () => {
        container.remove();
    });
}

/**
 * Get Bootstrap color class for toast type
 */
function getBootstrapColorClass(type) {
    const colorMap = {
        'success': 'success',
        'error': 'danger',
        'warning': 'warning',
        'info': 'info'
    };
    return colorMap[type] || 'info';
}

/**
 * Get icon for toast type
 */
function getToastIcon(type) {
    const iconMap = {
        'success': 'check-circle',
        'error': 'x-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    return iconMap[type] || 'info-circle';
}

/**
 * Set loading state for button
 */
function setLoadingState(button, isLoading) {
    if (isLoading) {
        button.disabled = true;
        button.dataset.originalText = button.innerHTML;
        button.innerHTML = `
            <span class="spinner-border spinner-border-sm me-2" role="status"></span>
            載入中...
        `;
    } else {
        button.disabled = false;
        button.innerHTML = button.dataset.originalText || button.innerHTML;
    }
}

/**
 * Auto-save form
 */
async function autoSaveForm(form) {
    const formData = new FormData(form);
    const saveUrl = form.getAttribute('data-save-url') || form.action;
    
    try {
        const response = await fetch(saveUrl, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            showToast('自動儲存成功', 'success', 1500);
            
            // Add saved indicator
            const saveIndicator = form.querySelector('.save-indicator') || createSaveIndicator(form);
            saveIndicator.classList.add('saved');
            setTimeout(() => saveIndicator.classList.remove('saved'), 2000);
        }
    } catch (error) {
        console.error('Auto-save failed:', error);
        showToast('自動儲存失敗', 'error', 2000);
    }
}

/**
 * Create save indicator
 */
function createSaveIndicator(form) {
    const indicator = document.createElement('div');
    indicator.className = 'save-indicator';
    indicator.innerHTML = '<i class="bi bi-check-circle text-success"></i> 已儲存';
    indicator.style.cssText = 'position: absolute; top: -25px; right: 0; opacity: 0; transition: opacity 0.3s;';
    
    form.style.position = 'relative';
    form.appendChild(indicator);
    
    return indicator;
}

/**
 * Format number with thousand separators
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Debounce function
 */
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction() {
        const context = this;
        const args = arguments;
        
        const later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        
        if (callNow) func.apply(context, args);
    };
}

/**
 * Throttle function
 */
function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Check if element is in viewport
 */
function isInViewport(element) {
    const rect = element.getBoundingClientRect();
    return (
        rect.top >= 0 &&
        rect.left >= 0 &&
        rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
        rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    );
}

/**
 * Smooth scroll to element
 */
function scrollToElement(element, offset = 0) {
    const elementPosition = element.getBoundingClientRect().top + window.pageYOffset;
    const offsetPosition = elementPosition - offset;
    
    window.scrollTo({
        top: offsetPosition,
        behavior: 'smooth'
    });
}

/**
 * Generate unique ID
 */
function generateId(prefix = 'id') {
    return `${prefix}-${Math.random().toString(36).substr(2, 9)}`;
}

/**
 * Validate email format
 */
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

/**
 * Validate phone number format (Taiwan)
 */
function isValidPhone(phone) {
    const phoneRegex = /^(\+886|886|0)?(9\d{8}|[2-8]\d{7,8})$/;
    return phoneRegex.test(phone);
}

/**
 * Format date for display
 */
function formatDate(date, format = 'YYYY-MM-DD') {
    const d = new Date(date);
    const year = d.getFullYear();
    const month = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hours = String(d.getHours()).padStart(2, '0');
    const minutes = String(d.getMinutes()).padStart(2, '0');
    const seconds = String(d.getSeconds()).padStart(2, '0');
    
    return format
        .replace('YYYY', year)
        .replace('MM', month)
        .replace('DD', day)
        .replace('HH', hours)
        .replace('mm', minutes)
        .replace('ss', seconds);
}

/**
 * Get relative time string
 */
function getRelativeTime(date) {
    const now = new Date();
    const targetDate = new Date(date);
    const diffTime = now - targetDate;
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    const diffHours = Math.floor(diffTime / (1000 * 60 * 60));
    const diffMinutes = Math.floor(diffTime / (1000 * 60));
    
    if (diffDays > 7) {
        return formatDate(targetDate, 'YYYY-MM-DD');
    } else if (diffDays > 0) {
        return `${diffDays} 天前`;
    } else if (diffHours > 0) {
        return `${diffHours} 小時前`;
    } else if (diffMinutes > 0) {
        return `${diffMinutes} 分鐘前`;
    } else {
        return '剛剛';
    }
}

// CSS for common components
const commonStyles = `
.save-indicator.saved {
    opacity: 1 !important;
}

.dark-theme {
    background-color: #1a1d23 !important;
    color: #e2e8f0 !important;
}

.dark-theme .card {
    background-color: #2d3748 !important;
    border-color: #4a5568 !important;
}

.dark-theme .navbar {
    background-color: #2d3748 !important;
}

.dark-theme .sidebar {
    background-color: #2d3748 !important;
    border-color: #4a5568 !important;
}

.dark-theme .table {
    color: #e2e8f0 !important;
}

.dark-theme .table th,
.dark-theme .table td {
    border-color: #4a5568 !important;
}

.dark-theme .form-control,
.dark-theme .form-select {
    background-color: #4a5568 !important;
    border-color: #718096 !important;
    color: #e2e8f0 !important;
}

.dark-theme .form-control:focus,
.dark-theme .form-select:focus {
    background-color: #4a5568 !important;
    border-color: #0d6efd !important;
    color: #e2e8f0 !important;
}
`;

// Inject common styles
const styleElement = document.createElement('style');
styleElement.textContent = commonStyles;
document.head.appendChild(styleElement);

// Export utilities for use in other scripts
window.PunchBotUtils = {
    showToast,
    copyToClipboard,
    setLoadingState,
    formatNumber,
    formatFileSize,
    formatDate,
    getRelativeTime,
    isValidEmail,
    isValidPhone,
    debounce,
    throttle,
    isInViewport,
    scrollToElement,
    generateId
};