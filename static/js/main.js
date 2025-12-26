// Main JavaScript file for Uwaila Global Platform

// Initialize tooltips
document.addEventListener('DOMContentLoaded', function() {
    // Initialize Bootstrap tooltips
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Initialize popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Password toggle functionality
    document.querySelectorAll('.password-toggle').forEach(function(button) {
        button.addEventListener('click', function() {
            const input = this.previousElementSibling;
            const icon = this.querySelector('i');
            
            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    });

    // Form validation
    document.querySelectorAll('form').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            if (!form.checkValidity()) {
                e.preventDefault();
                e.stopPropagation();
            }
            form.classList.add('was-validated');
        });
    });

    // Character counter for textareas
    document.querySelectorAll('textarea[data-max-length]').forEach(function(textarea) {
        const maxLength = textarea.getAttribute('data-max-length');
        const counterId = 'counter-' + textarea.id;
        let counter = document.getElementById(counterId);
        
        if (!counter) {
            counter = document.createElement('div');
            counter.id = counterId;
            counter.className = 'form-text text-end';
            textarea.parentNode.appendChild(counter);
        }
        
        function updateCounter() {
            const length = textarea.value.length;
            counter.textContent = length + '/' + maxLength + ' characters';
            
            if (length > maxLength) {
                counter.classList.add('text-danger');
            } else {
                counter.classList.remove('text-danger');
            }
        }
        
        textarea.addEventListener('input', updateCounter);
        updateCounter(); // Initial call
    });

    // Auto-format phone numbers
    document.querySelectorAll('input[type="tel"]').forEach(function(input) {
        input.addEventListener('input', function(e) {
            let value = this.value.replace(/\D/g, '');
            
            if (value.length > 3 && value.length <= 6) {
                value = value.replace(/(\d{3})(\d+)/, '$1-$2');
            } else if (value.length > 6 && value.length <= 10) {
                value = value.replace(/(\d{3})(\d{3})(\d+)/, '$1-$2-$3');
            } else if (value.length > 10) {
                value = value.replace(/(\d{3})(\d{3})(\d{4})(\d+)/, '$1-$2-$3-$4');
            }
            
            this.value = value;
        });
    });

    // Image preview for file inputs
    document.querySelectorAll('input[type="file"][accept^="image"]').forEach(function(input) {
        input.addEventListener('change', function(e) {
            const previewId = this.getAttribute('data-preview');
            if (!previewId) return;
            
            const preview = document.getElementById(previewId);
            if (!preview) return;
            
            preview.innerHTML = '';
            
            const files = this.files;
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const reader = new FileReader();
                
                reader.onload = function(e) {
                    const img = document.createElement('img');
                    img.src = e.target.result;
                    img.className = 'img-thumbnail m-1';
                    img.style.maxWidth = '100px';
                    img.style.maxHeight = '100px';
                    preview.appendChild(img);
                };
                
                reader.readAsDataURL(file);
            }
        });
    });

    // AJAX form submissions
    document.querySelectorAll('form[data-ajax]').forEach(function(form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const submitBtn = form.querySelector('[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...';
            submitBtn.disabled = true;
            
            const formData = new FormData(form);
            
            fetch(form.action, {
                method: form.method,
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    if (data.redirect) {
                        window.location.href = data.redirect;
                    } else {
                        // Show success message
                        showAlert('success', data.message || 'Operation successful');
                        
                        // Reset form if needed
                        if (form.hasAttribute('data-reset')) {
                            form.reset();
                            form.classList.remove('was-validated');
                        }
                        
                        // Reload page if needed
                        if (form.hasAttribute('data-reload')) {
                            setTimeout(() => location.reload(), 1500);
                        }
                    }
                } else {
                    showAlert('danger', data.message || 'An error occurred');
                }
            })
            .catch(error => {
                showAlert('danger', 'Network error. Please try again.');
                console.error('Error:', error);
            })
            .finally(() => {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            });
        });
    });

    // Show alert function
    window.showAlert = function(type, message, permanent = false) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show ${permanent ? 'alert-permanent' : ''}`;
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        const container = document.querySelector('.container:first-of-type') || document.body;
        container.insertBefore(alertDiv, container.firstChild);
        
        if (!permanent) {
            setTimeout(() => {
                if (alertDiv.parentNode) {
                    const bsAlert = new bootstrap.Alert(alertDiv);
                    bsAlert.close();
                }
            }, 5000);
        }
    };

    // Copy to clipboard
    document.querySelectorAll('.copy-to-clipboard').forEach(function(button) {
        button.addEventListener('click', function() {
            const text = this.getAttribute('data-clipboard-text') || 
                        this.previousElementSibling.value || 
                        this.previousElementSibling.textContent;
            
            navigator.clipboard.writeText(text).then(function() {
                const originalHTML = button.innerHTML;
                button.innerHTML = '<i class="fas fa-check"></i> Copied!';
                button.classList.add('btn-success');
                
                setTimeout(function() {
                    button.innerHTML = originalHTML;
                    button.classList.remove('btn-success');
                }, 2000);
            }).catch(function(err) {
                console.error('Failed to copy: ', err);
            });
        });
    });

    // Tab persistence
    document.querySelectorAll('a[data-bs-toggle="tab"]').forEach(function(tab) {
        tab.addEventListener('click', function(e) {
            localStorage.setItem('activeTab', e.target.getAttribute('href'));
        });
    });
    
    const activeTab = localStorage.getItem('activeTab');
    if (activeTab) {
        const tabElement = document.querySelector(`a[href="${activeTab}"]`);
        if (tabElement) {
            new bootstrap.Tab(tabElement).show();
        }
    }

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            
            const targetId = this.getAttribute('href');
            if (targetId === '#') return;
            
            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                window.scrollTo({
                    top: targetElement.offsetTop - 80,
                    behavior: 'smooth'
                });
            }
        });
    });

    /* const categorySelect = document.getElementById('category');
    if (categorySelect) {
        // Create search input
        const searchDiv = document.createElement('div');
        searchDiv.className = 'mb-3';
        searchDiv.innerHTML = `
            <input type="text" class="form-control" id="categorySearch" 
                   placeholder="Search for a service category...">
        `;
        categorySelect.parentNode.insertBefore(searchDiv, categorySelect);
        
        const searchInput = document.getElementById('categorySearch');
        
        searchInput.addEventListener('input', function() {
            const searchTerm = this.value.toLowerCase();
            const optgroups = categorySelect.querySelectorAll('optgroup');
            const options = categorySelect.querySelectorAll('option');
            
            // Show/hide optgroups based on search
            optgroups.forEach(optgroup => {
                let hasVisibleOptions = false;
                const groupOptions = optgroup.querySelectorAll('option');
                
                groupOptions.forEach(option => {
                    if (option.textContent.toLowerCase().includes(searchTerm)) {
                        option.style.display = '';
                        hasVisibleOptions = true;
                    } else {
                        option.style.display = 'none';
                    }
                });
                
                optgroup.style.display = hasVisibleOptions ? '' : 'none';
            });
            
            // Also search in regular options
            options.forEach(option => {
                if (!option.parentNode.tagName === 'OPTGROUP') {
                    if (option.textContent.toLowerCase().includes(searchTerm)) {
                        option.style.display = '';
                    } else {
                        option.style.display = 'none';
                    }
                }
            });
        });
    } */
});



// Utility functions
window.formatDate = function(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
};

window.formatDateTime = function(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
};

window.formatCurrency = function(amount, currency = 'NGN') {
    return new Intl.NumberFormat('en-NG', {
        style: 'currency',
        currency: currency
    }).format(amount);
};

// Debounce function for search inputs
window.debounce = function(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
};