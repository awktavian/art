/**
 * Professional Debug System for Patent Museum
 * ============================================
 * 
 * Inspired by:
 * - Unreal Engine stat commands
 * - Unity Profiler
 * - three.js stats.js / dat.gui
 * - Google Maps dev tools
 * 
 * Features:
 * - Performance HUD with real-time metrics
 * - System toggles for isolating issues
 * - Visual debugging helpers
 * - Console with commands
 * - Metrics recording
 * 
 * h(x) >= 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// URL PARAMETER PARSING
// ═══════════════════════════════════════════════════════════════════════════

function parseDebugParams() {
    const params = new URLSearchParams(window.location.search);
    return {
        debug: params.has('debug'),
        fps: params.has('fps'),
        wireframe: params.has('wireframe'),
        noclip: params.has('noclip'),
        quality: params.get('quality'),
        nopost: params.has('nopost'),
        noaudio: params.has('noaudio'),
        nolighting: params.has('nolighting'),
        noparticles: params.has('noparticles'),
        teleport: params.get('teleport'),
        minimal: params.has('minimal'),  // Ultra-minimal mode for testing
    };
}

// ═══════════════════════════════════════════════════════════════════════════
// DEBUG HUD
// ═══════════════════════════════════════════════════════════════════════════

class DebugHUD {
    constructor() {
        this.container = null;
        this.panels = {};
        this.visible = false;
        this.fpsHistory = new Array(60).fill(60);
        this.frameTimeHistory = new Array(60).fill(16.67);
        this.historyIndex = 0;
        
        this.createStyles();
        this.createContainer();
    }
    
    createStyles() {
        if (document.getElementById('debug-hud-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'debug-hud-styles';
        style.textContent = `
            #debug-hud {
                position: fixed;
                top: 10px;
                left: 10px;
                z-index: 10000;
                font-family: 'IBM Plex Mono', 'Consolas', monospace;
                font-size: 12px;
                color: #e0e0e0;
                pointer-events: none;
                user-select: none;
            }
            
            #debug-hud.hidden {
                display: none;
            }
            
            .debug-panel {
                background: rgba(0, 0, 0, 0.85);
                border: 1px solid rgba(103, 212, 228, 0.3);
                border-radius: 4px;
                padding: 8px 12px;
                margin-bottom: 8px;
                min-width: 200px;
                pointer-events: auto;
            }
            
            .debug-panel-header {
                color: #67d4e4;
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                margin-bottom: 6px;
                padding-bottom: 4px;
                border-bottom: 1px solid rgba(103, 212, 228, 0.2);
            }
            
            .debug-row {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 2px 0;
            }
            
            .debug-label {
                color: #9e9994;
            }
            
            .debug-value {
                font-weight: 500;
                min-width: 80px;
                text-align: right;
            }
            
            .debug-value.good { color: #7db87e; }
            .debug-value.warning { color: #f59e0b; }
            .debug-value.critical { color: #ef4444; }
            
            .debug-graph {
                height: 30px;
                background: rgba(0, 0, 0, 0.5);
                border-radius: 2px;
                margin-top: 4px;
                display: flex;
                align-items: flex-end;
                padding: 2px;
                gap: 1px;
            }
            
            .debug-graph-bar {
                flex: 1;
                background: #67d4e4;
                min-width: 2px;
                transition: height 0.05s;
            }
            
            .debug-graph-bar.warning { background: #f59e0b; }
            .debug-graph-bar.critical { background: #ef4444; }
            
            .debug-checkbox {
                pointer-events: auto;
                cursor: pointer;
            }
            
            .debug-checkbox input {
                margin-right: 8px;
                cursor: pointer;
            }
            
            .debug-select {
                background: rgba(0, 0, 0, 0.5);
                border: 1px solid rgba(103, 212, 228, 0.3);
                color: #e0e0e0;
                padding: 2px 6px;
                border-radius: 2px;
                font-size: 11px;
                pointer-events: auto;
                cursor: pointer;
            }
            
            .debug-button {
                background: rgba(103, 212, 228, 0.2);
                border: 1px solid rgba(103, 212, 228, 0.4);
                color: #67d4e4;
                padding: 4px 8px;
                border-radius: 2px;
                font-size: 10px;
                cursor: pointer;
                pointer-events: auto;
                margin: 2px;
            }
            
            .debug-button:hover {
                background: rgba(103, 212, 228, 0.3);
            }
            
            .debug-divider {
                height: 1px;
                background: rgba(103, 212, 228, 0.1);
                margin: 6px 0;
            }
        `;
        document.head.appendChild(style);
    }
    
    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'debug-hud';
        this.container.className = 'hidden';
        document.body.appendChild(this.container);
    }
    
    createPerformancePanel() {
        const panel = document.createElement('div');
        panel.className = 'debug-panel';
        panel.innerHTML = `
            <div class="debug-panel-header">Performance</div>
            <div class="debug-row">
                <span class="debug-label">FPS</span>
                <span class="debug-value" id="debug-fps">--</span>
            </div>
            <div class="debug-graph" id="debug-fps-graph"></div>
            <div class="debug-row">
                <span class="debug-label">Frame Time</span>
                <span class="debug-value" id="debug-frametime">--</span>
            </div>
            <div class="debug-divider"></div>
            <div class="debug-row">
                <span class="debug-label">Draw Calls</span>
                <span class="debug-value" id="debug-drawcalls">--</span>
            </div>
            <div class="debug-row">
                <span class="debug-label">Triangles</span>
                <span class="debug-value" id="debug-triangles">--</span>
            </div>
            <div class="debug-row">
                <span class="debug-label">Geometries</span>
                <span class="debug-value" id="debug-geometries">--</span>
            </div>
            <div class="debug-row">
                <span class="debug-label">Textures</span>
                <span class="debug-value" id="debug-textures">--</span>
            </div>
        `;
        this.panels.performance = panel;
        this.container.appendChild(panel);
        
        // Create FPS graph bars
        const graph = panel.querySelector('#debug-fps-graph');
        for (let i = 0; i < 60; i++) {
            const bar = document.createElement('div');
            bar.className = 'debug-graph-bar';
            bar.style.height = '100%';
            graph.appendChild(bar);
        }
    }
    
    createSystemsPanel(systems) {
        const panel = document.createElement('div');
        panel.className = 'debug-panel';
        
        let html = `<div class="debug-panel-header">Systems</div>`;
        
        for (const [key, config] of Object.entries(systems)) {
            html += `
                <label class="debug-checkbox debug-row">
                    <input type="checkbox" id="debug-toggle-${key}" ${config.enabled ? 'checked' : ''}>
                    <span class="debug-label">${config.label}</span>
                </label>
            `;
        }
        
        html += `
            <div class="debug-divider"></div>
            <div class="debug-row">
                <span class="debug-label">Quality</span>
                <select class="debug-select" id="debug-quality">
                    <option value="emergency">Emergency</option>
                    <option value="low">Low</option>
                    <option value="medium" selected>Medium</option>
                    <option value="high">High</option>
                    <option value="ultra">Ultra</option>
                </select>
            </div>
        `;
        
        panel.innerHTML = html;
        this.panels.systems = panel;
        this.container.appendChild(panel);
    }
    
    createNavigationPanel() {
        const panel = document.createElement('div');
        panel.className = 'debug-panel';
        panel.innerHTML = `
            <div class="debug-panel-header">Navigation</div>
            <div class="debug-row">
                <span class="debug-label">Position</span>
                <span class="debug-value" id="debug-position">--</span>
            </div>
            <div class="debug-row">
                <span class="debug-label">Velocity</span>
                <span class="debug-value" id="debug-velocity">--</span>
            </div>
            <div class="debug-row">
                <span class="debug-label">Zone</span>
                <span class="debug-value" id="debug-zone">--</span>
            </div>
            <div class="debug-row">
                <span class="debug-label">Locked</span>
                <span class="debug-value" id="debug-locked">--</span>
            </div>
            <div class="debug-divider"></div>
            <label class="debug-checkbox debug-row">
                <input type="checkbox" id="debug-noclip">
                <span class="debug-label">Noclip Mode</span>
            </label>
            <div class="debug-row">
                <button class="debug-button" id="debug-teleport-center">Center</button>
                <button class="debug-button" id="debug-teleport-rotunda">Rotunda</button>
            </div>
        `;
        this.panels.navigation = panel;
        this.container.appendChild(panel);
    }
    
    createActionsPanel() {
        const panel = document.createElement('div');
        panel.className = 'debug-panel';
        panel.innerHTML = `
            <div class="debug-panel-header">Actions</div>
            <div class="debug-row" style="flex-wrap: wrap;">
                <button class="debug-button" id="debug-wireframe">Wireframe</button>
                <button class="debug-button" id="debug-screenshot">Screenshot</button>
                <button class="debug-button" id="debug-record">Record</button>
            </div>
            <div class="debug-divider"></div>
            <div class="debug-row">
                <span class="debug-label" style="font-size: 10px; color: #666;">
                    F3: HUD | F4: Wire | \`: Console
                </span>
            </div>
        `;
        this.panels.actions = panel;
        this.container.appendChild(panel);
    }
    
    show() {
        this.visible = true;
        this.container.classList.remove('hidden');
    }
    
    hide() {
        this.visible = false;
        this.container.classList.add('hidden');
    }
    
    toggle() {
        if (this.visible) {
            this.hide();
        } else {
            this.show();
        }
        return this.visible;
    }
    
    updatePerformance(fps, frameTime, rendererInfo) {
        // Update history
        this.fpsHistory[this.historyIndex] = fps;
        this.frameTimeHistory[this.historyIndex] = frameTime;
        this.historyIndex = (this.historyIndex + 1) % 60;
        
        // Update FPS display
        const fpsEl = document.getElementById('debug-fps');
        if (fpsEl) {
            fpsEl.textContent = fps.toFixed(0);
            fpsEl.className = 'debug-value ' + this.getPerformanceClass(fps, 55, 30);
        }
        
        // Update frame time
        const ftEl = document.getElementById('debug-frametime');
        if (ftEl) {
            ftEl.textContent = frameTime.toFixed(1) + 'ms';
            ftEl.className = 'debug-value ' + this.getPerformanceClass(60 - frameTime, 43, 27);
        }
        
        // Update graph
        const graph = document.getElementById('debug-fps-graph');
        if (graph) {
            const bars = graph.children;
            for (let i = 0; i < 60; i++) {
                const idx = (this.historyIndex + i) % 60;
                const value = this.fpsHistory[idx];
                const height = Math.min(100, (value / 60) * 100);
                bars[i].style.height = height + '%';
                bars[i].className = 'debug-graph-bar ' + this.getPerformanceClass(value, 55, 30);
            }
        }
        
        // Update renderer info
        if (rendererInfo) {
            this.updateElement('debug-drawcalls', rendererInfo.render?.calls || 0);
            this.updateElement('debug-triangles', this.formatNumber(rendererInfo.render?.triangles || 0));
            this.updateElement('debug-geometries', rendererInfo.memory?.geometries || 0);
            this.updateElement('debug-textures', rendererInfo.memory?.textures || 0);
        }
    }
    
    updateNavigation(position, velocity, zone, isLocked) {
        if (position) {
            this.updateElement('debug-position', 
                `${position.x.toFixed(1)}, ${position.y.toFixed(1)}, ${position.z.toFixed(1)}`);
        }
        if (velocity) {
            const speed = Math.sqrt(velocity.x**2 + velocity.z**2);
            this.updateElement('debug-velocity', speed.toFixed(2));
        }
        this.updateElement('debug-zone', zone || '--');
        this.updateElement('debug-locked', isLocked ? 'Yes' : 'No');
    }
    
    updateElement(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    }
    
    getPerformanceClass(value, goodThreshold, warningThreshold) {
        if (value >= goodThreshold) return 'good';
        if (value >= warningThreshold) return 'warning';
        return 'critical';
    }
    
    formatNumber(num) {
        if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
        if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
        return num.toString();
    }
    
    dispose() {
        if (this.container) {
            this.container.remove();
        }
        const styles = document.getElementById('debug-hud-styles');
        if (styles) styles.remove();
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// DEBUG CONSOLE
// ═══════════════════════════════════════════════════════════════════════════

class DebugConsole {
    constructor(debugManager) {
        this.debugManager = debugManager;
        this.container = null;
        this.input = null;
        this.output = null;
        this.visible = false;
        this.history = [];
        this.historyIndex = -1;
        
        this.commands = {
            'help': () => this.showHelp(),
            'stat fps': () => this.debugManager.toggleHUD(),
            'stat render': () => this.log('Draw calls: ' + (this.debugManager.rendererInfo?.render?.calls || 0)),
            'stat all': () => this.debugManager.toggleHUD(),
            'wireframe': () => this.debugManager.toggleWireframe(),
            'noclip': () => this.debugManager.toggleNoclip(),
            'quality': (args) => this.debugManager.setQuality(args[0]),
            'teleport': (args) => this.debugManager.teleport(parseFloat(args[0]), parseFloat(args[1]), parseFloat(args[2])),
            'screenshot': () => this.debugManager.screenshot(),
            'record': (args) => args[0] === 'stop' ? this.debugManager.stopRecording() : this.debugManager.startRecording(),
            'clear': () => this.clearOutput(),
            'toggle': (args) => this.debugManager.toggleSystem(args[0]),
        };
        
        this.createStyles();
        this.createContainer();
    }
    
    createStyles() {
        if (document.getElementById('debug-console-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'debug-console-styles';
        style.textContent = `
            #debug-console {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                z-index: 10001;
                font-family: 'IBM Plex Mono', 'Consolas', monospace;
                font-size: 13px;
                background: rgba(0, 0, 0, 0.95);
                border-top: 2px solid #67d4e4;
                transform: translateY(100%);
                transition: transform 0.2s ease;
            }
            
            #debug-console.visible {
                transform: translateY(0);
            }
            
            #debug-console-output {
                max-height: 200px;
                overflow-y: auto;
                padding: 8px 12px;
                color: #e0e0e0;
            }
            
            #debug-console-output .log { color: #e0e0e0; }
            #debug-console-output .info { color: #67d4e4; }
            #debug-console-output .warn { color: #f59e0b; }
            #debug-console-output .error { color: #ef4444; }
            
            #debug-console-input-container {
                display: flex;
                align-items: center;
                padding: 8px 12px;
                border-top: 1px solid rgba(103, 212, 228, 0.2);
            }
            
            #debug-console-prompt {
                color: #67d4e4;
                margin-right: 8px;
            }
            
            #debug-console-input {
                flex: 1;
                background: transparent;
                border: none;
                color: #e0e0e0;
                font-family: inherit;
                font-size: inherit;
                outline: none;
            }
            
            #debug-console-input::placeholder {
                color: #555;
            }
        `;
        document.head.appendChild(style);
    }
    
    createContainer() {
        this.container = document.createElement('div');
        this.container.id = 'debug-console';
        this.container.innerHTML = `
            <div id="debug-console-output"></div>
            <div id="debug-console-input-container">
                <span id="debug-console-prompt">&gt;</span>
                <input type="text" id="debug-console-input" placeholder="Type 'help' for commands...">
            </div>
        `;
        document.body.appendChild(this.container);
        
        this.output = this.container.querySelector('#debug-console-output');
        this.input = this.container.querySelector('#debug-console-input');
        
        this.input.addEventListener('keydown', (e) => this.handleKeydown(e));
    }
    
    handleKeydown(e) {
        if (e.key === 'Enter') {
            const cmd = this.input.value.trim();
            if (cmd) {
                this.execute(cmd);
                this.history.push(cmd);
                this.historyIndex = this.history.length;
            }
            this.input.value = '';
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            if (this.historyIndex > 0) {
                this.historyIndex--;
                this.input.value = this.history[this.historyIndex];
            }
        } else if (e.key === 'ArrowDown') {
            e.preventDefault();
            if (this.historyIndex < this.history.length - 1) {
                this.historyIndex++;
                this.input.value = this.history[this.historyIndex];
            } else {
                this.historyIndex = this.history.length;
                this.input.value = '';
            }
        } else if (e.key === 'Escape') {
            this.hide();
        }
    }
    
    execute(cmdString) {
        this.log('> ' + cmdString, 'info');
        
        const parts = cmdString.toLowerCase().split(' ');
        const cmd = parts.slice(0, 2).join(' ');
        const args = parts.slice(2);
        
        // Try two-word command first, then single word
        if (this.commands[cmd]) {
            try {
                this.commands[cmd](args);
            } catch (err) {
                this.log('Error: ' + err.message, 'error');
            }
        } else if (this.commands[parts[0]]) {
            try {
                this.commands[parts[0]](parts.slice(1));
            } catch (err) {
                this.log('Error: ' + err.message, 'error');
            }
        } else {
            this.log('Unknown command: ' + parts[0], 'error');
        }
    }
    
    showHelp() {
        this.log('Available commands:', 'info');
        this.log('  stat fps      - Toggle FPS display');
        this.log('  stat render   - Show render stats');
        this.log('  wireframe     - Toggle wireframe mode');
        this.log('  noclip        - Toggle collision');
        this.log('  quality [preset] - Set quality (emergency/low/medium/high/ultra)');
        this.log('  teleport x y z   - Move to position');
        this.log('  toggle [system]  - Toggle system (post/lighting/particles/audio)');
        this.log('  screenshot    - Capture canvas');
        this.log('  record start/stop - Record metrics');
        this.log('  clear         - Clear console');
    }
    
    log(message, type = 'log') {
        const line = document.createElement('div');
        line.className = type;
        line.textContent = message;
        this.output.appendChild(line);
        this.output.scrollTop = this.output.scrollHeight;
    }
    
    clearOutput() {
        this.output.innerHTML = '';
    }
    
    show() {
        this.visible = true;
        this.container.classList.add('visible');
        this.input.focus();
    }
    
    hide() {
        this.visible = false;
        this.container.classList.remove('visible');
    }
    
    toggle() {
        if (this.visible) {
            this.hide();
        } else {
            this.show();
        }
        return this.visible;
    }
    
    dispose() {
        if (this.container) {
            this.container.remove();
        }
        const styles = document.getElementById('debug-console-styles');
        if (styles) styles.remove();
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// VISUAL HELPERS
// ═══════════════════════════════════════════════════════════════════════════

class VisualHelpers {
    constructor(scene) {
        this.scene = scene;
        this.helpers = new THREE.Group();
        this.helpers.name = 'debug-helpers';
        this.wireframeEnabled = false;
        this.originalMaterials = new Map();
        this.lightHelpers = [];
        
        scene.add(this.helpers);
    }
    
    toggleWireframe() {
        this.wireframeEnabled = !this.wireframeEnabled;
        
        this.scene.traverse((obj) => {
            if (obj.isMesh && obj.material) {
                if (Array.isArray(obj.material)) {
                    obj.material.forEach(mat => mat.wireframe = this.wireframeEnabled);
                } else {
                    obj.material.wireframe = this.wireframeEnabled;
                }
            }
        });
        
        return this.wireframeEnabled;
    }
    
    showLightHelpers() {
        this.scene.traverse((obj) => {
            if (obj.isLight) {
                let helper;
                if (obj.isPointLight) {
                    helper = new THREE.PointLightHelper(obj, 0.5);
                } else if (obj.isSpotLight) {
                    helper = new THREE.SpotLightHelper(obj);
                } else if (obj.isDirectionalLight) {
                    helper = new THREE.DirectionalLightHelper(obj, 1);
                }
                if (helper) {
                    this.lightHelpers.push(helper);
                    this.helpers.add(helper);
                }
            }
        });
    }
    
    hideLightHelpers() {
        this.lightHelpers.forEach(helper => {
            this.helpers.remove(helper);
            helper.dispose?.();
        });
        this.lightHelpers = [];
    }
    
    showCollisionBounds(collisionObjects) {
        if (!collisionObjects) return;
        
        collisionObjects.forEach(obj => {
            if (obj.geometry) {
                obj.geometry.computeBoundingBox();
                const box = new THREE.Box3Helper(obj.geometry.boundingBox, 0xff0000);
                box.position.copy(obj.position);
                this.helpers.add(box);
            }
        });
    }
    
    addAxisHelper(size = 5) {
        const axes = new THREE.AxesHelper(size);
        this.helpers.add(axes);
    }
    
    addGridHelper(size = 100, divisions = 50) {
        const grid = new THREE.GridHelper(size, divisions, 0x444455, 0x222233);
        grid.position.y = 0.01;
        this.helpers.add(grid);
    }
    
    clear() {
        while (this.helpers.children.length > 0) {
            const child = this.helpers.children[0];
            this.helpers.remove(child);
            child.dispose?.();
        }
        this.hideLightHelpers();
    }
    
    dispose() {
        this.clear();
        this.scene.remove(this.helpers);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// METRICS RECORDER
// ═══════════════════════════════════════════════════════════════════════════

class MetricsRecorder {
    constructor() {
        this.recording = false;
        this.data = [];
        this.startTime = 0;
    }
    
    start() {
        this.recording = true;
        this.data = [];
        this.startTime = performance.now();
        console.log('Recording started...');
    }
    
    stop() {
        this.recording = false;
        console.log(`Recording stopped. ${this.data.length} frames captured.`);
        return this.data;
    }
    
    record(metrics) {
        if (!this.recording) return;
        
        this.data.push({
            time: performance.now() - this.startTime,
            ...metrics
        });
    }
    
    export() {
        const blob = new Blob([JSON.stringify(this.data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `museum-metrics-${Date.now()}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// DEBUG MANAGER (Main Entry Point)
// ═══════════════════════════════════════════════════════════════════════════

export class DebugManager {
    constructor() {
        this.params = parseDebugParams();
        this.enabled = this.params.debug || this.params.fps;
        this.hud = null;
        this.console = null;
        this.visualHelpers = null;
        this.recorder = new MetricsRecorder();
        
        // References to museum systems (set externally)
        this.renderer = null;
        this.scene = null;
        this.camera = null;
        this.navigation = null;
        this.postProcessing = null;
        this.lighting = null;
        this.wingEnhancements = null;
        this.soundDesign = null;
        
        // Renderer info cache
        this.rendererInfo = null;
        
        // FPS calculation
        this.frameCount = 0;
        this.lastFpsUpdate = performance.now();
        this.currentFps = 60;
        this.lastFrameTime = 16.67;
        
        // System states
        this.systems = {
            postProcessing: { label: 'Post-Processing', enabled: !this.params.nopost },
            lighting: { label: 'Turrell Lighting', enabled: !this.params.nolighting },
            wingEnhancements: { label: 'Wing Effects', enabled: true },
            particles: { label: 'Particles', enabled: !this.params.noparticles },
            collision: { label: 'Collision', enabled: !this.params.noclip },
            audio: { label: 'Audio', enabled: !this.params.noaudio },
        };
        
        this.noclipEnabled = this.params.noclip;
        this.wireframeEnabled = this.params.wireframe;
        
        // Bind keyboard handler
        this.handleKeydown = this.handleKeydown.bind(this);
        document.addEventListener('keydown', this.handleKeydown);
        
        if (this.enabled) {
            console.log('Debug system enabled. Press F3 for HUD, ` for console.');
        }
    }
    
    init(renderer, scene, camera) {
        this.renderer = renderer;
        this.scene = scene;
        this.camera = camera;
        
        // Create HUD
        this.hud = new DebugHUD();
        this.hud.createPerformancePanel();
        this.hud.createSystemsPanel(this.systems);
        this.hud.createNavigationPanel();
        this.hud.createActionsPanel();
        
        // Create console
        this.console = new DebugConsole(this);
        
        // Create visual helpers
        this.visualHelpers = new VisualHelpers(scene);
        
        // Setup UI event listeners
        this.setupEventListeners();
        
        // Apply initial states from URL params
        if (this.params.wireframe) {
            this.toggleWireframe();
        }
        
        if (this.params.debug || this.params.fps) {
            this.hud.show();
        }
        
        // Handle teleport param
        if (this.params.teleport) {
            const [x, y, z] = this.params.teleport.split(',').map(parseFloat);
            if (!isNaN(x) && !isNaN(z)) {
                setTimeout(() => this.teleport(x, y || 1.7, z), 1000);
            }
        }
    }
    
    setupEventListeners() {
        // System toggles
        for (const key of Object.keys(this.systems)) {
            const checkbox = document.getElementById(`debug-toggle-${key}`);
            if (checkbox) {
                checkbox.addEventListener('change', (e) => {
                    this.systems[key].enabled = e.target.checked;
                    this.applySystemState(key);
                });
            }
        }
        
        // Quality selector
        const qualitySelect = document.getElementById('debug-quality');
        if (qualitySelect) {
            if (this.params.quality) {
                qualitySelect.value = this.params.quality;
            }
            qualitySelect.addEventListener('change', (e) => {
                this.setQuality(e.target.value);
            });
        }
        
        // Noclip toggle
        const noclipCheckbox = document.getElementById('debug-noclip');
        if (noclipCheckbox) {
            noclipCheckbox.checked = this.noclipEnabled;
            noclipCheckbox.addEventListener('change', (e) => {
                this.noclipEnabled = e.target.checked;
                if (this.navigation) {
                    this.navigation.noclipEnabled = this.noclipEnabled;
                }
            });
        }
        
        // Teleport buttons
        document.getElementById('debug-teleport-center')?.addEventListener('click', () => {
            this.teleport(0, 1.7, 0);
        });
        document.getElementById('debug-teleport-rotunda')?.addEventListener('click', () => {
            this.teleport(0, 1.7, -5);
        });
        
        // Action buttons
        document.getElementById('debug-wireframe')?.addEventListener('click', () => {
            this.toggleWireframe();
        });
        document.getElementById('debug-screenshot')?.addEventListener('click', () => {
            this.screenshot();
        });
        document.getElementById('debug-record')?.addEventListener('click', () => {
            if (this.recorder.recording) {
                this.stopRecording();
            } else {
                this.startRecording();
            }
        });
    }
    
    handleKeydown(e) {
        // Don't handle if typing in console
        if (this.console?.visible && e.target === this.console.input) {
            return;
        }
        
        switch (e.key) {
            case '`':
            case '~':
                e.preventDefault();
                this.console?.toggle();
                break;
            case 'F3':
                e.preventDefault();
                this.toggleHUD();
                break;
            case 'F4':
                e.preventDefault();
                this.toggleWireframe();
                break;
            case 'F5':
                e.preventDefault();
                this.cycleQuality();
                break;
            case 'F6':
                e.preventDefault();
                this.toggleSystem('postProcessing');
                break;
            case 'F7':
                e.preventDefault();
                this.toggleNoclip();
                break;
            case 'F8':
                e.preventDefault();
                this.screenshot();
                break;
        }
    }
    
    update(deltaTime) {
        // Calculate FPS
        this.frameCount++;
        const now = performance.now();
        const elapsed = now - this.lastFpsUpdate;
        
        if (elapsed >= 100) { // Update 10 times per second
            this.currentFps = (this.frameCount / elapsed) * 1000;
            this.frameCount = 0;
            this.lastFpsUpdate = now;
        }
        
        this.lastFrameTime = deltaTime * 1000;
        
        // Get renderer info
        if (this.renderer) {
            this.rendererInfo = this.renderer.info;
        }
        
        // Update HUD
        if (this.hud?.visible) {
            this.hud.updatePerformance(
                this.currentFps,
                this.lastFrameTime,
                this.rendererInfo
            );
            
            // Update navigation info
            if (this.navigation) {
                this.hud.updateNavigation(
                    this.camera?.position,
                    this.navigation.velocity,
                    this.navigation.currentZone || 'unknown',
                    this.navigation.isLocked
                );
            }
        }
        
        // Record metrics
        if (this.recorder.recording) {
            this.recorder.record({
                fps: this.currentFps,
                frameTime: this.lastFrameTime,
                drawCalls: this.rendererInfo?.render?.calls || 0,
                triangles: this.rendererInfo?.render?.triangles || 0,
            });
        }
    }
    
    toggleHUD() {
        return this.hud?.toggle();
    }
    
    toggleWireframe() {
        this.wireframeEnabled = this.visualHelpers?.toggleWireframe() || false;
        this.console?.log('Wireframe: ' + (this.wireframeEnabled ? 'ON' : 'OFF'), 'info');
        return this.wireframeEnabled;
    }
    
    toggleNoclip() {
        this.noclipEnabled = !this.noclipEnabled;
        if (this.navigation) {
            this.navigation.noclipEnabled = this.noclipEnabled;
        }
        const checkbox = document.getElementById('debug-noclip');
        if (checkbox) checkbox.checked = this.noclipEnabled;
        this.console?.log('Noclip: ' + (this.noclipEnabled ? 'ON' : 'OFF'), 'info');
        return this.noclipEnabled;
    }
    
    toggleSystem(systemKey) {
        if (!this.systems[systemKey]) {
            this.console?.log('Unknown system: ' + systemKey, 'error');
            return;
        }
        
        this.systems[systemKey].enabled = !this.systems[systemKey].enabled;
        const checkbox = document.getElementById(`debug-toggle-${systemKey}`);
        if (checkbox) checkbox.checked = this.systems[systemKey].enabled;
        
        this.applySystemState(systemKey);
        this.console?.log(`${this.systems[systemKey].label}: ${this.systems[systemKey].enabled ? 'ON' : 'OFF'}`, 'info');
    }
    
    applySystemState(systemKey) {
        const enabled = this.systems[systemKey].enabled;
        
        switch (systemKey) {
            case 'postProcessing':
                if (this.postProcessing) {
                    this.postProcessing.enabled = enabled;
                }
                break;
            case 'lighting':
                if (this.lighting) {
                    this.lighting.enabled = enabled;
                }
                break;
            case 'wingEnhancements':
                if (this.wingEnhancements?.enhancements) {
                    this.wingEnhancements.enhancements.forEach(e => {
                        e.group.visible = enabled;
                    });
                }
                break;
            case 'collision':
                this.noclipEnabled = !enabled;
                if (this.navigation) {
                    this.navigation.noclipEnabled = this.noclipEnabled;
                }
                break;
            case 'audio':
                if (this.soundDesign) {
                    if (enabled) {
                        this.soundDesign.unmute?.();
                    } else {
                        this.soundDesign.mute?.();
                    }
                }
                break;
        }
    }
    
    setQuality(preset) {
        this.console?.log('Setting quality: ' + preset, 'info');
        // Quality is applied through the PerformanceManager
        // This is a placeholder - integration happens in main.js
        const event = new CustomEvent('debug-quality-change', { detail: { preset } });
        document.dispatchEvent(event);
    }
    
    cycleQuality() {
        const presets = ['emergency', 'low', 'medium', 'high', 'ultra'];
        const select = document.getElementById('debug-quality');
        if (select) {
            const currentIndex = presets.indexOf(select.value);
            const nextIndex = (currentIndex + 1) % presets.length;
            select.value = presets[nextIndex];
            this.setQuality(presets[nextIndex]);
        }
    }
    
    teleport(x, y, z) {
        if (this.camera && !isNaN(x) && !isNaN(y) && !isNaN(z)) {
            this.camera.position.set(x, y, z);
            this.console?.log(`Teleported to ${x}, ${y}, ${z}`, 'info');
        }
    }
    
    screenshot() {
        if (!this.renderer) return;
        
        const canvas = this.renderer.domElement;
        const link = document.createElement('a');
        link.download = `museum-screenshot-${Date.now()}.png`;
        link.href = canvas.toDataURL('image/png');
        link.click();
        this.console?.log('Screenshot saved', 'info');
    }
    
    startRecording() {
        this.recorder.start();
        const btn = document.getElementById('debug-record');
        if (btn) btn.textContent = 'Stop';
        this.console?.log('Recording started', 'info');
    }
    
    stopRecording() {
        this.recorder.stop();
        this.recorder.export();
        const btn = document.getElementById('debug-record');
        if (btn) btn.textContent = 'Record';
        this.console?.log('Recording saved', 'info');
    }
    
    // Getters for URL params
    get shouldDisablePost() { return this.params.nopost || !this.systems.postProcessing.enabled; }
    get shouldDisableAudio() { return this.params.noaudio || !this.systems.audio.enabled; }
    get shouldDisableLighting() { return this.params.nolighting || !this.systems.lighting.enabled; }
    get shouldDisableParticles() { return this.params.noparticles || !this.systems.particles.enabled; }
    get isMinimalMode() { return this.params.minimal; }
    get forcedQuality() { return this.params.quality; }
    
    dispose() {
        document.removeEventListener('keydown', this.handleKeydown);
        this.hud?.dispose();
        this.console?.dispose();
        this.visualHelpers?.dispose();
    }
}

// Export singleton instance
let debugManagerInstance = null;

export function getDebugManager() {
    if (!debugManagerInstance) {
        debugManagerInstance = new DebugManager();
    }
    return debugManagerInstance;
}

export { parseDebugParams };
