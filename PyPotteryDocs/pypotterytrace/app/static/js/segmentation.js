// Segmentation Manager - Handles SAM2 segmentation interactions

class SegmentationManager {
    constructor() {
        this.points = [];
        this.labels = [];
        this.boxStart = null;
        this.boxEnd = null;
        this.currentMask = null;
        this.previewContours = null;
        this.isDrawingBox = false;
        
        // Manual polygon mode
        this.polygonVertices = [];
        this.isPolygonClosed = false;
        this.isManualMask = false;  // Flag to indicate this is a manual mask (no dilation)
        
        // Polygon editing mode
        this.isEditingPolygon = false;
        this.selectedVertexIndex = -1;
        this.isDraggingVertex = false;
        this.vertexHitRadius = 10;  // Pixels radius to detect vertex click
        this.originalContour = null;  // Store original contour for re-simplification
        
        this.init();
    }
    
    init() {
        this.setupCanvasInteraction();
        this.setupPolygonControls();
        this.setupEditMaskButton();
        this.setupPolygonEditControls();
    }
    
    setupEditMaskButton() {
        const editMaskBtn = document.getElementById('edit-mask-btn');
        if (editMaskBtn) {
            editMaskBtn.addEventListener('click', () => {
                this.convertMaskToEditablePolygon();
            });
        }
    }
    
    setupPolygonEditControls() {
        // Simplification slider
        const simplifySlider = document.getElementById('simplify-slider');
        const simplifyValue = document.getElementById('simplify-value');
        if (simplifySlider && simplifyValue) {
            simplifySlider.addEventListener('input', (e) => {
                simplifyValue.textContent = e.target.value;
            });
        }
        
        // Apply simplification button
        const applySimplifyBtn = document.getElementById('apply-simplify-btn');
        if (applySimplifyBtn) {
            applySimplifyBtn.addEventListener('click', () => {
                this.applySimplification();
            });
        }
        
        // Finish editing button
        const finishEditBtn = document.getElementById('finish-edit-btn');
        if (finishEditBtn) {
            finishEditBtn.addEventListener('click', () => {
                this.finishEditing();
            });
        }
    }
    
    applySimplification() {
        const slider = document.getElementById('simplify-slider');
        const epsilon = slider ? parseFloat(slider.value) : 15.0;
        
        // Use original contour if available, otherwise current vertices
        const sourceContour = this.originalContour || this.polygonVertices;
        
        if (!sourceContour || sourceContour.length < 4) {
            if (window.app) {
                window.app.showNotification('Not enough vertices to simplify (need at least 4)', 'warning');
            }
            return;
        }
        
        const originalCount = sourceContour.length;
        
        // Apply simplification from original contour
        let simplified = this.simplifyContour(sourceContour.slice(), epsilon);  // Use .slice() to clone
        
        // Ensure polygon stays closed (first and last point not duplicated)
        if (simplified.length > 1) {
            const first = simplified[0];
            const last = simplified[simplified.length - 1];
            if (Math.abs(first[0] - last[0]) < 1 && Math.abs(first[1] - last[1]) < 1) {
                simplified.pop();
            }
        }
        
        // Ensure we have at least 3 vertices
        if (simplified.length < 3) {
            if (window.app) {
                window.app.showNotification('Simplification too aggressive - would result in less than 3 vertices', 'warning');
            }
            return;
        }
        
        this.polygonVertices = simplified.map(p => [p[0], p[1]]);  // Ensure clean copy
        this.previewContours = [this.polygonVertices.slice()];  // Update preview contours too
        this.updatePolygonControls();
        
        if (window.app) {
            window.app.showNotification(`Simplified: ${originalCount} → ${this.polygonVertices.length} vertices (ε=${epsilon})`, 'info');
        }
        
        if (window.canvasManager) {
            window.canvasManager.redraw();
        }
    }
    
    convertMaskToEditablePolygon() {
        // Convert current SAM contours to editable polygon vertices
        if (!this.previewContours || this.previewContours.length === 0) {
            if (window.app) {
                window.app.showNotification('No mask to edit', 'warning');
            }
            return;
        }
        
        // Get the largest contour by AREA (not just point count)
        // This ensures we keep the main shape and discard small islands
        let largestContour = this.previewContours[0];
        let maxArea = this.calculatePolygonArea(largestContour);
        
        for (const contour of this.previewContours) {
            const area = this.calculatePolygonArea(contour);
            if (area > maxArea) {
                largestContour = contour;
                maxArea = area;
            }
        }
        
        // SAVE the original contour for re-simplification later
        this.originalContour = largestContour.map(p => [p[0], p[1]]);
        
        // Get simplification value from slider (or use default)
        // Use HIGH epsilon by default = very few vertices (better to add than remove)
        const slider = document.getElementById('simplify-slider');
        const epsilon = slider ? parseFloat(slider.value) : 15.0;
        
        // Simplify the contour to reduce number of vertices (RDP algorithm)
        const simplified = this.simplifyContour(largestContour.slice(), epsilon);  // Use .slice() to clone
        
        // Convert to polygon vertices
        this.polygonVertices = simplified.map(p => [p[0], p[1]]);
        
        // Remove duplicate last point if it matches first
        if (this.polygonVertices.length > 1) {
            const first = this.polygonVertices[0];
            const last = this.polygonVertices[this.polygonVertices.length - 1];
            if (Math.abs(first[0] - last[0]) < 1 && Math.abs(first[1] - last[1]) < 1) {
                this.polygonVertices.pop();
            }
        }
        
        this.isPolygonClosed = true;
        this.isManualMask = true;  // Manual mask = no dilation in post-processing
        this.isEditingPolygon = true;
        
        // Replace preview contours with only the largest one
        this.previewContours = [this.polygonVertices.slice()];
        
        // Switch to polygon editing mode
        this.enterEditMode();
        
        const discardedCount = this.previewContours.length > 1 ? 
            ` (discarded ${this.previewContours.length - 1} smaller regions)` : '';
        
        if (window.app) {
            window.app.showNotification(
                `Mask converted to ${this.polygonVertices.length} vertices${discardedCount}. Adjust simplification slider to change.`, 
                'success'
            );
        }
        
        // Redraw
        if (window.canvasManager) {
            window.canvasManager.redraw();
        }
    }
    
    calculatePolygonArea(vertices) {
        // Shoelace formula to calculate polygon area
        if (!vertices || vertices.length < 3) return 0;
        
        let area = 0;
        const n = vertices.length;
        
        for (let i = 0; i < n; i++) {
            const j = (i + 1) % n;
            area += vertices[i][0] * vertices[j][1];
            area -= vertices[j][0] * vertices[i][1];
        }
        
        return Math.abs(area) / 2;
    }
    
    simplifyContour(contour, epsilon = 2.0) {
        // Ramer-Douglas-Peucker algorithm for contour simplification
        if (contour.length < 3) return contour;
        
        // Find the point with the maximum distance from line between first and last
        let maxDist = 0;
        let maxIndex = 0;
        
        const start = contour[0];
        const end = contour[contour.length - 1];
        
        for (let i = 1; i < contour.length - 1; i++) {
            const dist = this.perpendicularDistance(contour[i], start, end);
            if (dist > maxDist) {
                maxDist = dist;
                maxIndex = i;
            }
        }
        
        // If max distance is greater than epsilon, recursively simplify
        if (maxDist > epsilon) {
            const left = this.simplifyContour(contour.slice(0, maxIndex + 1), epsilon);
            const right = this.simplifyContour(contour.slice(maxIndex), epsilon);
            
            // Combine results (remove duplicate point at junction)
            return left.slice(0, -1).concat(right);
        } else {
            // Return just the endpoints
            return [start, end];
        }
    }
    
    perpendicularDistance(point, lineStart, lineEnd) {
        const dx = lineEnd[0] - lineStart[0];
        const dy = lineEnd[1] - lineStart[1];
        
        // Line length squared
        const lenSq = dx * dx + dy * dy;
        
        if (lenSq === 0) {
            // Line is a point
            return Math.sqrt((point[0] - lineStart[0]) ** 2 + (point[1] - lineStart[1]) ** 2);
        }
        
        // Calculate perpendicular distance
        const t = ((point[0] - lineStart[0]) * dx + (point[1] - lineStart[1]) * dy) / lenSq;
        
        let nearestX, nearestY;
        if (t < 0) {
            nearestX = lineStart[0];
            nearestY = lineStart[1];
        } else if (t > 1) {
            nearestX = lineEnd[0];
            nearestY = lineEnd[1];
        } else {
            nearestX = lineStart[0] + t * dx;
            nearestY = lineStart[1] + t * dy;
        }
        
        return Math.sqrt((point[0] - nearestX) ** 2 + (point[1] - nearestY) ** 2);
    }
    
    enterEditMode() {
        this.isEditingPolygon = true;
        
        // Show polygon controls
        const polygonControls = document.getElementById('polygon-controls');
        if (polygonControls) {
            polygonControls.style.display = 'block';
        }
        
        // Show edit controls, hide draw controls
        const drawControls = document.getElementById('polygon-draw-controls');
        const editControls = document.getElementById('polygon-edit-controls');
        const instructions = document.getElementById('polygon-mode-instructions');
        
        if (drawControls) drawControls.style.display = 'none';
        if (editControls) editControls.style.display = 'block';
        if (instructions) {
            instructions.innerHTML = '<strong>Edit Mode:</strong> Drag vertices to move. Click on edge to add vertex. Right-click to delete.';
        }
        
        // Update counter
        this.updatePolygonControls();
        
        // Set app mode to polygon
        if (window.app) {
            window.app.setMode('polygon');
        }
    }
    
    finishEditing() {
        this.isEditingPolygon = false;
        
        // Update the mask from edited vertices
        this.currentMask = this.createMaskFromPolygon();
        this.previewContours = [this.polygonVertices.slice()];
        
        // Hide edit controls, show draw controls
        const drawControls = document.getElementById('polygon-draw-controls');
        const editControls = document.getElementById('polygon-edit-controls');
        const instructions = document.getElementById('polygon-mode-instructions');
        
        if (drawControls) drawControls.style.display = 'block';
        if (editControls) editControls.style.display = 'none';
        if (instructions) {
            instructions.textContent = 'Click to add vertices. Double-click or press Enter to close polygon.';
        }
        
        // Enable add segment button
        document.getElementById('add-segment-btn').disabled = false;
        document.getElementById('edit-mask-btn').disabled = false;
        
        if (window.app) {
            window.app.showNotification('Polygon editing complete!', 'success');
        }
        
        if (window.canvasManager) {
            window.canvasManager.redraw();
        }
    }
    
    // Handle vertex interaction during edit mode
    handleEditModeClick(x, y, event) {
        const coords = { x, y };
        
        // Check if clicking on a vertex
        const vertexIndex = this.findVertexAtPosition(coords.x, coords.y);
        
        if (event.button === 2) {  // Right click - delete vertex
            if (vertexIndex >= 0 && this.polygonVertices.length > 3) {
                this.polygonVertices.splice(vertexIndex, 1);
                this.updatePolygonControls();
                if (window.canvasManager) window.canvasManager.redraw();
                return true;
            }
        } else if (vertexIndex >= 0) {
            // Select vertex for dragging
            this.selectedVertexIndex = vertexIndex;
            this.isDraggingVertex = true;
            return true;
        } else {
            // Check if clicking on an edge to add a new vertex
            const edgeInfo = this.findEdgeAtPosition(coords.x, coords.y);
            if (edgeInfo) {
                // Insert new vertex at click position
                this.polygonVertices.splice(edgeInfo.insertIndex, 0, [coords.x, coords.y]);
                
                // IMMEDIATELY start dragging the new vertex (click-and-drag behavior)
                this.selectedVertexIndex = edgeInfo.insertIndex;
                this.isDraggingVertex = true;
                
                this.updatePolygonControls();
                if (window.canvasManager) window.canvasManager.redraw();
                return true;
            }
        }
        
        return false;
    }
    
    handleEditModeMove(x, y) {
        if (this.isDraggingVertex && this.selectedVertexIndex >= 0) {
            this.polygonVertices[this.selectedVertexIndex] = [x, y];
            if (window.canvasManager) window.canvasManager.redraw();
            return true;
        }
        return false;
    }
    
    handleEditModeUp() {
        this.isDraggingVertex = false;
        this.selectedVertexIndex = -1;
    }
    
    findVertexAtPosition(x, y) {
        if (!window.canvasManager) return -1;
        
        const scale = window.canvasManager.scale;
        const hitRadius = this.vertexHitRadius / scale;
        
        for (let i = 0; i < this.polygonVertices.length; i++) {
            const [vx, vy] = this.polygonVertices[i];
            const dist = Math.sqrt((x - vx) ** 2 + (y - vy) ** 2);
            if (dist <= hitRadius) {
                return i;
            }
        }
        return -1;
    }
    
    findEdgeAtPosition(x, y) {
        if (!window.canvasManager || this.polygonVertices.length < 2) return null;
        
        const scale = window.canvasManager.scale;
        const hitRadius = this.vertexHitRadius / scale;
        
        for (let i = 0; i < this.polygonVertices.length; i++) {
            const p1 = this.polygonVertices[i];
            const p2 = this.polygonVertices[(i + 1) % this.polygonVertices.length];
            
            const dist = this.perpendicularDistance([x, y], p1, p2);
            
            // Also check if point is within the segment bounds
            const minX = Math.min(p1[0], p2[0]) - hitRadius;
            const maxX = Math.max(p1[0], p2[0]) + hitRadius;
            const minY = Math.min(p1[1], p2[1]) - hitRadius;
            const maxY = Math.max(p1[1], p2[1]) + hitRadius;
            
            if (dist <= hitRadius && x >= minX && x <= maxX && y >= minY && y <= maxY) {
                return {
                    edgeIndex: i,
                    insertIndex: i + 1
                };
            }
        }
        return null;
    }
    
    setupPolygonControls() {
        // Close polygon button
        const closePolygonBtn = document.getElementById('close-polygon-btn');
        if (closePolygonBtn) {
            closePolygonBtn.addEventListener('click', () => {
                this.closePolygon();
            });
        }
        
        // Clear polygon button
        const clearPolygonBtn = document.getElementById('clear-polygon-btn');
        if (clearPolygonBtn) {
            clearPolygonBtn.addEventListener('click', () => {
                this.clearPolygon();
            });
        }
        
        // Undo last polygon point button
        const undoPolygonPointBtn = document.getElementById('undo-polygon-point-btn');
        if (undoPolygonPointBtn) {
            undoPolygonPointBtn.addEventListener('click', () => {
                this.removeLastPolygonPoint();
            });
        }
        
        // Keyboard shortcut to close polygon
        document.addEventListener('keydown', (e) => {
            if (window.app && window.app.currentMode === 'polygon') {
                if (e.key === 'Enter' && this.polygonVertices.length >= 3) {
                    this.closePolygon();
                } else if (e.key === 'Escape') {
                    // If there are points, remove the last one; otherwise clear all
                    if (this.polygonVertices.length > 0) {
                        this.removeLastPolygonPoint();
                    } else {
                        this.clearPolygon();
                    }
                } else if (e.key === 'Backspace') {
                    // Backspace always removes last point
                    if (this.polygonVertices.length > 0) {
                        this.removeLastPolygonPoint();
                    }
                }
            }
        });
    }
    
    removeLastPolygonPoint() {
        if (this.polygonVertices.length > 0) {
            this.polygonVertices.pop();
            this.updatePolygonControls();
            if (window.canvasManager) {
                window.canvasManager.redraw();
            }
        }
    }
    
    updatePolygonControls() {
        const numPoints = this.polygonVertices.length;
        
        // Update counter
        const counter = document.getElementById('polygon-points-counter');
        if (counter) {
            counter.textContent = `Points: ${numPoints}`;
        }
        
        // Update button states
        const closeBtn = document.getElementById('close-polygon-btn');
        const clearBtn = document.getElementById('clear-polygon-btn');
        const undoBtn = document.getElementById('undo-polygon-point-btn');
        
        if (closeBtn) closeBtn.disabled = numPoints < 3;
        if (clearBtn) clearBtn.disabled = numPoints === 0;
        if (undoBtn) undoBtn.disabled = numPoints === 0;
    }
    
    setupCanvasInteraction() {
        const canvas = document.getElementById('main-canvas');
        
        // Prevent context menu on right-click (for vertex deletion)
        canvas.addEventListener('contextmenu', (e) => {
            if (this.isEditingPolygon) {
                e.preventDefault();
            }
        });
        
        canvas.addEventListener('mousedown', (e) => {
            if (!window.app || !window.app.sessionId) return;
            if (!window.canvasManager) return;
            
            const coords = window.canvasManager.getImageCoordinates(e);
            
            // Handle polygon edit mode
            if (this.isEditingPolygon && window.app.currentMode === 'polygon') {
                if (this.handleEditModeClick(coords.x, coords.y, e)) {
                    e.preventDefault();
                    e.stopPropagation();
                    return;
                }
            }
            
            // Box mode
            if (window.app.currentMode === 'box') {
                if (e.button !== 0 || e.ctrlKey) return;
                console.log('Box mode: mousedown');
                this.boxStart = coords;
                this.isDrawingBox = true;
            }
        });
        
        canvas.addEventListener('mousemove', (e) => {
            if (!window.canvasManager) return;
            
            const coords = window.canvasManager.getImageCoordinates(e);
            
            // Handle vertex dragging in edit mode
            if (this.isEditingPolygon && this.isDraggingVertex) {
                this.handleEditModeMove(coords.x, coords.y);
                e.preventDefault();
                return;
            }
            
            // Box preview
            if (this.isDrawingBox) {
                this.boxEnd = coords;
                this.drawBoxPreview();
            }
        });
        
        canvas.addEventListener('mouseup', (e) => {
            // Handle edit mode mouse up
            if (this.isEditingPolygon && this.isDraggingVertex) {
                this.handleEditModeUp();
                e.preventDefault();
                return;
            }
            
            // Box mode
            if (this.isDrawingBox) {
                console.log('Box mode: mouseup');
                if (!window.canvasManager) return;
                
                const coords = window.canvasManager.getImageCoordinates(e);
                this.boxEnd = coords;
                this.isDrawingBox = false;
                this.segmentWithBox();
            }
        });
        
        canvas.addEventListener('click', (e) => {
            console.log('Canvas click event triggered', {
                hasApp: !!window.app,
                hasSessionId: window.app ? !!window.app.sessionId : false,
                currentMode: window.app ? window.app.currentMode : 'unknown',
                isEditingPolygon: this.isEditingPolygon
            });
            
            if (!window.app || !window.app.sessionId) {
                if (window.app) {
                    window.app.showNotification('Please upload an image first', 'warning');
                }
                return;
            }
            
            if (!window.canvasManager) {
                console.error('Canvas manager not available');
                return;
            }
            
            // Skip if in edit mode (handled by mousedown)
            if (this.isEditingPolygon) {
                return;
            }
            
            const coords = window.canvasManager.getImageCoordinates(e);
            console.log('Coordinates:', coords, 'Mode:', window.app.currentMode);
            
            switch(window.app.currentMode) {
                case 'point':
                    console.log('Adding point at', coords);
                    this.addPoint(coords.x, coords.y);
                    break;
                case 'polygon':
                    console.log('Adding polygon vertex at', coords);
                    this.addPolygonVertex(coords.x, coords.y);
                    break;
                case 'rotation':
                    console.log('Setting rotation center at', coords);
                    window.app.setRotationCenter(coords.x, coords.y);
                    break;
            }
        });
        
        // Double-click to close polygon
        canvas.addEventListener('dblclick', (e) => {
            if (!window.app || window.app.currentMode !== 'polygon') return;
            if (this.isEditingPolygon) return;  // Don't close in edit mode
            if (this.polygonVertices.length >= 3) {
                e.preventDefault();
                this.closePolygon();
            }
        });
    }
    
    addPolygonVertex(x, y) {
        if (this.isPolygonClosed) {
            // Reset if polygon was already closed
            this.clearPolygon();
        }
        
        this.polygonVertices.push([x, y]);
        console.log('Polygon vertices:', this.polygonVertices.length);
        
        // Update buttons and counter
        this.updatePolygonControls();
        
        // Redraw canvas to show polygon
        if (window.canvasManager) {
            window.canvasManager.redraw();
            this.drawPolygonPreview();
        }
    }
    
    closePolygon() {
        if (this.polygonVertices.length < 3) {
            if (window.app) {
                window.app.showNotification('Need at least 3 vertices to create a polygon', 'warning');
            }
            return;
        }
        
        console.log('Closing polygon with', this.polygonVertices.length, 'vertices');
        
        this.isPolygonClosed = true;
        this.isManualMask = true;  // This is a manual mask
        
        // Convert polygon to contours format for display
        this.previewContours = [this.polygonVertices.slice()];  // Clone the vertices
        
        // Create a simple mask representation from polygon
        // The actual mask will be created on the backend from contours
        this.currentMask = this.createMaskFromPolygon();
        
        // Redraw with filled polygon
        if (window.canvasManager) {
            window.canvasManager.redraw();
        }
        
        // Enable add segment button
        document.getElementById('add-segment-btn').disabled = false;
        document.getElementById('clear-preview-btn').disabled = false;
        
        if (window.app) {
            window.app.showNotification('Polygon created! Click "Add Segment" to confirm.', 'success');
        }
    }
    
    createMaskFromPolygon() {
        // Create a mask array from polygon vertices
        // This will be processed on the backend to create the actual binary mask
        // For now, we just return the polygon data - the backend will convert it
        return {
            type: 'polygon',
            vertices: this.polygonVertices.slice(),
            isManual: true
        };
    }
    
    clearPolygon() {
        this.polygonVertices = [];
        this.isPolygonClosed = false;
        this.isManualMask = false;
        
        // Update buttons and counter
        this.updatePolygonControls();
        
        // Clear preview if it was from polygon
        if (this.currentMask && this.currentMask.type === 'polygon') {
            this.currentMask = null;
            this.previewContours = null;
            document.getElementById('add-segment-btn').disabled = true;
            document.getElementById('clear-preview-btn').disabled = true;
        }
        
        // Redraw canvas
        if (window.canvasManager) {
            window.canvasManager.redraw();
        }
    }
    
    drawPolygonPreview() {
        if (!window.canvasManager || this.polygonVertices.length === 0) return;
        
        const ctx = window.canvasManager.ctx;
        const scale = window.canvasManager.scale;
        const offsetX = window.canvasManager.offsetX;
        const offsetY = window.canvasManager.offsetY;
        
        ctx.save();
        
        // Different style for edit mode
        const isEditing = this.isEditingPolygon;
        
        // Draw polygon lines
        ctx.strokeStyle = isEditing ? '#00aaff' : (this.isPolygonClosed ? '#00ff00' : '#ffff00');
        ctx.lineWidth = isEditing ? 2.5 : 2;
        ctx.setLineDash(this.isPolygonClosed ? [] : [5, 5]);
        
        ctx.beginPath();
        
        for (let i = 0; i < this.polygonVertices.length; i++) {
            const [x, y] = this.polygonVertices[i];
            const canvasX = x * scale + offsetX;
            const canvasY = y * scale + offsetY;
            
            if (i === 0) {
                ctx.moveTo(canvasX, canvasY);
            } else {
                ctx.lineTo(canvasX, canvasY);
            }
        }
        
        // Close path if polygon is closed
        if (this.isPolygonClosed && this.polygonVertices.length > 2) {
            ctx.closePath();
            ctx.fillStyle = isEditing ? 'rgba(0, 170, 255, 0.15)' : 'rgba(0, 255, 0, 0.2)';
            ctx.fill();
        }
        
        ctx.stroke();
        
        // Draw vertices
        for (let i = 0; i < this.polygonVertices.length; i++) {
            const [x, y] = this.polygonVertices[i];
            const canvasX = x * scale + offsetX;
            const canvasY = y * scale + offsetY;
            
            const isSelected = (i === this.selectedVertexIndex);
            const vertexRadius = isEditing ? 8 : 6;
            
            ctx.beginPath();
            ctx.arc(canvasX, canvasY, vertexRadius, 0, 2 * Math.PI);
            
            // Vertex colors
            if (isSelected) {
                ctx.fillStyle = '#ff0000';  // Selected vertex is red
            } else if (isEditing) {
                ctx.fillStyle = '#00aaff';  // Edit mode vertices are blue
            } else if (i === 0) {
                ctx.fillStyle = '#ff6b6b';  // First vertex is light red
            } else {
                ctx.fillStyle = '#ffffff';  // Other vertices are white
            }
            
            ctx.fill();
            ctx.strokeStyle = isSelected ? '#ffffff' : '#000000';
            ctx.lineWidth = isSelected ? 2 : 1;
            ctx.setLineDash([]);
            ctx.stroke();
            
            // Draw vertex number (only in draw mode or if few vertices)
            if (!isEditing || this.polygonVertices.length <= 20) {
                ctx.fillStyle = '#000000';
                ctx.font = isEditing ? 'bold 10px Arial' : '10px Arial';
                ctx.fillText((i + 1).toString(), canvasX + 10, canvasY - 10);
            }
        }
        
        // In edit mode, draw hint for adding points on edges
        if (isEditing && this.polygonVertices.length >= 3) {
            ctx.fillStyle = 'rgba(0, 170, 255, 0.7)';
            ctx.font = '11px Arial';
            // Don't draw text hint on canvas - it's in the UI
        }
        
        ctx.restore();
    }
    
    addPoint(x, y) {
        console.log('addPoint called with:', x, y);
        
        // Get current point label (positive or negative)
        const labelRadio = document.querySelector('input[name="point-label"]:checked');
        const label = parseInt(labelRadio.value);
        
        console.log('Point label:', label);
        
        this.points.push([x, y]);
        this.labels.push(label);
        
        console.log('Total points:', this.points.length);
        
        // Redraw canvas to show the new point
        if (window.canvasManager) {
            window.canvasManager.redraw();
        }
        
        // Perform segmentation
        this.segmentWithPoints();
    }
    
    drawBoxPreview() {
        if (!this.boxStart || !this.boxEnd || !window.canvasManager) return;
        
        window.canvasManager.redraw();
        
        const ctx = window.canvasManager.ctx;
        const start = window.canvasManager.imageToCanvas(this.boxStart.x, this.boxStart.y);
        const end = window.canvasManager.imageToCanvas(this.boxEnd.x, this.boxEnd.y);
        
        ctx.save();
        ctx.strokeStyle = '#00ff00';
        ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        
        ctx.strokeRect(
            start.x,
            start.y,
            end.x - start.x,
            end.y - start.y
        );
        
        ctx.restore();
    }
    
    async segmentWithPoints() {
        if (this.points.length === 0) return;
        
        try {
            const response = await fetch('/api/segment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: app.sessionId,
                    prompt_type: 'point',
                    points: this.points,
                    labels: this.labels
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentMask = data.mask;
                this.previewContours = data.contours;
                this.isManualMask = false;  // SAM mask, not manual
                
                // Redraw canvas with preview
                if (window.canvasManager) {
                    window.canvasManager.redraw();
                }
                
                // Enable buttons
                document.getElementById('add-segment-btn').disabled = false;
                document.getElementById('clear-preview-btn').disabled = false;
                document.getElementById('edit-mask-btn').disabled = false;  // Enable edit
            } else {
                throw new Error(data.error || 'Segmentation failed');
            }
        } catch (error) {
            console.error('Segmentation error:', error);
            if (window.app) {
                app.showNotification('Segmentation failed: ' + error.message, 'error');
            }
        }
    }
    
    async segmentWithBox() {
        if (!this.boxStart || !this.boxEnd) return;
        
        // Calculate box coordinates
        const x1 = Math.min(this.boxStart.x, this.boxEnd.x);
        const y1 = Math.min(this.boxStart.y, this.boxEnd.y);
        const x2 = Math.max(this.boxStart.x, this.boxEnd.x);
        const y2 = Math.max(this.boxStart.y, this.boxEnd.y);
        
        try {
            const response = await fetch('/api/segment', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    session_id: app.sessionId,
                    prompt_type: 'box',
                    box: [x1, y1, x2, y2]
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.currentMask = data.mask;
                this.previewContours = data.contours;
                this.isManualMask = false;  // SAM mask, not manual
                
                // Redraw canvas with preview
                if (window.canvasManager) {
                    window.canvasManager.redraw();
                }
                
                // Enable buttons
                document.getElementById('add-segment-btn').disabled = false;
                document.getElementById('clear-preview-btn').disabled = false;
                document.getElementById('edit-mask-btn').disabled = false;  // Enable edit
            } else {
                throw new Error(data.error || 'Segmentation failed');
            }
        } catch (error) {
            console.error('Segmentation error:', error);
            if (window.app) {
                app.showNotification('Segmentation failed: ' + error.message, 'error');
            }
        }
        
        // Reset box
        this.boxStart = null;
        this.boxEnd = null;
    }
    
    clearCurrentSegment() {
        this.points = [];
        this.labels = [];
        this.boxStart = null;
        this.boxEnd = null;
        this.currentMask = null;
        this.previewContours = null;
        
        // Clear polygon mode
        this.polygonVertices = [];
        this.isPolygonClosed = false;
        this.isManualMask = false;
        
        // Clear editing mode
        this.isEditingPolygon = false;
        this.selectedVertexIndex = -1;
        this.isDraggingVertex = false;
        this.originalContour = null;  // Clear original contour
        
        // Update polygon buttons
        const closeBtn = document.getElementById('close-polygon-btn');
        const clearBtn = document.getElementById('clear-polygon-btn');
        const editMaskBtn = document.getElementById('edit-mask-btn');
        if (closeBtn) closeBtn.disabled = true;
        if (clearBtn) clearBtn.disabled = true;
        if (editMaskBtn) editMaskBtn.disabled = true;
        
        // Reset edit controls visibility
        const drawControls = document.getElementById('polygon-draw-controls');
        const editControls = document.getElementById('polygon-edit-controls');
        if (drawControls) drawControls.style.display = 'block';
        if (editControls) editControls.style.display = 'none';
        
        // Redraw canvas
        if (window.canvasManager) {
            window.canvasManager.redraw();
        }
    }
}
