// Tabular Tab JavaScript - Project-aware version
// Uses window.PyPotteryUtils.* functions directly

// State
let tabularState = {
    currentProject: null,
    cards: [],
    currentIndex: 0,
    totalCards: 0,
    tableData: [],
    columns: [],
    currentImageName: null,  // Track current image for saving
    imageList: [],  // List of all images with reviewed status
    isReviewed: false,  // Current image reviewed status
    fullImageUrl: null  // Full resolution image URL for zoom
};

document.addEventListener('DOMContentLoaded', () => {
    setupTabularListeners();
    loadCurrentProject();
    
    // Listen for project changes
    window.addEventListener('projectChanged', (e) => {
        const project = e.detail && e.detail.project ? e.detail.project : null;
        tabularState.currentProject = project;
        loadProjectCards();
    });
});

function loadCurrentProject() {
    if (window.projectManager && window.projectManager.getCurrentProject) {
        tabularState.currentProject = window.projectManager.getCurrentProject();
    } else {
        const pid = localStorage.getItem('currentProjectId');
        const pname = localStorage.getItem('currentProjectName');
        if (pid) {
            tabularState.currentProject = { project_id: pid, project_name: pname || 'Unnamed' };
        }
    }
    
    if (tabularState.currentProject) {
        loadProjectCards();
    }
}

function setupTabularListeners() {
    // Navigation
    document.getElementById('tabular-prev')?.addEventListener('click', () => navigateTabular(-1));
    document.getElementById('tabular-next')?.addEventListener('click', () => navigateTabular(1));
    document.getElementById('tabular-goto-btn')?.addEventListener('click', handleTabularGoto);

    // Add column
    document.getElementById('add-column-btn')?.addEventListener('click', handleAddColumn);
    
    // Export to CSV - use combined export endpoint
    document.getElementById('export-csv-btn')?.addEventListener('click', exportCombinedCSV);
    
    // Mark as reviewed
    document.getElementById('tabular-mark-reviewed-btn')?.addEventListener('click', markAsReviewed);
    
    // Setup magnifying glass zoom on hover
    setupMagnifyingGlass();
}

async function loadProjectCards() {
    if (!tabularState.currentProject || !tabularState.currentProject.project_id) {
        showEmptyState('No project selected', 'Select a project from the Project Manager tab');
        return;
    }
    
    try {
        window.PyPotteryUtils.showLoading('Loading project cards...');
        
        const response = await window.PyPotteryUtils.apiRequest(
            `/api/projects/${tabularState.currentProject.project_id}/cards`
        );
        
        window.PyPotteryUtils.hideLoading();
        
        if (response.success) {
            tabularState.cards = response.cards || [];
            tabularState.totalCards = response.total || 0;
            
            if (tabularState.totalCards === 0) {
                showEmptyState('No cards found', 'Extract cards from masks in the Annotation tab first');
                return;
            }
            
            // Load first card data
            await loadTabularData(0);
        } else {
            showEmptyState('Error loading cards', response.error);
        }
        
    } catch (error) {
        window.PyPotteryUtils.hideLoading();
        console.error('Error loading project cards:', error);
        showEmptyState('Error', error.message);
    }
}

function showEmptyState(title, message) {
    const canvas = document.getElementById('tabular-canvas');
    const tableContainer = document.getElementById('tabular-table-container');
    
    if (canvas) {
        const ctx = canvas.getContext('2d');
        canvas.width = 400;
        canvas.height = 300;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.fillStyle = '#64748b';
        ctx.font = '16px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(title, canvas.width / 2, canvas.height / 2 - 20);
        ctx.fillText(message, canvas.width / 2, canvas.height / 2 + 20);
    }
    
    if (tableContainer) {
        tableContainer.innerHTML = `
            <div style="padding: 2rem; text-align: center; color: #64748b;">
                <h3>${title}</h3>
                <p>${message}</p>
            </div>
        `;
    }
}

async function loadTabularData(imgNum) {
    if (!tabularState.currentProject || !tabularState.currentProject.project_id) {
        return;
    }

    try {
        window.PyPotteryUtils.showLoading('Loading card data...');
        
        const response = await window.PyPotteryUtils.apiRequest(
            `/api/projects/${tabularState.currentProject.project_id}/tabular/load`,
            {
                method: 'POST',
                body: JSON.stringify({
                    img_num: imgNum
                })
            }
        );

        window.PyPotteryUtils.hideLoading();

        if (response.success) {
            tabularState.currentIndex = response.current;
            tabularState.totalCards = response.total;
            tabularState.tableData = response.table;
            tabularState.columns = response.columns;

            displayTabularData(response);
        } else {
            window.PyPotteryUtils.showToast('Failed to load data', 'error');
        }
    } catch (error) {
        window.PyPotteryUtils.hideLoading();
        console.error('Error loading tabular data:', error);
        window.PyPotteryUtils.showToast(error.message, 'error');
    }
}

function displayTabularData(data) {
    // Store image_name and other metadata
    tabularState.currentImageName = data.image_name;
    tabularState.imageList = data.image_list || [];
    tabularState.isReviewed = data.is_reviewed || false;
    tabularState.fullImageUrl = data.full_image_url;
    tabularState.currentIndex = data.current;
    tabularState.totalCards = data.total;

    // Update reviewed status button
    updateReviewedButton();
    
    // Display image list sidebar
    displayImageList();

    // Display image with annotations
    if (data.image) {
        displayAnnotatedImage(data.image, data.annotations);
    }

    // Display table
    if (data.table && data.columns) {
        displayTable(data.table, data.columns);
    }
}

function displayAnnotatedImage(imageData, annotations) {
    const canvas = document.getElementById('tabular-canvas');
    if (!canvas) {
        console.error('[Tabular] Canvas not found!');
        return;
    }

    const ctx = canvas.getContext('2d');
    const img = new Image();

    img.onload = () => {
        canvas.width = img.width;
        canvas.height = img.height;
        ctx.drawImage(img, 0, 0);

        // Draw annotations (bounding boxes)
        if (annotations && annotations.length > 0) {
            ctx.strokeStyle = '#2563eb';
            ctx.lineWidth = 3;
            ctx.font = 'bold 16px Arial';
            ctx.fillStyle = '#2563eb';

            annotations.forEach(annot => {
                const bbox = annot.bbox;  // [x1, y1, x2, y2]
                const label = annot.label;
                
                const [x1, y1, x2, y2] = bbox;
                const width = x2 - x1;
                const height = y2 - y1;
                
                // Draw rectangle
                ctx.strokeRect(x1, y1, width, height);
                
                // Draw label background
                const labelText = `ID: ${label}`;
                const textMetrics = ctx.measureText(labelText);
                const textWidth = textMetrics.width;
                const textHeight = 20;
                
                ctx.fillStyle = '#2563eb';
                ctx.fillRect(x1, y1 - textHeight - 4, textWidth + 8, textHeight + 4);
                
                // Draw label text
                ctx.fillStyle = '#ffffff';
                ctx.fillText(labelText, x1 + 4, y1 - 8);
                
                // Reset fill style for next annotation
                ctx.fillStyle = '#2563eb';
            });
        }
    };

    img.onerror = (error) => {
        console.error('[Tabular] Image load error:', error);
    };

    img.src = imageData;
}

function displayTable(data, columns) {
    const headerEl = document.getElementById('table-header');
    const bodyEl = document.getElementById('table-body');

    if (!headerEl || !bodyEl) return;

    // Clear existing content
    headerEl.innerHTML = '';
    bodyEl.innerHTML = '';

    // Create header
    const headerRow = document.createElement('tr');
    columns.forEach(col => {
        const th = document.createElement('th');
        th.textContent = col;
        headerRow.appendChild(th);
    });
    headerEl.appendChild(headerRow);

    // Create body
    data.forEach((row, rowIndex) => {
        const tr = document.createElement('tr');
        columns.forEach(col => {
            const td = document.createElement('td');
            const input = document.createElement('input');
            input.type = 'text';
            input.value = row[col] || '';
            input.dataset.row = rowIndex;
            input.dataset.col = col;
            input.addEventListener('change', handleCellChange);
            td.appendChild(input);
            tr.appendChild(td);
        });
        bodyEl.appendChild(tr);
    });
}

async function handleCellChange(e) {
    const rowIndex = parseInt(e.target.dataset.row);
    const column = e.target.dataset.col;
    const value = e.target.value;

    // Update local state
    if (tabularState.tableData[rowIndex]) {
        tabularState.tableData[rowIndex][column] = value;
    }

    // Auto-save
    await saveTabularData();
}

async function saveTabularData() {
    if (!tabularState.currentProject || !tabularState.tableData.length) return;

    try {
        await window.PyPotteryUtils.apiRequest(
            `/api/projects/${tabularState.currentProject.project_id}/tabular/save`,
            {
                method: 'POST',
                body: JSON.stringify({
                    table: tabularState.tableData,
                    image_name: tabularState.currentImageName  // Include current image name
                })
            }
        );
        console.log('Table auto-saved');
    } catch (error) {
        console.error('Error saving table:', error);
    }
}

async function handleAddColumn() {
    const input = document.getElementById('new-column-name');
    const columnName = input.value.trim();

    if (!columnName) {
        window.PyPotteryUtils.showToast('Please enter a column name', 'warning');
        return;
    }

    try {
        const response = await window.PyPotteryUtils.apiRequest('/api/tabular/add-column', {
            method: 'POST',
            body: JSON.stringify({
                column_name: columnName,
                table: tabularState.tableData
            })
        });

        if (response.success) {
            tabularState.tableData = response.table;
            tabularState.columns = response.columns;
            displayTable(tabularState.tableData, tabularState.columns);
            input.value = '';
            window.PyPotteryUtils.showToast('Column added successfully', 'success');
            await saveTabularData();
        } else {
            window.PyPotteryUtils.showToast('Failed to add column', 'error');
        }
    } catch (error) {
        console.error('Error adding column:', error);
        window.PyPotteryUtils.showToast(error.message, 'error');
    }
}

function navigateTabular(direction) {
    const newIndex = tabularState.currentIndex + direction;
    if (newIndex >= 0 && newIndex < tabularState.totalCards) {
        loadTabularData(newIndex);
    }
}

function handleTabularGoto() {
    const input = document.getElementById('tabular-goto');
    if (!input) return;
    
    const index = parseInt(input.value);

    if (!isNaN(index) && index >= 0 && index < tabularState.totalCards) {
        loadTabularData(index);
        input.value = '';
    } else {
        window.PyPotteryUtils.showToast('Invalid card number', 'warning');
    }
}

function exportToCSV() {
    if (!tabularState.tableData || tabularState.tableData.length === 0) {
        window.PyPotteryUtils.showToast('No data to export', 'warning');
        return;
    }
    
    try {
        // Convert table data to CSV
        const columns = tabularState.columns;
        const rows = tabularState.tableData;
        
        // Create CSV header
        let csv = columns.join(',') + '\n';
        
        // Add rows
        rows.forEach(row => {
            const values = columns.map(col => {
                const value = row[col] || '';
                // Escape quotes and wrap in quotes if contains comma
                return value.includes(',') ? `"${value.replace(/"/g, '""')}"` : value;
            });
            csv += values.join(',') + '\n';
        });
        
        // Create download link
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const url = URL.createObjectURL(blob);
        
        const projectName = tabularState.currentProject ? tabularState.currentProject.project_name : 'project';
        link.setAttribute('href', url);
        link.setAttribute('download', `${projectName}_tabular_data.csv`);
        link.style.visibility = 'hidden';
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        window.PyPotteryUtils.showToast('CSV exported successfully', 'success');
        
    } catch (error) {
        console.error('Error exporting CSV:', error);
        window.PyPotteryUtils.showToast('Failed to export CSV', 'error');
    }
}

async function exportCombinedCSV() {
    if (!tabularState.currentProject || !tabularState.currentProject.project_id) {
        window.PyPotteryUtils.showToast('No project selected', 'warning');
        return;
    }
    
    try {
        window.PyPotteryUtils.showLoading('Saving combined CSV to project folder...');
        
        const response = await window.PyPotteryUtils.apiRequest(
            `/api/projects/${tabularState.currentProject.project_id}/tabular/export`,
            {
                method: 'POST',
                body: JSON.stringify({})
            }
        );
        
        window.PyPotteryUtils.hideLoading();
        
        if (response.success) {
            window.PyPotteryUtils.showToast(`CSV saved: ${response.path}`, 'success');
        } else {
            window.PyPotteryUtils.showToast(response.error || 'Export failed', 'error');
        }
    } catch (error) {
        window.PyPotteryUtils.hideLoading();
        console.error('Error exporting CSV:', error);
        window.PyPotteryUtils.showToast('Failed to export CSV', 'error');
    }
}

function displayImageList() {
    const listContainer = document.getElementById('tabular-image-list');
    if (!listContainer) return;
    
    listContainer.innerHTML = '';
    
    if (!tabularState.imageList || tabularState.imageList.length === 0) {
        listContainer.innerHTML = '<div style="padding: 1rem; color: #64748b;">No images</div>';
        return;
    }
    
    tabularState.imageList.forEach((item, index) => {
        const div = document.createElement('div');
        div.className = 'tabular-image-item';
        if (index === tabularState.currentIndex) {
            div.classList.add('active');
        }
        if (item.reviewed) {
            div.classList.add('reviewed');
        }
        
        div.innerHTML = `
            <span class="image-name">${item.image_name}</span>
            <span class="status-icon">${item.reviewed ? '✅' : '⚪'}</span>
        `;
        
        div.addEventListener('click', () => {
            loadTabularData(index);
        });
        
        listContainer.appendChild(div);
    });
}

function updateReviewedButton() {
    const btn = document.getElementById('tabular-mark-reviewed-btn');
    if (!btn) return;
    
    if (tabularState.isReviewed) {
        btn.textContent = '✅ Reviewed';
        btn.disabled = true;
        btn.style.opacity = '0.6';
    } else {
        btn.textContent = '👁️ Mark as Reviewed';
        btn.disabled = false;
        btn.style.opacity = '1';
    }
}

async function markAsReviewed() {
    if (!tabularState.currentProject || !tabularState.currentImageName) return;
    
    try {
        const response = await window.PyPotteryUtils.apiRequest(
            `/api/projects/${tabularState.currentProject.project_id}/reviewed`,
            {
                method: 'POST',
                body: JSON.stringify({
                    image_name: tabularState.currentImageName
                })
            }
        );
        
        if (response.success) {
            tabularState.isReviewed = true;
            updateReviewedButton();
            
            // Update image list
            const item = tabularState.imageList.find(i => i.image_name === tabularState.currentImageName);
            if (item) {
                item.reviewed = true;
                displayImageList();
            }
            
            window.PyPotteryUtils.showToast('Marked as reviewed', 'success');
        }
    } catch (error) {
        console.error('Error marking as reviewed:', error);
        window.PyPotteryUtils.showToast('Failed to mark as reviewed', 'error');
    }
}

function openZoomModal() {
    if (!tabularState.fullImageUrl) {
        window.PyPotteryUtils.showToast('Full resolution image not available', 'warning');
        return;
    }
    
    // Create modal
    const modal = document.createElement('div');
    modal.id = 'zoom-modal';
    modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.9);
        z-index: 10000;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: zoom-out;
    `;
    
    const img = document.createElement('img');
    img.src = tabularState.fullImageUrl;
    img.style.cssText = `
        max-width: 95%;
        max-height: 95%;
        object-fit: contain;
    `;
    
    modal.appendChild(img);
    
    // Close on click
    modal.addEventListener('click', () => {
        document.body.removeChild(modal);
    });
    
    document.body.appendChild(modal);
}

function setupMagnifyingGlass() {
    const canvas = document.getElementById('tabular-canvas');
    const zoomHint = document.querySelector('.zoom-hint');
    if (!canvas) return;
    
    // Simple hover zoom: click to toggle between normal and zoomed view
    canvas.style.cursor = 'zoom-in';
    canvas.style.transition = 'transform 0.3s ease';
    canvas.style.transformOrigin = 'center center';
    
    let isZoomed = false;
    
    canvas.addEventListener('click', (e) => {
        if (isZoomed) {
            // Zoom out
            canvas.style.transform = 'scale(1)';
            canvas.style.cursor = 'zoom-in';
            canvas.style.position = 'relative';
            canvas.style.zIndex = '1';
            if (zoomHint) zoomHint.textContent = 'Click to zoom';
            isZoomed = false;
        } else {
            // Zoom in
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            
            // Calculate zoom origin as percentage
            const originX = (x / rect.width) * 100;
            const originY = (y / rect.height) * 100;
            
            canvas.style.transformOrigin = `${originX}% ${originY}%`;
            canvas.style.transform = 'scale(2)';
            canvas.style.cursor = 'zoom-out';
            canvas.style.position = 'relative';
            canvas.style.zIndex = '100';
            if (zoomHint) zoomHint.textContent = 'Click to zoom out';
            isZoomed = true;
        }
    });
    
    // Reset zoom when changing image
    const observer = new MutationObserver(() => {
        if (isZoomed) {
            canvas.style.transform = 'scale(1)';
            canvas.style.cursor = 'zoom-in';
            canvas.style.position = 'relative';
            canvas.style.zIndex = '1';
            if (zoomHint) zoomHint.textContent = 'Click to zoom';
            isZoomed = false;
        }
    });
    
    observer.observe(canvas, { attributes: true, attributeFilter: ['src'] });
}

// Export for use by main.js
window.refreshTabular = loadProjectCards;
