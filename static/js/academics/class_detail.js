// static/js/academics/class_detail.js

class ClassDetail {
    constructor(config) {
        this.config = config;
        this.currentTab = 'students';
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.setupStudentSearch();
        this.setupExportHandlers();
    }

    setupEventListeners() {
        // Tab switching
        const tabButtons = document.querySelectorAll('[data-bs-toggle="tab"]');
        tabButtons.forEach(button => {
            button.addEventListener('show.bs.tab', (event) => {
                this.currentTab = event.target.getAttribute('data-bs-target').replace('#', '');
                this.onTabChange(this.currentTab);
            });
        });

        // Quick actions
        document.getElementById('generate-attendance-report')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.generateAttendanceReport();
        });

        document.getElementById('generate-behavior-report')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.generateBehaviorReport();
        });
    }

    setupStudentSearch() {
        const searchInput = document.getElementById('student-search');
        if (searchInput) {
            searchInput.addEventListener('input', (e) => {
                this.filterStudents(e.target.value);
            });
        }
    }

    setupExportHandlers() {
        document.getElementById('export-student-list')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.exportStudentList();
        });

        document.getElementById('export-timetable')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.exportTimetable();
        });

        document.getElementById('export-class-report')?.addEventListener('click', (e) => {
            e.preventDefault();
            this.exportClassReport();
        });
    }

    onTabChange(tabName) {
        // Update any tab-specific functionality
        switch(tabName) {
            case 'students':
                this.loadStudentStatistics();
                break;
            case 'subjects':
                this.loadSubjectStatistics();
                break;
            case 'timetable':
                this.refreshTimetable();
                break;
            case 'materials':
                this.loadMaterialStats();
                break;
        }
    }

    filterStudents(searchTerm) {
        const table = document.getElementById('students-table');
        const rows = table?.getElementsByTagName('tbody')[0]?.getElementsByTagName('tr');
        
        if (!rows) return;

        searchTerm = searchTerm.toLowerCase();
        
        for (let row of rows) {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(searchTerm) ? '' : 'none';
        }
    }

    async loadStudentStatistics() {
        // Could load additional student statistics via AJAX
        console.log('Loading student statistics...');
    }

    async loadSubjectStatistics() {
        // Could load additional subject statistics via AJAX
        console.log('Loading subject statistics...');
    }

    refreshTimetable() {
        // Refresh timetable view if needed
        console.log('Refreshing timetable...');
    }

    loadMaterialStats() {
        // Load material statistics
        console.log('Loading material statistics...');
    }

    exportStudentList() {
        this.showLoading('Preparing student list...');
        
        // Simulate API call
        setTimeout(() => {
            this.hideLoading();
            this.showSuccess('Student list exported successfully!');
        }, 1500);
    }

    exportTimetable() {
        this.showLoading('Exporting timetable...');
        
        setTimeout(() => {
            this.hideLoading();
            this.showSuccess('Timetable exported successfully!');
        }, 1500);
    }

    exportClassReport() {
        window.open(this.config.apiUrls.exportReport, '_blank');
    }

    generateAttendanceReport() {
        this.showLoading('Generating attendance report...');
        
        setTimeout(() => {
            this.hideLoading();
            this.showSuccess('Attendance report generated!');
        }, 2000);
    }

    generateBehaviorReport() {
        this.showLoading('Generating behavior report...');
        
        setTimeout(() => {
            this.hideLoading();
            this.showSuccess('Behavior report generated!');
        }, 2000);
    }

    showLoading(message = 'Loading...') {
        // Implement loading indicator
        const loadingEl = document.createElement('div');
        loadingEl.className = 'loading-overlay';
        loadingEl.innerHTML = `
            <div class="loading-content">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-2">${message}</p>
            </div>
        `;
        document.body.appendChild(loadingEl);
    }

    hideLoading() {
        const loadingEl = document.querySelector('.loading-overlay');
        if (loadingEl) {
            loadingEl.remove();
        }
    }

    showSuccess(message) {
        // Show success message (could use Toast or Alert)
        alert(message); // Replace with better notification system
    }

    showError(message) {
        // Show error message
        alert('Error: ' + message); // Replace with better notification system
    }
}

// Initialize when document is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.ClassDetail = ClassDetail;
    });
} else {
    window.ClassDetail = ClassDetail;
}