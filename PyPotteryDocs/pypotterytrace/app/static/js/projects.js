/**
 * Project Management Module for PyPotteryTrace
 * Handles project creation, loading, and management
 */

const ProjectManager = {
    currentProject: null,
    selectedIcon: 'icon1',  // Default icon (stored as path reference)

    /**
     * Initialize project manager
     */
    init() {
        this.setupEventListeners();
        this.loadProjectsList();
    },

    /**
     * Setup event listeners for project UI
     */
    setupEventListeners() {
        // New project button
        const newBtn = document.getElementById('new-project-btn');
        if (newBtn) {
            newBtn.addEventListener('click', () => this.showCreateModal());
        }

        // Create project button (in modal)
        const createBtn = document.getElementById('create-project-btn');
        if (createBtn) {
            createBtn.addEventListener('click', () => this.createProject());
        }

        // Close modal buttons
        const closeBtn = document.getElementById('close-create-modal');
        const cancelBtn = document.getElementById('cancel-create-btn');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hideCreateModal());
        }
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.hideCreateModal());
        }

        // Modal overlay click
        const modal = document.getElementById('create-project-modal');
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target.classList.contains('modal-overlay')) {
                    this.hideCreateModal();
                }
            });
        }

        // Refresh projects button
        const refreshBtn = document.getElementById('refresh-projects-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadProjectsList());
        }

        // Icon selector
        const iconSelector = document.getElementById('icon-selector');
        if (iconSelector) {
            iconSelector.addEventListener('click', (e) => {
                if (e.target.classList.contains('icon-option') || e.target.parentElement.classList.contains('icon-option')) {
                    const btn = e.target.classList.contains('icon-option') ? e.target : e.target.parentElement;
                    // Remove active from all
                    iconSelector.querySelectorAll('.icon-option').forEach(b => {
                        b.classList.remove('active');
                    });
                    // Add active to clicked
                    btn.classList.add('active');
                    this.selectedIcon = btn.dataset.icon;
                }
            });
        }
    },

    /**
     * Show create project modal
     */
    showCreateModal() {
        const modal = document.getElementById('create-project-modal');
        if (modal) {
            modal.style.display = 'flex';
        }
    },

    /**
     * Hide create project modal
     */
    hideCreateModal() {
        const modal = document.getElementById('create-project-modal');
        if (modal) {
            modal.style.display = 'none';
        }
        // Clear form
        document.getElementById('new-project-name').value = '';
        document.getElementById('new-project-description').value = '';
    },

    /**
     * Create a new project
     */
    async createProject() {
        const name = document.getElementById('new-project-name').value.trim();
        const description = document.getElementById('new-project-description').value.trim();

        if (!name) {
            this.showNotification('Please enter a project name', 'error');
            return;
        }

        try {
            const response = await fetch('/api/projects', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_name: name,
                    description: description,
                    icon: this.selectedIcon
                })
            });

            const data = await response.json();

            if (data.success) {
                // Hide modal
                this.hideCreateModal();

                // Set current project
                this.currentProject = data.project;

                // Update UI
                this.updateProjectUI();

                // Immediately open folder selector to upload images (no confirmation dialog)
                this.showUploadImagesDialog(data.project.project_id);

                // Reload projects list
                await this.loadProjectsList();

                // Show success message
                this.showNotification('Project created! Now upload your images.', 'success');
            } else {
                this.showNotification(`Error: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error creating project:', error);
            this.showNotification('Failed to create project', 'error');
        }
    },

    /**
     * Show upload images dialog after project creation
     */
    showUploadImagesDialog(projectId) {
        // Open the folder selector directly so the user can pick images without an extra confirmation dialog
        this.uploadImagesToProject(projectId);
    },

    /**
     * Upload images to project
     */
    uploadImagesToProject(projectId) {
        // Create a temporary file input for selecting image files (multiple)
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.multiple = true;

        input.onchange = async (e) => {
            const files = Array.from(e.target.files);

            // Filter only images
            const imageExtensions = ['jpg', 'jpeg', 'png', 'tiff', 'bmp', 'gif'];
            const imageFiles = files.filter(file => {
                const ext = file.name.split('.').pop().toLowerCase();
                return imageExtensions.includes(ext);
            });

            if (imageFiles.length === 0) {
                this.showNotification('No image files selected', 'error');
                return;
            }

            this.showNotification(`Uploading ${imageFiles.length} images...`, 'info');

            // Upload images to project
            const formData = new FormData();
            imageFiles.forEach(file => {
                formData.append('files', file);
            });

            try {
                const response = await fetch(`/api/projects/${projectId}/upload`, {
                    method: 'POST',
                    body: formData
                });

                const data = await response.json();

                if (data.success) {
                    this.showNotification(`${data.count} images uploaded successfully!`, 'success');

                    // Load the project
                    await this.loadProject(projectId);
                } else {
                    this.showNotification(`Error uploading images: ${data.error}`, 'error');
                }
            } catch (error) {
                console.error('Error uploading images:', error);
                this.showNotification('Failed to upload images', 'error');
            }
        };

        input.click();
    },

    /**
     * Show load project dialog
     */
    async showLoadProjectDialog() {
        try {
            const response = await fetch('/api/projects');
            const data = await response.json();

            if (!data.success) {
                alert(`Error: ${data.error}`);
                return;
            }

            const projects = data.projects;

            const modal = document.createElement('div');
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-content" style="max-width: 800px;">
                    <div class="modal-header">
                        <h2>Load Project</h2>
                        <button class="close-btn" onclick="this.closest('.modal').remove()">×</button>
                    </div>
                    <div class="modal-body">
                        ${projects.length === 0 ? `
                            <p class="text-muted">No projects found. Create a new project to get started.</p>
                        ` : `
                            <div class="projects-list">
                                ${projects.map(project => this.renderProjectCard(project)).join('')}
                            </div>
                        `}
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">
                            Close
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
        } catch (error) {
            console.error('Error loading projects:', error);
            alert('Failed to load projects list');
        }
    },

    /**
     * Render a project card
     */
    renderProjectCard(project) {
        const createdDate = new Date(project.created_at).toLocaleDateString();
        const modifiedDate = new Date(project.last_modified).toLocaleDateString();

        return `
            <div class="project-card">
                <div class="project-info">
                    <h3>${project.project_name}</h3>
                    <p class="project-id">${project.project_id}</p>
                    ${project.description ? `<p class="project-description">${project.description}</p>` : ''}
                    <div class="project-meta">
                        <span>Created: ${createdDate}</span>
                        <span style="margin-left: 15px;">Modified: ${modifiedDate}</span>
                    </div>
                </div>
                <div class="project-actions">
                    <button class="btn btn-sm btn-primary" 
                            onclick="ProjectManager.loadProject('${project.project_id}')">
                        Load
                    </button>
                    <button class="btn btn-sm btn-secondary" 
                            onclick="ProjectManager.showProjectDetails('${project.project_id}')">
                        Details
                    </button>
                    <button class="btn btn-sm btn-danger" 
                            onclick="ProjectManager.deleteProject('${project.project_id}')">
                        Delete
                    </button>
                </div>
            </div>
        `;
    },

    /**
     * Load a project
     */
    async loadProject(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}`);
            const data = await response.json();

            if (!data.success) {
                this.showNotification(`Error: ${data.error}`, 'error');
                return;
            }

            this.currentProject = data.project;

            // Update UI
            this.updateProjectUI();

            // Hide modal if open
            this.hideCreateModal();

            // Load project images into Setup tab using TabManager
            if (window.tabManager) {
                const loaded = await window.tabManager.loadProjectImages(projectId, data.project.project_name);

                if (loaded) {
                    console.log('Project images loaded into Setup tab');
                } else {
                    console.log('No images found in project or failed to load');
                }
            }

            // Load project images into segmentation tab grid
            await this.loadProjectImages(projectId);

            // Enable segmentation tab
            const segmentationTab = document.getElementById('segmentation-tab-btn');
            if (segmentationTab) {
                segmentationTab.disabled = false;
            }

            // Switch to Setup tab to show loaded images
            if (window.tabManager && window.tabManager.switchTab) {
                window.tabManager.switchTab('model-tab');
            }

            // Show notification
            this.showNotification(`Project "${data.project.project_name}" loaded successfully!`, 'success');
        } catch (error) {
            console.error('Error loading project:', error);
            this.showNotification('Failed to load project', 'error');
        }
    },

    /**
     * Update project UI elements
     */
    updateProjectUI() {
        if (!this.currentProject) return;

        // Show project info bar
        const infoBar = document.getElementById('project-info-bar');
        if (infoBar) {
            infoBar.style.display = 'flex';
        }

        // Update project name and icon
        const projectNameEl = document.getElementById('current-project-name');
        if (projectNameEl) {
            projectNameEl.textContent = this.currentProject.project_name;
        }

        const projectIconEl = document.getElementById('project-icon');
        if (projectIconEl) {
            // Get icon path (icon1 -> imgs/icons/1.png)
            const iconPath = this.getIconPath(this.currentProject.icon || 'icon1');
            projectIconEl.innerHTML = `<img src="${iconPath}" alt="Project Icon" style="width: 100%; height: 100%; object-fit: contain;">`;
        }

        // Store in session
        sessionStorage.setItem('current_project_id', this.currentProject.project_id);
        sessionStorage.setItem('current_project_name', this.currentProject.project_name);
    },

    /**
     * Convert icon identifier to path
     */
    getIconPath(iconId) {
        // iconId is like "icon1", "icon2", etc.
        // Extract number and build path
        const iconNumber = iconId.replace('icon', '');
        return `/static/imgs/icons/${iconNumber}.png`;
    },

    /**
     * Load project images into segmentation tab
     */
    async loadProjectImages(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}/images?folder=uploads`);
            const data = await response.json();

            if (data.success) {
                console.log(`Loaded ${data.total} images from project`);

                // Load images into ImageGrid
                if (window.ImageGrid) {
                    await window.ImageGrid.loadProjectImages(projectId);

                    // Auto-load first image with annotations
                    if (data.images && data.images.length > 0 && window.app) {
                        const firstImage = typeof data.images[0] === 'string' ? data.images[0] : data.images[0].filename;
                        console.log('Auto-loading first image:', firstImage);
                        await window.app.loadProjectImage(firstImage);
                    }
                }
            }
        } catch (error) {
            console.error('Error loading project images:', error);
        }
    },

    /**
     * Close current project
     */
    closeCurrentProject() {
        if (confirm('Close current project?')) {
            this.currentProject = null;
            sessionStorage.removeItem('current_project_id');

            // Update UI
            const projectNameEl = document.getElementById('current-project-name');
            if (projectNameEl) {
                projectNameEl.textContent = 'No project loaded';
            }

            const projectControls = document.getElementById('project-controls');
            if (projectControls) {
                projectControls.style.display = 'none';
            }

            this.showNotification('Project closed', 'info');
        }
    },

    /**
     * Show project details
     */
    async showProjectDetails(projectId) {
        try {
            const response = await fetch(`/api/projects/${projectId}`);
            const data = await response.json();

            if (!data.success) {
                alert(`Error: ${data.error}`);
                return;
            }

            const project = data.project;
            const stats = data.stats;

            const modal = document.createElement('div');
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-content" style="max-width: 600px;">
                    <div class="modal-header">
                        <h2>${project.project_name}</h2>
                        <button class="close-btn" onclick="this.closest('.modal').remove()">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="project-details">
                            <p><strong>ID:</strong> ${project.project_id}</p>
                            ${project.description ? `<p><strong>Description:</strong> ${project.description}</p>` : ''}
                            <p><strong>Created:</strong> ${new Date(project.created_at).toLocaleString()}</p>
                            <p><strong>Last Modified:</strong> ${new Date(project.last_modified).toLocaleString()}</p>
                            
                            <hr>
                            
                            <h3>Statistics</h3>
                            <ul class="stats-list">
                                <li>Uploaded Images: ${stats.total_uploads}</li>
                                <li>Sessions: ${stats.total_sessions}</li>
                                <li>Vectorized: ${stats.total_vectorized}</li>
                                <li>Exports: ${stats.total_exports}</li>
                            </ul>
                            
                            <hr>
                            
                            <h3>Settings</h3>
                            <ul class="settings-list">
                                <li>SAM2 Model: ${project.settings.sam2_model_size}</li>
                                <li>Epsilon: ${project.settings.epsilon}</li>
                                <li>Smoothing: ${project.settings.smoothing_factor}</li>
                                <li>Include Background: ${project.settings.include_background ? 'Yes' : 'No'}</li>
                            </ul>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">
                            Close
                        </button>
                        <button class="btn btn-primary" onclick="ProjectManager.loadProject('${projectId}')">
                            Load Project
                        </button>
                    </div>
                </div>
            `;

            document.body.appendChild(modal);
        } catch (error) {
            console.error('Error loading project details:', error);
            alert('Failed to load project details');
        }
    },

    /**
     * Delete a project
     */
    async deleteProject(projectId) {
        if (!confirm('Are you sure you want to delete this project? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch(`/api/projects/${projectId}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                // Close modal if open
                const modal = document.querySelector('.modal');
                if (modal) modal.remove();

                // Reload projects list to update the UI
                await this.loadProjectsList();

                // Show notification
                this.showNotification('Project deleted successfully', 'success');
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            console.error('Error deleting project:', error);
            alert('Failed to delete project');
        }
    },

    /**
     * Show project settings
     */
    async showProjectSettings() {
        if (!this.currentProject) {
            alert('No project loaded');
            return;
        }

        const settings = this.currentProject.settings;

        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Project Settings</h2>
                    <button class="close-btn" onclick="this.closest('.modal').remove()">×</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label for="setting-model-size">SAM2 Model Size</label>
                        <select id="setting-model-size" class="form-control">
                            <option value="tiny" ${settings.sam2_model_size === 'tiny' ? 'selected' : ''}>Tiny</option>
                            <option value="small" ${settings.sam2_model_size === 'small' ? 'selected' : ''}>Small</option>
                            <option value="base" ${settings.sam2_model_size === 'base' ? 'selected' : ''}>Base</option>
                            <option value="large" ${settings.sam2_model_size === 'large' ? 'selected' : ''}>Large</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label for="setting-epsilon">Epsilon (Path Simplification)</label>
                        <input type="number" id="setting-epsilon" class="form-control" 
                               value="${settings.epsilon}" step="0.1" min="0.1" max="10">
                    </div>
                    <div class="form-group">
                        <label for="setting-smoothing">Smoothing Factor</label>
                        <input type="number" id="setting-smoothing" class="form-control" 
                               value="${settings.smoothing_factor}" step="0.1" min="0" max="1">
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="setting-background" 
                                   ${settings.include_background ? 'checked' : ''}>
                            Include Background in SVG
                        </label>
                    </div>
                    <div class="form-group">
                        <label>
                            <input type="checkbox" id="setting-training-data" 
                                   ${settings.save_training_data ? 'checked' : ''}>
                            Save ML Training Data
                        </label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">
                        Cancel
                    </button>
                    <button class="btn btn-primary" onclick="ProjectManager.saveProjectSettings()">
                        Save Settings
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    },

    /**
     * Save project settings
     */
    async saveProjectSettings() {
        if (!this.currentProject) return;

        const settings = {
            sam2_model_size: document.getElementById('setting-model-size').value,
            epsilon: parseFloat(document.getElementById('setting-epsilon').value),
            smoothing_factor: parseFloat(document.getElementById('setting-smoothing').value),
            include_background: document.getElementById('setting-background').checked,
            save_training_data: document.getElementById('setting-training-data').checked
        };

        try {
            const response = await fetch(`/api/projects/${this.currentProject.project_id}/settings`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ settings })
            });

            const data = await response.json();

            if (data.success) {
                // Update local settings
                this.currentProject.settings = settings;

                // Close modal
                document.querySelector('.modal').remove();

                this.showNotification('Settings saved successfully', 'success');
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            console.error('Error saving settings:', error);
            alert('Failed to save settings');
        }
    },

    /**
     * Load projects list (for initialization)
     */
    async loadProjectsList() {
        try {
            const response = await fetch('/api/projects');
            const data = await response.json();

            if (data.success) {
                console.log(`Loaded ${data.total} projects`);
                this.displayProjects(data.projects);
            }
        } catch (error) {
            console.error('Error loading projects:', error);
        }
    },

    /**
     * Display projects in grid
     */
    displayProjects(projects) {
        const container = document.getElementById('projects-list');

        if (!container) return;

        if (projects.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📁</div>
                    <h3>No Projects Yet</h3>
                    <p>Create your first project to start analyzing pottery images</p>
                    <button class="btn btn-primary" onclick="ProjectManager.showCreateModal()">
                        ➕ Create Your First Project
                    </button>
                </div>
            `;
            return;
        }

        container.innerHTML = projects.map(project => this.renderProjectCard(project)).join('');
    },

    /**
     * Render a project card (PyPotteryLens style)
     */
    renderProjectCard(project) {
        const createdDate = new Date(project.created_at).toLocaleDateString();
        const modifiedDate = new Date(project.last_modified).toLocaleDateString();
        const icon = project.icon || 'icon1';
        const iconPath = this.getIconPath(icon);
        const stats = project.workflow_status || {};

        return `
            <div class="project-card" onclick="ProjectManager.loadProject('${project.project_id}')">
                <div class="project-card-header">
                    <div class="project-card-icon">
                        <img src="${iconPath}" alt="${project.project_name}">
                    </div>
                    <div class="project-card-title">
                        <h4>${project.project_name}</h4>
                        <span class="project-card-id">${project.project_id}</span>
                    </div>
                </div>
                
                ${project.description ? `<p class="project-card-description">${project.description}</p>` : ''}
                
                <div class="project-card-stats">
                    <div class="project-stat">
                        <span class="project-stat-label">Uploaded</span>
                        <span class="project-stat-value">${stats.images_uploaded || 0}</span>
                    </div>
                    <div class="project-stat">
                        <span class="project-stat-label">Vectorized</span>
                        <span class="project-stat-value">${stats.images_vectorized || 0}</span>
                    </div>
                </div>
                
                <div class="project-card-meta">
                    <span>Created: ${createdDate}</span>
                    <span style="margin-left: 15px;">Modified: ${modifiedDate}</span>
                </div>
                
                <div class="project-card-actions" onclick="event.stopPropagation()">
                    <button class="btn btn-sm btn-danger" onclick="ProjectManager.deleteProject('${project.project_id}')">
                        🗑️ Delete
                    </button>
                </div>
            </div>
        `;
    },

    /**
     * Show import project dialog
     */
    showImportProjectDialog() {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h2>Import Project</h2>
                    <button class="close-btn" onclick="this.closest('.modal').remove()">×</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label for="import-file">Select Project ZIP File</label>
                        <input type="file" id="import-file" class="form-control" 
                               accept=".zip" required>
                    </div>
                    <p class="text-muted" style="font-size: 0.875rem;">
                        Select a ZIP file containing a previously exported project.
                    </p>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-secondary" onclick="this.closest('.modal').remove()">
                        Cancel
                    </button>
                    <button class="btn btn-primary" onclick="ProjectManager.importProject()">
                        Import
                    </button>
                </div>
            </div>
        `;

        document.body.appendChild(modal);
    },

    /**
     * Import a project from ZIP
     */
    async importProject() {
        const fileInput = document.getElementById('import-file');
        const file = fileInput.files[0];

        if (!file) {
            alert('Please select a file to import');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            this.showNotification('Importing project...', 'info');

            const response = await fetch('/api/projects/import', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                // Close modal
                document.querySelector('.modal').remove();

                // Load the imported project
                await this.loadProject(data.project_id);

                this.showNotification('Project imported successfully!', 'success');
            } else {
                alert(`Error: ${data.error}`);
            }
        } catch (error) {
            console.error('Error importing project:', error);
            alert('Failed to import project');
        }
    },

    /**
     * Show notification
     */
    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('show');
        }, 10);

        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }
};

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    ProjectManager.init();
});
