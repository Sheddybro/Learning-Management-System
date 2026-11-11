// static/js/academics/enrollment_list.js

class EnrollmentList {
    constructor(config) {
        this.config = config;
        this.selectedEnrollments = new Set();
        this.currentFilters = config.filters;
        this.init();
    }

    init() {
        this.cacheElements();
        this.setupEventListeners();
        this.updateActiveFiltersCount();
        this.setupColumnToggle();
    }

    cacheElements() {
        this.elements = {
            // Table and selection
            enrollmentsTable: document.getElementById('enrollments-table'),
            selectAllCheckbox: document.getElementById('select-all'),
            enrollmentCheckboxes: document.querySelectorAll('.enrollment-checkbox'),
            bulkActions: document.getElementById('bulk-actions'),
            selectedCount: document.getElementById('selected-count'),

            // Filters
            filtersForm: document.getElementById('enrollment-filters'),
            filtersCollapse: document.getElementById('filtersCollapse'),
            resetFiltersBtn: document.getElementById('reset-filters'),
            clearSearchBtn: document.getElementById('clear-search'),
            clearAllFiltersBtn: document.getElementById('clear-all-filters'),
            activeFiltersCount: document.getElementById('active-filters-count'),

            // Search
            searchInput: document.getElementById('search_input'),

            // Bulk actions
            bulkEditBtn: document.getElementById('bulk-edit'),
            bulkTransferBtn: document.getElementById('bulk-transfer'),
            bulkWithdrawBtn: document.getElementById('bulk-withdraw'),

            // Modals
            transferModal: new bootstrap.Modal(document.getElementById('transferModal')),
            withdrawModal: new bootstrap.Modal(document.getElementById('withdrawModal')),
            bulkStatusModal: new bootstrap.Modal(document.getElementById('bulkStatusModal'))
        };
    }

    setupEventListeners() {
        // Selection
        this.elements.selectAllCheckbox?.addEventListener('change', (e) => {
            this.toggleSelectAll(e.target.checked);
        });

        this.elements.enrollmentCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                this.toggleEnrollmentSelection(e.target.value, e.target.checked);
            });
        });

        // Filters
        this.elements.filtersForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.applyFilters();
        });

        this.elements.resetFiltersBtn?.addEventListener('click', () => {
            this.resetFilters();
        });

        this.elements.clearSearchBtn?.addEventListener('click', () => {
            this.clearSearch();
        });

        this.elements.clearAllFiltersBtn?.addEventListener('click', () => {
            this.clearAllFilters();
        });

        // Filter inputs change
        const filterInputs = this.elements.filtersForm?.querySelectorAll('input, select');
        filterInputs?.forEach(input => {
            input.addEventListener('change', () => {
                this.updateActiveFiltersCount();
            });
        });

        // Bulk actions
        this.elements.bulkEditBtn?.addEventListener('click', () => {
            this.openBulkStatusModal();
        });

        this.elements.bulkTransferBtn?.addEventListener('click', () => {
            this.openBulkTransferModal();
        });

        this.elements.bulkWithdrawBtn?.addEventListener('click', () => {
            this.openBulkWithdrawModal();
        });

        // Export
        document.querySelectorAll('[data-export-type]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                this.exportEnrollments(e.target.dataset.exportType);
            });
        });

        // Individual action modals
        document.querySelectorAll('[data-bs-target="#transferModal"]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const enrollmentId = e.target.closest('[data-enrollment-id]')?.dataset.enrollmentId;
                if (enrollmentId) {
                    this.openTransferModal(enrollmentId);
                }
            });
        });

        document.querySelectorAll('[data-bs-target="#withdrawModal"]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const enrollmentId = e.target.closest('[data-enrollment-id]')?.dataset.enrollmentId;
                if (enrollmentId) {
                    this.openWithdrawModal(enrollmentId);
                }
            });
        });

        // Modal confirmations
        document.getElementById('confirm-transfer')?.addEventListener('click', () => {
            this.confirmTransfer();
        });

        document.getElementById('confirm-withdraw')?.addEventListener('click', () => {
            this.confirmWithdraw();
        });

        document.getElementById('confirm-bulk-status')?.addEventListener('click', () => {
            this.confirmBulkStatusUpdate();
        });

        // Print
        document.getElementById('print-enrollments')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.printEnrollments();
        });

        // Export enrollments
        document.getElementById('export-enrollments')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.exportEnrollments('excel');
        });
    }

    setupColumnToggle() {
        const toggleBtn = document.getElementById('toggle-columns');
        if (!toggleBtn) return;

        // Create column toggle menu
        const menu = document.createElement('div');
        menu.className = 'dropdown-menu column-toggle-menu';
        menu.style.width = '200px';

        const columns = [
            { id: 'student', label: 'Student', visible: true },
            { id: 'student-id', label: 'Student ID', visible: true },
            { id: 'class', label: 'Class', visible: true },
            { id: 'roll-number', label: 'Roll No.', visible: true },
            { id: 'session', label: 'Session', visible: true },
            { id: 'enrollment-date', label: 'Enrollment Date', visible: true },
            { id: 'status', label: 'Status', visible: true },
            { id: 'type', label: 'Type', visible: true },
            { id: 'actions', label: 'Actions', visible: true }
        ];

        columns.forEach(col => {
            const item = document.createElement('div');
            item.className = 'column-toggle-item';
            item.innerHTML = `
                <div class="form-check">
                    <input class="form-check-input column-toggle" type="checkbox" 
                           id="toggle-${col.id}" data-column="${col.id}" ${col.visible ? 'checked' : ''}>
                    <label class="form-check-label" for="toggle-${col.id}">
                        ${col.label}
                    </label>
                </div>
            `;
            menu.appendChild(item);
        });

        toggleBtn.parentNode.appendChild(menu);

        // Toggle dropdown
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            menu.classList.toggle('show');
        });

        // Close menu when clicking outside
        document.addEventListener('click', () => {
            menu.classList.remove('show');
        });

        // Handle column toggling
        menu.addEventListener('change', (e) => {
            if (e.target.classList.contains('column-toggle')) {
                this.toggleColumn(e.target.dataset.column, e.target.checked);
            }
        });
    }

    toggleSelectAll(selected) {
        this.elements.enrollmentCheckboxes.forEach(checkbox => {
            checkbox.checked = selected;
            this.toggleEnrollmentSelection(checkbox.value, selected);
        });
        this.updateBulkActions();
    }

    toggleEnrollmentSelection(enrollmentId, selected) {
        if (selected) {
            this.selectedEnrollments.add(enrollmentId);
        } else {
            this.selectedEnrollments.delete(enrollmentId);
            this.elements.selectAllCheckbox.checked = false;
        }
        this.updateBulkActions();
    }

    updateBulkActions() {
        const count = this.selectedEnrollments.size;
        this.elements.selectedCount.textContent = count;

        if (count > 0) {
            this.elements.bulkActions.style.display = 'block';
        } else {
            this.elements.bulkActions.style.display = 'none';
        }
    }

    applyFilters() {
        // Show loading state
        this.showLoading();
        
        // Submit the form (normal form submission)
        this.elements.filtersForm.submit();
    }

    resetFilters() {
        // Clear all filter inputs
        const inputs = this.elements.filtersForm.querySelectorAll('input, select');
        inputs.forEach(input => {
            if (input.type === 'text' || input.type === 'search') {
                input.value = '';
            } else if (input.type === 'select-one') {
                input.selectedIndex = 0;
            } else if (input.type === 'date') {
                input.value = '';
            }
        });
        
        this.applyFilters();
    }

    clearSearch() {
        this.elements.searchInput.value = '';
        this.applyFilters();
    }

    clearAllFilters() {
        window.location.href = window.location.pathname;
    }

    updateActiveFiltersCount() {
        let count = 0;
        const inputs = this.elements.filtersForm.querySelectorAll('input, select');
        
        inputs.forEach(input => {
            if ((input.type === 'text' || input.type === 'search') && input.value.trim()) {
                count++;
            } else if (input.type === 'select-one' && input.value) {
                count++;
            } else if (input.type === 'date' && input.value) {
                count++;
            }
        });

        this.elements.activeFiltersCount.textContent = count;
    }

    openTransferModal(enrollmentId) {
        document.getElementById('transfer-enrollment-id').value = enrollmentId;
        document.getElementById('transfer-date').value = new Date().toISOString().split('T')[0];
        this.elements.transferModal.show();
    }

    openWithdrawModal(enrollmentId) {
        document.getElementById('withdraw-enrollment-id').value = enrollmentId;
        document.getElementById('withdraw-date').value = new Date().toISOString().split('T')[0];
        this.elements.withdrawModal.show();
    }

    openBulkStatusModal() {
        document.getElementById('bulk-status-date').value = new Date().toISOString().split('T')[0];
        this.elements.bulkStatusModal.show();
    }

    openBulkTransferModal() {
        // Implementation for bulk transfer modal
        console.log('Bulk transfer for:', Array.from(this.selectedEnrollments));
    }

    openBulkWithdrawModal() {
        // Implementation for bulk withdraw modal
        console.log('Bulk withdraw for:', Array.from(this.selectedEnrollments));
    }

    async confirmTransfer() {
        const enrollmentId = document.getElementById('transfer-enrollment-id').value;
        const newClassId = document.getElementById('transfer-class').value;
        const reason = document.getElementById('transfer-reason').value;
        const date = document.getElementById('transfer-date').value;

        if (!newClassId || !date) {
            this.showError('Please fill all required fields');
            return;
        }

        this.showLoading('Transferring student...');

        try {
            const response = await fetch(this.config.urls.transferStudent, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    enrollment_id: enrollmentId,
                    new_class_id: newClassId,
                    reason: reason,
                    transfer_date: date
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccess('Student transferred successfully');
                this.elements.transferModal.hide();
                // Reload the page to reflect changes
                setTimeout(() => location.reload(), 1000);
            } else {
                this.showError(data.message || 'Transfer failed');
            }
        } catch (error) {
            console.error('Transfer error:', error);
            this.showError('Transfer failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    async confirmWithdraw() {
        const enrollmentId = document.getElementById('withdraw-enrollment-id').value;
        const reason = document.getElementById('withdraw-reason').value;
        const details = document.getElementById('withdraw-details').value;
        const date = document.getElementById('withdraw-date').value;

        if (!reason || !date) {
            this.showError('Please fill all required fields');
            return;
        }

        this.showLoading('Withdrawing student...');

        try {
            const response = await fetch(this.config.urls.withdrawStudent, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    enrollment_id: enrollmentId,
                    reason: reason,
                    details: details,
                    withdrawal_date: date
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccess('Student withdrawn successfully');
                this.elements.withdrawModal.hide();
                // Reload the page to reflect changes
                setTimeout(() => location.reload(), 1000);
            } else {
                this.showError(data.message || 'Withdrawal failed');
            }
        } catch (error) {
            console.error('Withdrawal error:', error);
            this.showError('Withdrawal failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    async confirmBulkStatusUpdate() {
        const status = document.getElementById('bulk-status').value;
        const date = document.getElementById('bulk-status-date').value;
        const reason = document.getElementById('bulk-status-reason').value;

        if (!status || !date) {
            this.showError('Please fill all required fields');
            return;
        }

        if (this.selectedEnrollments.size === 0) {
            this.showError('No enrollments selected');
            return;
        }

        this.showLoading('Updating enrollment status...');

        try {
            const response = await fetch(this.config.urls.bulkUpdate, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    enrollment_ids: Array.from(this.selectedEnrollments),
                    status: status,
                    effective_date: date,
                    reason: reason
                })
            });

            const data = await response.json();

            if (data.success) {
                this.showSuccess(`Updated ${data.updated_count} enrollments`);
                this.elements.bulkStatusModal.hide();
                // Reload the page to reflect changes
                setTimeout(() => location.reload(), 1000);
            } else {
                this.showError(data.message || 'Update failed');
            }
        } catch (error) {
            console.error('Bulk update error:', error);
            this.showError('Update failed. Please try again.');
        } finally {
            this.hideLoading();
        }
    }

    exportEnrollments(format) {
        this.showLoading(`Exporting enrollments as ${format.toUpperCase()}...`);

        // Build export URL with current filters
        const params = new URLSearchParams(this.currentFilters);
        params.append('format', format);

        const exportUrl = `${this.config.urls.exportEnrollments}?${params.toString()}`;

        // Trigger download
        window.location.href = exportUrl;
        
        setTimeout(() => {
            this.hideLoading();
            this.showSuccess('Export completed');
        }, 1000);
    }

    printEnrollments() {
        window.print();
    }

    toggleColumn(columnId, visible) {
        const table = this.elements.enrollmentsTable;
        if (!table) return;

        // This would need to be implemented based on your table structure
        // For now, it's a placeholder for column visibility toggling
        console.log(`Toggle column ${columnId}: ${visible}`);
    }

    // Utility methods
    showLoading(message = 'Loading...') {
        // You could implement a loading overlay here
        console.log('Loading:', message);
    }

    hideLoading() {
        // Hide loading overlay
        console.log('Loading complete');
    }

    showError(message) {
        // You could replace this with a toast notification
        alert(`Error: ${message}`);
    }

    showSuccess(message) {
        // You could replace this with a toast notification
        alert(`Success: ${message}`);
    }

    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
}

// Initialize when document is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.EnrollmentList = EnrollmentList;
    });
} else {
    window.EnrollmentList = EnrollmentList;
}   