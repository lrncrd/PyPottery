/**
 * PyPotteryTrace Interactive - Post-Processing Module
 * Handles batch export of vectorized files from current project
 */

class PostProcessingManager {
    constructor() {
        this.currentProjectId = null;
        this.vectorizedFolder = null;
        this.files = {
            svg: [],
            png: []
        };
        this.svgCache = new Map();  // Cache SVG content to avoid re-reading
        this.categories = new Set();
        this.selectedCategories = new Set();

        this.initializeEventListeners();
        this.checkForCurrentProject();
    }

    checkForCurrentProject() {
        // Check if a project is loaded
        setInterval(() => {
            const projectId = sessionStorage.getItem('current_project_id');
            const projectName = sessionStorage.getItem('current_project_name');

            if (projectId && projectId !== this.currentProjectId) {
                this.currentProjectId = projectId;
                this.updateProjectInfo(projectId, projectName);
            } else if (!projectId && this.currentProjectId) {
                // Project was unloaded
                this.currentProjectId = null;
                this.updateProjectInfo(null, null);
            }
        }, 1000);
    }

    updateProjectInfo(projectId, projectName) {
        const projectInfoDiv = document.getElementById('postprocess-project-info');
        const noProjectDiv = document.getElementById('postprocess-no-project');
        const loadBtn = document.getElementById('postprocess-load-folder-btn');
        const folderInfoDiv = document.getElementById('postprocess-folder-info');

        if (projectId && projectName) {
            // Show project info
            projectInfoDiv.style.display = 'block';
            noProjectDiv.style.display = 'none';
            // Hide the load button - we'll load when tab is activated
            if (loadBtn) loadBtn.style.display = 'none';

            document.getElementById('postprocess-project-name').textContent = projectName;
            document.getElementById('postprocess-folder-path').textContent = `projects/${projectId}/vectorized`;

            // Hide old folder info when switching projects
            folderInfoDiv.style.display = 'none';

            // Mark that we need to reload files when tab is activated
            this.needsReload = true;
        } else {
            // No project loaded
            projectInfoDiv.style.display = 'none';
            noProjectDiv.style.display = 'block';
            if (loadBtn) loadBtn.style.display = 'none';
            folderInfoDiv.style.display = 'none';
        }
    }

    initializeEventListeners() {
        // Load folder button (loads vectorized files from current project)
        const loadBtn = document.getElementById('postprocess-load-folder-btn');
        if (loadBtn) {
            loadBtn.addEventListener('click', () => {
                this.loadProjectVectorizedFiles();
            });
        }

        // Format checkboxes
        document.getElementById('postprocess-format-svg').addEventListener('change', () => {
            this.updateExportButton();
        });
        document.getElementById('postprocess-format-png').addEventListener('change', () => {
            this.updateExportButton();
            this.toggleRasterSettings();
        });
        document.getElementById('postprocess-format-jpg').addEventListener('change', () => {
            this.updateExportButton();
            this.toggleRasterSettings();
        });

        // Transparent background toggle
        document.getElementById('postprocess-transparent-bg').addEventListener('change', (e) => {
            const bgColorGroup = document.getElementById('postprocess-bg-color-group');
            bgColorGroup.style.display = e.target.checked ? 'none' : 'block';
        });

        // JPG quality slider
        document.getElementById('postprocess-jpg-quality').addEventListener('input', (e) => {
            document.getElementById('postprocess-jpg-quality-value').textContent = e.target.value;
        });

        // Epsilon slider
        document.getElementById('postprocess-epsilon').addEventListener('input', (e) => {
            document.getElementById('postprocess-epsilon-value').textContent = e.target.value;
        });

        // Smoothing slider
        document.getElementById('postprocess-smoothing').addEventListener('input', (e) => {
            document.getElementById('postprocess-smoothing-value').textContent = e.target.value;
        });

        // Select all categories
        document.getElementById('postprocess-select-all-categories').addEventListener('change', (e) => {
            const checkboxes = document.querySelectorAll('#postprocess-category-filters input[type="checkbox"]');
            checkboxes.forEach(cb => cb.checked = e.target.checked);
            this.updateSelectedCategories();
        });

        // Export button
        document.getElementById('postprocess-export-btn').addEventListener('click', () => {
            this.handleExport();
        });
    }

    /**
     * Load vectorized files from current project
     */
    async loadProjectVectorizedFiles() {
        if (!this.currentProjectId) {
            alert('No project loaded!');
            return;
        }

        try {
            // Show loading
            if (window.tabManager) {
                window.tabManager.showLoadingOverlay('Loading Vectorized Files...', 'Please wait while we load your files');
            }

            // Fetch vectorized files list from project
            const response = await fetch(`/api/projects/${this.currentProjectId}/images?folder=vectorized`);
            const data = await response.json();

            console.log('Vectorized files response:', data);

            if (!data.success) {
                if (window.tabManager) window.tabManager.hideLoadingOverlay();
                console.log('Error loading vectorized files:', data.error || 'Unknown error');
                return;
            }

            if (!data.images || data.images.length === 0) {
                if (window.tabManager) window.tabManager.hideLoadingOverlay();
                console.log('No vectorized files found in project yet');
                // Show empty state in UI
                this.updateFolderInfo();
                return;
            }

            console.log(`Loading ${data.images.length} vectorized files from project...`);

            // Clear previous data
            this.files.svg = [];
            this.files.png = [];
            this.categories.clear();
            this.svgCache.clear();

            // Fetch each file
            const files = [];
            for (const filename of data.images) {
                try {
                    console.log(`Fetching file: ${filename}`);
                    const fileResponse = await fetch(`/api/projects/${this.currentProjectId}/images/${filename}?folder=vectorized`);

                    if (!fileResponse.ok) {
                        console.error(`Failed to fetch ${filename}: ${fileResponse.status}`);
                        continue;
                    }

                    const blob = await fileResponse.blob();

                    // Create File object
                    const file = new File([blob], filename, { type: blob.type });
                    files.push(file);

                    // Process file
                    const ext = filename.split('.').pop().toLowerCase();
                    if (ext === 'svg') {
                        // Read SVG content
                        const content = await file.text();
                        this.files.svg.push(file);
                        this.svgCache.set(filename, content);

                        // Extract categories
                        const allCategories = this.extractAllCategoriesFromSVG(content);
                        allCategories.forEach(cat => this.categories.add(cat));
                    } else if (ext === 'png') {
                        this.files.png.push(file);
                        const category = this.extractCategory(filename);
                        if (category) {
                            this.categories.add(category);
                        }
                    }
                } catch (err) {
                    console.error(`Failed to load file ${filename}:`, err);
                }
            }

            console.log(`✓ Loaded ${this.files.svg.length} SVG, ${this.files.png.length} PNG`);
            console.log(`✓ Found categories:`, Array.from(this.categories));

            // Hide loading
            if (window.tabManager) window.tabManager.hideLoadingOverlay();

            if (this.files.svg.length === 0 && this.files.png.length === 0) {
                console.log('No valid SVG or PNG files found after loading');
                return;
            }

            // Update UI
            this.updateFolderInfo();
            this.populateCategoryFilters();
            this.updateExportButton();

        } catch (error) {
            console.error('Error loading project vectorized files:', error);
            if (window.tabManager) window.tabManager.hideLoadingOverlay();
        }
    }

    handleFolderSelection(event) {
        const files = Array.from(event.target.files);

        if (files.length === 0) {
            return;
        }

        // Get folder path from first file
        const firstFile = files[0];
        const folderPath = firstFile.webkitRelativePath.split('/')[0];

        // Validate folder name (should end with _vectorized)
        if (!folderPath.endsWith('_vectorized')) {
            const suggestion = this.workingFolder ?
                `\n\nSuggested folder: ${this.workingFolder}` : '';
            alert(`⚠️ Please select a folder ending with "_vectorized"${suggestion}`);
            return;
        }

        this.selectedFolder = folderPath;
        this.files.svg = [];
        this.files.png = [];
        this.categories.clear();
        this.svgCache.clear();  // Clear cache for new folder

        // Process files - read SVG content to extract categories from layers
        const processPromises = Array.from(files).map(file => {
            const ext = file.name.split('.').pop().toLowerCase();

            if (ext === 'svg') {
                // Read SVG content to extract ALL categories from layer IDs
                return file.text().then(content => {
                    this.files.svg.push(file);
                    this.svgCache.set(file.name, content);  // Cache SVG content
                    const allCategories = this.extractAllCategoriesFromSVG(content);
                    console.log(`📄 ${file.name} → Categories:`, allCategories);
                    // Add all unique categories found in this SVG
                    allCategories.forEach(cat => this.categories.add(cat));
                });
            } else if (ext === 'png') {
                this.files.png.push(file);
                // For PNG, use filename-based extraction (fallback)
                const category = this.extractCategory(file.name);
                if (category) {
                    this.categories.add(category);
                }
                return Promise.resolve();
            }
            return Promise.resolve();
        });

        // Wait for all files to be processed
        Promise.all(processPromises).then(() => {
            console.log(`✓ Loaded ${this.files.svg.length} SVG, ${this.files.png.length} PNG`);
            console.log(`✓ Found categories:`, Array.from(this.categories));

            // Update UI
            this.updateFolderInfo();
            this.populateCategoryFilters();
            this.updateExportButton();
        });
    }

    extractCategory(filename) {
        // DEPRECATED: Category should be extracted from SVG content, not filename
        // Kept for backward compatibility with PNG files
        const categories = [
            'Profile_Mirrored',
            'Symmetry_Line',
            'Diameter',
            'Profile',
            'Prospectus',
            'Decoration',
            'Handle',
            'Application',
            'Background'
        ];

        const filenameStr = String(filename);
        for (const cat of categories) {
            if (filenameStr.includes(cat)) {
                return cat;
            }
        }
        return 'Other';
    }

    extractCategoryFromSVG(svgContent) {
        /**
         * Extract PRIMARY category from SVG layer IDs
         * Used for filtering individual files
         */
        const allCategories = this.extractAllCategoriesFromSVG(svgContent);
        return allCategories.length > 0 ? allCategories[0] : 'Other';
    }

    removeUnselectedLayersFromSVG(svgContent, selectedCategories) {
        /**
         * Remove layers from SVG that correspond to unselected categories
         * Returns modified SVG content with only selected layers
         */
        try {
            const parser = new DOMParser();
            const svgDoc = parser.parseFromString(svgContent, 'image/svg+xml');

            // Find all <g> elements with id starting with "layer_"
            const groups = svgDoc.querySelectorAll('g[id^="layer_"]');

            console.log(`  Filtering layers: found ${groups.length} layer groups`);

            for (const g of groups) {
                const layerId = g.getAttribute('id');
                if (!layerId) continue;

                // Extract category after "layer_" prefix
                const categoryRaw = layerId.replace('layer_', '');

                // Map to standard category name (same logic as extractAllCategoriesFromSVG)
                let category = null;

                if (categoryRaw.includes('Profile_Mirrored') || categoryRaw.includes('Mirrored')) {
                    category = 'Profile_Mirrored';
                } else if (categoryRaw.includes('Symmetry')) {
                    category = 'Symmetry_Line';
                } else if (categoryRaw.includes('Diameter')) {
                    category = 'Diameter';
                } else if (categoryRaw.includes('Profile')) {
                    category = 'Profile';
                } else if (categoryRaw.includes('Application')) {
                    category = 'Application';
                } else if (categoryRaw.includes('Handle')) {
                    category = 'Handle';
                } else if (categoryRaw.includes('Decoration')) {
                    category = 'Decoration';
                } else if (categoryRaw.includes('Running')) {
                    category = 'Running_Element';
                } else if (categoryRaw.includes('Detail')) {
                    category = 'Detail';
                } else if (categoryRaw.includes('Prospectus')) {
                    category = 'Prospectus';
                } else {
                    const firstPart = categoryRaw.split('_')[0];
                    category = firstPart || 'Other';
                }

                // Remove layer if category is NOT selected
                if (!selectedCategories.has(category)) {
                    console.log(`  ✂️ Removing layer: ${layerId} (category: ${category})`);
                    g.remove();
                } else {
                    console.log(`  ✓ Keeping layer: ${layerId} (category: ${category})`);
                }
            }

            // Serialize back to string
            const serializer = new XMLSerializer();
            const modifiedSvg = serializer.serializeToString(svgDoc);

            return modifiedSvg;

        } catch (e) {
            console.error('Error filtering SVG layers:', e);
            return svgContent; // Return original if error
        }
    }

    applyStrokeWidthsAndColorsToSVG(svgContent, strokeWidths) {
        /**
         * Apply custom stroke widths and ensure black colors to SVG layers
         * Returns modified SVG content
         */
        try {
            const parser = new DOMParser();
            const svgDoc = parser.parseFromString(svgContent, 'image/svg+xml');

            // Find all <g> elements with id starting with "layer_"
            const groups = svgDoc.querySelectorAll('g[id^="layer_"]');

            console.log(`  Applying stroke widths to ${groups.length} layer groups`);

            for (const g of groups) {
                const layerId = g.getAttribute('id');
                if (!layerId) continue;

                // Extract category
                const categoryRaw = layerId.replace('layer_', '');
                let category = null;

                if (categoryRaw.includes('Profile_Mirrored') || categoryRaw.includes('Mirrored')) {
                    category = 'Profile_Mirrored';
                } else if (categoryRaw.includes('Symmetry')) {
                    category = 'Symmetry_Line';
                } else if (categoryRaw.includes('Diameter')) {
                    category = 'Diameter';
                } else if (categoryRaw.includes('Profile')) {
                    category = 'Profile';
                } else if (categoryRaw.includes('Application')) {
                    category = 'Application';
                } else if (categoryRaw.includes('Handle')) {
                    category = 'Handle';
                } else if (categoryRaw.includes('Decoration')) {
                    category = 'Decoration';
                } else if (categoryRaw.includes('Running')) {
                    category = 'Running_Element';
                } else if (categoryRaw.includes('Detail')) {
                    category = 'Detail';
                } else if (categoryRaw.includes('Prospectus')) {
                    category = 'Prospectus';
                }

                if (category && strokeWidths[category] !== undefined) {
                    const strokeWidth = strokeWidths[category];

                    // Apply to group
                    g.setAttribute('stroke-width', strokeWidth);

                    // Apply black color to main elements (not construction lines)
                    if (category !== 'Symmetry_Line' && category !== 'Diameter') {
                        g.setAttribute('stroke', '#000000');
                    } else {
                        // Keep gray for construction lines
                        if (category === 'Symmetry_Line') {
                            g.setAttribute('stroke', '#999999');
                        } else if (category === 'Diameter') {
                            g.setAttribute('stroke', '#666666');
                        }
                    }

                    // Also apply to all path elements inside
                    const paths = g.querySelectorAll('path, polyline, line, circle, rect');
                    paths.forEach(path => {
                        path.setAttribute('stroke-width', strokeWidth);
                        if (category !== 'Symmetry_Line' && category !== 'Diameter') {
                            path.setAttribute('stroke', '#000000');
                        }
                    });

                    console.log(`  ✓ Applied width ${strokeWidth} to layer: ${layerId} (${category})`);
                }
            }

            // Serialize back to string
            const serializer = new XMLSerializer();
            const modifiedSvg = serializer.serializeToString(svgDoc);

            return modifiedSvg;

        } catch (e) {
            console.error('Error applying stroke widths:', e);
            return svgContent; // Return original if error
        }
    }

    applyVectorizationParametersToSVG(svgContent, epsilon, smoothing) {
        /**
         * Re-process SVG paths with new epsilon (simplification) and smoothing
         * Only applies to main elements (Profile, Application, Handle, Decoration, Running_Element, Detail, Prospectus)
         * Returns modified SVG content
         */

        // If both parameters are 0, skip processing
        if (epsilon === 0 && smoothing === 0) {
            console.log(`  ⏭️ Skipping vectorization (both parameters are 0)`);
            return svgContent;
        }

        try {
            const parser = new DOMParser();
            const svgDoc = parser.parseFromString(svgContent, 'image/svg+xml');

            // Main element categories that should be re-vectorized
            const mainCategories = ['Profile', 'Profile_Mirrored', 'Prospectus', 'Application', 'Handle', 'Decoration', 'Running_Element', 'Running_Element_Mirrored', 'Detail'];

            // Find all <g> elements with id starting with "layer_"
            const groups = svgDoc.querySelectorAll('g[id^="layer_"]');

            console.log(`  Applying vectorization parameters (ε=${epsilon}, s=${smoothing}) to main elements`);

            for (const g of groups) {
                const layerId = g.getAttribute('id');
                if (!layerId) continue;

                // Extract category
                const categoryRaw = layerId.replace('layer_', '');
                let category = null;

                if (categoryRaw.includes('Profile_Mirrored') || categoryRaw.includes('Mirrored')) {
                    category = 'Profile_Mirrored';
                } else if (categoryRaw.includes('Symmetry')) {
                    category = 'Symmetry_Line';
                } else if (categoryRaw.includes('Diameter')) {
                    category = 'Diameter';
                } else if (categoryRaw.includes('Profile')) {
                    category = 'Profile';
                } else if (categoryRaw.includes('Application')) {
                    category = 'Application';
                } else if (categoryRaw.includes('Handle')) {
                    category = 'Handle';
                } else if (categoryRaw.includes('Decoration')) {
                    category = 'Decoration';
                } else if (categoryRaw.includes('Running')) {
                    category = 'Running_Element';
                } else if (categoryRaw.includes('Detail')) {
                    category = 'Detail';
                } else if (categoryRaw.includes('Prospectus')) {
                    category = 'Prospectus';
                }

                // Only process main elements
                if (category && mainCategories.includes(category)) {
                    // Process all path elements inside this group
                    const paths = g.querySelectorAll('path');

                    paths.forEach(path => {
                        const dAttr = path.getAttribute('d');
                        if (!dAttr) return;

                        try {
                            // Parse path data
                            const points = this.parsePathData(dAttr);
                            if (points.length < 2) return;

                            // Apply simplification (Douglas-Peucker algorithm)
                            let simplifiedPoints = this.douglasPeucker(points, epsilon);

                            // Apply smoothing if needed
                            if (smoothing > 0) {
                                simplifiedPoints = this.smoothPath(simplifiedPoints, smoothing);
                            }

                            // Reconstruct path data
                            const newD = this.pointsToPathData(simplifiedPoints);
                            path.setAttribute('d', newD);

                        } catch (err) {
                            console.warn(`  ⚠️ Could not process path in ${layerId}:`, err);
                        }
                    });

                    console.log(`  ✓ Re-vectorized ${paths.length} paths in layer: ${layerId} (${category})`);
                }
            }

            // Serialize back to string
            const serializer = new XMLSerializer();
            const modifiedSvg = serializer.serializeToString(svgDoc);

            return modifiedSvg;

        } catch (e) {
            console.error('Error applying vectorization parameters:', e);
            return svgContent; // Return original if error
        }
    }

    parsePathData(d) {
        /**
         * Parse SVG path data string into array of {x, y} points
         * Simplified parser - handles M, L, C commands
         */
        const points = [];
        const commands = d.match(/[MLCZmlcz][^MLCZmlcz]*/g) || [];

        let currentX = 0, currentY = 0;

        for (const cmd of commands) {
            const type = cmd[0];
            const coords = cmd.slice(1).trim().split(/[\s,]+/).map(parseFloat).filter(n => !isNaN(n));

            if (type === 'M' || type === 'm') {
                for (let i = 0; i < coords.length; i += 2) {
                    if (type === 'M') {
                        currentX = coords[i];
                        currentY = coords[i + 1];
                    } else {
                        currentX += coords[i];
                        currentY += coords[i + 1];
                    }
                    points.push({ x: currentX, y: currentY });
                }
            } else if (type === 'L' || type === 'l') {
                for (let i = 0; i < coords.length; i += 2) {
                    if (type === 'L') {
                        currentX = coords[i];
                        currentY = coords[i + 1];
                    } else {
                        currentX += coords[i];
                        currentY += coords[i + 1];
                    }
                    points.push({ x: currentX, y: currentY });
                }
            } else if (type === 'C' || type === 'c') {
                // For curves, just take the end point (ignore control points for simplification)
                for (let i = 0; i < coords.length; i += 6) {
                    if (type === 'C') {
                        currentX = coords[i + 4];
                        currentY = coords[i + 5];
                    } else {
                        currentX += coords[i + 4];
                        currentY += coords[i + 5];
                    }
                    points.push({ x: currentX, y: currentY });
                }
            }
        }

        return points;
    }

    douglasPeucker(points, epsilon) {
        /**
         * Douglas-Peucker line simplification algorithm
         */
        if (points.length < 3) return points;

        let maxDist = 0;
        let maxIndex = 0;
        const end = points.length - 1;

        for (let i = 1; i < end; i++) {
            const dist = this.perpendicularDistance(points[i], points[0], points[end]);
            if (dist > maxDist) {
                maxDist = dist;
                maxIndex = i;
            }
        }

        if (maxDist > epsilon) {
            const left = this.douglasPeucker(points.slice(0, maxIndex + 1), epsilon);
            const right = this.douglasPeucker(points.slice(maxIndex), epsilon);
            return left.slice(0, -1).concat(right);
        } else {
            return [points[0], points[end]];
        }
    }

    perpendicularDistance(point, lineStart, lineEnd) {
        /**
         * Calculate perpendicular distance from point to line
         */
        const dx = lineEnd.x - lineStart.x;
        const dy = lineEnd.y - lineStart.y;
        const norm = Math.sqrt(dx * dx + dy * dy);

        if (norm === 0) {
            return Math.sqrt(
                (point.x - lineStart.x) ** 2 + (point.y - lineStart.y) ** 2
            );
        }

        return Math.abs(
            dy * point.x - dx * point.y + lineEnd.x * lineStart.y - lineEnd.y * lineStart.x
        ) / norm;
    }

    smoothPath(points, factor) {
        /**
         * Apply simple moving average smoothing to path points
         */
        if (points.length < 3 || factor === 0) return points;

        const smoothed = [];
        const window = Math.max(1, Math.floor(factor * 5)); // Window size based on factor

        for (let i = 0; i < points.length; i++) {
            if (i === 0 || i === points.length - 1) {
                // Keep first and last points unchanged
                smoothed.push(points[i]);
            } else {
                let sumX = 0, sumY = 0, count = 0;

                for (let j = Math.max(0, i - window); j <= Math.min(points.length - 1, i + window); j++) {
                    sumX += points[j].x;
                    sumY += points[j].y;
                    count++;
                }

                smoothed.push({
                    x: sumX / count,
                    y: sumY / count
                });
            }
        }

        return smoothed;
    }

    pointsToPathData(points) {
        /**
         * Convert array of points back to SVG path data string
         */
        if (points.length === 0) return '';

        let d = `M ${points[0].x.toFixed(2)} ${points[0].y.toFixed(2)}`;

        for (let i = 1; i < points.length; i++) {
            d += ` L ${points[i].x.toFixed(2)} ${points[i].y.toFixed(2)}`;
        }

        return d;
    }

    extractAllCategoriesFromSVG(svgContent) {
        /**
         * Extract ALL categories from SVG layer IDs like 'layer_Profile_Mirrored'
         * Returns array of unique categories found in the SVG
         */
        const categoriesFound = new Set();

        try {
            const parser = new DOMParser();
            const svgDoc = parser.parseFromString(svgContent, 'image/svg+xml');

            // Find all <g> elements with id starting with "layer_"
            const groups = svgDoc.querySelectorAll('g[id^="layer_"]');

            console.log(`  Parsing SVG: found ${groups.length} layer groups`);

            for (const g of groups) {
                const layerId = g.getAttribute('id');
                if (!layerId) continue;

                // Extract category after "layer_" prefix
                const categoryRaw = layerId.replace('layer_', '');

                console.log(`  Found layer: ${layerId} → Raw: ${categoryRaw}`);

                // Handle special cases with priority
                let category = null;
                if (categoryRaw.includes('Profile_Mirrored') || categoryRaw.includes('Mirrored')) {
                    category = 'Profile_Mirrored';
                } else if (categoryRaw.includes('Symmetry')) {
                    category = 'Symmetry_Line';
                } else if (categoryRaw.includes('Diameter')) {
                    category = 'Diameter';
                } else if (categoryRaw.includes('Profile')) {
                    category = 'Profile';
                } else if (categoryRaw.includes('Application')) {
                    category = 'Application';
                } else if (categoryRaw.includes('Handle')) {
                    category = 'Handle';
                } else if (categoryRaw.includes('Decoration')) {
                    category = 'Decoration';
                } else if (categoryRaw.includes('Running')) {
                    category = 'Running_Element';
                } else if (categoryRaw.includes('Detail')) {
                    category = 'Detail';
                } else {
                    // Return first part before underscore
                    const firstPart = categoryRaw.split('_')[0];
                    category = firstPart || 'Other';
                }

                if (category && category !== 'Other') {
                    categoriesFound.add(category);
                    console.log(`  → Mapped to category: ${category}`);
                }
            }
        } catch (e) {
            console.error('Error parsing SVG for categories:', e);
        }

        const categoriesArray = Array.from(categoriesFound);
        if (categoriesArray.length === 0) {
            categoriesArray.push('Other');
        }
        console.log(`  Final categories for this SVG:`, categoriesArray);
        return categoriesArray;
    }

    updateFolderInfo() {
        const folderInfo = document.getElementById('postprocess-folder-info');
        const svgCount = document.getElementById('postprocess-svg-count');
        const pngCount = document.getElementById('postprocess-png-count');

        if (svgCount) svgCount.textContent = this.files.svg.length || 0;
        if (pngCount) pngCount.textContent = this.files.png.length || 0;

        if (folderInfo) folderInfo.style.display = 'block';

        // Update categories display
        this.updateCategoriesDisplay();
    }

    updateCategoriesDisplay() {
        const categoriesList = document.getElementById('postprocess-categories-list');
        categoriesList.innerHTML = '';

        Array.from(this.categories).sort().forEach(category => {
            const badge = document.createElement('span');
            badge.className = 'postprocess-category-badge';
            badge.textContent = category;
            categoriesList.appendChild(badge);
        });
    }

    populateCategoryFilters() {
        const container = document.getElementById('postprocess-category-filters');
        container.innerHTML = '';

        Array.from(this.categories).sort().forEach(category => {
            const label = document.createElement('label');
            label.innerHTML = `
                <input type="checkbox" class="category-filter-checkbox" value="${category}" checked>
                ${category}
            `;
            container.appendChild(label);

            // Add event listener
            label.querySelector('input').addEventListener('change', () => {
                this.updateSelectedCategories();
            });
        });

        this.updateSelectedCategories();
    }

    updateSelectedCategories() {
        this.selectedCategories.clear();

        const checkboxes = document.querySelectorAll('#postprocess-category-filters input[type="checkbox"]:checked');
        checkboxes.forEach(cb => {
            this.selectedCategories.add(cb.value);
        });

        this.updateExportButton();
    }

    toggleRasterSettings() {
        const pngChecked = document.getElementById('postprocess-format-png').checked;
        const jpgChecked = document.getElementById('postprocess-format-jpg').checked;
        const rasterSettings = document.getElementById('postprocess-raster-settings');

        rasterSettings.style.display = (pngChecked || jpgChecked) ? 'block' : 'none';
    }

    updateExportButton() {
        const exportBtn = document.getElementById('postprocess-export-btn');

        const hasFiles = this.files.svg.length > 0 || this.files.png.length > 0;
        const hasFormats = document.getElementById('postprocess-format-svg').checked ||
            document.getElementById('postprocess-format-png').checked ||
            document.getElementById('postprocess-format-jpg').checked;
        const hasCategories = this.selectedCategories.size > 0;

        exportBtn.disabled = !(hasFiles && hasFormats && hasCategories);
    }

    async handleExport() {
        const exportBtn = document.getElementById('postprocess-export-btn');
        const progressDiv = document.getElementById('postprocess-progress');
        const progressBar = document.getElementById('postprocess-progress-bar');
        const progressText = document.getElementById('postprocess-progress-text');
        const resultDiv = document.getElementById('postprocess-result');

        // Disable button
        exportBtn.disabled = true;
        resultDiv.style.display = 'none';
        progressDiv.style.display = 'block';

        try {
            // Collect export settings
            const settings = {
                formats: {
                    svg: document.getElementById('postprocess-format-svg').checked,
                    png: document.getElementById('postprocess-format-png').checked,
                    jpg: document.getElementById('postprocess-format-jpg').checked
                },
                raster: {
                    dpi: parseInt(document.getElementById('postprocess-dpi').value),
                    transparent: document.getElementById('postprocess-transparent-bg').checked,
                    bgColor: document.getElementById('postprocess-bg-color').value,
                    jpgQuality: parseInt(document.getElementById('postprocess-jpg-quality').value)
                },
                strokeWidths: {
                    Profile: parseFloat(document.getElementById('postprocess-stroke-profile').value),
                    Profile_Mirrored: parseFloat(document.getElementById('postprocess-stroke-profile').value),
                    Prospectus: parseFloat(document.getElementById('postprocess-stroke-profile').value),
                    Application: parseFloat(document.getElementById('postprocess-stroke-application').value),
                    Handle: parseFloat(document.getElementById('postprocess-stroke-handle').value),
                    Decoration: parseFloat(document.getElementById('postprocess-stroke-decoration').value),
                    Running_Element: parseFloat(document.getElementById('postprocess-stroke-runningelement').value),
                    Running_Element_Mirrored: parseFloat(document.getElementById('postprocess-stroke-runningelement').value),
                    Detail: parseFloat(document.getElementById('postprocess-stroke-detail').value),
                    Symmetry_Line: parseFloat(document.getElementById('postprocess-stroke-symmetry').value),
                    Diameter: parseFloat(document.getElementById('postprocess-stroke-diameter').value)
                },
                vectorization: {
                    epsilon: parseFloat(document.getElementById('postprocess-epsilon').value),
                    smoothing: parseFloat(document.getElementById('postprocess-smoothing').value)
                },
                archive: {
                    createZip: document.getElementById('postprocess-create-zip').checked,
                    organizeByCategory: document.getElementById('postprocess-organize-by-category').checked,
                    categories: Array.from(this.selectedCategories)  // Move here for backend
                }
            };

            console.log('Export settings:', settings);
            console.log('Selected categories:', settings.archive.categories);
            console.log('Total SVG files:', this.files.svg.length);
            console.log('Total PNG files:', this.files.png.length);

            // Process ALL SVG files - remove unselected layers from each
            const filteredSvgData = this.files.svg
                .map(file => {
                    const svgText = this.svgCache.get(file.name);
                    if (!svgText) {
                        console.warn(`⚠️ No cached content for ${file.name}, skipping`);
                        return null;
                    }

                    // Get ALL categories in this SVG
                    const allCategories = this.extractAllCategoriesFromSVG(svgText);

                    console.log(`Processing SVG: ${file.name} → Categories: [${allCategories.join(', ')}]`);

                    // Remove unselected layers from SVG
                    let processedSvgText = this.removeUnselectedLayersFromSVG(svgText, this.selectedCategories);

                    // Apply custom stroke widths and ensure black colors
                    processedSvgText = this.applyStrokeWidthsAndColorsToSVG(processedSvgText, settings.strokeWidths);

                    // Apply vectorization parameters (simplification and smoothing) - only for main elements
                    processedSvgText = this.applyVectorizationParametersToSVG(
                        processedSvgText,
                        settings.vectorization.epsilon,
                        settings.vectorization.smoothing
                    );

                    // Check if ANY category remains selected
                    const hasSelectedCategory = allCategories.some(cat => this.selectedCategories.has(cat));

                    if (!hasSelectedCategory) {
                        console.log(`  ⚠️ Skipping ${file.name} - no selected categories`);
                        return null;
                    }

                    // Use the first SELECTED category for organization
                    const primaryCategory = allCategories.find(cat => this.selectedCategories.has(cat)) || allCategories[0];

                    return { file, svgText: processedSvgText, category: primaryCategory };
                })
                .filter(item => item !== null);

            console.log(`Filtered: ${filteredSvgData.length} SVG files from ${this.files.svg.length} total`);

            if (filteredSvgData.length === 0) {
                throw new Error('No files match the selected categories');
            }

            // Prepare arrays for JSON payload
            const svgFilesArray = [];
            const pngFilesArray = [];
            const jpgFilesArray = [];

            // Process SVG files
            for (let i = 0; i < filteredSvgData.length; i++) {
                const { file, svgText, category } = filteredSvgData[i];

                progressBar.style.width = `${((i + 1) / filteredSvgData.length) * 50}%`;
                progressText.textContent = `Processing ${i + 1}/${filteredSvgData.length}: ${file.name}`;

                // Add SVG if format selected
                if (settings.formats.svg) {
                    svgFilesArray.push({
                        name: file.name,
                        content: svgText,
                        category: category
                    });
                }

                try {
                    // Convert to PNG if needed
                    if (settings.formats.png) {
                        const pngBlob = await this.convertSvgToPng(svgText, settings.raster);
                        if (pngBlob) {
                            const pngBase64 = await this.blobToBase64(pngBlob);
                            pngFilesArray.push({
                                name: file.name.replace('.svg', '.png'),
                                content: pngBase64.split(',')[1], // Remove data:image/png;base64, prefix
                                category: category
                            });
                            console.log(`✓ Converted to PNG: ${file.name}`);
                        }
                    }

                    // Convert to JPG if needed
                    if (settings.formats.jpg) {
                        const jpgBlob = await this.convertSvgToJpg(svgText, settings.raster);
                        if (jpgBlob) {
                            const jpgBase64 = await this.blobToBase64(jpgBlob);
                            jpgFilesArray.push({
                                name: file.name.replace('.svg', '.jpg'),
                                content: jpgBase64.split(',')[1], // Remove data:image/jpeg;base64, prefix
                                category: category
                            });
                            console.log(`✓ Converted to JPG: ${file.name}`);
                        }
                    }
                } catch (error) {
                    console.error(`Error converting ${file.name}:`, error);
                }
            }

            // Send JSON payload
            const payload = {
                svg_files: svgFilesArray,
                png_files: pngFilesArray,
                jpg_files: jpgFilesArray,
                settings: settings
            };

            console.log('Sending payload:', {
                svg: payload.svg_files.length,
                png: payload.png_files.length,
                jpg: payload.jpg_files.length
            });

            // Update progress
            progressBar.style.width = '60%';
            progressText.textContent = 'Uploading to server...';

            // Send to server
            const response = await fetch('/api/postprocess_export', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Export failed: ${errorText}`);
            }

            const result = await response.json();

            // Update progress
            progressBar.style.width = '100%';
            progressText.textContent = 'Export complete!';

            // Show results
            setTimeout(() => {
                progressDiv.style.display = 'none';
                this.showExportResults(result);
            }, 1000);

        } catch (error) {
            console.error('Export error:', error);

            progressDiv.style.display = 'none';
            resultDiv.style.display = 'block';
            resultDiv.innerHTML = `
                <div style="background: #fee; border: 1px solid #fcc; padding: 15px; border-radius: 8px; color: #c00;">
                    <h4 style="margin: 0 0 10px 0;">❌ Export Failed</h4>
                    <p style="margin: 0;">${error.message}</p>
                </div>
            `;
        } finally {
            exportBtn.disabled = false;
        }
    }

    showExportResults(result) {
        const resultDiv = document.getElementById('postprocess-result');
        resultDiv.style.display = 'block';

        let html = `
            <div style="background: #f0fdf4; border: 1px solid #86efac; padding: 15px; border-radius: 8px;">
                <h4 style="margin: 0 0 10px 0; color: #15803d;">✓ Export Successful</h4>
                <p style="margin: 5px 0;"><strong>Files processed:</strong> ${result.total_files}</p>
                <p style="margin: 5px 0;"><strong>Output formats:</strong> ${result.formats.join(', ').toUpperCase()}</p>
        `;

        if (result.download_url) {
            html += `
                <button onclick="window.location.href='${result.download_url}'" class="btn btn-success" style="margin-top: 15px;">
                    <span>📥</span> Download Results
                </button>
            `;
        }

        html += `</div>`;
        resultDiv.innerHTML = html;
    }

    /**
     * Convert SVG to PNG using Canvas API
     */
    async convertSvgToPng(svgText, rasterSettings) {
        return new Promise((resolve, reject) => {
            try {
                // Create image from SVG
                const img = new Image();
                const blob = new Blob([svgText], { type: 'image/svg+xml' });
                const url = URL.createObjectURL(blob);

                img.onload = () => {
                    try {
                        // Calculate dimensions based on DPI
                        const scale = rasterSettings.dpi / 96; // 96 is default browser DPI
                        const width = img.width * scale;
                        const height = img.height * scale;

                        // Create canvas
                        const canvas = document.createElement('canvas');
                        canvas.width = width;
                        canvas.height = height;
                        const ctx = canvas.getContext('2d');

                        // Set background if not transparent
                        if (!rasterSettings.transparent) {
                            ctx.fillStyle = rasterSettings.bgColor;
                            ctx.fillRect(0, 0, width, height);
                        }

                        // Draw SVG
                        ctx.drawImage(img, 0, 0, width, height);

                        // Convert to PNG blob
                        canvas.toBlob(blob => {
                            URL.revokeObjectURL(url);
                            resolve(blob);
                        }, 'image/png');

                    } catch (error) {
                        URL.revokeObjectURL(url);
                        reject(error);
                    }
                };

                img.onerror = (error) => {
                    URL.revokeObjectURL(url);
                    reject(error);
                };

                img.src = url;

            } catch (error) {
                reject(error);
            }
        });
    }

    /**
     * Convert SVG to JPG using Canvas API
     */
    async convertSvgToJpg(svgText, rasterSettings) {
        return new Promise((resolve, reject) => {
            try {
                // Create image from SVG
                const img = new Image();
                const blob = new Blob([svgText], { type: 'image/svg+xml' });
                const url = URL.createObjectURL(blob);

                img.onload = () => {
                    try {
                        // Calculate dimensions based on DPI
                        const scale = rasterSettings.dpi / 96;
                        const width = img.width * scale;
                        const height = img.height * scale;

                        // Create canvas
                        const canvas = document.createElement('canvas');
                        canvas.width = width;
                        canvas.height = height;
                        const ctx = canvas.getContext('2d');

                        // JPG always needs background (no transparency)
                        ctx.fillStyle = rasterSettings.bgColor;
                        ctx.fillRect(0, 0, width, height);

                        // Draw SVG
                        ctx.drawImage(img, 0, 0, width, height);

                        // Convert to JPG blob
                        const quality = rasterSettings.jpgQuality / 100;
                        canvas.toBlob(blob => {
                            URL.revokeObjectURL(url);
                            resolve(blob);
                        }, 'image/jpeg', quality);

                    } catch (error) {
                        URL.revokeObjectURL(url);
                        reject(error);
                    }
                };

                img.onerror = (error) => {
                    URL.revokeObjectURL(url);
                    reject(error);
                };

                img.src = url;

            } catch (error) {
                reject(error);
            }
        });
    }

    blobToBase64(blob) {
        /**
         * Convert Blob to base64 data URL
         */
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.postProcessingManager = new PostProcessingManager();
});
