/**
 * Users Management JavaScript for Punch Bot Management Interface
 */

let currentUserId = null;
let statusModal = null;

/**
 * Initialize users page
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize modal
    const modalElement = document.getElementById('statusModal');
    if (modalElement) {
        statusModal = new bootstrap.Modal(modalElement);
    }
    
    // Initialize tooltips
    initTooltips();
    
    // Initialize form validation
    initFormValidation();
    
    // Setup search functionality
    setupSearch();
    
    // Setup bulk operations
    setupBulkOperations();
});

/**
 * Toggle user status
 */
async function toggleUserStatus(userId, checkbox) {
    const userName = checkbox.closest('tr').querySelector('strong').textContent;
    const isActive = checkbox.checked;
    const action = isActive ? '啟用' : '停用';
    
    // Show confirmation modal
    document.getElementById('statusModalText').textContent = 
        `確定要${action}用戶「${userName}」嗎？`;
    
    currentUserId = userId;
    
    // Set up confirmation handler
    document.getElementById('confirmStatusToggle').onclick = async function() {
        try {
            const response = await fetch(`/admin/users/${userId}/toggle`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                
                // Update checkbox state
                checkbox.checked = data.is_active;
                
                // Update label
                const label = checkbox.nextElementSibling;
                label.textContent = data.is_active ? '啟用' : '停用';
                
                // Update row style
                const row = checkbox.closest('tr');
                if (data.is_active) {
                    row.classList.remove('table-secondary');
                } else {
                    row.classList.add('table-secondary');
                }
                
                // Show success message
                showAlert(`用戶「${userName}」已${data.is_active ? '啟用' : '停用'}`, 'success');
                
                statusModal.hide();
            } else {
                throw new Error('Failed to toggle status');
            }
        } catch (error) {
            console.error('Error toggling user status:', error);
            
            // Revert checkbox state
            checkbox.checked = !isActive;
            
            showAlert('操作失敗，請稍後再試', 'danger');
            statusModal.hide();
        }
    };
    
    statusModal.show();
}

/**
 * Delete user
 */
async function deleteUser(userId, userName) {
    if (!confirm(`確定要刪除用戶「${userName}」嗎？此操作無法復原。`)) {
        return;
    }
    
    try {
        const response = await fetch(`/admin/users/${userId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            // Remove row from table
            const row = document.querySelector(`tr[data-user-id="${userId}"]`);
            if (row) {
                row.remove();
            }
            
            showAlert(`用戶「${userName}」已刪除`, 'success');
        } else {
            throw new Error('Failed to delete user');
        }
    } catch (error) {
        console.error('Error deleting user:', error);
        showAlert('刪除失敗，請稍後再試', 'danger');
    }
}

/**
 * Sync user from Slack
 */
async function syncUserFromSlack(userId, userName) {
    const button = event.target;
    const originalText = button.textContent;
    
    // Show loading state
    button.textContent = '同步中...';
    button.disabled = true;
    button.classList.add('loading');
    
    try {
        const response = await fetch(`/admin/users/${userId}/sync`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            showAlert(`用戶「${userName}」資料同步成功`, 'success');
            
            // Optionally reload the page to show updated data
            setTimeout(() => {
                window.location.reload();
            }, 1000);
        } else {
            throw new Error('Failed to sync user');
        }
    } catch (error) {
        console.error('Error syncing user:', error);
        showAlert('同步失敗，請稍後再試', 'danger');
    } finally {
        // Restore button state
        button.textContent = originalText;
        button.disabled = false;
        button.classList.remove('loading');
    }
}

/**
 * Setup search functionality
 */
function setupSearch() {
    const searchForm = document.querySelector('form[method="GET"]');
    if (!searchForm) return;
    
    // Add search input event listener for live search
    const searchInput = searchForm.querySelector('input[name="search"]');
    let searchTimeout;
    
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                // Auto-submit form for live search (optional)
                // searchForm.submit();
            }, 500);
        });
    }
    
    // Add Enter key handler
    searchInput?.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            searchForm.submit();
        }
    });
    
    // Clear search functionality
    const clearButton = document.getElementById('clearSearch');
    if (clearButton) {
        clearButton.addEventListener('click', function() {
            searchInput.value = '';
            document.querySelector('select[name="department"]').value = '';
            document.querySelector('select[name="status"]').value = '';
            searchForm.submit();
        });
    }
}

/**
 * Setup bulk operations
 */
function setupBulkOperations() {
    const selectAll = document.getElementById('selectAll');
    const userCheckboxes = document.querySelectorAll('.user-checkbox');
    const bulkActions = document.getElementById('bulkActions');
    
    if (!selectAll || !bulkActions) return;
    
    // Select all functionality
    selectAll.addEventListener('change', function() {
        userCheckboxes.forEach(checkbox => {
            checkbox.checked = this.checked;
        });
        toggleBulkActions();
    });
    
    // Individual checkbox change
    userCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            const checkedCount = document.querySelectorAll('.user-checkbox:checked').length;
            selectAll.checked = checkedCount === userCheckboxes.length;
            selectAll.indeterminate = checkedCount > 0 && checkedCount < userCheckboxes.length;
            toggleBulkActions();
        });
    });
    
    // Bulk actions
    document.getElementById('bulkActivate')?.addEventListener('click', () => bulkStatusChange(true));
    document.getElementById('bulkDeactivate')?.addEventListener('click', () => bulkStatusChange(false));
    document.getElementById('bulkDelete')?.addEventListener('click', bulkDelete);
    document.getElementById('bulkExport')?.addEventListener('click', bulkExport);
}

/**
 * Toggle bulk actions visibility
 */
function toggleBulkActions() {
    const checkedCount = document.querySelectorAll('.user-checkbox:checked').length;
    const bulkActions = document.getElementById('bulkActions');
    
    if (bulkActions) {
        bulkActions.style.display = checkedCount > 0 ? 'block' : 'none';
        
        // Update count in bulk actions
        const countSpan = bulkActions.querySelector('.selected-count');
        if (countSpan) {
            countSpan.textContent = checkedCount;
        }
    }
}

/**
 * Bulk status change
 */
async function bulkStatusChange(isActive) {
    const selectedUsers = getSelectedUsers();
    if (selectedUsers.length === 0) return;
    
    const action = isActive ? '啟用' : '停用';
    if (!confirm(`確定要${action} ${selectedUsers.length} 個用戶嗎？`)) {
        return;
    }
    
    const results = {
        success: 0,
        failed: 0,
        errors: []
    };
    
    // Show progress
    const progressModal = showProgressModal(`正在${action}用戶...`, selectedUsers.length);
    
    for (let i = 0; i < selectedUsers.length; i++) {
        const user = selectedUsers[i];
        try {
            const response = await fetch(`/admin/users/${user.id}/toggle`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                results.success++;
                
                // Update UI
                const checkbox = document.querySelector(`input[onchange*="${user.id}"]`);
                if (checkbox) {
                    checkbox.checked = isActive;
                    const label = checkbox.nextElementSibling;
                    label.textContent = isActive ? '啟用' : '停用';
                }
            } else {
                results.failed++;
                results.errors.push(`${user.name}: 操作失敗`);
            }
        } catch (error) {
            results.failed++;
            results.errors.push(`${user.name}: ${error.message}`);
        }
        
        // Update progress
        updateProgress(progressModal, i + 1, selectedUsers.length);
    }
    
    // Hide progress modal
    hideProgressModal(progressModal);
    
    // Show results
    const message = `${action}完成：成功 ${results.success} 個，失敗 ${results.failed} 個`;
    showAlert(message, results.failed === 0 ? 'success' : 'warning');
    
    if (results.errors.length > 0) {
        console.error('Bulk operation errors:', results.errors);
    }
    
    // Clear selections
    clearSelections();
}

/**
 * Bulk delete
 */
async function bulkDelete() {
    const selectedUsers = getSelectedUsers();
    if (selectedUsers.length === 0) return;
    
    if (!confirm(`確定要刪除 ${selectedUsers.length} 個用戶嗎？此操作無法復原。`)) {
        return;
    }
    
    // Implementation similar to bulkStatusChange
    // ... (for brevity, omitted detailed implementation)
    
    showAlert('批量刪除功能開發中', 'info');
}

/**
 * Bulk export
 */
function bulkExport() {
    const selectedUsers = getSelectedUsers();
    if (selectedUsers.length === 0) {
        showAlert('請選擇要匯出的用戶', 'warning');
        return;
    }
    
    const userIds = selectedUsers.map(user => user.id).join(',');
    const exportUrl = `/admin/users/export/csv?user_ids=${userIds}`;
    
    // Create download link
    const link = document.createElement('a');
    link.href = exportUrl;
    link.download = `selected_users_${new Date().toISOString().split('T')[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    showAlert(`正在匯出 ${selectedUsers.length} 個用戶資料`, 'success');
}

/**
 * Get selected users
 */
function getSelectedUsers() {
    const selectedCheckboxes = document.querySelectorAll('.user-checkbox:checked');
    return Array.from(selectedCheckboxes).map(checkbox => {
        const row = checkbox.closest('tr');
        return {
            id: checkbox.value,
            name: row.querySelector('strong').textContent
        };
    });
}

/**
 * Clear all selections
 */
function clearSelections() {
    document.getElementById('selectAll').checked = false;
    document.querySelectorAll('.user-checkbox').forEach(checkbox => {
        checkbox.checked = false;
    });
    toggleBulkActions();
}

/**
 * Show progress modal
 */
function showProgressModal(title, total) {
    const modal = document.createElement('div');
    modal.className = 'modal fade show';
    modal.style.display = 'block';
    modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
    modal.innerHTML = `
        <div class="modal-dialog">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">${title}</h5>
                </div>
                <div class="modal-body">
                    <div class="progress mb-3">
                        <div class="progress-bar" style="width: 0%"></div>
                    </div>
                    <div class="text-center">
                        <span class="progress-text">0 / ${total}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    return modal;
}

/**
 * Update progress
 */
function updateProgress(modal, current, total) {
    const progressBar = modal.querySelector('.progress-bar');
    const progressText = modal.querySelector('.progress-text');
    
    const percentage = (current / total) * 100;
    progressBar.style.width = `${percentage}%`;
    progressText.textContent = `${current} / ${total}`;
}

/**
 * Hide progress modal
 */
function hideProgressModal(modal) {
    setTimeout(() => {
        if (modal.parentNode) {
            modal.parentNode.removeChild(modal);
        }
    }, 500);
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
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alert.parentNode) {
            alert.remove();
        }
    }, 5000);
}

/**
 * Create alert container if not exists
 */
function createAlertContainer() {
    const container = document.createElement('div');
    container.id = 'alertContainer';
    container.style.cssText = 'position: fixed; top: 70px; right: 20px; z-index: 1050; max-width: 400px;';
    document.body.appendChild(container);
    return container;
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Validate file upload
 */
function validateFileUpload(input, maxSize = 5 * 1024 * 1024, allowedTypes = ['.csv']) {
    const file = input.files[0];
    if (!file) return true;
    
    // Check file size
    if (file.size > maxSize) {
        showAlert(`檔案大小不能超過 ${formatFileSize(maxSize)}`, 'danger');
        input.value = '';
        return false;
    }
    
    // Check file type
    const fileName = file.name.toLowerCase();
    const isAllowed = allowedTypes.some(type => fileName.endsWith(type));
    
    if (!isAllowed) {
        showAlert(`只允許上傳 ${allowedTypes.join(', ')} 格式的檔案`, 'danger');
        input.value = '';
        return false;
    }
    
    return true;
}

// Global functions
window.toggleUserStatus = toggleUserStatus;
window.deleteUser = deleteUser;
window.syncUserFromSlack = syncUserFromSlack;