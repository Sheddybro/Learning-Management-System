/**
 * Student Dashboard JavaScript
 * Provides real-time updates and interactive functionality
 */

// Global variables
let refreshInterval;
let notificationCount = 0;

// Initialize dashboard when document is ready
$(document).ready(function() {
    initializeDashboard();
    setupEventListeners();
    startAutoRefresh();
});

// Initialize dashboard components
function initializeDashboard() {
    // Load initial data
    updateDashboardData();

    // Initialize tooltips
    $('[data-toggle="tooltip"]').tooltip();

    // Initialize popovers
    $('[data-toggle="popover"]').popover();

    // Check for browser notifications permission
    if ('Notification' in window) {
        if (Notification.permission === 'default') {
            Notification.requestPermission();
        }
    }
}

// Setup event listeners
function setupEventListeners() {
    // Handle window focus/blur for auto-refresh
    $(window).focus(function() {
        startAutoRefresh();
    });

    $(window).blur(function() {
        stopAutoRefresh();
    });

    // Handle online/offline events
    $(window).on('online', function() {
        showNotification('Connection restored', 'success');
        startAutoRefresh();
    });

    $(window).on('offline', function() {
        showNotification('Connection lost', 'warning');
        stopAutoRefresh();
    });

    // Handle announcement clicks
    $('.announcement-item a').on('click', function(e) {
        e.preventDefault();
        const target = $(this).data('target');
        $(target).modal('show');
        markAnnouncementAsRead($(this).closest('.announcement-item').data('announcement-id'));
    });

    // Handle quick action buttons
    $('.quick-action-btn').on('click', function() {
        const action = $(this).data('action');
        handleQuickAction(action);
    });
}

// Start auto-refresh functionality
function startAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
    }

    refreshInterval = setInterval(function() {
        updateDashboardData();
    }, 30000); // Refresh every 30 seconds
}

// Stop auto-refresh functionality
function stopAutoRefresh() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Update dashboard data via AJAX
function updateDashboardData() {
    // Only update if online
    if (!navigator.onLine) {
        return;
    }

    $.ajax({
        url: '/academics/student/dashboard-data/',
        type: 'GET',
        timeout: 10000,
        success: function(data) {
            updateAttendanceStatus(data.today_attendance);
            updateAssignmentCount(data.upcoming_assignments_count);
            updateAnnouncementCount(data.unread_announcements_count);
            updateRecentGrades(data.recent_grades);

            // Show browser notification for new announcements
            if (data.new_announcements && data.new_announcements.length > 0) {
                showBrowserNotification('New Announcements', `You have ${data.new_announcements.length} new announcement(s)`);
            }
        },
        error: function(xhr, status, error) {
            if (status !== 'timeout') {
                console.error('Failed to update dashboard data:', error);
            }
        }
    });
}

// Update today's attendance status
function updateAttendanceStatus(attendance) {
    if (!attendance) return;

    const attendanceElement = $('.attendance-status');
    let statusHtml = '';

    if (attendance.status === 'present') {
        statusHtml = '<span class="text-success"><i class="fas fa-check-circle"></i> Present</span>';
    } else if (attendance.status === 'absent') {
        statusHtml = '<span class="text-danger"><i class="fas fa-times-circle"></i> Absent</span>';
    } else if (attendance.status === 'late') {
        statusHtml = '<span class="text-warning"><i class="fas fa-clock"></i> Late</span>';
    } else {
        statusHtml = `<span class="text-info">${attendance.status_display}</span>`;
    }

    if (attendance.late_minutes) {
        statusHtml += ` <small class="text-muted">(${attendance.late_minutes} min late)</small>`;
    }

    attendanceElement.html(statusHtml);
}

// Update upcoming assignments count
function updateAssignmentCount(count) {
    const badge = $('.assignments-badge');
    if (count > 0) {
        badge.text(count).show();
    } else {
        badge.hide();
    }
}

// Update unread announcements count
function updateAnnouncementCount(count) {
    const badge = $('.announcements-badge');
    if (count > 0) {
        badge.text(count).show();
        notificationCount = count;
        updatePageTitle();
    } else {
        badge.hide();
        notificationCount = 0;
        updatePageTitle();
    }
}

// Update recent grades
function updateRecentGrades(grades) {
    if (!grades || grades.length === 0) return;

    const gradesContainer = $('.recent-grades');
    gradesContainer.empty();

    grades.forEach(function(grade) {
        const gradeHtml = `
            <div class="grade-item text-center p-3 border rounded mr-3 mb-3">
                <div class="grade-score h4 mb-1 ${getGradeColorClass(grade.percentage)}">
                    ${grade.percentage}%
                </div>
                <div class="grade-subject small text-muted mb-1">${grade.subject_name}</div>
                <div class="grade-exam small">${grade.exam_name}</div>
            </div>
        `;
        gradesContainer.append(gradeHtml);
    });
}

// Get color class based on grade percentage
function getGradeColorClass(percentage) {
    if (percentage >= 90) return 'text-success';
    if (percentage >= 80) return 'text-info';
    if (percentage >= 70) return 'text-warning';
    return 'text-danger';
}

// Mark announcement as read
function markAnnouncementAsRead(announcementId) {
    $.ajax({
        url: `/academics/announcements/${announcementId}/mark-read/`,
        type: 'POST',
        data: {
            'csrfmiddlewaretoken': getCsrfToken()
        },
        success: function() {
            updateAnnouncementCount(notificationCount - 1);
        }
    });
}

// Handle quick actions
function handleQuickAction(action) {
    switch(action) {
        case 'view_timetable':
            window.location.href = '/academics/student/timetable/';
            break;
        case 'view_materials':
            window.location.href = '/academics/student/materials/';
            break;
        case 'view_performance':
            window.location.href = '/academics/student/performance/';
            break;
        case 'view_attendance':
            window.location.href = '/academics/student/attendance/';
            break;
        case 'view_messages':
            window.location.href = '/communication/inbox/';
            break;
        case 'view_library':
            window.location.href = '/library/dashboard/';
            break;
        default:
            console.log('Unknown action:', action);
    }
}

// Show notification to user
function showNotification(message, type = 'info', duration = 5000) {
    // Create notification element
    const notification = $(`
        <div class="alert alert-${type} alert-dismissible fade show notification-toast" role="alert">
            ${message}
            <button type="button" class="close" data-dismiss="alert">
                <span>&times;</span>
            </button>
        </div>
    `);

    // Add to notification container
    let container = $('.notification-container');
    if (container.length === 0) {
        container = $('<div class="notification-container"></div>');
        $('body').append(container);
    }

    container.append(notification);

    // Auto-dismiss after duration
    setTimeout(function() {
        notification.alert('close');
    }, duration);

    // Add styles if not present
    if (!$('#notification-styles').length) {
        $('head').append(`
            <style id="notification-styles">
                .notification-container {
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    z-index: 9999;
                    max-width: 400px;
                }
                .notification-toast {
                    margin-bottom: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                }
            </style>
        `);
    }
}

// Show browser notification
function showBrowserNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        const notification = new Notification(title, {
            body: body,
            icon: '/static/images/logo.png', // Update with your logo path
            tag: 'school-notification'
        });

        notification.onclick = function() {
            window.focus();
            this.close();
        };

        // Auto-close after 5 seconds
        setTimeout(function() {
            notification.close();
        }, 5000);
    }
}

// Update page title with notification count
function updatePageTitle() {
    const baseTitle = document.title.replace(/^\(\d+\)\s/, '');
    if (notificationCount > 0) {
        document.title = `(${notificationCount}) ${baseTitle}`;
    } else {
        document.title = baseTitle;
    }
}

// Get CSRF token from cookies
function getCsrfToken() {
    const name = 'csrftoken';
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Handle AJAX errors globally
$(document).ajaxError(function(event, xhr, settings, thrownError) {
    if (xhr.status === 403) {
        showNotification('Session expired. Please refresh the page.', 'warning');
    } else if (xhr.status >= 500) {
        showNotification('Server error occurred. Please try again later.', 'danger');
    }
});

// Export functions for global access
window.DashboardUtils = {
    updateDashboardData: updateDashboardData,
    showNotification: showNotification,
    startAutoRefresh: startAutoRefresh,
    stopAutoRefresh: stopAutoRefresh
};
