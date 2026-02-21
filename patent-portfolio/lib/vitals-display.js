/**
 * Vitals Display - Beautiful sparkline FPS monitor
 * 
 * Inspired by medical vitals monitors - clean, minimal, informative
 * Position: Bottom-left, next to help button
 * 
 * h(x) ≥ 0 always
 */

export class VitalsDisplay {
    constructor(renderer, performanceManager) {
        this.renderer = renderer;
        this.performanceManager = performanceManager;
        this.history = new Array(60).fill(60);
        this.historyIndex = 0;
        this.currentFps = 60;
        this.frameCount = 0;
        this.lastTime = performance.now();
        this.idleOpacity = 0.25;
        this.activeOpacity = 0.9;
        this.currentOpacity = this.idleOpacity;
        this.isLowFps = false;

        this.createElement();
    }
    
    createElement() {
        // Container
        this.container = document.createElement('div');
        this.container.id = 'vitals-display';
        this.container.innerHTML = `
            <div class="vitals-sparkline">
                <svg viewBox="0 0 120 32" preserveAspectRatio="none">
                    <defs>
                        <linearGradient id="vitals-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" style="stop-color:#67D4E4;stop-opacity:0.1"/>
                            <stop offset="100%" style="stop-color:#67D4E4;stop-opacity:0.6"/>
                        </linearGradient>
                        <linearGradient id="vitals-stroke" x1="0%" y1="0%" x2="100%" y2="0%">
                            <stop offset="0%" style="stop-color:#67D4E4;stop-opacity:0.3"/>
                            <stop offset="100%" style="stop-color:#67D4E4;stop-opacity:1"/>
                        </linearGradient>
                    </defs>
                    <path class="vitals-area" fill="url(#vitals-gradient)"/>
                    <path class="vitals-line" fill="none" stroke="url(#vitals-stroke)" stroke-width="1.5"/>
                    <circle class="vitals-dot" r="3" fill="#67D4E4"/>
                </svg>
                <span class="vitals-value">60</span>
            </div>
            <div class="vitals-stats">
                <span class="vitals-stat" data-stat="draws">0 draws</span>
                <span class="vitals-stat" data-stat="tris">0K tris</span>
                <span class="vitals-stat" data-stat="preset">—</span>
            </div>
            <div class="vitals-gpu">
                <div class="vitals-gpu-bar"></div>
                <span class="vitals-gpu-label">GPU</span>
            </div>
        `;
        
        // Styles
        const style = document.createElement('style');
        style.textContent = `
            #vitals-display {
                position: fixed;
                bottom: 20px;
                left: 80px;
                display: flex;
                flex-direction: column;
                gap: 4px;
                font-family: 'IBM Plex Mono', monospace;
                font-size: 11px;
                z-index: 500;
                pointer-events: none;
                opacity: 0.15;
                transition: opacity 0.5s ease;
            }
            
            #vitals-display.active {
                opacity: 0.9;
            }
            
            #vitals-display.warning {
                opacity: 1;
            }
            
            .vitals-sparkline {
                display: flex;
                align-items: center;
                gap: 8px;
                background: rgba(7, 6, 11, 0.6);
                backdrop-filter: blur(8px);
                -webkit-backdrop-filter: blur(8px);
                padding: 6px 10px;
                border-radius: 6px;
                border: 1px solid rgba(103, 212, 228, 0.15);
            }
            
            .vitals-sparkline svg {
                width: 80px;
                height: 24px;
            }
            
            .vitals-line {
                vector-effect: non-scaling-stroke;
            }
            
            .vitals-dot {
                filter: drop-shadow(0 0 4px #67D4E4);
                animation: vitals-pulse 1s ease-in-out infinite;
            }
            
            @keyframes vitals-pulse {
                0%, 100% { opacity: 1; r: 3; }
                50% { opacity: 0.6; r: 2; }
            }
            
            .vitals-value {
                color: #67D4E4;
                font-weight: 500;
                min-width: 24px;
                text-align: right;
            }
            
            #vitals-display.warning .vitals-value {
                color: #F59E0B;
            }
            
            #vitals-display.critical .vitals-value {
                color: #FF6B35;
                animation: vitals-blink 0.5s ease infinite;
            }
            
            @keyframes vitals-blink {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }
            
            .vitals-stats {
                display: flex;
                gap: 8px;
                padding: 2px 10px;
                font-size: 9px;
                color: rgba(103, 212, 228, 0.6);
            }

            .vitals-gpu {
                display: flex;
                align-items: center;
                gap: 6px;
                padding: 0 10px;
            }
            
            .vitals-gpu-bar {
                width: 80px;
                height: 3px;
                background: rgba(103, 212, 228, 0.15);
                border-radius: 2px;
                overflow: hidden;
                position: relative;
            }
            
            .vitals-gpu-bar::after {
                content: '';
                position: absolute;
                left: 0;
                top: 0;
                height: 100%;
                width: var(--gpu-load, 30%);
                background: linear-gradient(90deg, rgba(103, 212, 228, 0.3), rgba(103, 212, 228, 0.8));
                border-radius: 2px;
                transition: width 0.3s ease;
            }
            
            .vitals-gpu-label {
                color: rgba(103, 212, 228, 0.5);
                font-size: 9px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            /* Hide on mobile */
            @media (max-width: 768px) {
                #vitals-display {
                    display: none;
                }
            }
        `;
        
        document.head.appendChild(style);
        document.body.appendChild(this.container);
        
        // Cache elements
        this.areaPath = this.container.querySelector('.vitals-area');
        this.linePath = this.container.querySelector('.vitals-line');
        this.dot = this.container.querySelector('.vitals-dot');
        this.valueEl = this.container.querySelector('.vitals-value');
        this.gpuBar = this.container.querySelector('.vitals-gpu-bar');
        this.drawsStat = this.container.querySelector('[data-stat="draws"]');
        this.trisStat = this.container.querySelector('[data-stat="tris"]');
        this.presetStat = this.container.querySelector('[data-stat="preset"]');
    }
    
    update() {
        this.frameCount++;
        const now = performance.now();
        const elapsed = now - this.lastTime;
        
        // Update FPS every 250ms for smoother sparkline
        if (elapsed >= 250) {
            this.currentFps = Math.round((this.frameCount / elapsed) * 1000);
            this.frameCount = 0;
            this.lastTime = now;
            
            // Add to history (circular buffer)
            this.history[this.historyIndex] = Math.min(this.currentFps, 120);
            this.historyIndex = (this.historyIndex + 1) % 60;
            
            // Update display
            this.render();
        }
    }
    
    render() {
        // Build sparkline path
        const width = 120;
        const height = 32;
        const padding = 2;
        const maxFps = 80;  // Scale max
        
        let linePath = '';
        let areaPath = '';
        let lastX = 0;
        let lastY = height;
        
        for (let i = 0; i < 60; i++) {
            // Read from circular buffer in order
            const idx = (this.historyIndex + i) % 60;
            const fps = this.history[idx];
            const x = (i / 59) * width;
            const y = height - padding - ((fps / maxFps) * (height - padding * 2));
            const clampedY = Math.max(padding, Math.min(height - padding, y));
            
            if (i === 0) {
                linePath = `M ${x} ${clampedY}`;
                areaPath = `M ${x} ${height} L ${x} ${clampedY}`;
            } else {
                linePath += ` L ${x} ${clampedY}`;
                areaPath += ` L ${x} ${clampedY}`;
            }
            
            lastX = x;
            lastY = clampedY;
        }
        
        // Close area path
        areaPath += ` L ${width} ${height} Z`;
        
        // Update SVG
        this.linePath.setAttribute('d', linePath);
        this.areaPath.setAttribute('d', areaPath);
        this.dot.setAttribute('cx', lastX);
        this.dot.setAttribute('cy', lastY);
        
        // Update value
        this.valueEl.textContent = this.currentFps;
        
        // Update status classes
        this.container.classList.remove('warning', 'critical', 'active');
        if (this.currentFps < 30) {
            this.container.classList.add('critical');
        } else if (this.currentFps < 50) {
            this.container.classList.add('warning');
        }
        
        // Update stats + GPU load estimate
        if (this.renderer?.info?.render) {
            const drawCalls = this.renderer.info.render.calls || 0;
            const triangles = this.renderer.info.render.triangles || 0;
            const textures = this.renderer.info.memory?.textures || 0;

            this.drawsStat.textContent = `${drawCalls} draws`;
            this.trisStat.textContent = `${Math.round(triangles / 1000)}K tris`;

            const loadEstimate = Math.min(100, Math.max(5,
                (drawCalls / 500) * 50 + (triangles / 500000) * 50
            ));
            this.gpuBar.style.setProperty('--gpu-load', `${loadEstimate}%`);
        }

        if (this.performanceManager) {
            this.presetStat.textContent = this.performanceManager.getPresetName?.() || '—';
        }
    }
    
    // Show when moving mouse
    activate() {
        this.container.classList.add('active');
        clearTimeout(this._fadeTimeout);
        this._fadeTimeout = setTimeout(() => {
            if (this.currentFps >= 50) {
                this.container.classList.remove('active');
            }
        }, 3000);
    }
    
    dispose() {
        this.container?.remove();
    }
}
