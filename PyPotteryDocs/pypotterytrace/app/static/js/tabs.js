// Tab Management for PyPotteryTrace Interactive

class TabManager {
    constructor() {
        this.currentTab = 'model-tab';
        this.selectedModel = null;
        this.imageFiles = [];
        this.currentImageIndex = 0;
        this.folderPath = null;

        this.init();
    }

    init() {
        this.setupTabButtons();
        this.setupFolderSelection();
    }

    setupTabButtons() {
        const tabButtons = document.querySelectorAll('.tab-button');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                if (button.disabled) return;

                const tabId = button.dataset.tab;
                this.switchTab(tabId);
            });
        });
    }

    switchTab(tabId) {
        console.log('Switching to tab:', tabId);

        // Update buttons
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.tab === tabId);
        });

        // Update content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.toggle('active', content.id === tabId);
        });

        this.currentTab = tabId;

        // If switching to segmentation tab, resize canvas
        if (tabId === 'segmentation-tab' && window.canvasManager) {
            console.log('Resizing canvas for segmentation tab');
            setTimeout(() => {
                window.canvasManager.resize();
                console.log('Canvas resized');
            }, 50);
        }

        // If switching to SVG Editor tab, click reset view after 1 second
        if (tabId === 'svg-tab') {
            setTimeout(() => {
                const resetViewBtn = document.getElementById('svg-reset-view-btn');
                if (resetViewBtn) {
                    console.log('Auto-clicking Reset View for SVG Editor (1s delay)');
                    resetViewBtn.click();
                }
            }, 1000);
        }

        // If switching to Post-Processing tab, ALWAYS load vectorized files
        if (tabId === 'postprocess-tab' && window.postProcessingManager) {
            if (window.postProcessingManager.currentProjectId) {
                console.log('Loading vectorized files for Post-Processing tab');
                window.postProcessingManager.loadProjectVectorizedFiles();
            }
        }

        // If switching to Projects tab, refresh the project list
        if (tabId === 'project-tab' && window.ProjectManager) {
            console.log('Refreshing project list');
            window.ProjectManager.loadProjectsList();
        }
    }

    enableTab(tabId) {
        const button = document.querySelector(`.tab-button[data-tab="${tabId}"]`);
        if (button) {
            button.disabled = false;
        }
    }

    // Folder Selection (legacy - now handled by project manager)
    setupFolderSelection() {
        const selectButton = document.getElementById('select-folder-btn');
        const folderInput = document.getElementById('folder-input');

        // Skip if elements don't exist (folder selection removed from UI)
        if (!selectButton || !folderInput) {
            console.log('Folder selection elements not found - using project manager instead');
            return;
        }

        selectButton.addEventListener('click', () => {
            folderInput.click();
        });

        folderInput.addEventListener('change', (e) => {
            this.handleFolderSelection(e.target.files);
        });
    }

    handleFolderSelection(files) {
        console.log('=== handleFolderSelection START ===');
        console.log('Received files:', files);
        console.log('Files count:', files.length);

        // Show loading overlay
        this.showLoadingOverlay('Loading Images...', 'Processing your image files', 0, files.length);

        // Use setTimeout to allow UI to update
        setTimeout(() => {
            // Filter only image files
            const imageExtensions = ['jpg', 'jpeg', 'png', 'tiff', 'bmp', 'gif'];
            this.imageFiles = [];

            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const ext = file.name.split('.').pop().toLowerCase();
                console.log(`File: ${file.name}, ext: ${ext}, webkitRelativePath: ${file.webkitRelativePath}`);

                if (imageExtensions.includes(ext)) {
                    this.imageFiles.push(file);
                }

                // Update progress every 10 files or at the end
                if (i % 10 === 0 || i === files.length - 1) {
                    this.updateLoadingProgress(i + 1, files.length);
                }
            }

            console.log('Filtered imageFiles count:', this.imageFiles.length);

            if (this.imageFiles.length === 0) {
                this.hideLoadingOverlay();
                alert('No image files found in the selected folder!');
                return;
            }

            // Sort files by name
            this.imageFiles.sort((a, b) => a.name.localeCompare(b.name));

            // Extract folder path from first file
            this.folderPath = this.imageFiles[0].webkitRelativePath.split('/')[0];

            // Output folder is automatically set to project's exports folder
            this.outputFolderPath = this.folderPath + '_vectorized';

            // Enable post-processing tab immediately (can work independently)
            this.enableTab('postprocess-tab');

            // Update UI - show project images info, hide "no project" message
            const noProjectMsg = document.getElementById('no-project-message');
            const projectImagesInfo = document.getElementById('project-images-info');
            if (noProjectMsg) noProjectMsg.style.display = 'none';
            if (projectImagesInfo) projectImagesInfo.style.display = 'block';

            document.getElementById('folder-name').textContent = this.folderPath;
            document.getElementById('images-count').textContent = this.imageFiles.length;

            // Show preview thumbnails
            this.showImagePreviews();

            // Enable start button
            this.checkStartButton();

            // Hide loading overlay after a brief delay
            setTimeout(() => {
                this.hideLoadingOverlay();
            }, 300);
        }, 100);
    }

    /**
     * Load images from a project (called by ProjectManager)
     */
    async loadProjectImages(projectId, projectName) {
        try {
            console.log('=== loadProjectImages START ===');
            console.log('Project ID:', projectId);
            console.log('Project Name:', projectName);

            // Fetch images list from project
            const response = await fetch(`/api/projects/${projectId}/images?folder=uploads`);
            const data = await response.json();

            console.log('API Response:', data);

            if (!data.success || !data.images || data.images.length === 0) {
                console.log('No images in project uploads folder');
                return false;
            }

            const totalImages = data.images.length;
            console.log(`Loading ${totalImages} images from project...`);

            // Show loading overlay
            this.showLoadingOverlay('Loading Project Images...', `Loading ${totalImages} images from project`, 0, totalImages);

            // Fetch each image and create File objects with webkitRelativePath
            const files = [];

            for (let i = 0; i < data.images.length; i++) {
                try {
                    const imgName = data.images[i];
                    // imgName is just a string (filename), not an object
                    const filename = typeof imgName === 'string' ? imgName : imgName.filename;
                    console.log(`Fetching image ${i + 1}/${totalImages}: ${filename}`);

                    const imgResponse = await fetch(`/api/projects/${projectId}/images/${filename}?folder=uploads`);
                    const blob = await imgResponse.blob();

                    // Create File object with fake webkitRelativePath
                    const file = new File([blob], filename, { type: blob.type });

                    // Add fake webkitRelativePath property (needed by handleFolderSelection)
                    Object.defineProperty(file, 'webkitRelativePath', {
                        value: `${projectName}_uploads/${filename}`,
                        writable: false
                    });

                    files.push(file);
                    console.log(`✓ Loaded: ${filename}`);

                    // Update progress
                    this.updateLoadingProgress(i + 1, totalImages);
                } catch (err) {
                    console.error(`Failed to load image ${filename}:`, err);
                }
            }

            console.log(`Total files loaded: ${files.length}`);

            if (files.length === 0) {
                this.hideLoadingOverlay();
                console.log('No files to load!');
                return false;
            }

            // Use the existing handleFolderSelection function!
            console.log('Calling handleFolderSelection with', files.length, 'files');
            this.handleFolderSelection(files);

            console.log('=== loadProjectImages END ===');
            return true;
        } catch (error) {
            console.error('Error loading project images:', error);
            this.hideLoadingOverlay();
            return false;
        }
    }

    showImagePreviews() {
        const previewContainer = document.getElementById('images-preview');
        previewContainer.innerHTML = '';

        // Show first 30 images as thumbnails (increased from 20)
        const previewCount = Math.min(30, this.imageFiles.length);

        for (let i = 0; i < previewCount; i++) {
            const file = this.imageFiles[i];
            const img = document.createElement('img');
            img.src = URL.createObjectURL(file);
            img.title = file.name;
            img.alt = file.name;
            previewContainer.appendChild(img);
        }

        if (this.imageFiles.length > 30) {
            const moreText = document.createElement('div');
            moreText.style.cssText = 'grid-column: 1 / -1; text-align: center; color: #666; font-size: 0.9em; padding: 10px;';
            moreText.textContent = `... and ${this.imageFiles.length - 30} more images`;
            previewContainer.appendChild(moreText);
        }
    }


    checkStartButton() {
        const hasImages = this.imageFiles.length > 0;

        // If images are present, enable segmentation tab so user can proceed.
        // Model loading is handled separately by server-side endpoints or other UI flows.
        if (hasImages) {
            this.enableTab('segmentation-tab');
        }
    }

    // startProcessing removed: model loading can be triggered via other UI flows or server-side endpoints.

    // Loading overlay utilities
    showLoadingOverlay(title, message, current, total) {
        const overlay = document.getElementById('loading-overlay');
        const titleEl = document.getElementById('loading-overlay-title');
        const messageEl = document.getElementById('loading-overlay-message');
        const progressBar = document.getElementById('loading-overlay-progress-bar');
        const progressText = document.getElementById('loading-overlay-progress-text');

        if (overlay) {
            overlay.classList.add('active');
            if (titleEl) titleEl.textContent = title;
            if (messageEl) messageEl.textContent = message;
            if (progressBar) progressBar.style.width = '0%';
            if (progressText) progressText.textContent = `${current} / ${total} images loaded`;
        }
    }

    updateLoadingProgress(current, total) {
        const progressBar = document.getElementById('loading-overlay-progress-bar');
        const progressText = document.getElementById('loading-overlay-progress-text');

        if (progressBar && progressText) {
            const percentage = Math.round((current / total) * 100);
            progressBar.style.width = `${percentage}%`;
            progressText.textContent = `${current} / ${total} images loaded`;
        }
    }

    hideLoadingOverlay() {
        const overlay = document.getElementById('loading-overlay');
        if (overlay) {
            overlay.classList.remove('active');
        }
    }
}

// Note: TabManager is initialized in app.js to avoid double initialization

