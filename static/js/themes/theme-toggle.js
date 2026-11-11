
// theme-toggle.js
document.addEventListener('DOMContentLoaded', function() {
    const themeToggle = document.getElementById('theme-toggle');
    const themeSelect = document.getElementById('theme-select');
    
    // Debug logging
    console.log('Theme toggle script loaded');
    console.log('Theme toggle element:', themeToggle);

    if (!themeToggle) {
        console.log('Theme toggle button not found on this page - skipping initialization');
        return;
    }

    // Get current theme from localStorage or system preference
    function getCurrentTheme() {
        const savedTheme = localStorage.getItem('theme');
        console.log('Saved theme from localStorage:', savedTheme);
        
        if (savedTheme) return savedTheme;
        
        // Check system preference
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
            return 'dark';
        }
        return 'light';
    }

    // Apply theme
function applyTheme(theme) {
    const html = document.documentElement;
    const lightTheme = document.getElementById('light-theme');
    const darkTheme = document.getElementById('dark-theme');
    
    console.log('Applying theme:', theme);

    if (theme === 'auto') {
        // Use system preference - let media queries handle it
        html.removeAttribute('data-bs-theme');
        localStorage.setItem('theme', 'auto');
    } else {
        html.setAttribute('data-bs-theme', theme);
        localStorage.setItem('theme', theme);
        
        // Override media queries for manual theme selection
        if (lightTheme && darkTheme) {
            if (theme === 'light') {
                lightTheme.media = 'all';
                darkTheme.media = 'not all';
            } else {
                lightTheme.media = 'not all';
                darkTheme.media = 'all';
            }
        }
    }
    
    // Update toggle button icon
    updateToggleIcon(theme);
    
    // Update theme select if exists
    if (themeSelect) {
        themeSelect.value = theme;
    }
    
    console.log('Theme applied successfully');
}

    // Update toggle button icon
    function updateToggleIcon(theme) {
        const icon = themeToggle.querySelector('i');
        if (icon) {
            if (theme === 'dark' || (theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
                icon.className = 'bi bi-moon-fill';
                themeToggle.title = 'Switch to light theme';
            } else {
                icon.className = 'bi bi-sun-fill';
                themeToggle.title = 'Switch to dark theme';
            }
        }
    }

    // Toggle theme
    function toggleTheme() {
        const currentTheme = getCurrentTheme();
        let newTheme;
        
        if (currentTheme === 'auto') {
            // If auto, toggle based on current system preference
            newTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'light' : 'dark';
        } else {
            newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        }
        
        console.log('Toggling theme from', currentTheme, 'to', newTheme);
        applyTheme(newTheme);
    }

    // Initialize theme
    function initTheme() {
        const currentTheme = getCurrentTheme();
        console.log('Initializing theme:', currentTheme);
        applyTheme(currentTheme);
    }

    // Event listeners
    themeToggle.addEventListener('click', function(e) {
        e.preventDefault();
        toggleTheme();
    });
    
    if (themeSelect) {
        themeSelect.addEventListener('change', function() {
            applyTheme(this.value);
        });
    }

    // Listen for system theme changes
    if (window.matchMedia) {
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
            const currentSavedTheme = localStorage.getItem('theme');
            console.log('System theme changed to:', e.matches ? 'dark' : 'light');
            if (currentSavedTheme === 'auto' || !currentSavedTheme) {
                applyTheme('auto');
            }
        });
    }

    // Initialize
    initTheme();
});
