document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const loginButton = document.getElementById('loginButton');
    const passwordInput = document.getElementById('password');
    const togglePasswordButtons = document.querySelectorAll('.toggle-password');
    
    // Toggle password visibility
    togglePasswordButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetId = this.getAttribute('data-target');
            const targetInput = document.getElementById(targetId);
            const icon = this.querySelector('i');
            
            if (targetInput.type === 'password') {
                targetInput.type = 'text';
                icon.classList.remove('bi-eye');
                icon.classList.add('bi-eye-slash');
            } else {
                targetInput.type = 'password';
                icon.classList.remove('bi-eye-slash');
                icon.classList.add('bi-eye');
            }
        });
    });
    
    // Form submission handling
    loginForm.addEventListener('submit', function(e) {
        // Show loading state
        loginButton.classList.add('btn-loading');
        loginButton.disabled = true;
        
        // Basic client-side validation
        const email = document.getElementById('email').value.trim();
        const password = document.getElementById('password').value;
        
        if (!email || !password) {
            e.preventDefault();
            loginButton.classList.remove('btn-loading');
            loginButton.disabled = false;
            return;
        }
        
        // Add slight delay to show loading state
        setTimeout(() => {
            if (!loginButton.disabled) {
                loginButton.classList.remove('btn-loading');
                loginButton.disabled = false;
            }
        }, 3000);
    });
    
    // Auto-focus on email field
    const emailField = document.getElementById('email');
    if (emailField && !emailField.value) {
        emailField.focus();
    }
    
    // Show security modal on first visit (optional)
    const hasSeenSecurityNotice = localStorage.getItem('hasSeenSecurityNotice');
    if (!hasSeenSecurityNotice) {
        setTimeout(() => {
            const securityModal = new bootstrap.Modal(document.getElementById('securityModal'));
            securityModal.show();
            localStorage.setItem('hasSeenSecurityNotice', 'true');
        }, 2000);
    }
    
    // Enhanced input validation
    const inputs = loginForm.querySelectorAll('input[required]');
    inputs.forEach(input => {
        input.addEventListener('blur', function() {
            if (!this.value.trim()) {
                this.classList.add('is-invalid');
            } else {
                this.classList.remove('is-invalid');
            }
        });
        
        input.addEventListener('input', function() {
            if (this.value.trim()) {
                this.classList.remove('is-invalid');
            }
        });
    });
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Ctrl + / to focus search (if implemented elsewhere)
        if (e.ctrlKey && e.key === '/') {
            e.preventDefault();
            emailField.focus();
        }
        
        // Escape to clear form
        if (e.key === 'Escape') {
            loginForm.reset();
        }
    });
    
    // Network status monitoring
    function updateOnlineStatus() {
        const statusIndicator = document.querySelector('.bi-circle-fill');
        if (!navigator.onLine) {
            statusIndicator.classList.remove('text-success');
            statusIndicator.classList.add('text-warning');
            document.querySelector('.text-muted').textContent = 'Offline Mode';
        } else {
            statusIndicator.classList.remove('text-warning');
            statusIndicator.classList.add('text-success');
            document.querySelector('.text-muted').textContent = 'System Online';
        }
    }
    
    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    updateOnlineStatus();
});