// SVG Editor - Manager for editing exported SVG files
// Allows viewing, selecting, and deleting points from SVG paths

class SVGEditor {
    constructor(canvasId) {
        console.log('SVGEditor constructor called with canvasId:', canvasId);

        this.canvas = document.getElementById(canvasId);

        if (!this.canvas) {
            console.error('Canvas element not found:', canvasId);
            return;
        }

        console.log('Canvas element found:', this.canvas);

        this.ctx = this.canvas.getContext('2d');

        if (!this.ctx) {
            console.error('Failed to get 2D context');
            return;
        }

        console.log('Canvas context initialized');

        // SVG data
        this.svgData = null;
        this.layers = [];
        this.paths = [];  // All paths with their points
        this.images = []; // PNG/image layers
        this.layerCategories = {}; // Organized by category (Profile, Symmetry, etc.)
        this.layerVisibility = {}; // Track which layers are visible
        this.imageVisibility = {}; // Track which images are visible

        // ZIP download URL (set by app.js after export)
        this.zipDownloadUrl = null;
        this.sessionId = null;  // Session ID for backend communication
        this.currentImageName = null;  // Current image name for output filename
        this.currentProjectId = null;  // Current project ID for saving

        // View transform
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.isDragging = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;

        // Selection
        this.selectedPoints = [];
        this.hoveredPoint = null;
        this.draggedPoint = null; // Point being dragged
        this.draggedImage = null; // Image layer being dragged

        // Settings
        this.pointSize = 8;
        this.showPoints = true;
        this.showLabels = true;
        this.currentMode = 'view';  // 'view', 'select', 'delete'

        // History for undo
        this.history = [];
        this.historyIndex = -1;

        this.setupCanvas();
        this.setupEventListeners();

        console.log('SVGEditor initialization complete');
    }

    setupCanvas() {
        // Set canvas size to container
        const container = this.canvas.parentElement;
        const resizeCanvas = () => {
            // Get actual container size
            const rect = container.getBoundingClientRect();
            this.canvas.width = rect.width || container.clientWidth;
            this.canvas.height = rect.height || container.clientHeight;
            console.log('Canvas resized to:', this.canvas.width, 'x', this.canvas.height);

            // Force redraw after a short delay to ensure canvas is ready
            setTimeout(() => {
                this.redraw();
            }, 10);
        };

        // Initial resize with delay
        setTimeout(resizeCanvas, 100);

        window.addEventListener('resize', resizeCanvas);

        // Also resize when tab becomes visible
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
                    const tab = document.getElementById('svg-editor-tab');
                    if (tab && tab.classList.contains('active')) {
                        console.log('SVG Editor tab became active, resizing canvas...');
                        setTimeout(resizeCanvas, 50);
                    }
                }
            });
        });

        const svgTab = document.getElementById('svg-editor-tab');
        if (svgTab) {
            observer.observe(svgTab, { attributes: true });
        }
    }

    setupEventListeners() {
        // Mouse events for pan, zoom, and selection
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        this.canvas.addEventListener('wheel', (e) => this.handleWheel(e));

        // Mode buttons
        document.querySelectorAll('[data-svg-mode]').forEach(btn => {
            btn.addEventListener('click', () => {
                this.setMode(btn.dataset.svgMode);
            });
        });

        // Settings
        document.getElementById('svg-point-size-slider').addEventListener('input', (e) => {
            this.pointSize = parseInt(e.target.value);
            document.getElementById('svg-point-size-value').textContent = this.pointSize;
            this.redraw();
        });

        document.getElementById('svg-show-points').addEventListener('change', (e) => {
            this.showPoints = e.target.checked;
            this.redraw();
        });

        document.getElementById('svg-show-labels').addEventListener('change', (e) => {
            this.showLabels = e.target.checked;
            this.redraw();
        });

        // Toolbar
        document.getElementById('svg-zoom-in-btn').addEventListener('click', () => {
            this.zoom(1.2);
        });

        document.getElementById('svg-zoom-out-btn').addEventListener('click', () => {
            this.zoom(0.8);
        });

        document.getElementById('svg-reset-view-btn').addEventListener('click', () => {
            this.resetView();
        });

        document.getElementById('svg-undo-btn').addEventListener('click', () => {
            this.undo();
        });

        // Save button
        document.getElementById('svg-save-btn').addEventListener('click', () => {
            this.exportModifiedSVG();
        });

        // Download ZIP button
        const zipBtn = document.getElementById('svg-download-zip-btn');
        if (zipBtn) {
            zipBtn.addEventListener('click', () => {
                this.downloadCompleteZip();
            });
        }

        // Add Image button
        const addImageBtn = document.getElementById('svg-add-image-btn');

        if (addImageBtn) {
            addImageBtn.addEventListener('click', () => {
                // Load current image automatically instead of opening file picker
                if (window.app && window.app.currentImage) {
                    this.addImageFromUrl(window.app.currentImage, window.app.currentImageFilename || 'Original Image');
                } else {
                    if (window.app) {
                        window.app.showNotification('No image loaded. Please load an image first.', 'warning');
                    } else {
                        alert('No image loaded. Please load an image first.');
                    }
                }
            });
        }
    }

    setMode(mode) {
        this.currentMode = mode;

        // Update UI
        document.querySelectorAll('[data-svg-mode]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.svgMode === mode);
        });

        // Update cursor
        const cursors = {
            'view': 'grab',
            'select': 'crosshair',
            'delete': 'not-allowed'
        };
        this.canvas.style.cursor = cursors[mode] || 'default';

        this.redraw();
    }

    async loadSVG(svgUrl) {
        try {
            console.log('Loading SVG from:', svgUrl);

            const response = await fetch(svgUrl);
            const svgText = await response.text();

            console.log('SVG text loaded, length:', svgText.length);

            // Parse SVG
            const parser = new DOMParser();
            const svgDoc = parser.parseFromString(svgText, 'image/svg+xml');
            const svgElement = svgDoc.querySelector('svg');

            if (!svgElement) {
                throw new Error('Invalid SVG file');
            }

            console.log('SVG element found:', svgElement);

            // Extract viewBox or dimensions
            const viewBox = svgElement.getAttribute('viewBox');
            let width, height;

            if (viewBox) {
                const [, , w, h] = viewBox.split(' ').map(Number);
                width = w;
                height = h;
            } else {
                width = parseFloat(svgElement.getAttribute('width')) || 1000;
                height = parseFloat(svgElement.getAttribute('height')) || 1000;
            }

            console.log('SVG dimensions:', width, 'x', height);

            this.svgData = {
                width,
                height,
                element: svgElement,
                text: svgText
            };

            // Extract paths and their points
            this.extractPaths(svgElement);

            console.log('Paths extracted:', this.paths.length);

            // Update UI
            this.updateLayersList();
            this.updateStats();
            this.resetView();

            // Hide message
            document.getElementById('svg-canvas-message').style.display = 'none';

            // Enable save button
            document.getElementById('svg-save-btn').disabled = false;

            // Enable ZIP download button if URL is available
            if (this.zipDownloadUrl) {
                document.getElementById('svg-download-zip-btn').disabled = false;
            }

            // Save initial state
            this.saveState();

            console.log('SVG loaded successfully:', {
                width,
                height,
                totalPaths: this.paths.length,
                totalPoints: this.getTotalPoints()
            });

        } catch (error) {
            console.error('Failed to load SVG:', error);
            alert('Errore nel caricamento dell\'SVG: ' + error.message);
        }
    }

    extractPaths(svgElement) {
        console.log('extractPaths() called');

        this.paths = [];
        this.layers = [];
        this.images = [];
        this.layerCategories = {};
        this.layerVisibility = {};
        this.imageVisibility = {};

        // Extract all layer groups (g elements with id starting with "layer_")
        const layerGroups = svgElement.querySelectorAll('g[id^="layer_"]');

        console.log('Found', layerGroups.length, 'layer groups');

        // Categorize layers
        layerGroups.forEach((layerG, layerIndex) => {
            const layerId = layerG.getAttribute('id');

            // Extract category from layer name (e.g., "layer_Profile" -> "Profile")
            const categoryMatch = layerId.match(/^layer_(.+?)(?:_|$)/);
            const category = categoryMatch ? categoryMatch[1].replace(/_/g, ' ') : 'Other';

            if (!this.layerCategories[category]) {
                this.layerCategories[category] = [];
            }

            // Initialize visibility (all visible by default)
            this.layerVisibility[layerId] = true;

            // Extract all paths in this layer
            const pathElements = layerG.querySelectorAll('path');

            pathElements.forEach((pathEl, pathIndex) => {
                const d = pathEl.getAttribute('d');
                if (!d) return;

                // Parse path data to extract points
                const points = this.parsePathData(d);
                if (points.length === 0) return;

                // Get style
                const stroke = pathEl.getAttribute('stroke') || '#000000';
                const strokeWidth = parseFloat(pathEl.getAttribute('stroke-width')) || 1;
                const fill = pathEl.getAttribute('fill') || 'none';

                const pathData = {
                    id: `path-${this.paths.length}`,
                    layerId,
                    layerName: layerId.replace('layer_', '').replace(/_/g, ' '),
                    category,
                    element: pathEl,
                    originalD: d,
                    currentD: d,
                    points,
                    style: { stroke, strokeWidth, fill },
                    visible: true
                };

                this.paths.push(pathData);
                this.layerCategories[category].push(pathData);
            });

            this.layers.push({
                id: layerId,
                name: layerId.replace('layer_', '').replace(/_/g, ' '),
                category,
                visible: true
            });
        });

        // Extract standalone paths (not in a layer group)
        const standalonePaths = svgElement.querySelectorAll('svg > path');
        if (standalonePaths.length > 0) {
            const category = 'Ungrouped';
            if (!this.layerCategories[category]) {
                this.layerCategories[category] = [];
            }

            standalonePaths.forEach((pathEl, index) => {
                const d = pathEl.getAttribute('d');
                if (!d) return;

                const points = this.parsePathData(d);
                if (points.length === 0) return;

                const stroke = pathEl.getAttribute('stroke') || '#000000';
                const strokeWidth = parseFloat(pathEl.getAttribute('stroke-width')) || 1;
                const fill = pathEl.getAttribute('fill') || 'none';

                const layerId = `standalone-${index}`;
                this.layerVisibility[layerId] = true;

                const pathData = {
                    id: `path-${this.paths.length}`,
                    layerId,
                    layerName: `Standalone ${index + 1}`,
                    category,
                    element: pathEl,
                    originalD: d,
                    currentD: d,
                    points,
                    style: { stroke, strokeWidth, fill },
                    visible: true
                };

                this.paths.push(pathData);
                this.layerCategories[category].push(pathData);
            });
        }

        // Extract images (PNG layers)
        const imageElements = svgElement.querySelectorAll('image');
        console.log('Found', imageElements.length, 'image elements');

        imageElements.forEach((imgEl, index) => {
            const href = imgEl.getAttribute('href') || imgEl.getAttribute('xlink:href');
            if (!href) return;

            const x = parseFloat(imgEl.getAttribute('x')) || 0;
            const y = parseFloat(imgEl.getAttribute('y')) || 0;
            const width = parseFloat(imgEl.getAttribute('width')) || 100;
            const height = parseFloat(imgEl.getAttribute('height')) || 100;
            const opacity = parseFloat(imgEl.getAttribute('opacity')) || 1;

            const imgId = imgEl.getAttribute('id') || `image-${index}`;
            this.imageVisibility[imgId] = true;

            // Load image
            const img = new Image();
            img.src = href;

            const imageData = {
                id: imgId,
                name: imgId.replace(/_/g, ' ') || `Image ${index + 1}`,
                element: imgEl,
                img,
                x,
                y,
                width,
                height,
                opacity,
                visible: true,
                loaded: false
            };

            img.onload = () => {
                imageData.loaded = true;
                this.redraw();
            };

            this.images.push(imageData);
        });

        console.log('Extracted:', {
            paths: this.paths.length,
            layers: this.layers.length,
            images: this.images.length,
            categories: Object.keys(this.layerCategories)
        });
    }

    parsePathData(d) {
        // Parse SVG path data to extract points
        // Supports M, L, H, V, C, S, Q, T, Z commands
        const points = [];

        // Regex to match path commands and their coordinates
        const commandRegex = /([MLHVCSQTAZmlhvcsqtaz])\s*([^MLHVCSQTAZmlhvcsqtaz]*)/gi;
        let match;

        let currentX = 0;
        let currentY = 0;
        let startX = 0;
        let startY = 0;
        let lastControlX = 0;
        let lastControlY = 0;
        let lastCmd = '';

        while ((match = commandRegex.exec(d)) !== null) {
            const cmd = match[1];
            const isRelative = cmd === cmd.toLowerCase();
            const cmdUpper = cmd.toUpperCase();

            const coords = match[2].trim()
                .split(/[\s,]+/)
                .filter(c => c)
                .map(Number);

            switch (cmdUpper) {
                case 'M': // Move to
                    if (coords.length >= 2) {
                        currentX = isRelative ? currentX + coords[0] : coords[0];
                        currentY = isRelative ? currentY + coords[1] : coords[1];
                        startX = currentX;
                        startY = currentY;
                        points.push({ x: currentX, y: currentY, cmd: 'M', index: points.length });

                        // Additional coordinate pairs after M are treated as L
                        for (let i = 2; i < coords.length; i += 2) {
                            if (i + 1 < coords.length) {
                                currentX = isRelative ? currentX + coords[i] : coords[i];
                                currentY = isRelative ? currentY + coords[i + 1] : coords[i + 1];
                                points.push({ x: currentX, y: currentY, cmd: 'L', index: points.length });
                            }
                        }
                    }
                    break;

                case 'L': // Line to
                    for (let i = 0; i < coords.length; i += 2) {
                        if (i + 1 < coords.length) {
                            currentX = isRelative ? currentX + coords[i] : coords[i];
                            currentY = isRelative ? currentY + coords[i + 1] : coords[i + 1];
                            points.push({ x: currentX, y: currentY, cmd: 'L', index: points.length });
                        }
                    }
                    break;

                case 'H': // Horizontal line
                    coords.forEach(x => {
                        currentX = isRelative ? currentX + x : x;
                        points.push({ x: currentX, y: currentY, cmd: 'H', index: points.length });
                    });
                    break;

                case 'V': // Vertical line
                    coords.forEach(y => {
                        currentY = isRelative ? currentY + y : y;
                        points.push({ x: currentX, y: currentY, cmd: 'V', index: points.length });
                    });
                    break;

                case 'C': // Cubic Bezier
                    for (let i = 0; i < coords.length; i += 6) {
                        if (i + 5 < coords.length) {
                            const cp1x = isRelative ? currentX + coords[i] : coords[i];
                            const cp1y = isRelative ? currentY + coords[i + 1] : coords[i + 1];
                            const cp2x = isRelative ? currentX + coords[i + 2] : coords[i + 2];
                            const cp2y = isRelative ? currentY + coords[i + 3] : coords[i + 3];
                            const x = isRelative ? currentX + coords[i + 4] : coords[i + 4];
                            const y = isRelative ? currentY + coords[i + 5] : coords[i + 5];

                            points.push({ x: cp1x, y: cp1y, cmd: 'C1', index: points.length });
                            points.push({ x: cp2x, y: cp2y, cmd: 'C2', index: points.length });
                            points.push({ x: x, y: y, cmd: 'C', index: points.length });

                            lastControlX = cp2x;
                            lastControlY = cp2y;
                            currentX = x;
                            currentY = y;
                        }
                    }
                    break;

                case 'S': // Smooth cubic Bezier (shorthand)
                    for (let i = 0; i < coords.length; i += 4) {
                        if (i + 3 < coords.length) {
                            // First control point is reflection of last control point
                            let cp1x, cp1y;
                            if (lastCmd === 'C' || lastCmd === 'S') {
                                cp1x = 2 * currentX - lastControlX;
                                cp1y = 2 * currentY - lastControlY;
                            } else {
                                cp1x = currentX;
                                cp1y = currentY;
                            }

                            const cp2x = isRelative ? currentX + coords[i] : coords[i];
                            const cp2y = isRelative ? currentY + coords[i + 1] : coords[i + 1];
                            const x = isRelative ? currentX + coords[i + 2] : coords[i + 2];
                            const y = isRelative ? currentY + coords[i + 3] : coords[i + 3];

                            points.push({ x: cp1x, y: cp1y, cmd: 'C1', index: points.length });
                            points.push({ x: cp2x, y: cp2y, cmd: 'C2', index: points.length });
                            points.push({ x: x, y: y, cmd: 'C', index: points.length });

                            lastControlX = cp2x;
                            lastControlY = cp2y;
                            currentX = x;
                            currentY = y;
                        }
                    }
                    break;

                case 'Q': // Quadratic Bezier
                    for (let i = 0; i < coords.length; i += 4) {
                        if (i + 3 < coords.length) {
                            const cpx = isRelative ? currentX + coords[i] : coords[i];
                            const cpy = isRelative ? currentY + coords[i + 1] : coords[i + 1];
                            const x = isRelative ? currentX + coords[i + 2] : coords[i + 2];
                            const y = isRelative ? currentY + coords[i + 3] : coords[i + 3];

                            points.push({ x: cpx, y: cpy, cmd: 'Q1', index: points.length });
                            points.push({ x: x, y: y, cmd: 'Q', index: points.length });

                            lastControlX = cpx;
                            lastControlY = cpy;
                            currentX = x;
                            currentY = y;
                        }
                    }
                    break;

                case 'T': // Smooth quadratic Bezier
                    for (let i = 0; i < coords.length; i += 2) {
                        if (i + 1 < coords.length) {
                            // Control point is reflection of last control point
                            let cpx, cpy;
                            if (lastCmd === 'Q' || lastCmd === 'T') {
                                cpx = 2 * currentX - lastControlX;
                                cpy = 2 * currentY - lastControlY;
                            } else {
                                cpx = currentX;
                                cpy = currentY;
                            }

                            const x = isRelative ? currentX + coords[i] : coords[i];
                            const y = isRelative ? currentY + coords[i + 1] : coords[i + 1];

                            points.push({ x: cpx, y: cpy, cmd: 'Q1', index: points.length });
                            points.push({ x: x, y: y, cmd: 'Q', index: points.length });

                            lastControlX = cpx;
                            lastControlY = cpy;
                            currentX = x;
                            currentY = y;
                        }
                    }
                    break;

                case 'Z': // Close path
                    if (currentX !== startX || currentY !== startY) {
                        points.push({ x: startX, y: startY, cmd: 'Z', index: points.length });
                    }
                    currentX = startX;
                    currentY = startY;
                    break;
            }

            lastCmd = cmdUpper;
        }

        return points;
    }

    handleMouseDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Middle mouse button (pan) - Works in ANY mode
        if (e.button === 1) {
            e.preventDefault();
            this.isDragging = true;
            this.lastMouseX = mouseX;
            this.lastMouseY = mouseY;
            this.canvas.style.cursor = 'grabbing';
            return;
        }

        if (this.currentMode === 'view') {
            // Check if clicking on an image first
            const clickedImage = this.findImageAt(mouseX, mouseY);

            if (clickedImage) {
                // Check if image is locked
                if (clickedImage.isLocked) {
                    // Locked image - pan the view instead
                    this.isDragging = true;
                    this.lastMouseX = mouseX;
                    this.lastMouseY = mouseY;
                    this.canvas.style.cursor = 'grabbing';
                } else if (!e.shiftKey) {
                    // Click directly on image to drag it (no Shift needed)
                    // Use Shift to pan the view instead
                    // Direct click on image = drag image
                    this.draggedImage = clickedImage;
                    this.lastMouseX = mouseX;
                    this.lastMouseY = mouseY;
                    this.canvas.style.cursor = 'move';
                    this.saveState(); // Save state before dragging
                } else {
                    // Shift + click on image = pan view (override image drag)
                    this.isDragging = true;
                    this.lastMouseX = mouseX;
                    this.lastMouseY = mouseY;
                    this.canvas.style.cursor = 'grabbing';
                }
            } else {
                // Click on empty area = pan the view
                this.isDragging = true;
                this.lastMouseX = mouseX;
                this.lastMouseY = mouseY;
                this.canvas.style.cursor = 'grabbing';
            }
        } else if (this.currentMode === 'select') {
            // Check if clicking on a point
            const clickedPoint = this.findPointAt(mouseX, mouseY);

            if (clickedPoint) {
                // If Ctrl+click, start dragging the point
                if (e.ctrlKey || e.metaKey) {
                    this.draggedPoint = clickedPoint;
                    this.lastMouseX = mouseX;
                    this.lastMouseY = mouseY;
                    this.canvas.style.cursor = 'move';
                    this.saveState(); // Save state before dragging
                } else {
                    // Toggle selection
                    const isSelected = this.selectedPoints.some(
                        p => p.pathId === clickedPoint.pathId && p.pointIndex === clickedPoint.pointIndex
                    );

                    if (isSelected) {
                        // Deselect
                        this.selectedPoints = this.selectedPoints.filter(
                            p => !(p.pathId === clickedPoint.pathId && p.pointIndex === clickedPoint.pointIndex)
                        );
                    } else {
                        // Select (allow multi-selection with Shift)
                        if (!e.shiftKey) {
                            this.selectedPoints = [];
                        }
                        this.selectedPoints.push(clickedPoint);
                    }

                    this.updateSelectionInfo();
                    this.redraw();
                }
            }
        } else if (this.currentMode === 'add') {
            // Add point mode - click on path to insert a new point
            const clickedPoint = this.findPointAt(mouseX, mouseY);

            if (!clickedPoint) {
                // No existing point clicked, try to find nearest path segment
                this.addPointOnPath(mouseX, mouseY);
            }
        } else if (this.currentMode === 'delete') {
            // Delete point
            const clickedPoint = this.findPointAt(mouseX, mouseY);

            if (clickedPoint) {
                this.deletePoint(clickedPoint);
            }
        }
    }

    handleMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        if (this.draggedPoint) {
            // Dragging a point
            const dx = (mouseX - this.lastMouseX) / this.scale;
            const dy = (mouseY - this.lastMouseY) / this.scale;

            this.draggedPoint.point.x += dx;
            this.draggedPoint.point.y += dy;

            // Rebuild path data
            this.rebuildPathData(this.draggedPoint.path);

            this.lastMouseX = mouseX;
            this.lastMouseY = mouseY;

            this.redraw();
        } else if (this.draggedImage) {
            // Dragging an image
            const dx = (mouseX - this.lastMouseX) / this.scale;
            const dy = (mouseY - this.lastMouseY) / this.scale;

            this.draggedImage.x += dx;
            this.draggedImage.y += dy;

            this.lastMouseX = mouseX;
            this.lastMouseY = mouseY;

            this.redraw();
            this.redraw();
        } else if (this.isDragging) {
            // Panning view (Works in View mode OR via middle click in any mode)
            const dx = mouseX - this.lastMouseX;
            const dy = mouseY - this.lastMouseY;

            this.offsetX += dx;
            this.offsetY += dy;

            this.lastMouseX = mouseX;
            this.lastMouseY = mouseY;

            this.redraw();
        } else if (this.currentMode === 'select' || this.currentMode === 'delete' || this.currentMode === 'add') {
            // Highlight hovered point
            const hoveredPoint = this.findPointAt(mouseX, mouseY);

            if (hoveredPoint !== this.hoveredPoint) {
                this.hoveredPoint = hoveredPoint;

                // Change cursor if Ctrl is pressed and hovering a point
                if (this.currentMode === 'select' && hoveredPoint && (e.ctrlKey || e.metaKey)) {
                    this.canvas.style.cursor = 'move';
                } else if (this.currentMode === 'select') {
                    this.canvas.style.cursor = 'pointer';
                } else if (this.currentMode === 'add') {
                    this.canvas.style.cursor = 'crosshair';
                } else if (this.currentMode === 'delete') {
                    this.canvas.style.cursor = hoveredPoint ? 'crosshair' : 'default';
                }

                this.redraw();
            }
        } else if (this.currentMode === 'view') {
            // Check if hovering over an image
            const hoveredImage = this.findImageAt(mouseX, mouseY);
            if (hoveredImage && e.shiftKey) {
                this.canvas.style.cursor = 'move';
            } else {
                this.canvas.style.cursor = 'grab';
            }
        }
    }

    handleMouseUp(e) {
        if (this.draggedPoint) {
            // Finished dragging a point
            this.draggedPoint = null;
            this.canvas.style.cursor = 'pointer';
            this.updateStats();
        } else if (this.draggedImage) {
            // Finished dragging an image
            this.draggedImage = null;
            this.canvas.style.cursor = 'grab';
        } else if (this.isDragging) {
            this.isDragging = false;
            this.canvas.style.cursor = 'grab';
        }
    }

    handleWheel(e) {
        e.preventDefault();

        const rect = this.canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        // Zoom towards mouse cursor
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        const oldScale = this.scale;
        const newScale = this.scale * delta;

        // Constrain zoom
        if (newScale < 0.1 || newScale > 10) return;

        this.scale = newScale;

        // Adjust offset to zoom towards cursor
        this.offsetX = mouseX - (mouseX - this.offsetX) * (this.scale / oldScale);
        this.offsetY = mouseY - (mouseY - this.offsetY) * (this.scale / oldScale);

        this.redraw();
    }

    zoom(factor) {
        const centerX = this.canvas.width / 2;
        const centerY = this.canvas.height / 2;

        const oldScale = this.scale;
        this.scale *= factor;

        // Constrain
        this.scale = Math.max(0.1, Math.min(10, this.scale));

        // Adjust offset to zoom towards center
        this.offsetX = centerX - (centerX - this.offsetX) * (this.scale / oldScale);
        this.offsetY = centerY - (centerY - this.offsetY) * (this.scale / oldScale);

        this.redraw();
    }

    resetView() {
        if (!this.svgData) {
            console.log('resetView() called but no SVG data');
            return;
        }

        console.log('Resetting view for SVG:', this.svgData.width, 'x', this.svgData.height);
        console.log('Canvas size:', this.canvas.width, 'x', this.canvas.height);

        // Fit SVG to canvas
        const padding = 50;
        const scaleX = (this.canvas.width - padding * 2) / this.svgData.width;
        const scaleY = (this.canvas.height - padding * 2) / this.svgData.height;

        this.scale = Math.min(scaleX, scaleY);
        this.offsetX = (this.canvas.width - this.svgData.width * this.scale) / 2;
        this.offsetY = (this.canvas.height - this.svgData.height * this.scale) / 2;

        console.log('View reset - scale:', this.scale, 'offsetX:', this.offsetX, 'offsetY:', this.offsetY);

        this.redraw();
    }

    findPointAt(mouseX, mouseY) {
        // Find point near mouse position
        const threshold = this.pointSize + 2;

        for (const path of this.paths) {
            const layerVisible = this.layerVisibility[path.layerId] !== false;
            if (!path.visible || !layerVisible) continue;

            for (let i = 0; i < path.points.length; i++) {
                const point = path.points[i];
                const screenX = point.x * this.scale + this.offsetX;
                const screenY = point.y * this.scale + this.offsetY;

                const dist = Math.sqrt((mouseX - screenX) ** 2 + (mouseY - screenY) ** 2);

                if (dist <= threshold) {
                    return {
                        pathId: path.id,
                        pointIndex: i,
                        point: point,
                        path: path
                    };
                }
            }
        }

        return null;
    }

    findImageAt(mouseX, mouseY) {
        // Find image at mouse position (check in reverse order - top to bottom)
        for (let i = this.images.length - 1; i >= 0; i--) {
            const img = this.images[i];
            if (!img.visible || !img.loaded) continue;

            const x = img.x * this.scale + this.offsetX;
            const y = img.y * this.scale + this.offsetY;
            const width = img.width * this.scale;
            const height = img.height * this.scale;

            if (mouseX >= x && mouseX <= x + width &&
                mouseY >= y && mouseY <= y + height) {
                return img;
            }
        }

        return null;
    }

    deletePoint(pointInfo) {
        const path = this.paths.find(p => p.id === pointInfo.pathId);
        if (!path) return;

        // Save state before modification
        this.saveState();

        const pointToDelete = path.points[pointInfo.pointIndex];

        // Special case: Deleting M (MoveTo) - the starting point
        if (pointToDelete.cmd === 'M') {
            // Find the next anchor point and promote it to M
            let nextAnchorIndex = -1;
            for (let j = pointInfo.pointIndex + 1; j < path.points.length; j++) {
                const p = path.points[j];
                if (p.cmd === 'L' || p.cmd === 'C' || p.cmd === 'Q' || p.cmd === 'M') {
                    nextAnchorIndex = j;
                    break;
                }
            }

            if (nextAnchorIndex >= 0) {
                // Promote the next anchor to M
                path.points[nextAnchorIndex].cmd = 'M';

                // Remove the old M and any control points between M and the new M
                const pointsToRemove = [];
                for (let j = pointInfo.pointIndex; j < nextAnchorIndex; j++) {
                    pointsToRemove.push(j);
                }

                // Remove in reverse order
                for (let j = pointsToRemove.length - 1; j >= 0; j--) {
                    path.points.splice(pointsToRemove[j], 1);
                }
            } else {
                // No next anchor - this is the only point, just remove it
                path.points.splice(pointInfo.pointIndex, 1);
            }
        }
        // Check if we're deleting an anchor point that has associated control points
        else if (pointToDelete.cmd === 'C' || pointToDelete.cmd === 'Q') {
            // This is an anchor point for a Bezier curve
            // We need to remove its control points too
            const pointsToRemove = [pointInfo.pointIndex];

            if (pointToDelete.cmd === 'C') {
                // Look backwards for C1 and C2
                for (let j = pointInfo.pointIndex - 1; j >= 0; j--) {
                    if (path.points[j].cmd === 'C2') {
                        pointsToRemove.push(j);
                    } else if (path.points[j].cmd === 'C1') {
                        pointsToRemove.push(j);
                        break;  // Found both control points
                    } else if (path.points[j].cmd === 'M' || path.points[j].cmd === 'L' || path.points[j].cmd === 'C') {
                        break;  // Reached previous anchor
                    }
                }
            } else if (pointToDelete.cmd === 'Q') {
                // Look backwards for Q1
                for (let j = pointInfo.pointIndex - 1; j >= 0; j--) {
                    if (path.points[j].cmd === 'Q1') {
                        pointsToRemove.push(j);
                        break;
                    } else if (path.points[j].cmd === 'M' || path.points[j].cmd === 'L' || path.points[j].cmd === 'Q') {
                        break;  // Reached previous anchor
                    }
                }
            }

            // Sort in descending order to remove from end first
            pointsToRemove.sort((a, b) => b - a);

            // Remove all points
            for (const idx of pointsToRemove) {
                path.points.splice(idx, 1);
            }
        } else if (pointToDelete.cmd === 'C1' || pointToDelete.cmd === 'C2' || pointToDelete.cmd === 'Q1') {
            // This is a control point - find and remove the associated anchor and other control points
            let anchorIndex = -1;
            const pointsToRemove = [pointInfo.pointIndex];

            if (pointToDelete.cmd === 'C1' || pointToDelete.cmd === 'C2') {
                // Find the C anchor point after this control point
                for (let j = pointInfo.pointIndex + 1; j < path.points.length; j++) {
                    if (path.points[j].cmd === 'C') {
                        anchorIndex = j;
                        break;
                    } else if (path.points[j].cmd === 'C1' || path.points[j].cmd === 'C2') {
                        pointsToRemove.push(j);  // Other control point
                    }
                }

                // Also remove the anchor
                if (anchorIndex >= 0) {
                    pointsToRemove.push(anchorIndex);
                }
            } else if (pointToDelete.cmd === 'Q1') {
                // Find the Q anchor point after this control point
                for (let j = pointInfo.pointIndex + 1; j < path.points.length; j++) {
                    if (path.points[j].cmd === 'Q') {
                        anchorIndex = j;
                        pointsToRemove.push(j);
                        break;
                    }
                }
            }

            // Sort in descending order
            pointsToRemove.sort((a, b) => b - a);

            // Remove all points
            for (const idx of pointsToRemove) {
                path.points.splice(idx, 1);
            }
        } else {
            // Regular point (L) - just remove it
            path.points.splice(pointInfo.pointIndex, 1);
        }

        // Rebuild path data
        this.rebuildPathData(path);

        // Remove from selection if selected
        this.selectedPoints = this.selectedPoints.filter(
            p => !(p.pathId === pointInfo.pathId && p.pointIndex === pointInfo.pointIndex)
        );

        this.updateStats();
        this.updateSelectionInfo();
        this.redraw();

        // Enable undo button
        document.getElementById('svg-undo-btn').disabled = false;
    }

    rebuildPathData(path) {
        // Rebuild the 'd' attribute from points array
        if (path.points.length === 0) {
            path.currentD = '';
            return;
        }

        let d = '';
        let i = 0;

        while (i < path.points.length) {
            const point = path.points[i];

            if (point.cmd === 'M') {
                d += `M ${point.x} ${point.y} `;
                i++;
            } else if (point.cmd === 'L') {
                d += `L ${point.x} ${point.y} `;
                i++;
            } else if (point.cmd === 'H') {
                d += `H ${point.x} `;
                i++;
            } else if (point.cmd === 'V') {
                d += `V ${point.y} `;
                i++;
            } else if (point.cmd === 'C') {
                // Cubic Bezier - look for control points BEFORE this point
                // Find the two preceding C1 and C2 control points
                let cp1 = null, cp2 = null;
                let j = i - 1;

                // Look backwards for C2
                while (j >= 0 && !cp2) {
                    if (path.points[j].cmd === 'C2') {
                        cp2 = path.points[j];
                        break;
                    }
                    j--;
                }

                // Look backwards for C1 (before C2)
                j = j - 1;
                while (j >= 0 && !cp1) {
                    if (path.points[j].cmd === 'C1') {
                        cp1 = path.points[j];
                        break;
                    }
                    j--;
                }

                if (cp1 && cp2) {
                    d += `C ${cp1.x} ${cp1.y} ${cp2.x} ${cp2.y} ${point.x} ${point.y} `;
                } else {
                    // Fallback: convert to line if control points are missing
                    console.warn('Missing control points for C command, converting to L');
                    d += `L ${point.x} ${point.y} `;
                }
                i++;
            } else if (point.cmd === 'Q') {
                // Quadratic Bezier - look for control point BEFORE this point
                let cp = null;
                let j = i - 1;

                while (j >= 0 && !cp) {
                    if (path.points[j].cmd === 'Q1') {
                        cp = path.points[j];
                        break;
                    }
                    j--;
                }

                if (cp) {
                    d += `Q ${cp.x} ${cp.y} ${point.x} ${point.y} `;
                } else {
                    // Fallback: convert to line if control point is missing
                    console.warn('Missing control point for Q command, converting to L');
                    d += `L ${point.x} ${point.y} `;
                }
                i++;
            } else if (point.cmd === 'C1' || point.cmd === 'C2' || point.cmd === 'Q1') {
                // Control points - skip, they're included when we process C/Q
                i++;
            } else if (point.cmd === 'Z' || point.cmd === 'z') {
                d += 'Z ';
                i++;
            } else {
                // Fallback - treat as line
                d += `L ${point.x} ${point.y} `;
                i++;
            }
        }

        path.currentD = d.trim();
    }

    addPointOnPath(mouseX, mouseY) {
        // Find the nearest path segment to the click position
        // and insert a new point at that location

        const clickX = (mouseX - this.offsetX) / this.scale;
        const clickY = (mouseY - this.offsetY) / this.scale;

        let nearestPath = null;
        let nearestSegmentIndex = -1;
        let nearestDistance = Infinity;
        let nearestT = 0;  // Parameter along the segment (0 to 1)
        let nearestPrevAnchor = null;  // Previous anchor point

        // Search through all visible paths
        for (const path of this.paths) {
            const layerVisible = this.layerVisibility[path.layerId] !== false;
            if (!path.visible || !layerVisible) continue;

            // Check each segment between anchor points
            let lastAnchor = null;
            for (let i = 0; i < path.points.length; i++) {
                const point = path.points[i];

                // Only consider anchor points (M, L, C, Q, not control points)
                if (point.cmd === 'C1' || point.cmd === 'C2' || point.cmd === 'Q1') {
                    continue;
                }

                if (lastAnchor !== null) {
                    // We have a segment from lastAnchor to current point
                    let distance, t;

                    if (point.cmd === 'C') {
                        // Bezier curve - find control points
                        let cp1 = null, cp2 = null;
                        for (let j = i - 1; j > lastAnchor.index; j--) {
                            if (path.points[j].cmd === 'C2' && !cp2) cp2 = path.points[j];
                            else if (path.points[j].cmd === 'C1' && !cp1) cp1 = path.points[j];
                        }

                        if (cp1 && cp2) {
                            // Sample the cubic Bezier curve
                            ({ distance, t } = this.pointToCubicBezierDistance(
                                clickX, clickY,
                                lastAnchor.point.x, lastAnchor.point.y,
                                cp1.x, cp1.y,
                                cp2.x, cp2.y,
                                point.x, point.y
                            ));
                        } else {
                            // Fallback to line
                            ({ distance, t } = this.pointToSegmentDistance(
                                clickX, clickY, lastAnchor.point.x, lastAnchor.point.y, point.x, point.y
                            ));
                        }
                    } else {
                        // Line segment
                        ({ distance, t } = this.pointToSegmentDistance(
                            clickX, clickY, lastAnchor.point.x, lastAnchor.point.y, point.x, point.y
                        ));
                    }

                    if (distance < nearestDistance) {
                        nearestDistance = distance;
                        nearestPath = path;
                        nearestSegmentIndex = i;
                        nearestT = t;
                        nearestPrevAnchor = lastAnchor;
                    }
                }

                lastAnchor = { point: point, index: i };
            }
        }

        // If we found a nearby segment (within 20 pixels), insert a point
        const threshold = 20 / this.scale;
        if (nearestPath && nearestDistance < threshold && nearestPrevAnchor) {
            this.saveState();

            const p1 = nearestPrevAnchor.point;
            const p2 = nearestPath.points[nearestSegmentIndex];

            // Interpolate position along the segment
            const newX = p1.x + (p2.x - p1.x) * nearestT;
            const newY = p1.y + (p2.y - p1.y) * nearestT;

            // Create new point (as a line point for simplicity)
            const newPoint = {
                x: newX,
                y: newY,
                cmd: 'L',
                index: nearestSegmentIndex
            };

            // Insert the new point
            nearestPath.points.splice(nearestSegmentIndex, 0, newPoint);

            // Update indices
            for (let i = nearestSegmentIndex; i < nearestPath.points.length; i++) {
                nearestPath.points[i].index = i;
            }

            // Rebuild path data
            this.rebuildPathData(nearestPath);

            // Select the new point
            this.selectedPoints = [{
                pathId: nearestPath.id,
                pointIndex: nearestSegmentIndex
            }];

            this.updateStats();
            this.updateSelectionInfo();
            this.redraw();

            // Enable undo
            document.getElementById('svg-undo-btn').disabled = false;

            if (window.app) {
                window.app.showNotification('New point added!', 'success');
            }
        }
    }

    pointToSegmentDistance(px, py, x1, y1, x2, y2) {
        // Calculate the shortest distance from point (px, py) to line segment (x1, y1) -> (x2, y2)
        // Returns { distance, t } where t is the parameter along the segment (0 to 1)

        const dx = x2 - x1;
        const dy = y2 - y1;
        const lengthSquared = dx * dx + dy * dy;

        if (lengthSquared === 0) {
            // Degenerate segment (point)
            const dist = Math.sqrt((px - x1) ** 2 + (py - y1) ** 2);
            return { distance: dist, t: 0 };
        }

        // Project point onto line
        let t = ((px - x1) * dx + (py - y1) * dy) / lengthSquared;
        t = Math.max(0, Math.min(1, t));  // Clamp to [0, 1]

        // Find closest point on segment
        const closestX = x1 + t * dx;
        const closestY = y1 + t * dy;

        // Calculate distance
        const distance = Math.sqrt((px - closestX) ** 2 + (py - closestY) ** 2);

        return { distance, t };
    }

    pointToCubicBezierDistance(px, py, x0, y0, x1, y1, x2, y2, x3, y3) {
        // Calculate the shortest distance from point (px, py) to cubic Bezier curve
        // Bezier: B(t) = (1-t)³P0 + 3(1-t)²t*P1 + 3(1-t)t²P2 + t³P3
        // We sample the curve at multiple points to find the closest one

        let minDistance = Infinity;
        let minT = 0;
        const samples = 50;  // Number of samples along the curve

        for (let i = 0; i <= samples; i++) {
            const t = i / samples;
            const oneMinusT = 1 - t;

            // Cubic Bezier formula
            const bx = oneMinusT * oneMinusT * oneMinusT * x0 +
                3 * oneMinusT * oneMinusT * t * x1 +
                3 * oneMinusT * t * t * x2 +
                t * t * t * x3;

            const by = oneMinusT * oneMinusT * oneMinusT * y0 +
                3 * oneMinusT * oneMinusT * t * y1 +
                3 * oneMinusT * t * t * y2 +
                t * t * t * y3;

            const distance = Math.sqrt((px - bx) ** 2 + (py - by) ** 2);

            if (distance < minDistance) {
                minDistance = distance;
                minT = t;
            }
        }

        return { distance: minDistance, t: minT };
    }

    saveState() {
        // Save current state for undo
        const state = {
            paths: this.paths.map(p => ({
                ...p,
                points: [...p.points]
            })),
            images: this.images.map(img => ({
                ...img,
                // Don't clone the Image object, just save the properties
                img: img.img,
                element: img.element
            })),
            layerVisibility: { ...this.layerVisibility },
            imageVisibility: { ...this.imageVisibility }
        };

        // Remove future states if we're not at the end
        this.history = this.history.slice(0, this.historyIndex + 1);

        this.history.push(state);
        this.historyIndex++;

        // Limit history size
        if (this.history.length > 50) {
            this.history.shift();
            this.historyIndex--;
        }
    }

    undo() {
        if (this.historyIndex <= 0) return;

        this.historyIndex--;
        const state = this.history[this.historyIndex];

        // Restore state
        this.paths = state.paths.map(p => ({
            ...p,
            points: [...p.points]
        }));

        if (state.images) {
            this.images = state.images.map(img => ({
                ...img
            }));
        }

        if (state.layerVisibility) {
            this.layerVisibility = { ...state.layerVisibility };
        }

        if (state.imageVisibility) {
            this.imageVisibility = { ...state.imageVisibility };
        }

        this.selectedPoints = [];
        this.updateStats();
        this.updateSelectionInfo();
        this.updateLayersList();
        this.redraw();

        document.getElementById('svg-undo-btn').disabled = this.historyIndex <= 0;
    }

    redraw() {
        if (!this.svgData) {
            console.log('redraw() called but no SVG data');
            return;
        }

        console.log('Redrawing SVG, paths:', this.paths.length, 'scale:', this.scale);

        // Clear canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw background
        this.drawBackground();

        // Save context
        this.ctx.save();

        // Draw image layers first (behind paths)
        for (const imageData of this.images) {
            if (!imageData.visible || !imageData.loaded) continue;

            const x = imageData.x * this.scale + this.offsetX;
            const y = imageData.y * this.scale + this.offsetY;
            const width = imageData.width * this.scale;
            const height = imageData.height * this.scale;

            this.ctx.globalAlpha = imageData.opacity;
            this.ctx.drawImage(imageData.img, x, y, width, height);
            this.ctx.globalAlpha = 1.0;

            // Draw border if image is being dragged
            if (this.draggedImage && this.draggedImage.id === imageData.id) {
                this.ctx.strokeStyle = '#ff6b6b';
                this.ctx.lineWidth = 2;
                this.ctx.strokeRect(x, y, width, height);
            }
        }

        // Draw paths with proper curve commands
        for (const path of this.paths) {
            // Check both path visibility and layer visibility
            const layerVisible = this.layerVisibility[path.layerId] !== false;
            if (!path.visible || !layerVisible || path.points.length === 0) continue;

            console.log('Drawing path:', path.id, 'with', path.points.length, 'points');

            this.ctx.beginPath();

            let i = 0;
            while (i < path.points.length) {
                const point = path.points[i];
                const x = point.x * this.scale + this.offsetX;
                const y = point.y * this.scale + this.offsetY;

                if (point.cmd === 'M') {
                    // Move to
                    this.ctx.moveTo(x, y);
                    i++;
                } else if (point.cmd === 'L' || point.cmd === 'H' || point.cmd === 'V') {
                    // Line to
                    this.ctx.lineTo(x, y);
                    i++;
                } else if (point.cmd === 'C' && i >= 2) {
                    // Cubic Bezier curve - need 2 control points + end point
                    const cp1 = path.points[i - 2];
                    const cp2 = path.points[i - 1];

                    const cp1x = cp1.x * this.scale + this.offsetX;
                    const cp1y = cp1.y * this.scale + this.offsetY;
                    const cp2x = cp2.x * this.scale + this.offsetX;
                    const cp2y = cp2.y * this.scale + this.offsetY;

                    this.ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, x, y);
                    i++;
                } else if (point.cmd === 'Q' && i >= 1) {
                    // Quadratic Bezier curve - need 1 control point + end point
                    const cp = path.points[i - 1];

                    const cpx = cp.x * this.scale + this.offsetX;
                    const cpy = cp.y * this.scale + this.offsetY;

                    this.ctx.quadraticCurveTo(cpx, cpy, x, y);
                    i++;
                } else if (point.cmd === 'C1' || point.cmd === 'C2' || point.cmd === 'Q1') {
                    // Control points - skip, they're used when we hit C or Q
                    i++;
                } else {
                    // Default: line to
                    this.ctx.lineTo(x, y);
                    i++;
                }
            }

            this.ctx.strokeStyle = path.stroke;
            this.ctx.lineWidth = path.strokeWidth * this.scale;
            this.ctx.stroke();
        }

        // Draw points if enabled
        if (this.showPoints) {
            // First pass: Draw handle lines connecting control points to their anchors
            this.ctx.strokeStyle = '#9333ea';  // Purple for handle lines
            this.ctx.lineWidth = 1;
            this.ctx.setLineDash([3, 3]);  // Dashed lines

            for (const path of this.paths) {
                const layerVisible = this.layerVisibility[path.layerId] !== false;
                if (!path.visible || !layerVisible) continue;

                for (let i = 0; i < path.points.length; i++) {
                    const point = path.points[i];

                    // Draw lines from control points to their anchor points
                    if (point.cmd === 'C') {
                        // Find the two control points before this C point
                        let cp1 = null, cp2 = null;
                        let prevAnchor = null;

                        // Look backwards for C2 and C1
                        for (let j = i - 1; j >= 0; j--) {
                            if (path.points[j].cmd === 'C2' && !cp2) {
                                cp2 = path.points[j];
                            } else if (path.points[j].cmd === 'C1' && !cp1) {
                                cp1 = path.points[j];
                            } else if ((path.points[j].cmd === 'M' || path.points[j].cmd === 'L' || path.points[j].cmd === 'C') && !prevAnchor) {
                                prevAnchor = path.points[j];
                                break;
                            }
                        }

                        // Draw line from previous anchor to cp1
                        if (cp1 && prevAnchor) {
                            this.ctx.beginPath();
                            this.ctx.moveTo(
                                prevAnchor.x * this.scale + this.offsetX,
                                prevAnchor.y * this.scale + this.offsetY
                            );
                            this.ctx.lineTo(
                                cp1.x * this.scale + this.offsetX,
                                cp1.y * this.scale + this.offsetY
                            );
                            this.ctx.stroke();
                        }

                        // Draw line from cp2 to current anchor
                        if (cp2) {
                            this.ctx.beginPath();
                            this.ctx.moveTo(
                                cp2.x * this.scale + this.offsetX,
                                cp2.y * this.scale + this.offsetY
                            );
                            this.ctx.lineTo(
                                point.x * this.scale + this.offsetX,
                                point.y * this.scale + this.offsetY
                            );
                            this.ctx.stroke();
                        }
                    } else if (point.cmd === 'Q') {
                        // Find the control point before this Q point
                        let cp = null;
                        let prevAnchor = null;

                        for (let j = i - 1; j >= 0; j--) {
                            if (path.points[j].cmd === 'Q1' && !cp) {
                                cp = path.points[j];
                            } else if ((path.points[j].cmd === 'M' || path.points[j].cmd === 'L' || path.points[j].cmd === 'Q') && !prevAnchor) {
                                prevAnchor = path.points[j];
                                break;
                            }
                        }

                        // Draw lines from previous anchor to cp to current anchor
                        if (cp && prevAnchor) {
                            this.ctx.beginPath();
                            this.ctx.moveTo(
                                prevAnchor.x * this.scale + this.offsetX,
                                prevAnchor.y * this.scale + this.offsetY
                            );
                            this.ctx.lineTo(
                                cp.x * this.scale + this.offsetX,
                                cp.y * this.scale + this.offsetY
                            );
                            this.ctx.lineTo(
                                point.x * this.scale + this.offsetX,
                                point.y * this.scale + this.offsetY
                            );
                            this.ctx.stroke();
                        }
                    }
                }
            }

            // Reset line dash
            this.ctx.setLineDash([]);

            // Second pass: Draw the points themselves
            for (const path of this.paths) {
                const layerVisible = this.layerVisibility[path.layerId] !== false;
                if (!path.visible || !layerVisible) continue;

                for (let i = 0; i < path.points.length; i++) {
                    const point = path.points[i];
                    const x = point.x * this.scale + this.offsetX;
                    const y = point.y * this.scale + this.offsetY;

                    // Check if selected
                    const isSelected = this.selectedPoints.some(
                        p => p.pathId === path.id && p.pointIndex === i
                    );

                    // Check if hovered
                    const isHovered = this.hoveredPoint &&
                        this.hoveredPoint.pathId === path.id &&
                        this.hoveredPoint.pointIndex === i;

                    // Draw point
                    this.ctx.beginPath();
                    this.ctx.arc(x, y, this.pointSize / 2, 0, Math.PI * 2);

                    // Different colors for control points
                    if (point.cmd === 'C1' || point.cmd === 'C2' || point.cmd === 'Q1') {
                        this.ctx.fillStyle = '#9333ea';  // Purple for control points
                    } else if (isSelected) {
                        this.ctx.fillStyle = '#ef4444';  // Red for selected
                    } else if (isHovered) {
                        this.ctx.fillStyle = '#f59e0b';  // Orange for hovered
                    } else {
                        this.ctx.fillStyle = '#2563eb';  // Blue for normal
                    }

                    this.ctx.fill();

                    // Draw point label if enabled
                    if (this.showLabels && (isSelected || isHovered)) {
                        this.ctx.fillStyle = '#000';
                        this.ctx.font = '10px sans-serif';
                        this.ctx.fillText(`P${i} (${point.cmd})`, x + this.pointSize, y - this.pointSize);
                    }
                }
            }
        }

        this.ctx.restore();

        console.log('Redraw complete');
    }

    drawBackground() {
        this.ctx.save();

        // Fill white background
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw dot grid
        this.ctx.fillStyle = '#e5e5e5'; // Light gray
        const gridSize = 25;
        const dotRadius = 1.5;

        for (let x = gridSize / 2; x < this.canvas.width; x += gridSize) {
            for (let y = gridSize / 2; y < this.canvas.height; y += gridSize) {
                this.ctx.beginPath();
                this.ctx.arc(x, y, dotRadius, 0, Math.PI * 2);
                this.ctx.fill();
            }
        }

        this.ctx.restore();
    }

    updateLayersList() {
        const list = document.getElementById('svg-layers-list');

        if (Object.keys(this.layerCategories).length === 0 && this.images.length === 0) {
            list.innerHTML = '<p class="empty-message">No layers loaded</p>';
            return;
        }

        list.innerHTML = '';

        // Add image layers section if there are any
        if (this.images.length > 0) {
            const imageSection = document.createElement('div');
            imageSection.className = 'layer-category';
            imageSection.innerHTML = `
                <div class="layer-category-header" onclick="this.parentElement.classList.toggle('collapsed')">
                    <span class="category-icon">▼</span>
                    <strong>📷 Images</strong>
                    <span class="category-count">(${this.images.length})</span>
                </div>
                <div class="layer-category-content"></div>
            `;

            const imageContent = imageSection.querySelector('.layer-category-content');

            this.images.forEach(img => {
                const item = document.createElement('div');
                item.className = 'segment-item image-layer';
                item.innerHTML = `
                    <div class="segment-info">
                        <div class="segment-name">📷 ${img.name}</div>
                        <div class="segment-category">${Math.round(img.width)}x${Math.round(img.height)}px</div>
                    </div>
                    <div class="segment-actions">
                        <label title="Visibilità">
                            <input type="checkbox" ${img.visible ? 'checked' : ''} 
                                   onchange="window.svgEditor.toggleImage('${img.id}', this.checked)">
                        </label>
                        <button class="btn-icon" title="Opacità" 
                                onclick="window.svgEditor.adjustImageOpacity('${img.id}')">
                            ◐
                        </button>
                        ${img.isUserAdded ? `
                        <button class="btn-icon btn-danger-icon" title="Rimuovi" 
                                onclick="window.svgEditor.removeImage('${img.id}')">
                            🗑️
                        </button>
                        ` : ''}
                    </div>
                `;
                imageContent.appendChild(item);
            });

            list.appendChild(imageSection);
        }

        // Add layer categories
        const categories = Object.keys(this.layerCategories).sort();

        categories.forEach(category => {
            const paths = this.layerCategories[category];
            if (paths.length === 0) return;

            // Get unique layers in this category
            const layersInCategory = [...new Set(paths.map(p => p.layerId))];

            const section = document.createElement('div');
            section.className = 'layer-category';
            section.innerHTML = `
                <div class="layer-category-header" onclick="this.parentElement.classList.toggle('collapsed')">
                    <span class="category-icon">▼</span>
                    <strong>${this.getCategoryIcon(category)} ${category}</strong>
                    <span class="category-count">(${layersInCategory.length})</span>
                </div>
                <div class="layer-category-content"></div>
            `;

            const content = section.querySelector('.layer-category-content');

            layersInCategory.forEach(layerId => {
                const layerPaths = paths.filter(p => p.layerId === layerId);
                const totalPoints = layerPaths.reduce((sum, p) => sum + p.points.length, 0);
                const layerName = layerPaths[0].layerName;
                const isVisible = this.layerVisibility[layerId] !== false;

                const item = document.createElement('div');
                item.className = 'segment-item';
                item.innerHTML = `
                    <div class="segment-info">
                        <div class="segment-name">${layerName}</div>
                        <div class="segment-category">${layerPaths.length} path(s), ${totalPoints} points</div>
                    </div>
                    <div class="segment-actions">
                        <label title="Visibilità">
                            <input type="checkbox" ${isVisible ? 'checked' : ''} 
                                   onchange="window.svgEditor.toggleLayer('${layerId}', this.checked)">
                        </label>
                    </div>
                `;
                content.appendChild(item);
            });

            list.appendChild(section);
        });
    }

    getCategoryIcon(category) {
        const icons = {
            'Profile': '🏺',
            'Profile Mirrored': '🪞',
            'Symmetry': '⚖️',
            'Symmetry Line': '⚖️',
            'Diameter': '⬌',
            'Ungrouped': '📄',
            'Other': '📋'
        };
        return icons[category] || '📋';
    }

    toggleLayer(layerId, visible) {
        this.layerVisibility[layerId] = visible;

        // Update all paths in this layer
        this.paths.forEach(p => {
            if (p.layerId === layerId) {
                p.visible = visible;
            }
        });

        this.redraw();
    }

    toggleImage(imageId, visible) {
        const image = this.images.find(img => img.id === imageId);
        if (image) {
            image.visible = visible;
            this.imageVisibility[imageId] = visible;
            this.saveState();
            this.redraw();
        }
    }

    removeImage(imageId) {
        if (!confirm('Vuoi davvero rimuovere questa immagine?')) return;

        const index = this.images.findIndex(img => img.id === imageId);
        if (index !== -1) {
            this.images.splice(index, 1);
            delete this.imageVisibility[imageId];

            this.saveState();
            this.updateLayersList();
            this.redraw();

            if (window.app) {
                window.app.showNotification('Immagine rimossa!', 'success');
            }
        }
    }

    adjustImageOpacity(imageId) {
        const image = this.images.find(img => img.id === imageId);
        if (!image) return;

        const newOpacity = prompt(`Opacità per ${image.name} (0.0 - 1.0):`, image.opacity);
        if (newOpacity !== null) {
            const opacity = parseFloat(newOpacity);
            if (!isNaN(opacity) && opacity >= 0 && opacity <= 1) {
                image.opacity = opacity;
                this.saveState();
                this.redraw();
            }
        }
    }

    addImageFromUrl(imageUrl, imageName) {
        const img = new Image();

        img.onload = () => {
            // Center the image in the viewport
            const centerX = (this.svgData ? this.svgData.width / 2 : 500) - img.width / 2;
            const centerY = (this.svgData ? this.svgData.height / 2 : 500) - img.height / 2;

            const imageId = `current-image-${Date.now()}`;
            const cleanName = imageName ? imageName.replace(/\.[^/.]+$/, '') : 'Image';

            const imageData = {
                id: imageId,
                name: cleanName,
                element: null, // No original SVG element
                img,
                x: Math.max(0, centerX),
                y: Math.max(0, centerY),
                width: img.width,
                height: img.height,
                opacity: 0.7, // Start semi-transparent
                visible: true,
                loaded: true,
                isUserAdded: true, // Flag for user-added images
                isLocked: true // Lock the current image so it can't be moved
            };

            this.images.push(imageData);
            this.imageVisibility[imageId] = true;

            this.saveState();
            this.updateLayersList();
            this.redraw();

            if (window.app) {
                window.app.showNotification(`Image "${cleanName}" added (locked)!`, 'success');
            }
        };

        img.onerror = () => {
            console.error('Failed to load image from URL:', imageUrl);
            if (window.app) {
                window.app.showNotification('Failed to load image', 'error');
            }
        };

        // Set crossOrigin to allow loading from same origin
        img.crossOrigin = 'anonymous';
        img.src = imageUrl;
    }

    addImageFromFile(file) {
        if (!file.type.startsWith('image/')) {
            alert('Per favore seleziona un file immagine valido.');
            return;
        }

        const reader = new FileReader();

        reader.onload = (e) => {
            const img = new Image();

            img.onload = () => {
                // Center the image in the viewport
                const centerX = (this.svgData ? this.svgData.width / 2 : 500) - img.width / 2;
                const centerY = (this.svgData ? this.svgData.height / 2 : 500) - img.height / 2;

                const imageId = `user-image-${Date.now()}`;
                const imageName = file.name.replace(/\.[^/.]+$/, '');

                const imageData = {
                    id: imageId,
                    name: imageName,
                    element: null, // No original SVG element
                    img,
                    x: Math.max(0, centerX),
                    y: Math.max(0, centerY),
                    width: img.width,
                    height: img.height,
                    opacity: 0.7, // Start semi-transparent
                    visible: true,
                    loaded: true,
                    isUserAdded: true // Flag for user-added images
                };

                this.images.push(imageData);
                this.imageVisibility[imageId] = true;

                this.saveState();
                this.updateLayersList();
                this.redraw();

                if (window.app) {
                    window.app.showNotification(`Immagine "${imageName}" aggiunta!`, 'success');
                }
            };

            img.src = e.target.result;
        };

        reader.readAsDataURL(file);
    }

    updateStats() {
        const totalPaths = this.paths.length;
        const totalPoints = this.getTotalPoints();
        const selectedPoints = this.selectedPoints.length;

        document.getElementById('svg-stat-paths').textContent = totalPaths;
        document.getElementById('svg-stat-points').textContent = totalPoints;
        document.getElementById('svg-stat-selected').textContent = selectedPoints;
    }

    updateSelectionInfo() {
        const info = document.getElementById('svg-selection-info');

        if (this.selectedPoints.length === 0) {
            info.innerHTML = '<p>No point selected</p>';
        } else {
            const pointsText = this.selectedPoints.length === 1 ? 'point' : 'points';
            info.innerHTML = `
                <p><strong>${this.selectedPoints.length}</strong> ${pointsText} selected</p>
                <button class="btn btn-danger btn-small" 
                        onclick="window.svgEditor.deleteSelectedPoints()" 
                        style="margin-top: 8px; width: 100%;">
                    <span>🗑️</span> Delete Selected
                </button>
            `;
        }
    }

    deleteSelectedPoints() {
        if (this.selectedPoints.length === 0) return;

        if (!confirm(`Eliminare ${this.selectedPoints.length} punti selezionati?`)) {
            return;
        }

        this.saveState();

        // Sort by pathId and pointIndex (descending) to delete from end to start
        const sorted = [...this.selectedPoints].sort((a, b) => {
            if (a.pathId !== b.pathId) return b.pathId.localeCompare(a.pathId);
            return b.pointIndex - a.pointIndex;
        });

        // Delete points
        sorted.forEach(pointInfo => {
            const path = this.paths.find(p => p.id === pointInfo.pathId);
            if (path && pointInfo.pointIndex < path.points.length) {
                path.points.splice(pointInfo.pointIndex, 1);
                this.rebuildPathData(path);
            }
        });

        this.selectedPoints = [];
        this.updateStats();
        this.updateSelectionInfo();
        this.redraw();

        document.getElementById('svg-undo-btn').disabled = false;
    }

    getTotalPoints() {
        return this.paths.reduce((sum, path) => sum + path.points.length, 0);
    }

    async exportModifiedSVG() {
        if (!this.svgData) return;

        try {
            // Get the include background checkbox state
            const includeBackground = document.getElementById('svg-bg-checkbox').checked;

            // Clone the original SVG element
            const svgClone = this.svgData.element.cloneNode(true);

            // Update all path elements with modified data
            const pathElements = svgClone.querySelectorAll('path');

            pathElements.forEach((pathEl, index) => {
                const pathData = this.paths[index];
                if (pathData && pathData.currentD) {
                    pathEl.setAttribute('d', pathData.currentD);
                }
            });

            // Update all image elements with modified positions
            const imageElements = svgClone.querySelectorAll('image');

            imageElements.forEach((imgEl, index) => {
                const imageData = this.images[index];
                if (imageData) {
                    imgEl.setAttribute('x', imageData.x);
                    imgEl.setAttribute('y', imageData.y);
                    imgEl.setAttribute('opacity', imageData.opacity);

                    // Remove invisible images
                    if (!imageData.visible) {
                        imgEl.parentNode.removeChild(imgEl);
                    }
                }
            });

            // Remove invisible layers (groups)
            const groups = svgClone.querySelectorAll('g[id^="layer_"]');
            groups.forEach(group => {
                const layerId = group.getAttribute('id');
                if (this.layerVisibility[layerId] === false) {
                    group.parentNode.removeChild(group);
                }
            });

            // Serialize to string
            const serializer = new XMLSerializer();
            const svgString = serializer.serializeToString(svgClone);

            // Send to backend to save in the project folder
            const response = await fetch('/api/save_modified_svg', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    svg_content: svgString,
                    include_background: includeBackground,
                    session_id: this.sessionId || 'default',
                    image_name: this.currentImageName || 'output',
                    project_id: this.currentProjectId || (window.app ? window.app.currentProjectId : null)
                })
            });

            const data = await response.json();

            if (data.success) {
                // Show success message with the actual save path
                const fileName = data.output_path ? data.output_path.split(/[/\\]/).pop() : 'file';
                const message = `✓ SVG saved: ${fileName}`;
                if (window.app) {
                    window.app.showNotification(message, 'success');
                }
                console.log('Modified SVG saved to:', data.output_path);

                // Mark current image as vectorized in ImageGrid
                if (window.ImageGrid && this.sessionId) {
                    await window.ImageGrid.markAsVectorized(this.sessionId);
                    console.log('✓ Image marked as vectorized in thumbnails');
                }

                // NO automatic ZIP download - just save the SVG file
            } else {
                throw new Error(data.error || 'Error while saving');
            }

        } catch (error) {
            console.error('Export error:', error);
            alert('Errore durante l\'esportazione: ' + error.message);
        }
    }

    downloadCompleteZip() {
        if (!this.zipDownloadUrl) {
            alert('ZIP file non disponibile. Esporta prima i segmenti dalla tab Segmentation.');
            return;
        }

        console.log('Downloading complete ZIP from:', this.zipDownloadUrl);

        // Trigger download
        window.location.href = this.zipDownloadUrl;

        if (window.app) {
            window.app.showNotification('Download ZIP completo avviato!', 'success');
        }
    }

    loadTestSVG() {
        console.log('Loading test SVG...');

        // Create a test SVG directly
        const testSVG = `<?xml version="1.0" encoding="UTF-8"?>
<svg width="500" height="500" viewBox="0 0 500 500" xmlns="http://www.w3.org/2000/svg">
    <g id="layer1">
        <path d="M 100 100 L 200 100 L 200 200 L 100 200 Z" 
              stroke="#000000" stroke-width="2" fill="none"/>
        <path d="M 250 100 L 350 100 L 350 200 L 250 200 Z" 
              stroke="#ff0000" stroke-width="2" fill="none"/>
    </g>
    <g id="layer2">
        <path d="M 100 250 C 100 250 150 300 200 250" 
              stroke="#0000ff" stroke-width="2" fill="none"/>
    </g>
</svg>`;

        console.log('Test SVG text:', testSVG);

        // Parse SVG directly
        const parser = new DOMParser();
        const svgDoc = parser.parseFromString(testSVG, 'image/svg+xml');
        const svgElement = svgDoc.querySelector('svg');

        if (!svgElement) {
            console.error('Failed to parse test SVG');
            alert('Errore nel parsing del test SVG');
            return;
        }

        console.log('Test SVG element:', svgElement);

        // Extract viewBox or dimensions
        const viewBox = svgElement.getAttribute('viewBox');
        let width, height;

        if (viewBox) {
            const [, , w, h] = viewBox.split(' ').map(Number);
            width = w;
            height = h;
        } else {
            width = parseFloat(svgElement.getAttribute('width')) || 500;
            height = parseFloat(svgElement.getAttribute('height')) || 500;
        }

        console.log('Test SVG dimensions:', width, 'x', height);

        this.svgData = {
            width,
            height,
            element: svgElement,
            text: testSVG
        };

        // Extract paths and their points
        this.extractPaths(svgElement);

        console.log('Test SVG paths extracted:', this.paths.length);

        // Update UI
        this.updateLayersList();
        this.updateStats();

        // Hide message
        document.getElementById('svg-canvas-message').style.display = 'none';

        // Enable save button
        document.getElementById('svg-save-btn').disabled = false;

        // ZIP download button stays disabled for test SVG (no ZIP available)
        document.getElementById('svg-download-zip-btn').disabled = true;

        // Save initial state
        this.saveState();

        // Force canvas resize and redraw
        const container = this.canvas.parentElement;
        const rect = container.getBoundingClientRect();
        this.canvas.width = rect.width || container.clientWidth;
        this.canvas.height = rect.height || container.clientHeight;

        console.log('Canvas size after load:', this.canvas.width, 'x', this.canvas.height);

        // Reset view and redraw
        this.resetView();

        console.log('Test SVG loaded successfully!');
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // SVG Editor will be initialized when tab is activated
    console.log('SVG Editor script loaded');
});
