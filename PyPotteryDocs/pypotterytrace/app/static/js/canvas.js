// Canvas Manager - Handles canvas drawing and interactions

class CanvasManager {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        this.ctx = this.canvas.getContext('2d');
        this.image = null;
        this.svgImage = null;  // For SVG preview overlay
        this.scale = 1;
        this.offsetX = 0;
        this.offsetY = 0;
        this.isDragging = false;
        this.lastMouseX = 0;
        this.lastMouseY = 0;
        this.mode = 'point';
        this.rotationCenter = null;
        this.savedMasks = [];  // Array to store all added masks with their colors

        this.init();
    }

    init() {
        this.setupEventListeners();
        this.resize();
        window.addEventListener('resize', () => this.resize());

        // Listen for image selection from grid
        document.addEventListener('imageSelected', (e) => {
            const { projectId, filename } = e.detail;
            const imageUrl = `/api/projects/${projectId}/images/${encodeURIComponent(filename)}?folder=uploads`;
            this.loadImage(imageUrl);

            // Hide the "Upload an image" message
            const canvasMessage = document.getElementById('canvas-message');
            if (canvasMessage) {
                canvasMessage.style.display = 'none';
            }
        });
    }

    setupEventListeners() {
        // Mouse events for panning
        this.canvas.addEventListener('mousedown', (e) => {
            if (e.button === 1 || (e.button === 0 && e.ctrlKey)) {
                // Middle mouse or Ctrl+Left for panning
                this.isDragging = true;
                this.lastMouseX = e.clientX;
                this.lastMouseY = e.clientY;
                this.canvas.style.cursor = 'grabbing';
                e.preventDefault();
                e.stopPropagation(); // Stop propagation only for panning
            }
            // Don't prevent default or stop propagation for normal clicks
            // Let them through to segmentation handlers
        });

        this.canvas.addEventListener('mousemove', (e) => {
            if (this.isDragging) {
                const dx = e.clientX - this.lastMouseX;
                const dy = e.clientY - this.lastMouseY;

                this.offsetX += dx;
                this.offsetY += dy;

                this.lastMouseX = e.clientX;
                this.lastMouseY = e.clientY;

                this.redraw();
                e.preventDefault(); // Prevent default only during dragging
            }
        });

        this.canvas.addEventListener('mouseup', (e) => {
            if (this.isDragging) {
                this.isDragging = false;
                this.updateCursor();
                e.preventDefault(); // Prevent default only if we were dragging
            }
        });

        this.canvas.addEventListener('mouseleave', () => {
            this.isDragging = false;
            this.updateCursor();
        });

        // Mouse wheel for zooming
        this.canvas.addEventListener('wheel', (e) => {
            e.preventDefault();
            const delta = e.deltaY > 0 ? 0.9 : 1.1;
            this.zoom(delta, e.offsetX, e.offsetY);
        });
    }

    resize() {
        const container = this.canvas.parentElement;
        this.canvas.width = container.clientWidth;
        this.canvas.height = container.clientHeight;
        this.redraw();
    }

    loadImage(imageUrl) {
        console.log('CanvasManager.loadImage called with:', imageUrl);

        // Clear all previous data when loading a new image
        this.savedMasks = [];
        this.svgImage = null;
        this.rotationCenter = null;

        const img = new Image();
        img.onload = () => {
            console.log('Image loaded successfully:', img.width, 'x', img.height);
            this.image = img;
            this.fitToCanvas();
            this.redraw();
            console.log('Canvas should now show the image');
        };
        img.onerror = (e) => {
            console.error('Failed to load image:', imageUrl, e);
        };
        img.src = imageUrl;
        console.log('Image loading started...');
    }

    fitToCanvas() {
        if (!this.image) return;

        // Calculate scale to fit image entirely within canvas (90% to leave some margin)
        const scaleX = (this.canvas.width * 0.9) / this.image.width;
        const scaleY = (this.canvas.height * 0.9) / this.image.height;
        this.scale = Math.min(scaleX, scaleY);

        // Center image
        this.offsetX = (this.canvas.width - this.image.width * this.scale) / 2;
        this.offsetY = (this.canvas.height - this.image.height * this.scale) / 2;
    }

    zoom(factor, centerX = null, centerY = null) {
        const oldScale = this.scale;
        this.scale *= factor;

        // Limit zoom
        this.scale = Math.max(0.1, Math.min(10, this.scale));

        if (centerX !== null && centerY !== null) {
            // Zoom towards cursor position
            const scaleChange = this.scale / oldScale;
            this.offsetX = centerX - (centerX - this.offsetX) * scaleChange;
            this.offsetY = centerY - (centerY - this.offsetY) * scaleChange;
        }

        this.redraw();
    }

    resetView() {
        this.fitToCanvas();
        this.redraw();
    }

    redraw() {
        console.log('=== REDRAW DEBUG ===');
        console.log('Image loaded:', !!this.image);
        if (this.image) {
            console.log('Image dimensions:', this.image.width, 'x', this.image.height);
        }
        console.log('Canvas dimensions:', this.canvas.width, 'x', this.canvas.height);
        console.log('Scale:', this.scale, 'Offset:', this.offsetX, this.offsetY);
        console.log('SVG overlay present:', !!this.svgImage);
        console.log('Saved masks count:', this.savedMasks.length);
        console.log('Preview contours present:', !!(window.segmentationManager && segmentationManager.previewContours));

        // Clear canvas - Force a complete clear
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        // Draw custom background (White with dot grid)
        this.drawBackground();

        console.log('Canvas background drawn');

        // Draw image if loaded
        if (this.image) {
            console.log('Attempting to draw image...');
            this.ctx.save();
            this.ctx.translate(this.offsetX, this.offsetY);
            this.ctx.scale(this.scale, this.scale);
            this.ctx.drawImage(this.image, 0, 0);
            this.ctx.restore();
            console.log('Background image drawn successfully');
        } else {
            console.warn('No image to draw!');
        }

        // Draw SVG overlay if available (replaces masks view)
        if (this.svgImage) {
            console.log('Drawing SVG overlay instead of masks');
            this.ctx.save();
            this.ctx.translate(this.offsetX, this.offsetY);
            this.ctx.scale(this.scale, this.scale);
            this.ctx.drawImage(this.svgImage, 0, 0);
            this.ctx.restore();
        } else {
            // Draw all saved masks (only if SVG is not shown)
            console.log('Drawing saved masks:', this.savedMasks.length);
            this.savedMasks.forEach((maskData, idx) => {
                console.log(`  Drawing mask ${idx}: ${maskData.name} (ID: ${maskData.segmentId})`);
                this.drawContours(maskData.contours, maskData.color, maskData.fillColor);
            });
        }

        // Draw rotation center if set
        if (this.rotationCenter) {
            this.drawRotationCenterMarker(this.rotationCenter.x, this.rotationCenter.y);
        }

        // Draw current points if available
        if (window.segmentationManager && segmentationManager.points && segmentationManager.points.length > 0) {
            segmentationManager.points.forEach((point, index) => {
                this.drawPointMarker(point[0], point[1], segmentationManager.labels[index]);
            });
        }

        // Draw current segmentation preview if available
        if (window.segmentationManager && segmentationManager.previewContours) {
            this.drawContours(segmentationManager.previewContours, '#00ff00', 'rgba(0, 255, 0, 0.2)');
        }

        // Draw polygon preview if in polygon mode
        if (window.segmentationManager && segmentationManager.polygonVertices && segmentationManager.polygonVertices.length > 0) {
            segmentationManager.drawPolygonPreview();
        }
    }

    drawContours(contours, strokeColor = '#00ff00', fillColor = 'rgba(0, 255, 0, 0.2)') {
        this.ctx.save();
        this.ctx.translate(this.offsetX, this.offsetY);
        this.ctx.scale(this.scale, this.scale);

        this.ctx.strokeStyle = strokeColor;
        this.ctx.lineWidth = 2 / this.scale;
        this.ctx.fillStyle = fillColor;

        contours.forEach(contour => {
            if (contour.length < 2) return;

            this.ctx.beginPath();
            this.ctx.moveTo(contour[0][0], contour[0][1]);

            for (let i = 1; i < contour.length; i++) {
                this.ctx.lineTo(contour[i][0], contour[i][1]);
            }

            this.ctx.closePath();
            this.ctx.fill();
            this.ctx.stroke();
        });

        this.ctx.restore();
    }

    // Add a mask to the saved masks list (called when a segment is added)
    addSavedMask(contours, category, name, segmentId) {
        // Generate a color based on category
        const categoryColors = {
            'Profile': { stroke: '#ff6b6b', fill: 'rgba(255, 107, 107, 0.15)' },
            'Application': { stroke: '#ffa500', fill: 'rgba(255, 165, 0, 0.15)' },
            'Handle': { stroke: '#dda0dd', fill: 'rgba(221, 160, 221, 0.15)' },
            'Prospectus': { stroke: '#4ecdc4', fill: 'rgba(78, 205, 196, 0.15)' },
            'Decoration': { stroke: '#ffe66d', fill: 'rgba(255, 230, 109, 0.15)' },
            'Section': { stroke: '#a8dadc', fill: 'rgba(168, 218, 220, 0.15)' },
            'Detail': { stroke: '#f1a7fe', fill: 'rgba(241, 167, 254, 0.15)' }
        };

        const colors = categoryColors[category] || { stroke: '#00ff00', fill: 'rgba(0, 255, 0, 0.15)' };

        const maskData = {
            contours: contours,
            color: colors.stroke,
            fillColor: colors.fill,
            category: category,
            name: name,
            segmentId: segmentId
        };

        this.savedMasks.push(maskData);

        this.redraw();
    }

    // Remove a mask from the saved masks list (called when a segment is deleted)
    removeSavedMask(segmentId) {
        console.log('=== REMOVE MASK DEBUG ===');
        console.log('Removing mask for segment ID:', segmentId, 'Type:', typeof segmentId);
        console.log('Masks before filter:', this.savedMasks.length);
        this.savedMasks.forEach((mask, idx) => {
            console.log(`  Mask ${idx}: ID="${mask.segmentId}" (type: ${typeof mask.segmentId}), Name=${mask.name}`);
            console.log(`    String comparison: "${String(mask.segmentId)}" === "${String(segmentId)}" = ${String(mask.segmentId) === String(segmentId)}`);
        });

        // Convert both to string for reliable comparison
        const targetId = String(segmentId);
        const initialLength = this.savedMasks.length;
        this.savedMasks = this.savedMasks.filter(mask => {
            const maskId = String(mask.segmentId);
            const shouldKeep = maskId !== targetId;
            console.log(`  Filtering mask ${maskId}: shouldKeep=${shouldKeep}`);
            return shouldKeep;
        });

        const removedCount = initialLength - this.savedMasks.length;
        console.log(`Removed ${removedCount} mask(s)`);
        console.log('Masks after filter:', this.savedMasks.length);
        this.savedMasks.forEach((mask, idx) => {
            console.log(`  Mask ${idx}: ID=${mask.segmentId}, Name=${mask.name}`);
        });

        // Clear the SVG overlay to ensure we show masks
        this.svgImage = null;

        // Force a complete redraw
        console.log('Forcing complete redraw...');
        this.redraw();
        console.log('=== REMOVE MASK COMPLETE ===');
    }

    // Clear all saved masks (called when deleting segments)
    clearSavedMasks() {
        this.savedMasks = [];
        this.redraw();
    }

    /**
     * Add a mask to the canvas (used when loading saved sessions)
     */
    addMask(contours, color = 'rgba(59, 130, 246, 0.5)') {
        const maskData = {
            contours: contours,
            color: color,
            fillColor: color,
            category: 'Loaded',
            name: 'Loaded Segment'
        };
        this.savedMasks.push(maskData);
    }

    // Clear everything (masks, SVG overlay, rotation center) - used when loading new image
    clearAll() {
        console.log('=== CLEARING ALL CANVAS DATA ===');
        this.savedMasks = [];
        this.svgImage = null;
        this.rotationCenter = null;
        console.log('Cleared: masks, SVG overlay, rotation center');
        this.redraw();
    }

    drawRotationCenter(x, y) {
        this.rotationCenter = { x, y };
        this.redraw();
    }

    clearRotationCenter() {
        this.rotationCenter = null;
        this.redraw();
    }

    drawPointMarker(x, y, label) {
        this.ctx.save();

        const canvasCoords = this.imageToCanvas(x, y);

        // Draw circle
        this.ctx.beginPath();
        this.ctx.arc(canvasCoords.x, canvasCoords.y, 5, 0, 2 * Math.PI);
        this.ctx.fillStyle = label === 1 ? '#00ff00' : '#ff0000';
        this.ctx.fill();
        this.ctx.strokeStyle = '#ffffff';
        this.ctx.lineWidth = 2;
        this.ctx.stroke();

        this.ctx.restore();
    }

    drawRotationCenterMarker(x, y) {
        this.ctx.save();
        this.ctx.translate(this.offsetX, this.offsetY);
        this.ctx.scale(this.scale, this.scale);

        // Draw crosshair
        this.ctx.strokeStyle = '#ff0000';
        this.ctx.lineWidth = 2 / this.scale;

        const size = 20 / this.scale;

        // Vertical line
        this.ctx.beginPath();
        this.ctx.moveTo(x, y - size);
        this.ctx.lineTo(x, y + size);
        this.ctx.stroke();

        // Horizontal line
        this.ctx.beginPath();
        this.ctx.moveTo(x - size, y);
        this.ctx.lineTo(x + size, y);
        this.ctx.stroke();

        // Circle
        this.ctx.beginPath();
        this.ctx.arc(x, y, 5 / this.scale, 0, 2 * Math.PI);
        this.ctx.fillStyle = '#ff0000';
        this.ctx.fill();

        this.ctx.restore();
    }

    setMode(mode) {
        this.mode = mode;
        this.updateCursor();
    }

    updateCursor() {
        if (this.isDragging) {
            this.canvas.style.cursor = 'grabbing';
        } else {
            switch (this.mode) {
                case 'point':
                    this.canvas.style.cursor = 'crosshair';
                    break;
                case 'box':
                    this.canvas.style.cursor = 'crosshair';
                    break;
                case 'polygon':
                    this.canvas.style.cursor = 'crosshair';
                    break;
                case 'rotation':
                    this.canvas.style.cursor = 'crosshair';
                    break;
                default:
                    this.canvas.style.cursor = 'default';
            }
        }
    }

    // Convert canvas coordinates to image coordinates
    canvasToImage(canvasX, canvasY) {
        const imageX = (canvasX - this.offsetX) / this.scale;
        const imageY = (canvasY - this.offsetY) / this.scale;
        return { x: imageX, y: imageY };
    }

    // Convert image coordinates to canvas coordinates
    imageToCanvas(imageX, imageY) {
        const canvasX = imageX * this.scale + this.offsetX;
        const canvasY = imageY * this.scale + this.offsetY;
        return { x: canvasX, y: canvasY };
    }

    getImageCoordinates(e) {
        const rect = this.canvas.getBoundingClientRect();
        const canvasX = e.clientX - rect.left;
        const canvasY = e.clientY - rect.top;
        return this.canvasToImage(canvasX, canvasY);
    }

    // Display SVG content on canvas
    async displaySVG(svgContent) {
        return new Promise((resolve, reject) => {
            try {
                // Create an image from SVG content
                const blob = new Blob([svgContent], { type: 'image/svg+xml' });
                const url = URL.createObjectURL(blob);

                const img = new Image();
                img.onload = () => {
                    // Clear saved masks since we're showing SVG now
                    this.savedMasks = [];

                    // Store the SVG image
                    this.svgImage = img;

                    // Redraw canvas with SVG overlay
                    this.redraw();

                    // Clean up blob URL
                    URL.revokeObjectURL(url);

                    resolve();
                };
                img.onerror = (error) => {
                    console.error('Failed to load SVG as image:', error);
                    URL.revokeObjectURL(url);
                    reject(error);
                };
                img.src = url;
            } catch (error) {
                console.error('Error creating SVG blob:', error);
                reject(error);
            }
        });
    }

    // Clear SVG overlay
    clearSVG() {
        this.svgImage = null;
        this.redraw();
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
}
