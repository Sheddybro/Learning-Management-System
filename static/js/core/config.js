/**
 * System Configuration Management JavaScript
 * Handles dynamic functionality for configuration forms and interactions
 */

class ConfigManager {
    constructor() {
        this.codeMirrorInstances = new Map();
        this.init();
    }

    init() {
        this.initializeCodeMirror();
        this.bindEvents();
        this.setupValidation();
    }

    initializeCodeMirror() {
        // Initialize CodeMirror for all configuration value textareas
        $('textarea[id^="id_value"], textarea[id^="id_config_"]').each((index, element) => {
            this.createCodeMirrorInstance(element);
        });
    }

    createCodeMirrorInstance(textarea) {
        const $textarea = $(textarea);
        const textareaId = $textarea.attr('id');

        if (this.codeMirrorInstances.has(textareaId)) {
            return; // Already initialized
        }

        const codeMirror = CodeMirror.fromTextArea(textarea, {
            mode: {name: "javascript", json: true},
            theme: "default",
            lineNumbers: true,
            lineWrapping: true,
            autoCloseBrackets: true,
            matchBrackets: true,
            indentUnit: 2,
            tabSize: 2,
            gutters: ["CodeMirror-lint-markers"],
            lint: true,
            extraKeys: {
                "Ctrl-Space": "autocomplete",
                "Ctrl-Q": function(cm) { cm.foldCode(cm.getCursor()); }
            }
        });

        // Store the instance
        this.codeMirrorInstances.set(textareaId, codeMirror);

        // Update preview on change
        codeMirror.on('change', () => {
            this.updatePreview(textareaId);
            this.validateValue(textareaId);
        });

        // Initial setup
        this.updatePreview(textareaId);
        this.validateValue(textareaId);

        return codeMirror;
    }

    bindEvents() {
        // Format JSON buttons
        $(document).on('click', '.format-json-btn', (e) => {
            e.preventDefault();
            const targetId = $(e.target).data('target');
            this.formatJson(targetId);
        });

        // Validate buttons
        $(document).on('click', '.validate-btn', (e) => {
            e.preventDefault();
            const targetId = $(e.target).data('target');
            this.validateValue(targetId, true);
        });

        // Compress JSON buttons
        $(document).on('click', '.compress-json-btn', (e) => {
            e.preventDefault();
            const targetId = $(e.target).data('target');
            this.compressJson(targetId);
        });

        // Copy value buttons
        $(document).on('click', '.copy-value-btn', (e) => {
            e.preventDefault();
            const targetId = $(e.target).data('target');
            this.copyValue(targetId);
        });

        // Form submission
        $(document).on('submit', 'form[id*="config"]', (e) => {
            // Save all CodeMirror instances to their textareas
            this.codeMirrorInstances.forEach((cm, id) => {
                cm.save();
            });
        });

        // Bulk select all
        $(document).on('change', '#selectAll', (e) => {
            const isChecked = $(e.target).prop('checked');
            $('.config-checkbox').prop('checked', isChecked).trigger('change');
        });

        // Individual checkbox change
        $(document).on('change', '.config-checkbox', () => {
            this.updateBulkActions();
        });

        // Bulk update button
        $(document).on('click', '#bulkUpdateBtn', (e) => {
            if ($('.config-checkbox:checked').length > 0) {
                $('#bulkForm').submit();
            }
        });

        // Configuration type change
        $(document).on('change', '#id_config_type', (e) => {
            this.onConfigTypeChange($(e.target).val());
        });
    }

    setupValidation() {
        // Real-time validation for configuration keys
        $(document).on('input', '#id_key', (e) => {
            this.validateKey($(e.target).val());
        });

        // Debounced validation for values
        let validationTimeout;
        $(document).on('input', 'textarea[id^="id_value"], textarea[id^="id_config_"]', (e) => {
            clearTimeout(validationTimeout);
            validationTimeout = setTimeout(() => {
                const textareaId = $(e.target).attr('id');
                this.validateValue(textareaId);
            }, 500);
        });
    }

    formatJson(textareaId) {
        const cm = this.codeMirrorInstances.get(textareaId);
        if (!cm) return;

        try {
            const currentValue = cm.getValue();
            if (!currentValue.trim()) return;

            const parsed = JSON.parse(currentValue);
            const formatted = JSON.stringify(parsed, null, 2);
            cm.setValue(formatted);

            this.showNotification('JSON formatted successfully!', 'success', textareaId);
        } catch (e) {
            this.showNotification('Invalid JSON: ' + e.message, 'error', textareaId);
        }
    }

    compressJson(textareaId) {
        const cm = this.codeMirrorInstances.get(textareaId);
        if (!cm) return;

        try {
            const currentValue = cm.getValue();
            if (!currentValue.trim()) return;

            const parsed = JSON.parse(currentValue);
            const compressed = JSON.stringify(parsed);
            cm.setValue(compressed);

            this.showNotification('JSON compressed successfully!', 'success', textareaId);
        } catch (e) {
            this.showNotification('Invalid JSON: ' + e.message, 'error', textareaId);
        }
    }

    validateValue(textareaId, showNotification = false) {
        const cm = this.codeMirrorInstances.get(textareaId);
        if (!cm) return true;

        const value = cm.getValue();
        const configType = $('#id_config_type').val();

        // AJAX validation
        $.ajax({
            url: '{% url "core:validate_config_value" %}',
            method: 'POST',
            data: {
                'value': value,
                'config_type': configType,
                'csrfmiddlewaretoken': $('input[name=csrfmiddlewaretoken]').val()
            },
            success: (response) => {
                const $textarea = $(`#${textareaId}`);
                $textarea.removeClass('is-valid is-invalid');

                if (response.is_valid) {
                    $textarea.addClass('is-valid');
                    if (showNotification) {
                        this.showNotification('Configuration value is valid!', 'success', textareaId);
                    }
                } else {
                    $textarea.addClass('is-invalid');
                    if (showNotification) {
                        this.showNotification('Invalid: ' + response.error_message, 'error', textareaId);
                    }
                }
            },
            error: () => {
                if (showNotification) {
                    this.showNotification('Validation failed. Please try again.', 'error', textareaId);
                }
            }
        });

        return true; // Assume valid for now
    }

    validateKey(key) {
        const $keyInput = $('#id_key');
        $keyInput.removeClass('is-valid is-invalid');

        if (!key) return;

        // Basic validation
        const isValid = /^[a-zA-Z_][a-zA-Z0-9_]*$/.test(key);

        if (isValid) {
            $keyInput.addClass('is-valid');
        } else {
            $keyInput.addClass('is-invalid');
        }
    }

    updatePreview(textareaId) {
        const cm = this.codeMirrorInstances.get(textareaId);
        if (!cm) return;

        const value = cm.getValue();
        const previewId = textareaId.replace('id_value', 'configPreview').replace('id_config_', 'configPreview_');

        let formattedValue = '';
        try {
            if (value.trim().startsWith('{') || value.trim().startsWith('[')) {
                const parsed = JSON.parse(value);
                formattedValue = JSON.stringify(parsed, null, 2);
            } else {
                formattedValue = value;
            }
        } catch (e) {
            formattedValue = value;
        }

        const $preview = $(`#${previewId}`);
        if ($preview.length) {
            $preview.html(`<pre class="mb-0"><code>${this.escapeHtml(formattedValue)}</code></pre>`);
        }
    }

    copyValue(textareaId) {
        const cm = this.codeMirrorInstances.get(textareaId);
        if (!cm) return;

        const value = cm.getValue();

        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(value).then(() => {
                this.showNotification('Value copied to clipboard!', 'success', textareaId);
            });
        } else {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = value;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            this.showNotification('Value copied to clipboard!', 'success', textareaId);
        }
    }

    updateBulkActions() {
        const checkedCount = $('.config-checkbox:checked').length;
        const $bulkBtn = $('#bulkUpdateBtn');

        if (checkedCount > 0) {
            $bulkBtn.prop('disabled', false);
            $bulkBtn.html(`<i class="fas fa-edit"></i> Bulk Update (${checkedCount})`);
        } else {
            $bulkBtn.prop('disabled', true);
            $bulkBtn.html('<i class="fas fa-edit"></i> Bulk Update');
        }

        // Update select all checkbox
        const totalCheckboxes = $('.config-checkbox').length;
        const $selectAll = $('#selectAll');
        const allChecked = checkedCount === totalCheckboxes;
        const someChecked = checkedCount > 0;

        $selectAll.prop('checked', allChecked);
        $selectAll.prop('indeterminate', someChecked && !allChecked);
    }

    onConfigTypeChange(configType) {
        // Update help text or validation rules based on config type
        const helpText = this.getConfigTypeHelp(configType);
        $('#configTypeHelp').text(helpText);
    }

    getConfigTypeHelp(configType) {
        const helpTexts = {
            'general': 'General system-wide settings and preferences.',
            'academic': 'Academic year, terms, grading scales, and calendar settings.',
            'finance': 'Financial settings including currency, fees, and payment options.',
            'communication': 'Email, SMS, and notification settings.',
            'security': 'Password policies, access controls, and authentication settings.',
            'ui': 'User interface themes, layouts, and display preferences.'
        };

        return helpTexts[configType] || 'System configuration setting.';
    }

    showNotification(message, type = 'info', targetId = null) {
        // Remove existing notifications for this target
        if (targetId) {
            $(`.notification[data-target="${targetId}"]`).remove();
        }

        const notificationClass = `alert-${type === 'error' ? 'danger' : type}`;
        const iconClass = `fas fa-${type === 'success' ? 'check' : type === 'error' ? 'times' : 'info'}`;

        const notification = `
            <div class="alert ${notificationClass} alert-dismissible notification" data-target="${targetId || ''}">
                <button type="button" class="close" data-dismiss="alert">
                    <span>&times;</span>
                </button>
                <i class="${iconClass}"></i> ${message}
            </div>
        `;

        // Insert notification
        if (targetId) {
            $(`#${targetId}`).closest('.form-group').append(notification);
        } else {
            $('.card-body').first().prepend(notification);
        }

        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            $('.notification').first().fadeOut();
        }, 5000);
    }

    escapeHtml(text) {
        const map = {
            '&': '&',
            '<': '<',
            '>': '>',
            '"': '"',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    // Utility method to get configuration value
    static getConfigValue(key, callback) {
        $.ajax({
            url: `{% url "core:get_config_value" "PLACEHOLDER" %}`.replace('PLACEHOLDER', key),
            method: 'GET',
            success: (response) => {
                if (callback) callback(response.value, response);
            },
            error: () => {
                console.warn(`Failed to get config value for key: ${key}`);
                if (callback) callback(null);
            }
        });
    }

    // Utility method to validate configuration value
    static validateConfigValue(value, configType, callback) {
        $.ajax({
            url: '{% url "core:validate_config_value" %}',
            method: 'POST',
            data: {
                'value': value,
                'config_type': configType,
                'csrfmiddlewaretoken': $('input[name=csrfmiddlewaretoken]').val()
            },
            success: (response) => {
                if (callback) callback(response.is_valid, response.error_message);
            },
            error: () => {
                if (callback) callback(false, 'Validation request failed');
            }
        });
    }
}

// Initialize when document is ready
$(document).ready(() => {
    window.configManager = new ConfigManager();
});

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ConfigManager;
}
