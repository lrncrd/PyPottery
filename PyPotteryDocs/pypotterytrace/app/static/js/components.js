/**
 * SVG Display - Shows extracted SVGs in a simple grid
 */

class SVGDisplay {
    constructor() {
        this.container = document.getElementById('svg-container');
        this.svgs = [];
        
        this.init();
    }
    
    init() {
        // Load SVGs when tab is activated
        this.loadSVGs();
    }
    
    async loadSVGs() {
        if (!window.currentSessionId) {
            this.showMessage('No session active. Please upload an image first.');
            return;
        }
        
        this.showMessage('Loading extracted SVGs...');
        
        try {
            // Fetch list of SVG files for the session
            const response = await fetch(`/api/list_svgs/${window.currentSessionId}`);
            const data = await response.json();
            
            if (data.success && data.svgs.length > 0) {
                this.svgs = data.svgs;
                this.displaySVGs();
            } else {
                this.showMessage('No SVGs found. Please complete segmentation and vectorization first.');
            }
        } catch (error) {
            console.error('Error loading SVGs:', error);
            this.showMessage('Error loading SVGs. Please try again.');
        }
    }
    
    async displaySVGs() {
        this.container.innerHTML = '';
        
        for (const svgInfo of this.svgs) {
            const svgItem = document.createElement('div');
            svgItem.className = 'svg-item';
            
            const title = document.createElement('h3');
            title.textContent = svgInfo.name;
            svgItem.appendChild(title);
            
            try {
                const svgResponse = await fetch(svgInfo.url);
                const svgText = await svgResponse.text();
                
                const svgContainer = document.createElement('div');
                svgContainer.innerHTML = svgText;
                svgItem.appendChild(svgContainer);
            } catch (error) {
                console.error('Error loading SVG:', svgInfo.url, error);
                const errorMsg = document.createElement('p');
                errorMsg.textContent = 'Error loading SVG';
                errorMsg.style.color = 'red';
                svgItem.appendChild(errorMsg);
            }
            
            this.container.appendChild(svgItem);
        }
    }
    
    showMessage(message) {
        this.container.innerHTML = `
            <div class="loading-message">
                <span class="message-icon">🎨</span>
                <p>${message}</p>
            </div>
        `;
    }
}

// Initialize when tab is shown
window.svgDisplay = null;

function initSVGDisplay() {
    if (!window.svgDisplay) {
        window.svgDisplay = new SVGDisplay();
    } else {
        // Reload SVGs if already initialized
        window.svgDisplay.loadSVGs();
    }
}

// Call when preview tab is activated
document.addEventListener('DOMContentLoaded', () => {
    const previewTabBtn = document.getElementById('preview-tab-btn');
    if (previewTabBtn) {
        previewTabBtn.addEventListener('click', () => {
            initSVGDisplay();
        });
    }
});
