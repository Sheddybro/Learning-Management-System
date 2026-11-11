// static/js/core/base.js

class BaseApp {
    constructor() {
        this.init();
    }

    init() {
        this.setupCSRF();
        this.setupGlobalHandlers();
        this.setupBackToTop();
        this.setupOfflineDetection();
        this.setupLoadingSpinner();
        this.setupAccessibility();
        this.setupPrintHandlers();
    }

    // CSRF Token setup for AJAX requests
    setupCSRF() {
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (csrfToken) {
            $.ajaxSetup({
                headers: {
                    'X-CSRFToken': csrfToken
                }
            });
            
            // Also setup for Fetch API
            this.setupFetchCSRF(csrfToken);
        }
    }

    setupFetchCSRF(csrfToken) {
        const originalFetch = window.fetch;
        window.fetch = function(...args) {
            if (args[1] && (args[1].method === 'POST' || args[1].method === 'PUT' || args[1].method === 'DELETE' || args[1].method === 'PATCH')) {
                args[1].headers = {
                    ...args[1].headers,
                    'X-CSRFToken': csrfToken
                };
            }
            return originalFetch.apply(this, args);
        };
    }

    // Global event handlers
    setupGlobalHandlers() {
        // Handle form submissions with loading state
        document.addEventListener('submit', (e) => {
            const form = e.target;
            if (form.method.toLowerCase() === 'post') {
                window.showLoading();
            }
        });

        // Handle link clicks with data-loading attribute
        document.addEventListener('click', (e) => {
            const target = e.target.closest('[data-loading]');
            if (target) {
                window.showLoading();
            }
        });

        // Escape key handler for modals
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                this.handleEscapeKey();
            }
        });
    }

    // Back to top functionality
    setupBackToTop() {
        const backToTop = document.getElementById('backToTop');
        if (!backToTop) return;

        window.addEventListener('scroll', () => {
            if (window.pageYOffset > 300) {
                backToTop.classList.add('show');
            } else {
                backToTop.classList.remove('show');
            }
        });

        backToTop.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }

    // Offline detection
    setupOfflineDetection() {
        const offlineIndicator = document.getElementById('offline-indicator');
        if (!offlineIndicator) return;

        window.addEventListener('online', () => {
            offlineIndicator.style.display = 'none';
            this.showToast('Connection restored', 'success');
        });

        window.addEventListener('offline', () => {
            offlineIndicator.style.display = 'block';
        });
    }

    // Loading spinner management
    setupLoadingSpinner() {
        // Global loading state management
        window.showLoading = () => {
            const spinner = document.getElementById('loading-spinner');
            if (spinner) spinner.style.display = 'flex';
        };

        window.hideLoading = () => {
            const spinner = document.getElementById('loading-spinner');
            if (spinner) spinner.style.display = 'none';
        };
    }

    // Accessibility features
    setupAccessibility() {
        // Focus management for modals
        document.addEventListener('shown.bs.modal', (e) => {
            const modal = e.target;
            const focusElement = modal.querySelector('[autofocus]') || 
                               modal.querySelector('.btn-primary') || 
                               modal.querySelector('input, select, textarea');
            if (focusElement) focusElement.focus();
        });

        // Skip link functionality
        document.addEventListener('click', (e) => {
            if (e.target.matches('.skip-link')) {
                e.preventDefault();
                const targetId = e.target.getAttribute('href').substring(1);
                const targetElement = document.getElementById(targetId);
                if (targetElement) {
                    targetElement.setAttribute('tabindex', '-1');
                    targetElement.focus();
                    targetElement.removeAttribute('tabindex');
                }
            }
        });
    }

    // Print functionality
    setupPrintHandlers() {
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'p') {
                e.preventDefault();
                this.handlePrint();
            }
        });
    }

    // Utility methods
    handleEscapeKey() {
        // Close any open modals
        const openModals = document.querySelectorAll('.modal.show');
        openModals.forEach(modal => {
            const bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) bsModal.hide();
        });
    }

    handlePrint() {
        window.print();
    }

    showToast(message, type = 'info') {
        // Simple toast notification
        const toast = document.createElement('div');
        toast.className = `alert alert-${type} alert-dismissible fade show`;
        toast.style.cssText = 'position: fixed; top: 20px; right: 20px; z-index: 1060; min-width: 300px;';
        toast.innerHTML = `
            <div class="d-flex align-items-center">
                <i class="bi ${this.getToastIcon(type)} me-2"></i>
                <span>${message}</span>
                <button type="button" class="btn-close ms-auto" data-bs-dismiss="alert"></button>
            </div>
        `;
        document.body.appendChild(toast);
        
        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
    }

    getToastIcon(type) {
        const icons = {
            success: 'bi-check-circle-fill',
            warning: 'bi-exclamation-triangle-fill',
            error: 'bi-x-circle-fill',
            info: 'bi-info-circle-fill'
        };
        return icons[type] || icons.info;
    }

    // Global utility functions
    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString(CURRENT_LANGUAGE || 'en');
    }

    formatCurrency(amount, currency = 'USD') {
        return new Intl.NumberFormat(CURRENT_LANGUAGE || 'en', {
            style: 'currency',
            currency: currency
        }).format(amount);
    }

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Initialize the base application when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    window.BaseApp = new BaseApp();
});

// Global utility functions
function hideAnnouncement() {
    const banner = document.getElementById('announcement-banner');
    if (banner) banner.style.display = 'none';
}

function saveSettings() {
    const theme = document.getElementById('theme-select')?.value;
    const language = document.getElementById('language-select')?.value;
    
    // Save settings via AJAX
    if (CURRENT_USER_ID) {
        fetch('/api/user/settings/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': CSRF_TOKEN
            },
            body: JSON.stringify({ theme, language })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                window.BaseApp.showToast('Settings saved successfully!', 'success');
                // Reload to apply language changes
                if (language !== CURRENT_LANGUAGE) {
                    setTimeout(() => window.location.reload(), 1000);
                }
            } else {
                window.BaseApp.showToast('Failed to save settings', 'error');
            }
        })
        .catch(error => {
            console.error('Error saving settings:', error);
            window.BaseApp.showToast('Error saving settings', 'error');
        });
    }
    
    // Close modal
    const modal = bootstrap.Modal.getInstance(document.getElementById('settingsModal'));
    if (modal) modal.hide();
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { BaseApp };
}
