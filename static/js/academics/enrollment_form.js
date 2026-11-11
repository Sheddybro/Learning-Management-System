// static/js/academics/enrollment_form.js

class EnrollmentForm {
    constructor(config) {
        this.config = config;
        this.elements = {};
        this.selectedStudent = null;
        this.selectedClass = null;
        this.selectedSession = null;
    }

    init() {
        this.cacheElements();
        this.setupEventListeners();
        this.loadInitialData();
    }

    cacheElements() {
        this.elements = {
            form: document.getElementById('enrollment-form'),
            studentSelect: document.getElementById('id_student'),
            classSelect: document.getElementById('id_class_enrolled'),
            sessionSelect: document.getElementById('id_academic_session'),
            departmentSelect: document.getElementById('id_department'),
            rollNumberInput: document.getElementById('id_roll_number'),
            enrollmentDateInput: document.getElementById('id_enrollment_date'),

            // Department field container
            departmentRow: document.getElementById('department-row'),

            // Preview elements
            studentPreview: document.getElementById('student-preview'),
            studentInitials: document.getElementById('student-initials'),
            studentName: document.getElementById('student-name'),
            studentDetails: document.getElementById('student-details'),
            studentStatus: document.getElementById('student-status'),

            classPreview: document.getElementById('class-preview'),
            className: document.getElementById('class-name'),
            classDetails: document.getElementById('class-details'),
            classTeacher: document.getElementById('class-teacher'),
            classCapacity: document.getElementById('class-capacity'),
            classCurrent: document.getElementById('class-current'),
            classAvailable: document.getElementById('class-available'),

            // Information elements
            availableClassesList: document.getElementById('available-classes-list'),
            currentSessionInfo: document.getElementById('current-session-info'),
            totalEnrollments: document.getElementById('total-enrollments'),
            activeStudents: document.getElementById('active-students'),

            // Modals
            loadingModal: new bootstrap.Modal(document.getElementById('loadingModal'))
        };
    }

    setupEventListeners() {
        // Student selection
        this.elements.studentSelect.addEventListener('change', (e) => {
            this.handleStudentChange(e.target.value);
        });

        // Session selection
        this.elements.sessionSelect.addEventListener('change', (e) => {
            this.handleSessionChange(e.target.value);
        });

        // Class selection
        this.elements.classSelect.addEventListener('change', (e) => {
            this.handleClassChange(e.target.value);
        });

        // Roll number validation
        this.elements.rollNumberInput.addEventListener('blur', (e) => {
            this.validateRollNumber(e.target.value);
        });

        // Form submission
        this.elements.form.addEventListener('submit', (e) => {
            this.handleFormSubmit(e);
        });

        // Enrollment date validation
        this.elements.enrollmentDateInput.addEventListener('change', (e) => {
            this.validateEnrollmentDate(e.target.value);
        });
    }

    async loadInitialData() {
        // Load current session info
        if (this.config.currentSessionId) {
            await this.loadSessionInfo(this.config.currentSessionId);
        }

        // Load system statistics
        await this.loadSystemStats();

        // If editing existing enrollment, load existing data
        if (this.config.formData.studentId) {
            await this.handleStudentChange(this.config.formData.studentId);
        }
        if (this.config.formData.sessionId) {
            await this.handleSessionChange(this.config.formData.sessionId);
        }
        if (this.config.formData.classId) {
            await this.handleClassChange(this.config.formData.classId);
        }
    }

    async handleStudentChange(studentId) {
        if (!studentId) {
            this.hideStudentPreview();
            return;
        }

        this.showLoading('Loading student information...');
        
        try {
            const response = await fetch(`${this.config.urls.getStudents}?student_id=${studentId}`);
            const data = await response.json();
            
            if (data.success && data.student) {
                this.displayStudentInfo(data.student);
                this.checkExistingEnrollment(studentId, this.selectedSession);
            } else {
                this.hideStudentPreview();
                this.showError('Failed to load student information');
            }
        } catch (error) {
            console.error('Error loading student info:', error);
            this.showError('Error loading student information');
        } finally {
            this.hideLoading();
        }
    }

    async handleSessionChange(sessionId) {
        this.selectedSession = sessionId;
        
        if (!sessionId) {
            this.hideClassPreview();
            this.clearAvailableClasses();
            return;
        }

        await this.loadSessionInfo(sessionId);
        await this.loadAvailableClasses(sessionId);
        
        // Check if student is already enrolled in this session
        if (this.selectedStudent) {
            this.checkExistingEnrollment(this.selectedStudent.id, sessionId);
        }
    }

    async handleClassChange(classId) {
        if (!classId) {
            this.hideClassPreview();
            return;
        }

        this.showLoading('Loading class information...');
        
        try {
            const response = await fetch(`${this.config.urls.getClassInfo}?class_id=${classId}`);
            const data = await response.json();
            
            if (data.success && data.class_info) {
                this.displayClassInfo(data.class_info);
                this.suggestRollNumber();
            } else {
                this.hideClassPreview();
                this.showError('Failed to load class information');
            }
        } catch (error) {
            console.error('Error loading class info:', error);
            this.showError('Error loading class information');
        } finally {
            this.hideLoading();
        }
    }

    displayStudentInfo(student) {
        this.selectedStudent = student;
        
        this.elements.studentInitials.textContent = student.initials || '--';
        this.elements.studentName.textContent = student.full_name;
        this.elements.studentDetails.textContent = `${student.student_id} • ${student.grade_level || 'N/A'}`;
        this.elements.studentStatus.textContent = student.status;
        this.elements.studentStatus.className = `badge bg-${student.status === 'active' ? 'success' : 'secondary'}`;
        
        this.elements.studentPreview.classList.remove('d-none');
    }

    displayClassInfo(classInfo) {
        this.selectedClass = classInfo;

        this.elements.className.textContent = classInfo.name;
        this.elements.classDetails.textContent = `${classInfo.grade_level} • ${classInfo.class_type}`;
        this.elements.classTeacher.innerHTML = `<i class="bi bi-person me-1"></i>${classInfo.teacher || 'No teacher assigned'}`;
        this.elements.classCapacity.textContent = classInfo.capacity;
        this.elements.classCurrent.textContent = classInfo.current_students;
        this.elements.classAvailable.textContent = classInfo.available_seats;

        // Update available seats color based on availability
        const availableElement = this.elements.classAvailable;
        availableElement.className = 'stat-number ' +
            (classInfo.available_seats < 5 ? 'text-danger' :
             classInfo.available_seats < 10 ? 'text-warning' : 'text-success');

        // Handle department field visibility for tertiary education
        this.handleDepartmentFieldVisibility(classInfo);

        this.elements.classPreview.classList.remove('d-none');
    }

    handleDepartmentFieldVisibility(classInfo) {
        // Check if this is a tertiary education class
        const tertiaryStages = ['undergraduate', 'graduate', 'postgraduate', 'diploma'];
        const isTertiary = classInfo.education_stage && tertiaryStages.includes(classInfo.education_stage.toLowerCase());

        if (isTertiary) {
            // Show department field and make it required
            this.elements.departmentRow.style.display = 'block';
            if (this.elements.departmentSelect) {
                this.elements.departmentSelect.required = true;
                // Update label to show it's required
                const label = this.elements.departmentSelect.previousElementSibling;
                if (label && label.tagName === 'LABEL') {
                    label.innerHTML = label.innerHTML.replace('*', '') + ' *';
                }
            }
        } else {
            // Hide department field and make it not required
            this.elements.departmentRow.style.display = 'none';
            if (this.elements.departmentSelect) {
                this.elements.departmentSelect.required = false;
                this.elements.departmentSelect.value = '';
                // Remove required indicator from label
                const label = this.elements.departmentSelect.previousElementSibling;
                if (label && label.tagName === 'LABEL') {
                    label.innerHTML = label.innerHTML.replace(' *', '');
                }
            }
        }
    }

    async loadSessionInfo(sessionId) {
        try {
            const response = await fetch(`${this.config.urls.getSessionInfo}?session_id=${sessionId}`);
            const data = await response.json();
            
            if (data.success && data.session_info) {
                this.elements.currentSessionInfo.textContent = data.session_info.name;
            }
        } catch (error) {
            console.error('Error loading session info:', error);
        }
    }

    async loadAvailableClasses(sessionId) {
        this.showLoading('Loading available classes...');
        
        try {
            const response = await fetch(`${this.config.urls.getAvailableClasses}?session_id=${sessionId}`);
            const data = await response.json();
            
            if (data.success && data.classes) {
                this.displayAvailableClasses(data.classes);
            } else {
                this.clearAvailableClasses();
            }
        } catch (error) {
            console.error('Error loading available classes:', error);
            this.clearAvailableClasses();
        } finally {
            this.hideLoading();
        }
    }

    displayAvailableClasses(classes) {
        if (classes.length === 0) {
            this.elements.availableClassesList.innerHTML = `
                <div class="text-center text-muted py-3">
                    <i class="bi bi-exclamation-circle display-6"></i>
                    <p class="mt-2 mb-0">{% trans "No classes available for this session" %}</p>
                </div>
            `;
            return;
        }

        const classesHTML = classes.map(classInfo => `
            <div class="available-class-item ${classInfo.id == this.selectedClass?.id ? 'selected' : ''}" 
                 data-class-id="${classInfo.id}">
                <div class="class-name">${classInfo.name}</div>
                <div class="class-details">
                    ${classInfo.grade_level} • ${classInfo.class_type} • 
                    <span class="class-stats">
                        ${classInfo.current_students}/${classInfo.capacity} students
                    </span>
                </div>
                ${classInfo.teacher ? `
                <div class="class-teacher small text-muted">
                    <i class="bi bi-person me-1"></i>${classInfo.teacher}
                </div>
                ` : ''}
            </div>
        `).join('');

        this.elements.availableClassesList.innerHTML = classesHTML;

        // Add click handlers for class items
        this.elements.availableClassesList.querySelectorAll('.available-class-item').forEach(item => {
            item.addEventListener('click', () => {
                const classId = item.getAttribute('data-class-id');
                this.elements.classSelect.value = classId;
                this.handleClassChange(classId);
                
                // Update selection UI
                this.elements.availableClassesList.querySelectorAll('.available-class-item').forEach(i => {
                    i.classList.remove('selected');
                });
                item.classList.add('selected');
            });
        });
    }

    async validateRollNumber(rollNumber) {
        if (!rollNumber || !this.selectedClass || !this.selectedSession) {
            return;
        }

        try {
            const response = await fetch(this.config.urls.checkRollNumber, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.getCSRFToken()
                },
                body: JSON.stringify({
                    roll_number: rollNumber,
                    class_id: this.selectedClass.id,
                    session_id: this.selectedSession,
                    enrollment_id: this.config.formData.enrollmentId || null
                })
            });
            
            const data = await response.json();
            
            if (data.available) {
                this.markFieldValid(this.elements.rollNumberInput);
            } else {
                this.markFieldInvalid(this.elements.rollNumberInput, data.message || 'Roll number already taken');
            }
        } catch (error) {
            console.error('Error validating roll number:', error);
        }
    }

    suggestRollNumber() {
        if (!this.selectedClass || this.elements.rollNumberInput.value) {
            return;
        }

        // Simple suggestion - next available number
        const suggestedNumber = this.selectedClass.current_students + 1;
        this.elements.rollNumberInput.value = suggestedNumber;
        this.validateRollNumber(suggestedNumber);
    }

    async checkExistingEnrollment(studentId, sessionId) {
        if (!studentId || !sessionId) return;

        try {
            // This would typically call an API to check for existing enrollment
            console.log(`Checking enrollment for student ${studentId} in session ${sessionId}`);
            // Implementation would depend on your backend API
        } catch (error) {
            console.error('Error checking existing enrollment:', error);
        }
    }

    validateEnrollmentDate(dateString) {
        if (!dateString || !this.selectedSession) return;

        const enrollmentDate = new Date(dateString);
        const sessionStart = new Date(this.selectedSession.start_date);
        const sessionEnd = new Date(this.selectedSession.end_date);

        if (enrollmentDate < sessionStart || enrollmentDate > sessionEnd) {
            this.markFieldInvalid(this.elements.enrollmentDateInput, 
                'Enrollment date must be within the academic session dates');
        } else {
            this.markFieldValid(this.elements.enrollmentDateInput);
        }
    }

    async loadSystemStats() {
        try {
            // This would typically call an API to get system statistics
            // For now, we'll set placeholder values
            this.elements.totalEnrollments.textContent = 'Loading...';
            this.elements.activeStudents.textContent = 'Loading...';
            
            // Simulate API call
            setTimeout(() => {
                this.elements.totalEnrollments.textContent = '1,247';
                this.elements.activeStudents.textContent = '856';
            }, 1000);
        } catch (error) {
            console.error('Error loading system stats:', error);
        }
    }

    async handleFormSubmit(event) {
        event.preventDefault();
        
        // Validate form
        if (!this.validateForm()) {
            this.showError('Please fix the errors in the form before submitting');
            return;
        }

        this.showLoading('Saving enrollment...');
        
        try {
            // Form will submit normally since we're not using AJAX for final submission
            // Additional processing can be done here if needed
            this.elements.form.submit();
        } catch (error) {
            console.error('Error submitting form:', error);
            this.hideLoading();
            this.showError('Error submitting form. Please try again.');
        }
    }

    validateForm() {
        let isValid = true;

        // Basic required field validation
        const requiredFields = [
            this.elements.studentSelect,
            this.elements.sessionSelect,
            this.elements.classSelect,
            this.elements.rollNumberInput,
            this.elements.enrollmentDateInput
        ];

        requiredFields.forEach(field => {
            if (!field.value.trim()) {
                this.markFieldInvalid(field, 'This field is required');
                isValid = false;
            }
        });

        // Check department field if it's required for tertiary education
        if (this.elements.departmentSelect && this.elements.departmentSelect.required) {
            if (!this.elements.departmentSelect.value.trim()) {
                this.markFieldInvalid(this.elements.departmentSelect, 'Department is required for tertiary education enrollments');
                isValid = false;
            }
        }

        return isValid;
    }

    // Utility methods
    markFieldValid(field) {
        field.classList.remove('is-invalid');
        field.classList.add('is-valid');
    }

    markFieldInvalid(field, message) {
        field.classList.remove('is-valid');
        field.classList.add('is-invalid');
        
        // Update or create feedback element
        let feedback = field.parentNode.querySelector('.invalid-feedback');
        if (!feedback) {
            feedback = document.createElement('div');
            feedback.className = 'invalid-feedback';
            field.parentNode.appendChild(feedback);
        }
        feedback.textContent = message;
    }

    showLoading(message = 'Loading...') {
        document.getElementById('loading-message').textContent = message;
        this.elements.loadingModal.show();
    }

    hideLoading() {
        this.elements.loadingModal.hide();
    }

    showError(message) {
        // You could replace this with a toast notification
        alert(`Error: ${message}`);
    }

    showSuccess(message) {
        // You could replace this with a toast notification
        alert(`Success: ${message}`);
    }

    hideStudentPreview() {
        this.elements.studentPreview.classList.add('d-none');
        this.selectedStudent = null;
    }

    hideClassPreview() {
        this.elements.classPreview.classList.add('d-none');
        this.selectedClass = null;
    }

    clearAvailableClasses() {
        this.elements.availableClassesList.innerHTML = `
            <div class="text-center text-muted py-3">
                <i class="bi bi-exclamation-circle display-6"></i>
                <p class="mt-2 mb-0">{% trans "No classes available" %}</p>
            </div>
        `;
    }

    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
}

// Initialize when document is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.EnrollmentForm = EnrollmentForm;
    });
} else {
    window.EnrollmentForm = EnrollmentForm;
}
