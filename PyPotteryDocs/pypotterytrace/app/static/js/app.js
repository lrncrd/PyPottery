// PyPotteryTrace Interactive - Main Application Script

console.log('app.js loaded');

class PyPotteryTraceApp {
    constructor() {
        console.log('PyPotteryTraceApp constructor called');
        this.sessionId = null;
        this.currentImage = null;
        this.segments = [];
        this.rotationCenter = null;
        this.currentMode = 'point';
        this.epsilon = 1.5;
        this.smoothing = 0.3;

        // New: Image folder navigation
        this.imageFiles = [];
        this.currentImageIndex = 0;
        this.saveTrainingData = false;

        // Project context for persistence
        this.currentProjectId = null;
        this.currentImageName = null;
        this.saveTimeout = null;  // For debouncing auto-save

        console.log('Calling init()');
        this.init();
        console.log('Constructor complete');
    }

    init() {
        this.setupEventListeners();
        this.setupHelpModal();
        this.updateUI();

        // Listen for image selection from grid
        document.addEventListener('imageSelected', async (e) => {
            const { projectId, filename, index } = e.detail;
            await this.loadProjectImage(projectId, filename, index);
        });

        // Listen for session loaded event from ImageGrid
        document.addEventListener('sessionLoaded', (e) => {
            this.loadSession(e.detail);
        });
    }

    setupEventListeners() {
        // Mode selection
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.setMode(btn.dataset.mode);
            });
        });

        // Category and name
        document.getElementById('category-select').addEventListener('change', () => {
            this.updateElementName();
        });

        // Add segment button
        document.getElementById('add-segment-btn').addEventListener('click', () => {
            this.addCurrentSegment();
        });

        // Clear preview button
        document.getElementById('clear-preview-btn').addEventListener('click', () => {
            this.clearPreview();
        });

        // Clear rotation center button
        document.getElementById('clear-rotation-btn').addEventListener('click', () => {
            if (window.canvasManager) {
                window.canvasManager.clearRotationCenter();
                document.getElementById('rotation-center-info').style.display = 'none';
            }
        });

        // Settings sliders
        document.getElementById('epsilon-slider').addEventListener('input', (e) => {
            this.epsilon = parseFloat(e.target.value);
            document.getElementById('epsilon-value').textContent = this.epsilon.toFixed(1);
        });

        document.getElementById('smoothing-slider').addEventListener('input', (e) => {
            this.smoothing = parseFloat(e.target.value);
            document.getElementById('smoothing-value').textContent = this.smoothing.toFixed(1);
        });

        // Export button
        document.getElementById('export-btn').addEventListener('click', () => {
            this.exportSegments();
        });

        // Debug export button (PNG masks)
        document.getElementById('debug-export-btn').addEventListener('click', () => {
            this.exportMasksDebug();
        });

        // Update ML export notice visibility when Training Data checkbox changes
        const saveTrainingCheckbox = document.getElementById('save-training-data');
        if (saveTrainingCheckbox) {
            saveTrainingCheckbox.addEventListener('change', () => {
                this.updateMLExportNotice();
            });
        }

        // Zoom controls
        document.getElementById('zoom-in-btn').addEventListener('click', () => {
            if (window.canvasManager) window.canvasManager.zoom(1.2);
        });

        document.getElementById('zoom-out-btn').addEventListener('click', () => {
            if (window.canvasManager) window.canvasManager.zoom(0.8);
        });

        document.getElementById('reset-view-btn').addEventListener('click', () => {
            if (window.canvasManager) window.canvasManager.resetView();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            this.handleKeyboardShortcut(e);
        });
    }

    setupHelpModal() {
        // Help Modal
        const helpModal = document.getElementById('help-modal');
        const helpBtn = document.getElementById('help-btn');
        const helpClose = helpModal?.querySelector('.close');

        if (helpBtn && helpModal && helpClose) {
            helpBtn.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                helpModal.style.display = 'flex';
                console.log('Help modal opened');
            };

            helpClose.onclick = (e) => {
                e.preventDefault();
                e.stopPropagation();
                helpModal.style.display = 'none';
            };
        } else {
            console.error('Help modal elements not found:', { helpBtn, helpModal, helpClose });
        }

        // Help Modal Tabs
        const helpTabBtns = document.querySelectorAll('.help-tab-btn');
        const helpTabContents = document.querySelectorAll('.help-tab-content');

        helpTabBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                const targetTab = btn.dataset.helpTab;

                // Update active tab button
                helpTabBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Update active tab content
                helpTabContents.forEach(content => {
                    if (content.dataset.helpContent === targetTab) {
                        content.classList.add('active');
                    } else {
                        content.classList.remove('active');
                    }
                });
            });
        });

        // Close modals when clicking outside
        window.onclick = (event) => {
            if (event.target == helpModal) {
                helpModal.style.display = 'none';
            }
        };

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                if (helpModal.style.display === 'flex') {
                    helpModal.style.display = 'none';
                }
            }
        });
    }

    async loadSystemInfo() {
        // Get CPU info (from navigator)
        const cpuCores = navigator.hardwareConcurrency || 'Unknown';
        document.getElementById('info-cpu').textContent = `${cpuCores} cores (Available)`;

        // Try to get GPU info from backend
        try {
            const response = await fetch('/api/system_info');
            if (response.ok) {
                const data = await response.json();

                if (data.gpu_available) {
                    document.getElementById('info-gpu').textContent =
                        `Available (${data.gpu_count} device${data.gpu_count > 1 ? 's' : ''})\n${data.gpu_name || ''}`;
                } else {
                    document.getElementById('info-gpu').textContent = 'Not Available';
                }

                if (data.mps_available) {
                    document.getElementById('info-mps').textContent = 'Available';
                } else {
                    document.getElementById('info-mps').textContent = 'Not Available';
                }
            }
        } catch (error) {
            console.log('Could not fetch system info from backend');
            // Fallback to basic detection
            document.getElementById('info-gpu').textContent = 'Unknown';
            document.getElementById('info-mps').textContent = 'Not Available';
        }
    }

    setMode(mode) {
        console.log('Setting mode to:', mode);
        this.currentMode = mode;

        // Update UI
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        // Show/hide point controls
        const pointControls = document.getElementById('point-controls');
        const polygonControls = document.getElementById('polygon-controls');

        pointControls.style.display = mode === 'point' ? 'block' : 'none';
        if (polygonControls) {
            polygonControls.style.display = mode === 'polygon' ? 'block' : 'none';
        }

        // Clear previous mode data when switching modes
        if (window.segmentationManager) {
            if (mode !== 'polygon') {
                segmentationManager.clearPolygon();
            }
        }

        // Update canvas cursor
        if (window.canvasManager) {
            window.canvasManager.setMode(mode);
        }

        console.log('Mode set successfully. Current mode:', this.currentMode);
    }

    async loadImageAtIndex(index) {
        console.log('=== loadImageAtIndex called ===');
        console.log('Index:', index);
        console.log('Total images:', this.imageFiles.length);

        if (index < 0 || index >= this.imageFiles.length) {
            console.error('Invalid image index:', index);
            return;
        }

        this.currentImageIndex = index;
        const file = this.imageFiles[index];
        console.log('Loading file:', file.name);

        const formData = new FormData();
        formData.append('file', file);

        // Add output folder path if available
        if (window.tabManager && window.tabManager.outputFolderPath) {
            formData.append('output_folder_path', window.tabManager.outputFolderPath);
        }

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                this.sessionId = data.session_id;
                this.currentImage = data.image_url;
                this.currentImageFilename = data.filename;  // Store filename for SVG export

                // Clear segments for new image
                this.segments = [];
                this.rotationCenter = null;

                // IMPORTANT: Clear canvas completely (masks, SVG overlay, rotation center)
                if (window.canvasManager) {
                    console.log('Clearing canvas for new image...');
                    window.canvasManager.clearAll();
                }

                // Clear segmentation preview
                if (window.segmentationManager) {
                    window.segmentationManager.clearCurrentSegment();
                }

                // Update UI
                document.getElementById('filename').textContent = data.filename;
                document.getElementById('current-image-number').textContent = index + 1;
                document.getElementById('total-images').textContent = this.imageFiles.length;
                document.getElementById('canvas-message').style.display = 'none';

                // Load image in canvas
                console.log('Loading image in canvas:', this.currentImage);
                console.log('canvasManager available:', window.canvasManager ? 'YES' : 'NO');

                if (window.canvasManager) {
                    window.canvasManager.loadImage(this.currentImage);
                } else {
                    console.error('canvasManager not available!');
                }

                // Update UI
                this.updateSegmentsList();
                this.updateStats();

                this.showNotification(`Loaded image ${index + 1} of ${this.imageFiles.length}`, 'success');
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showNotification('Failed to upload image: ' + error.message, 'error');
        }
    }

    navigateImage(direction) {
        const newIndex = this.currentImageIndex + direction;

        if (newIndex >= 0 && newIndex < this.imageFiles.length) {
            this.loadImageAtIndex(newIndex);
        }
    }

    async handleImageUpload(file) {
        if (!file) return;

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                this.sessionId = data.session_id;
                this.currentImage = data.image_url;

                // Update UI
                document.getElementById('filename').textContent = data.filename;
                document.getElementById('canvas-message').style.display = 'none';

                // Load image in canvas
                if (window.canvasManager) {
                    window.canvasManager.loadImage(this.currentImage);
                }

                // Switch to segmentation tab to show the image
                if (window.tabManager) {
                    tabManager.switchTab('segmentation-tab');
                }

                this.showNotification('Image uploaded successfully!', 'success');
            } else {
                throw new Error(data.error || 'Upload failed');
            }
        } catch (error) {
            console.error('Upload error:', error);
            this.showNotification('Failed to upload image: ' + error.message, 'error');
        }
    }

    updateElementName() {
        const category = document.getElementById('category-select').value;
        const nameInput = document.getElementById('element-name');
        const count = this.segments.filter(s => s.category === category).length + 1;
        nameInput.placeholder = `${category} ${count}`;

        // Set default vectorization based on category
        const vectorizeCheckbox = document.getElementById('vectorize-checkbox');
        vectorizeCheckbox.checked = this.getDefaultVectorization(category);
    }

    async addCurrentSegment() {
        if (!segmentationManager.currentMask) {
            this.showNotification('No segment to add', 'warning');
            return;
        }

        if (!segmentationManager.previewContours) {
            this.showNotification('No preview contours available', 'warning');
            return;
        }

        const category = document.getElementById('category-select').value;
        const nameInput = document.getElementById('element-name');
        const name = nameInput.value || nameInput.placeholder;
        const shouldVectorize = document.getElementById('vectorize-checkbox').checked;

        // Check if this is a manual mask (polygon)
        const isManualMask = segmentationManager.isManualMask;

        // Store preview contours before clearing
        const contoursToSave = segmentationManager.previewContours;

        // For manual masks, use the contours directly as the mask data
        let maskData = segmentationManager.currentMask;
        if (isManualMask && segmentationManager.currentMask.type === 'polygon') {
            // Convert polygon to contour format for backend
            maskData = {
                type: 'polygon',
                vertices: segmentationManager.currentMask.vertices,
                isManual: true
            };
        }

        // Disable the add button immediately to prevent double-clicking
        const addButton = document.getElementById('add-segment-btn');
        addButton.disabled = true;

        try {
            const response = await fetch('/api/add_segment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    mask: maskData,
                    category: category,
                    name: name,
                    should_vectorize: shouldVectorize,
                    is_manual: isManualMask  // Flag for manual masks - no dilation
                })
            });

            const data = await response.json();

            if (data.success) {
                // Add to local list
                this.segments.push({
                    id: data.segment_id,
                    name: name,
                    category: category,
                    mask: maskData,  // Save mask data for persistence
                    contours: contoursToSave,  // Save contours for redrawing
                    should_vectorize: shouldVectorize,
                    is_manual: isManualMask  // Store manual mask flag
                });

                // Save the stored contours to canvas as a permanent mask
                if (window.canvasManager) {
                    window.canvasManager.addSavedMask(contoursToSave, category, name, data.segment_id);

                    // Clear SVG overlay since we now have updated masks
                    window.canvasManager.clearSVG();
                }

                // Save annotations to project if we have a project ID
                await this.saveAnnotationsToProject();

                // Update UI
                this.updateSegmentsList();
                this.updateStats();
                this.clearPreview();
                nameInput.value = '';
                this.updateElementName();

                const manualText = isManualMask ? ' (manual)' : '';
                this.showNotification(`Segment added successfully${manualText}!`, 'success');
            } else {
                throw new Error(data.error || 'Failed to add segment');
            }
        } catch (error) {
            console.error('Add segment error:', error);
            this.showNotification('Failed to add segment: ' + error.message, 'error');
            // Re-enable the button if there was an error
            addButton.disabled = false;
        }
    }

    clearPreview() {
        segmentationManager.clearCurrentSegment();
        document.getElementById('add-segment-btn').disabled = true;
        document.getElementById('clear-preview-btn').disabled = true;
    }

    updateSegmentsList() {
        const list = document.getElementById('segments-list');

        if (this.segments.length === 0) {
            list.innerHTML = '<p class="empty-message">No segments yet</p>';
            document.getElementById('export-btn').disabled = true;
            return;
        }

        list.innerHTML = '';

        this.segments.forEach((segment, index) => {
            // Use stored value or default based on category
            const shouldVectorize = segment.should_vectorize !== undefined ? segment.should_vectorize : this.getDefaultVectorization(segment.category);
            const vectorizeIcon = shouldVectorize ? '🎨' : '🖼️';
            const vectorizeText = shouldVectorize ? 'SVG' : 'PNG';

            // Check if manual mask
            const isManual = segment.is_manual || false;
            const manualBadge = isManual ? '<span style="background: #f59e0b; color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.7em; margin-left: 4px;">Manual</span>' : '';

            const item = document.createElement('div');
            item.className = 'segment-item';
            item.innerHTML = `
                <div class="segment-info">
                    <div class="segment-name">${segment.name}${manualBadge}</div>
                    <div class="segment-category">${this.getCategoryIcon(segment.category)} ${segment.category}</div>
                    <div class="segment-vectorize" style="font-size: 0.8em; color: #666; margin-top: 2px;">
                        ${vectorizeIcon} ${vectorizeText}
                    </div>
                </div>
                <div class="segment-actions">
                    <button class="icon-btn delete" onclick="window.app.deleteSegment('${segment.id}')">
                        🗑️
                    </button>
                </div>
            `;
            list.appendChild(item);
        });

        document.getElementById('export-btn').disabled = false;
        document.getElementById('debug-export-btn').disabled = false;

        // Update ML notice based on training data setting
        this.updateMLExportNotice();
    }

    getCategoryIcon(category) {
        const icons = {
            'Profile': '🏺',
            'Application': '🎯',
            'Handle': '🪢',
            'Prospectus': '👁️',
            'Decoration': '🎨',
            'Section': '✂️',
            'Detail': '📌'
        };
        return icons[category] || '📄';
    }

    getDefaultVectorization(category) {
        // Profile, Application, and Running_Element are vectorized by default
        return category === 'Profile' || category === 'Application' || category === 'Running_Element';
    }

    async deleteSegment(segmentId) {
        console.log('=== DELETE SEGMENT DEBUG (Frontend) ===');
        console.log('Deleting segment ID:', segmentId);
        console.log('All segments in frontend:', this.segments.map(s => ({ id: s.id, name: s.name })));
        if (window.canvasManager) {
            console.log('Saved masks in canvas:', window.canvasManager.savedMasks.map(m => ({ id: m.segmentId, name: m.name })));
        }

        if (!confirm('Are you sure you want to delete this segment?')) {
            return;
        }

        try {
            const response = await fetch('/api/delete_segment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    segment_id: segmentId
                })
            });

            const data = await response.json();

            if (data.success) {
                console.log('Backend deleted successfully, total segments now:', data.total_segments);

                // Remove from local list
                const beforeLength = this.segments.length;
                this.segments = this.segments.filter(s => s.id !== segmentId);
                console.log(`Frontend segments: ${beforeLength} -> ${this.segments.length}`);

                // Remove the specific mask from canvas
                console.log('Calling removeSavedMask for:', segmentId);
                if (window.canvasManager) {
                    window.canvasManager.removeSavedMask(segmentId);

                    // Clear SVG overlay since it's no longer accurate
                    window.canvasManager.clearSVG();
                }

                // Update UI
                this.updateSegmentsList();
                this.updateStats();

                // Save to project
                await this.saveAnnotationsToProject();

                this.showNotification('Segment deleted', 'success');
            } else {
                throw new Error(data.error || 'Failed to delete segment');
            }
        } catch (error) {
            console.error('Delete segment error:', error);
            this.showNotification('Failed to delete segment: ' + error.message, 'error');
        }
    }

    updateStats() {
        // Stats panel removed
    }

    async setRotationCenter(x, y) {
        try {
            const response = await fetch('/api/set_rotation_center', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    x: x,
                    y: y
                })
            });

            const data = await response.json();

            if (data.success) {
                this.rotationCenter = { x, y };

                // Update UI
                document.getElementById('rotation-center-info').style.display = 'block';
                document.getElementById('rotation-coords').textContent = `(${Math.round(x)}, ${Math.round(y)})`;

                // Draw marker on canvas
                if (window.canvasManager) {
                    window.canvasManager.drawRotationCenter(x, y);
                }

                // Save to project
                await this.saveAnnotationsToProject();

                this.showNotification('Rotation center set', 'success');
            } else {
                throw new Error(data.error || 'Failed to set rotation center');
            }
        } catch (error) {
            console.error('Set rotation center error:', error);
            this.showNotification('Failed to set rotation center: ' + error.message, 'error');
        }
    }

    updateMLExportNotice() {
        const saveTrainingCheckbox = document.getElementById('save-training-data');
        const mlNotice = document.getElementById('ml-export-notice');

        if (saveTrainingCheckbox && mlNotice) {
            mlNotice.style.display = saveTrainingCheckbox.checked ? 'block' : 'none';
        }
    }

    async exportSegments() {
        if (this.segments.length === 0) {
            this.showNotification('No segments to export', 'warning');
            return;
        }

        const exportStatus = document.getElementById('export-status');
        const progressFill = document.getElementById('progress-fill');
        const statusText = document.getElementById('status-text');

        exportStatus.style.display = 'block';
        progressFill.style.width = '0%';
        statusText.textContent = 'Processing segments...';

        try {
            progressFill.style.width = '30%';

            // Background will be added later in SVG Editor if needed
            // Don't include background in initial export

            console.log('Calling /api/generate_svg_preview with:', {
                session_id: this.sessionId,
                epsilon: this.epsilon,
                smoothing_factor: this.smoothing,
                include_background: false
            });

            // Call the export endpoint
            const response = await fetch('/api/generate_svg_preview', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    epsilon: this.epsilon,
                    smoothing_factor: this.smoothing,
                    include_background: false
                })
            });

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Export failed');
            }

            progressFill.style.width = '80%';
            statusText.textContent = 'Loading SVG in editor...';

            // Load the unified SVG into the SVG Editor (NO DOWNLOAD HERE!)
            if (data.output_files && data.output_files.length > 0) {
                // Find the unified SVG (it's usually the first one or has "vectorized" in name)
                const unifiedSVG = data.output_files.find(f =>
                    f.type === 'svg' && (f.name.includes('vectorized') || f.description.includes('Unified'))
                );

                if (unifiedSVG && window.svgEditor) {
                    console.log('Loading SVG into editor:', unifiedSVG.url);

                    // Enable SVG Editor tab
                    document.getElementById('svg-editor-tab-btn').disabled = false;

                    // Set session ID, image name, and project ID in SVG Editor (for saving)
                    window.svgEditor.sessionId = this.sessionId;
                    window.svgEditor.currentImageName = this.currentImageFilename;
                    window.svgEditor.currentProjectId = this.currentProjectId;

                    // Load SVG in editor
                    await window.svgEditor.loadSVG(unifiedSVG.url);

                    // Store the ZIP URL for later download from SVG Editor
                    window.svgEditor.zipDownloadUrl = data.zip_url;

                    progressFill.style.width = '100%';
                    statusText.textContent = 'SVG loaded! Switching to editor...';

                    // Switch to SVG Editor tab after a short delay
                    setTimeout(() => {
                        if (window.tabManager) {
                            window.tabManager.switchTab('svg-editor-tab');
                        }
                        exportStatus.style.display = 'none';
                    }, 1000);

                    this.showNotification('SVG loaded! You can now edit it in the "SVG Editor" tab.', 'success');
                } else {
                    throw new Error('SVG file not found in export results');
                }
            } else {
                throw new Error('No output files generated');
            }

        } catch (error) {
            console.error('Export error:', error);
            statusText.textContent = 'Error: ' + error.message;
            this.showNotification('Failed to export: ' + error.message, 'error');

            setTimeout(() => {
                exportStatus.style.display = 'none';
            }, 3000);
        }
    }

    async exportMasksDebug() {
        if (this.segments.length === 0) {
            this.showNotification('No segments to export', 'warning');
            return;
        }

        const exportStatus = document.getElementById('export-status');
        const progressFill = document.getElementById('progress-fill');
        const statusText = document.getElementById('status-text');

        exportStatus.style.display = 'block';
        progressFill.style.width = '0%';
        statusText.textContent = 'Exporting masks as PNG...';

        try {
            progressFill.style.width = '30%';

            // Call the debug export endpoint
            const response = await fetch('/api/export_masks_debug', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId
                })
            });

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Export failed');
            }

            progressFill.style.width = '80%';
            statusText.textContent = `Exported ${data.total_masks} masks. Downloading...`;

            // Trigger download
            window.location.href = data.download_url;

            progressFill.style.width = '100%';
            statusText.textContent = 'Download started!';

            setTimeout(() => {
                exportStatus.style.display = 'none';
            }, 2000);

            this.showNotification(`Exported ${data.total_masks} masks as PNG`, 'success');

        } catch (error) {
            console.error('Export error:', error);
            statusText.textContent = 'Error: ' + error.message;
            this.showNotification('Failed to export masks: ' + error.message, 'error');
        }
    }

    async exportMLMasks() {
        if (this.segments.length === 0) {
            this.showNotification('No segments to export', 'warning');
            return;
        }

        // Ask user to choose format
        const format = confirm('Choose format:\n\nOK = COCO format (standard ML)\nCancel = Simple format (custom)')
            ? 'coco'
            : 'simple';

        const exportStatus = document.getElementById('export-status');
        const progressFill = document.getElementById('progress-fill');
        const statusText = document.getElementById('status-text');

        exportStatus.style.display = 'block';
        progressFill.style.width = '0%';
        statusText.textContent = `Exporting masks in ${format.toUpperCase()} format...`;

        try {
            progressFill.style.width = '30%';

            // Call the ML export endpoint
            const response = await fetch('/api/export_ml_dataset', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    format: format
                })
            });

            const data = await response.json();

            if (!data.success) {
                throw new Error(data.error || 'Export failed');
            }

            progressFill.style.width = '80%';
            statusText.textContent = `Exported ${data.total_masks} masks. Downloading...`;

            // Trigger download
            window.location.href = data.download_url;

            progressFill.style.width = '100%';
            statusText.textContent = 'Download started!';

            setTimeout(() => {
                exportStatus.style.display = 'none';
            }, 2000);

            this.showNotification(`Exported ${data.total_masks} masks in ${format.toUpperCase()} format`, 'success');

        } catch (error) {
            console.error('ML export error:', error);
            statusText.textContent = 'Error: ' + error.message;
            this.showNotification('Failed to export ML masks: ' + error.message, 'error');

            setTimeout(() => {
                exportStatus.style.display = 'none';
            }, 3000);
        }
    }

    handleKeyboardShortcut(e) {
        // Check if user is typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            return;
        }

        switch (e.key.toLowerCase()) {
            case 'p':
                this.setMode('point');
                break;
            case 'b':
                this.setMode('box');
                break;
            case 'm':
                this.setMode('polygon');
                break;
            case 'r':
                this.setMode('rotation');
                break;
            case '+':
            case '=':
                if (window.canvasManager) window.canvasManager.zoom(1.2);
                break;
            case '-':
            case '_':
                if (window.canvasManager) window.canvasManager.zoom(0.8);
                break;
            case 'z':
                if (e.ctrlKey || e.metaKey) {
                    e.preventDefault();
                    // Implement undo
                }
                break;
        }
    }

    /**
     * Load an image from project (called when clicking thumbnail)
     */
    async loadProjectImage(projectId, filename, index) {
        try {
            console.log('Loading project image:', filename);

            // Store project info for later use
            this.currentProjectId = projectId;
            this.currentImageName = filename;

            // CLEAR EVERYTHING FROM PREVIOUS IMAGE
            this.segments = [];
            this.rotationCenter = null;

            // Clear canvas masks
            if (window.canvasManager) {
                window.canvasManager.savedMasks = [];
                window.canvasManager.clearRotationCenter();
            }

            // Clear segmentation preview
            if (window.segmentationManager) {
                window.segmentationManager.currentMask = null;
                window.segmentationManager.previewContours = null;
                window.segmentationManager.points = [];
                window.segmentationManager.labels = [];
            }

            // Update UI immediately to show empty state
            this.updateSegmentsList();
            this.updateStats();
            document.getElementById('rotation-center-info').style.display = 'none';

            // Create a session for this image
            const imageUrl = `/api/projects/${projectId}/images/${encodeURIComponent(filename)}?folder=uploads`;

            // Create a fake File object to upload
            const response = await fetch(imageUrl);
            const blob = await response.blob();
            const file = new File([blob], filename, { type: blob.type });

            // Upload image to create session
            const formData = new FormData();
            formData.append('file', file);

            const uploadResponse = await fetch('/api/upload', {
                method: 'POST',
                body: formData
            });

            const uploadData = await uploadResponse.json();

            if (uploadData.success) {
                this.sessionId = uploadData.session_id;
                this.currentImage = uploadData.image_url;
                this.currentImageFilename = filename;  // Store filename for SVG export

                // Update UI
                document.getElementById('filename').textContent = filename;
                document.getElementById('current-image-number').textContent = index + 1;

                console.log('Session created:', this.sessionId);

                // Load saved annotations from project if they exist
                await this.loadAnnotationsFromProject(projectId, filename);

                this.showNotification('Image loaded successfully', 'success');
            }
        } catch (error) {
            console.error('Error loading project image:', error);
            this.showNotification('Failed to load image: ' + error.message, 'error');
        }
    }

    /**
     * Save annotations to project (with debounce)
     */
    async saveAnnotationsToProject() {
        if (!this.currentProjectId || !this.currentImageName) {
            console.log('No project context, skipping save');
            return;
        }

        // Clear previous timeout
        if (this.saveTimeout) {
            clearTimeout(this.saveTimeout);
        }

        // Debounce: save after 500ms of inactivity
        this.saveTimeout = setTimeout(async () => {
            try {
                console.log('💾 Auto-saving annotations...');
                console.log('  Segments:', this.segments.length);
                console.log('  Rotation center:', this.rotationCenter);

                const response = await fetch(
                    `/api/projects/${this.currentProjectId}/annotations/${encodeURIComponent(this.currentImageName)}`,
                    {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            segments: this.segments,
                            rotation_center: this.rotationCenter
                        })
                    }
                );

                const data = await response.json();

                if (data.success) {
                    console.log('✓ Annotations saved to project');

                    // Show subtle indicator (optional)
                    const indicator = document.createElement('div');
                    indicator.style.cssText = `
                        position: fixed;
                        bottom: 20px;
                        right: 20px;
                        background: #10b981;
                        color: white;
                        padding: 8px 16px;
                        border-radius: 4px;
                        font-size: 12px;
                        z-index: 1000;
                        opacity: 0;
                        transition: opacity 0.3s;
                    `;
                    indicator.textContent = '💾 Saved';
                    document.body.appendChild(indicator);

                    setTimeout(() => indicator.style.opacity = '1', 10);
                    setTimeout(() => {
                        indicator.style.opacity = '0';
                        setTimeout(() => indicator.remove(), 300);
                    }, 1500);
                } else {
                    console.error('Failed to save annotations:', data.error);
                }
            } catch (error) {
                console.error('Error saving annotations to project:', error);
            }
        }, 500);  // 500ms debounce
    }

    /**
     * Load annotations from project
     */
    async loadAnnotationsFromProject(projectId, imageName) {
        try {
            const response = await fetch(
                `/api/projects/${projectId}/annotations/${encodeURIComponent(imageName)}`
            );

            const data = await response.json();

            if (data.success && data.has_annotations) {
                console.log('📂 Loading saved annotations:', data);
                console.log('  Segments loaded:', data.segments.length);
                console.log('  Rotation center:', data.rotation_center);

                // Load segments
                this.segments = data.segments || [];
                this.rotationCenter = data.rotation_center;

                console.log('✓ Segments assigned to this.segments:', this.segments.length);
                this.segments.forEach((seg, idx) => {
                    console.log(`  [${idx}] ${seg.name} (${seg.category}) - has contours: ${!!seg.contours}, id: ${seg.id}`);
                });

                // Sync segments with backend session
                if (this.segments.length > 0 && this.sessionId) {
                    console.log('🔄 Syncing loaded segments with backend session...');
                    await this.syncSegmentsWithBackend();
                }

                // Redraw all masks on canvas
                if (window.canvasManager && this.segments.length > 0) {
                    // Clear previous masks
                    window.canvasManager.savedMasks = [];

                    // Add all loaded masks
                    this.segments.forEach(seg => {
                        if (seg.contours) {
                            window.canvasManager.addSavedMask(
                                seg.contours,
                                seg.category,
                                seg.name,
                                seg.id
                            );
                        }
                    });

                    window.canvasManager.redraw();
                }

                // Load rotation center
                if (this.rotationCenter) {
                    document.getElementById('rotation-center-info').style.display = 'block';
                    document.getElementById('rotation-coords').textContent =
                        `(${Math.round(this.rotationCenter.x)}, ${Math.round(this.rotationCenter.y)})`;

                    // Sync rotation center with backend session
                    if (this.sessionId) {
                        await fetch('/api/set_rotation_center', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                session_id: this.sessionId,
                                x: this.rotationCenter.x,
                                y: this.rotationCenter.y
                            })
                        });
                    }

                    if (window.canvasManager) {
                        window.canvasManager.drawRotationCenter(this.rotationCenter.x, this.rotationCenter.y);
                        window.canvasManager.redraw();
                    }
                }

                // Update UI
                this.updateUI();

                this.showNotification(`Loaded ${this.segments.length} saved segments`, 'info');
            } else {
                console.log('No saved annotations for this image');
            }
        } catch (error) {
            console.error('Error loading annotations from project:', error);
        }
    }

    /**
     * Load a saved session (segments and rotation center)
     */
    loadSession(sessionData) {
        console.log('Loading session:', sessionData);

        // Clear current segments
        this.segments = [];

        // Load segments from session
        if (sessionData.segments && Array.isArray(sessionData.segments)) {
            this.segments = sessionData.segments.map(seg => ({
                id: seg.id,
                name: seg.name,
                category: seg.category,
                mask: seg.mask,
                contours: seg.contours || null,
                should_vectorize: seg.should_vectorize !== undefined ? seg.should_vectorize : true
            }));

            console.log(`Loaded ${this.segments.length} segments from session`);

            // Redraw all masks on canvas
            if (window.canvasManager && this.segments.length > 0) {
                // Clear previous masks
                window.canvasManager.savedMasks = [];

                // Add all loaded masks
                this.segments.forEach(seg => {
                    if (seg.contours) {
                        window.canvasManager.addMask(seg.contours, this.getCategoryColor(seg.category));
                    }
                });

                window.canvasManager.redraw();
            }
        }

        // Load rotation center
        if (sessionData.rotation_center) {
            this.rotationCenter = sessionData.rotation_center;

            // Update UI
            document.getElementById('rotation-center-info').style.display = 'block';
            document.getElementById('rotation-coords').textContent =
                `(${Math.round(this.rotationCenter.x)}, ${Math.round(this.rotationCenter.y)})`;

            // Draw on canvas
            if (window.canvasManager) {
                window.canvasManager.setRotationCenter(this.rotationCenter.x, this.rotationCenter.y);
            }
        }

        // Update UI
        this.updateUI();

        this.showNotification(`Loaded ${this.segments.length} segments from previous session`, 'success');
    }

    /**
     * Get color for category
     */
    getCategoryColor(category) {
        const colors = {
            'Profile': 'rgba(59, 130, 246, 0.5)',         // Blue
            'Prospectus': 'rgba(16, 185, 129, 0.5)',      // Green
            'Decoration': 'rgba(245, 158, 11, 0.5)',      // Orange
            'Application': 'rgba(139, 92, 246, 0.5)',     // Purple
            'Handle': 'rgba(236, 72, 153, 0.5)',          // Pink
            'Running_Element': 'rgba(96, 165, 250, 0.5)', // Light Blue
            'Detail': 'rgba(34, 197, 94, 0.5)'            // Emerald
        };
        return colors[category] || 'rgba(156, 163, 175, 0.5)'; // Gray fallback
    }

    showNotification(message, type = 'info') {
        // Simple notification system (can be enhanced with a library)
        const colors = {
            success: '#10b981',
            error: '#ef4444',
            warning: '#f59e0b',
            info: '#2563eb'
        };

        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            background: ${colors[type]};
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    /**
     * Sync loaded segments with backend session
     * This is needed when loading annotations from project file
     */
    async syncSegmentsWithBackend() {
        if (!this.sessionId || this.segments.length === 0) {
            return;
        }

        try {
            // Convert segments to format expected by backend
            const segmentsData = this.segments.map(seg => ({
                id: seg.id,
                name: seg.name,
                category: seg.category,
                contours: seg.contours,
                mask: seg.mask,  // Include mask data (contains polygon vertices for manual masks)
                should_vectorize: seg.should_vectorize !== undefined ? seg.should_vectorize : true,
                is_manual: seg.is_manual || false  // Preserve manual mask flag
            }));

            // Send to backend to update session
            const response = await fetch('/api/sync_segments', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: this.sessionId,
                    segments: segmentsData
                })
            });

            const data = await response.json();

            if (data.success) {
                console.log('✓ Segments synced with backend:', data.total_segments, 'segments');
            } else {
                console.error('Failed to sync segments:', data.error);
            }
        } catch (error) {
            console.error('Error syncing segments with backend:', error);
        }
    }

    updateUI() {
        this.updateSegmentsList();
        this.updateStats();
        this.updateElementName();
    }
}



// Add CSS animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);


// Initialize the application when DOM is loaded
document.addEventListener('DOMContentLoaded', function () {
    console.log('DOM Content Loaded - Starting initialization');

    // Show splash screen with progress
    const splashScreen = document.getElementById('splash-screen');
    const splashMessage = document.getElementById('splash-message');
    const splashProgressBar = document.getElementById('splash-progress-bar');
    const splashProgressText = document.getElementById('splash-progress-text');

    let progress = 0;

    function updateSplash(message, percent) {
        splashMessage.textContent = message;
        splashProgressBar.style.width = percent + '%';
        splashProgressText.textContent = percent + '%';
        progress = percent;
    }

    try {
        updateSplash('Initializing canvas...', 20);

        // Initialize canvas manager
        console.log('Initializing canvas manager...');
        window.canvasManager = new CanvasManager('main-canvas');
        console.log('Canvas manager initialized:', window.canvasManager);

        updateSplash('Loading tab manager...', 40);

        // Initialize tab manager
        console.log('Initializing tab manager...');
        window.tabManager = new TabManager();
        console.log('Tab manager initialized:', window.tabManager);

        updateSplash('Setting up application...', 60);

        // Initialize ONE main app instance and assign it to window.app
        console.log('Initializing main app...');
        window.app = new PyPotteryTraceApp();
        console.log('Main app initialized:', window.app);

        updateSplash('Loading segmentation engine...', 80);

        // Initialize segmentation manager
        console.log('Initializing segmentation manager...');
        window.segmentationManager = new SegmentationManager();
        console.log('Segmentation manager initialized:', window.segmentationManager);

        updateSplash('Preparing SVG editor...', 90);

        // Initialize SVG editor
        console.log('Initializing SVG editor...');
        window.svgEditor = new SVGEditor('svg-canvas');
        console.log('SVG editor initialized:', window.svgEditor);

        updateSplash('Ready!', 100);

        console.log('All initialization complete!');

        // Hide splash screen after a short delay
        setTimeout(() => {
            splashScreen.classList.add('fade-out');
            setTimeout(() => {
                splashScreen.style.display = 'none';
            }, 500);
        }, 800);

    } catch (error) {
        console.error('Error during initialization:', error);
        updateSplash('Error: ' + error.message, progress);
        setTimeout(() => {
            splashScreen.classList.add('fade-out');
            setTimeout(() => {
                splashScreen.style.display = 'none';
            }, 500);
        }, 2000);
    }
});