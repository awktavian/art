/**
 * Settings Menu & Performance Visualization
 * ==========================================
 * 
 * User-friendly settings menu with:
 * - Simple quality presets (Auto/Low/Medium/High/Ultra)
 * - Advanced toggle options
 * - Real-time performance graphs
 * - Device auto-detection
 * - Adaptive quality system
 * 
 * Pareto optimal: Balance quality vs. performance automatically
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// DEVICE PROFILES - Pareto optimal presets per device class
// ═══════════════════════════════════════════════════════════════════════════

const DEVICE_PROFILES = {
    // High-end desktop (M1/M2/RTX/RX)
    desktop_high: {
        name: 'High-End Desktop',
        defaultPreset: 'high',
        adaptiveRange: ['medium', 'high', 'ultra'],
        targetFPS: 60,
        minFPS: 45
    },
    // Mid-range desktop
    desktop_mid: {
        name: 'Desktop',
        defaultPreset: 'medium',
        adaptiveRange: ['low', 'medium', 'high'],
        targetFPS: 60,
        minFPS: 30
    },
    // Low-end desktop / old laptop
    desktop_low: {
        name: 'Basic Desktop',
        defaultPreset: 'low',
        adaptiveRange: ['emergency', 'low', 'medium'],
        targetFPS: 30,
        minFPS: 20
    },
    // Modern tablet (iPad Pro, etc)
    tablet_high: {
        name: 'Tablet',
        defaultPreset: 'medium',
        adaptiveRange: ['low', 'medium'],
        targetFPS: 60,
        minFPS: 30
    },
    // Mobile phone
    mobile: {
        name: 'Mobile',
        defaultPreset: 'low',
        adaptiveRange: ['emergency', 'low'],
        targetFPS: 30,
        minFPS: 20
    },
    // VR headset (Quest, etc)
    vr: {
        name: 'VR Headset',
        defaultPreset: 'medium',
        adaptiveRange: ['low', 'medium'],
        targetFPS: 72,  // Quest native
        minFPS: 60
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// SETTINGS MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export class SettingsManager {
    constructor() {
        this.deviceProfile = null;
        this.currentPreset = 'medium';
        this.adaptiveEnabled = true;
        this.settings = {};
        
        // Performance tracking
        this.fpsHistory = new Array(120).fill(60);
        this.frameTimeHistory = new Array(120).fill(16.67);
        this.historyIndex = 0;
        this.lastFpsUpdate = performance.now();
        this.frameCount = 0;
        this.currentFps = 60;
        this.currentFrameTime = 16.67;
        
        // Adaptive quality state
        this.adaptiveTimer = 0;
        this.stableFrames = 0;
        this.lastAdaptTime = 0;
        
        // UI elements
        this.menuContainer = null;
        this.perfOverlay = null;
        
        // Detect device and set defaults
        this.detectDevice();
        this.loadSettings();
        
        // Low FPS counter for adaptive quality
        this.lowFpsCount = 0;
    }
    
    /**
     * Sync with PerformanceManager preset (call after PerformanceManager is initialized)
     */
    syncWithPerformanceManager(performanceManager) {
        if (performanceManager) {
            const pmPreset = performanceManager.getPresetName();
            // Only sync if we haven't saved custom settings
            if (!localStorage.getItem('museum-settings')) {
                this.currentPreset = pmPreset;
                console.log(`Settings synced with PerformanceManager: ${pmPreset}`);
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DEVICE DETECTION
    // ═══════════════════════════════════════════════════════════════════════
    
    detectDevice() {
        const ua = navigator.userAgent.toLowerCase();
        const memory = navigator.deviceMemory || 4;
        const cores = navigator.hardwareConcurrency || 4;
        
        // Check for VR
        if (/oculus|quest/i.test(ua) || navigator.xr) {
            this.deviceProfile = DEVICE_PROFILES.vr;
            return;
        }
        
        // Check for mobile
        const isMobile = /android|iphone|ipod|webos|blackberry|windows phone/i.test(ua);
        const isTablet = /ipad|android(?!.*mobile)/i.test(ua) || 
                         (window.innerWidth >= 768 && 'ontouchstart' in window);
        
        if (isMobile && !isTablet) {
            this.deviceProfile = DEVICE_PROFILES.mobile;
            return;
        }
        
        if (isTablet) {
            this.deviceProfile = DEVICE_PROFILES.tablet_high;
            return;
        }
        
        // Desktop - check GPU
        const gpuTier = this.detectGPUTier();
        
        if (gpuTier >= 3 || (memory >= 16 && cores >= 8)) {
            this.deviceProfile = DEVICE_PROFILES.desktop_high;
        } else if (gpuTier >= 2 || (memory >= 8 && cores >= 4)) {
            this.deviceProfile = DEVICE_PROFILES.desktop_mid;
        } else {
            this.deviceProfile = DEVICE_PROFILES.desktop_low;
        }
        
        console.log(`Device detected: ${this.deviceProfile.name} (GPU tier ${gpuTier}, ${memory}GB RAM, ${cores} cores)`);
    }
    
    detectGPUTier() {
        const canvas = document.createElement('canvas');
        const gl = canvas.getContext('webgl');
        if (!gl) return 0;
        
        try {
            const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
            if (!debugInfo) return 1;
            
            const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL).toLowerCase();
            
            // High-end
            if (/nvidia.*rtx|nvidia.*gtx (16|20|30|40)|amd.*rx (5|6|7)|apple m[123]/i.test(renderer)) {
                return 3;
            }
            // Mid-range
            if (/nvidia|amd|radeon/i.test(renderer)) {
                return 2;
            }
            // Low-end
            if (/intel|mali|adreno|powervr/i.test(renderer)) {
                return 1;
            }
        } catch (e) {
            console.warn('GPU detection failed:', e);
        } finally {
            const ext = gl.getExtension('WEBGL_lose_context');
            if (ext) ext.loseContext();
        }
        
        return 1;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SETTINGS PERSISTENCE
    // ═══════════════════════════════════════════════════════════════════════
    
    loadSettings() {
        try {
            const saved = localStorage.getItem('museum-settings');
            if (saved) {
                const parsed = JSON.parse(saved);
                this.currentPreset = parsed.preset || this.deviceProfile.defaultPreset;
                this.adaptiveEnabled = parsed.adaptive !== false;
                this.settings = parsed.settings || {};
            } else {
                // Use device defaults - high-end desktop should use 'high' not 'medium'
                this.currentPreset = this.deviceProfile.defaultPreset;
                this.settings = {
                    postProcessing: true, // Always enable by default on capable devices
                    particles: true,
                    shadows: this.deviceProfile !== DEVICE_PROFILES.mobile && 
                             this.deviceProfile !== DEVICE_PROFILES.desktop_low,
                    audio: true
                };
            }
        } catch (e) {
            console.warn('Failed to load settings:', e);
            this.currentPreset = this.deviceProfile.defaultPreset;
        }
        
        console.log(`Settings loaded: preset=${this.currentPreset}, adaptive=${this.adaptiveEnabled}`);
    }
    
    saveSettings() {
        try {
            localStorage.setItem('museum-settings', JSON.stringify({
                preset: this.currentPreset,
                adaptive: this.adaptiveEnabled,
                settings: this.settings
            }));
        } catch (e) {
            console.warn('Failed to save settings:', e);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ADAPTIVE QUALITY SYSTEM
    // ═══════════════════════════════════════════════════════════════════════
    
    updatePerformance(deltaTime) {
        this.frameCount++;
        const now = performance.now();
        const elapsed = now - this.lastFpsUpdate;
        
        // Update FPS every 100ms
        if (elapsed >= 100) {
            this.currentFps = (this.frameCount / elapsed) * 1000;
            this.currentFrameTime = elapsed / this.frameCount;
            
            // Store in history
            this.fpsHistory[this.historyIndex] = this.currentFps;
            this.frameTimeHistory[this.historyIndex] = this.currentFrameTime;
            this.historyIndex = (this.historyIndex + 1) % 120;
            
            this.frameCount = 0;
            this.lastFpsUpdate = now;
            
            // Run adaptive quality check
            if (this.adaptiveEnabled) {
                this.adaptQuality();
            }
        }
    }
    
    adaptQuality() {
        const now = performance.now();
        
        // Don't adapt too frequently (min 3 seconds between changes)
        if (now - this.lastAdaptTime < 3000) return;
        
        const avgFps = this.getAverageFPS(30); // Last 3 seconds
        const profile = this.deviceProfile;
        const range = profile.adaptiveRange;
        const currentIndex = range.indexOf(this.currentPreset);
        
        // If preset not in range, find closest
        if (currentIndex === -1) {
            // Check if current preset is above or below range
            const presetOrder = ['emergency', 'low', 'medium', 'high', 'ultra'];
            const currentOrder = presetOrder.indexOf(this.currentPreset);
            const rangeMaxOrder = presetOrder.indexOf(range[range.length - 1]);
            
            // If we're above the range max, that's fine - don't reduce
            if (currentOrder >= rangeMaxOrder) return;
            
            // Otherwise use the default from range
            return;
        }
        
        // CRITICAL: Only reduce quality if SUSTAINED low FPS (not brief dips)
        // Use 5-second rolling average and require 3 consecutive low readings
        if (avgFps < profile.minFPS - 5) { // Give 5fps buffer
            this.lowFpsCount = (this.lowFpsCount || 0) + 1;
            
            // Require 3 consecutive low readings before reducing
            if (this.lowFpsCount >= 3 && currentIndex > 0) {
                const newPreset = range[currentIndex - 1];
                console.log(`Adaptive: Sustained low FPS (${avgFps.toFixed(0)}), reducing to ${newPreset}`);
                this.setPreset(newPreset);
                this.lastAdaptTime = now;
                this.stableFrames = 0;
                this.lowFpsCount = 0;
            }
        } else {
            this.lowFpsCount = 0;
        }
        
        // Check if we can increase quality (need very stable high FPS)
        if (avgFps > profile.targetFPS * 0.92 && currentIndex < range.length - 1) {
            this.stableFrames++;
            
            // Require 80 stable samples (~8 seconds) before increasing
            if (this.stableFrames > 80) {
                const newPreset = range[currentIndex + 1];
                console.log(`Adaptive: Stable high FPS (${avgFps.toFixed(0)}), increasing to ${newPreset}`);
                this.setPreset(newPreset);
                this.lastAdaptTime = now;
                this.stableFrames = 0;
            }
        } else if (avgFps < profile.targetFPS * 0.85) {
            this.stableFrames = 0;
        }
    }
    
    getAverageFPS(samples = 60) {
        let sum = 0;
        let count = 0;
        for (let i = 0; i < samples; i++) {
            const idx = (this.historyIndex - 1 - i + 120) % 120;
            if (this.fpsHistory[idx] > 0) {
                sum += this.fpsHistory[idx];
                count++;
            }
        }
        return count > 0 ? sum / count : 60;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PRESET MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════════
    
    setPreset(presetName) {
        this.currentPreset = presetName;
        this.saveSettings();
        
        // Dispatch event for other systems to respond
        const event = new CustomEvent('settings-preset-change', {
            detail: { preset: presetName }
        });
        document.dispatchEvent(event);
        
        // Update UI
        this.updateUI();
    }
    
    setSetting(key, value) {
        this.settings[key] = value;
        this.saveSettings();
        
        const event = new CustomEvent('settings-change', {
            detail: { key, value }
        });
        document.dispatchEvent(event);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UI CREATION
    // ═══════════════════════════════════════════════════════════════════════
    
    createSettingsMenu() {
        if (this.menuContainer) return;
        
        // Inject styles
        this.injectStyles();
        
        // Create menu container
        this.menuContainer = document.createElement('div');
        this.menuContainer.id = 'settings-menu';
        this.menuContainer.className = 'hidden';
        this.menuContainer.innerHTML = this.getMenuHTML();
        document.body.appendChild(this.menuContainer);
        
        // Create settings button
        const settingsBtn = document.createElement('button');
        settingsBtn.id = 'settings-button';
        settingsBtn.innerHTML = '⚙️';
        settingsBtn.title = 'Settings';
        settingsBtn.addEventListener('click', () => this.toggleMenu());
        document.body.appendChild(settingsBtn);
        
        // Bind events
        this.bindMenuEvents();
        this.updateUI();
    }
    
    createPerfOverlay() {
        if (this.perfOverlay) return;
        
        this.perfOverlay = document.createElement('div');
        this.perfOverlay.id = 'perf-overlay';
        this.perfOverlay.innerHTML = `
            <div class="perf-header">
                <span class="perf-fps">60</span>
                <span class="perf-label">FPS</span>
            </div>
            <canvas id="perf-graph" width="200" height="60"></canvas>
            <div class="perf-stats">
                <div class="perf-stat">
                    <span class="stat-label">Frame</span>
                    <span class="stat-value" id="stat-frametime">16.7ms</span>
                </div>
                <div class="perf-stat">
                    <span class="stat-label">Draw</span>
                    <span class="stat-value" id="stat-drawcalls">0</span>
                </div>
                <div class="perf-stat">
                    <span class="stat-label">Tris</span>
                    <span class="stat-value" id="stat-triangles">0</span>
                </div>
            </div>
            <div class="perf-device">
                <span>${this.deviceProfile.name}</span>
                <span class="perf-preset">${this.currentPreset}</span>
            </div>
        `;
        document.body.appendChild(this.perfOverlay);
        
        this.perfCanvas = document.getElementById('perf-graph');
        this.perfCtx = this.perfCanvas.getContext('2d');
    }
    
    getMenuHTML() {
        return `
            <div class="settings-header">
                <h2>Settings</h2>
                <button class="settings-close">&times;</button>
            </div>
            
            <div class="settings-section">
                <h3>Quality</h3>
                <div class="quality-presets">
                    <button class="preset-btn" data-preset="auto">
                        <span class="preset-icon">🔄</span>
                        <span class="preset-name">Auto</span>
                        <span class="preset-desc">Adapts to your device</span>
                    </button>
                    <button class="preset-btn" data-preset="low">
                        <span class="preset-icon">🌱</span>
                        <span class="preset-name">Low</span>
                        <span class="preset-desc">Best performance</span>
                    </button>
                    <button class="preset-btn" data-preset="medium">
                        <span class="preset-icon">⚖️</span>
                        <span class="preset-name">Medium</span>
                        <span class="preset-desc">Balanced</span>
                    </button>
                    <button class="preset-btn" data-preset="high">
                        <span class="preset-icon">✨</span>
                        <span class="preset-name">High</span>
                        <span class="preset-desc">Best quality</span>
                    </button>
                </div>
            </div>
            
            <div class="settings-section">
                <h3>Features</h3>
                <label class="setting-toggle">
                    <input type="checkbox" id="setting-postprocessing" checked>
                    <span class="toggle-slider"></span>
                    <span class="toggle-label">Post-Processing</span>
                    <span class="toggle-desc">Bloom, color grading</span>
                </label>
                <label class="setting-toggle">
                    <input type="checkbox" id="setting-particles" checked>
                    <span class="toggle-slider"></span>
                    <span class="toggle-label">Particles</span>
                    <span class="toggle-desc">Dust, atmosphere</span>
                </label>
                <label class="setting-toggle">
                    <input type="checkbox" id="setting-shadows" checked>
                    <span class="toggle-slider"></span>
                    <span class="toggle-label">Shadows</span>
                    <span class="toggle-desc">Dynamic shadows</span>
                </label>
                <label class="setting-toggle">
                    <input type="checkbox" id="setting-audio" checked>
                    <span class="toggle-slider"></span>
                    <span class="toggle-label">Sound</span>
                    <span class="toggle-desc">Ambient audio</span>
                </label>
            </div>
            
            <div class="settings-section">
                <h3>Performance</h3>
                <div class="perf-mini">
                    <div class="perf-mini-fps">
                        <span class="fps-value">60</span>
                        <span class="fps-label">FPS</span>
                    </div>
                    <canvas id="mini-perf-graph" width="150" height="40"></canvas>
                </div>
                <label class="setting-toggle">
                    <input type="checkbox" id="setting-adaptive" checked>
                    <span class="toggle-slider"></span>
                    <span class="toggle-label">Adaptive Quality</span>
                    <span class="toggle-desc">Auto-adjust for smooth performance</span>
                </label>
                <label class="setting-toggle">
                    <input type="checkbox" id="setting-perfoverlay">
                    <span class="toggle-slider"></span>
                    <span class="toggle-label">Show FPS</span>
                    <span class="toggle-desc">Performance overlay</span>
                </label>
            </div>
            
            <div class="settings-section settings-data">
                <h3>Data</h3>
                <div class="journey-stats" id="journey-stats">
                    <div class="stat-item">
                        <span class="stat-label">Patents Viewed</span>
                        <span class="stat-value" id="stat-patents">0/54</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Wings Explored</span>
                        <span class="stat-value" id="stat-wings">1/8</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-label">Total Time</span>
                        <span class="stat-value" id="stat-time">0m</span>
                    </div>
                </div>
                <button class="clear-data-btn" id="clear-data-btn">
                    <span class="clear-icon">🗑️</span>
                    <span class="clear-text">Clear All Data</span>
                </button>
            </div>
            
            <div class="settings-footer">
                <span class="device-info">${this.deviceProfile.name}</span>
                <span class="version-info">v1.0</span>
            </div>
        `;
    }
    
    injectStyles() {
        if (document.getElementById('settings-menu-styles')) return;
        
        const style = document.createElement('style');
        style.id = 'settings-menu-styles';
        style.textContent = `
            #settings-button {
                position: fixed;
                top: 15px;
                right: 15px;
                width: 44px;
                height: 44px;
                border-radius: 50%;
                background: rgba(0, 0, 0, 0.7);
                border: 1px solid rgba(103, 212, 228, 0.3);
                color: #67d4e4;
                font-size: 20px;
                cursor: pointer;
                z-index: 9000;
                transition: all 0.2s;
            }
            
            #settings-button:hover {
                background: rgba(103, 212, 228, 0.2);
                transform: rotate(90deg);
            }
            
            #settings-menu {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                width: 360px;
                max-height: 80vh;
                background: rgba(10, 10, 20, 0.95);
                border: 1px solid rgba(103, 212, 228, 0.3);
                border-radius: 12px;
                z-index: 9500;
                overflow-y: auto;
                font-family: 'IBM Plex Sans', -apple-system, sans-serif;
                color: #e0e0e0;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
            }
            
            #settings-menu.hidden {
                display: none;
            }
            
            .settings-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 16px 20px;
                border-bottom: 1px solid rgba(103, 212, 228, 0.2);
            }
            
            .settings-header h2 {
                margin: 0;
                font-size: 18px;
                font-weight: 500;
                color: #67d4e4;
            }
            
            .settings-close {
                background: none;
                border: none;
                color: #999;
                font-size: 24px;
                cursor: pointer;
                padding: 0;
                line-height: 1;
            }
            
            .settings-close:hover {
                color: #fff;
            }
            
            .settings-section {
                padding: 16px 20px;
                border-bottom: 1px solid rgba(103, 212, 228, 0.1);
            }
            
            .settings-section h3 {
                margin: 0 0 12px;
                font-size: 12px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 1px;
                color: #888;
            }
            
            .quality-presets {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 8px;
            }
            
            .preset-btn {
                display: flex;
                flex-direction: column;
                align-items: center;
                padding: 12px 8px;
                background: rgba(255, 255, 255, 0.03);
                border: 1px solid rgba(255, 255, 255, 0.1);
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .preset-btn:hover {
                background: rgba(103, 212, 228, 0.1);
                border-color: rgba(103, 212, 228, 0.3);
            }
            
            .preset-btn.active {
                background: rgba(103, 212, 228, 0.15);
                border-color: #67d4e4;
            }
            
            .preset-icon {
                font-size: 24px;
                margin-bottom: 4px;
            }
            
            .preset-name {
                font-size: 14px;
                font-weight: 500;
                color: #fff;
            }
            
            .preset-desc {
                font-size: 10px;
                color: #888;
                margin-top: 2px;
            }
            
            .setting-toggle {
                display: flex;
                align-items: center;
                padding: 10px 0;
                cursor: pointer;
                border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            }
            
            .setting-toggle:last-child {
                border-bottom: none;
            }
            
            .setting-toggle input {
                display: none;
            }
            
            .toggle-slider {
                width: 44px;
                height: 24px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 12px;
                position: relative;
                transition: background 0.2s;
                flex-shrink: 0;
            }
            
            .toggle-slider::after {
                content: '';
                position: absolute;
                width: 20px;
                height: 20px;
                background: #fff;
                border-radius: 50%;
                top: 2px;
                left: 2px;
                transition: transform 0.2s;
            }
            
            .setting-toggle input:checked + .toggle-slider {
                background: #67d4e4;
            }
            
            .setting-toggle input:checked + .toggle-slider::after {
                transform: translateX(20px);
            }
            
            .toggle-label {
                flex: 1;
                margin-left: 12px;
                font-size: 14px;
            }
            
            .toggle-desc {
                font-size: 11px;
                color: #666;
                margin-left: auto;
            }
            
            .perf-mini {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 12px;
                padding: 12px;
                background: rgba(0, 0, 0, 0.3);
                border-radius: 8px;
            }
            
            .perf-mini-fps {
                display: flex;
                flex-direction: column;
                align-items: center;
            }
            
            .fps-value {
                font-size: 28px;
                font-weight: 600;
                color: #7db87e;
                font-family: 'IBM Plex Mono', monospace;
            }
            
            .fps-value.warning { color: #f59e0b; }
            .fps-value.critical { color: #ef4444; }
            
            .fps-label {
                font-size: 10px;
                color: #888;
                text-transform: uppercase;
            }
            
            #mini-perf-graph {
                flex: 1;
                background: rgba(0, 0, 0, 0.3);
                border-radius: 4px;
            }
            
            .settings-footer {
                display: flex;
                justify-content: space-between;
                padding: 12px 20px;
                font-size: 11px;
                color: #555;
            }
            
            /* Journey Stats */
            .journey-stats {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 8px;
                margin-bottom: 12px;
            }
            
            .stat-item {
                text-align: center;
                padding: 8px;
                background: rgba(255, 255, 255, 0.03);
                border-radius: 6px;
            }
            
            .stat-label {
                display: block;
                font-size: 10px;
                color: #666;
                margin-bottom: 4px;
            }
            
            .stat-value {
                display: block;
                font-size: 14px;
                font-weight: 600;
                color: #67d4e4;
            }
            
            /* Clear Data Button */
            .clear-data-btn {
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
                width: 100%;
                padding: 10px;
                background: rgba(255, 100, 100, 0.1);
                border: 1px solid rgba(255, 100, 100, 0.3);
                border-radius: 6px;
                color: #ff6b6b;
                font-size: 13px;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .clear-data-btn:hover {
                background: rgba(255, 100, 100, 0.2);
                border-color: rgba(255, 100, 100, 0.5);
            }
            
            /* Confirmation Dialog */
            .confirm-overlay {
                position: fixed;
                inset: 0;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                animation: fadeIn 0.2s ease-out;
            }
            
            @keyframes fadeIn {
                from { opacity: 0; }
                to { opacity: 1; }
            }
            
            .confirm-dialog {
                background: rgba(15, 15, 25, 0.98);
                border: 1px solid rgba(255, 100, 100, 0.3);
                border-radius: 12px;
                padding: 24px;
                max-width: 320px;
                text-align: center;
            }
            
            .confirm-dialog h3 {
                margin: 0 0 12px;
                color: #ff6b6b;
                font-size: 18px;
            }
            
            .confirm-dialog p {
                margin: 0 0 20px;
                color: #999;
                font-size: 13px;
                line-height: 1.5;
            }
            
            .confirm-buttons {
                display: flex;
                gap: 12px;
            }
            
            .confirm-cancel, .confirm-clear {
                flex: 1;
                padding: 10px;
                border-radius: 6px;
                font-size: 13px;
                cursor: pointer;
                transition: all 0.2s;
            }
            
            .confirm-cancel {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: #ccc;
            }
            
            .confirm-cancel:hover {
                background: rgba(255, 255, 255, 0.15);
            }
            
            .confirm-clear {
                background: rgba(255, 100, 100, 0.2);
                border: 1px solid rgba(255, 100, 100, 0.5);
                color: #ff6b6b;
            }
            
            .confirm-clear:hover {
                background: rgba(255, 100, 100, 0.3);
            }
            
            /* Performance Overlay */
            #perf-overlay {
                position: fixed;
                top: 70px;
                right: 15px;
                width: 200px;
                background: rgba(0, 0, 0, 0.85);
                border: 1px solid rgba(103, 212, 228, 0.3);
                border-radius: 8px;
                padding: 12px;
                font-family: 'IBM Plex Mono', monospace;
                font-size: 11px;
                color: #e0e0e0;
                z-index: 8999;
            }
            
            #perf-overlay.hidden {
                display: none;
            }
            
            .perf-header {
                display: flex;
                align-items: baseline;
                gap: 6px;
                margin-bottom: 8px;
            }
            
            .perf-fps {
                font-size: 32px;
                font-weight: 600;
                color: #7db87e;
            }
            
            .perf-fps.warning { color: #f59e0b; }
            .perf-fps.critical { color: #ef4444; }
            
            .perf-label {
                font-size: 12px;
                color: #888;
            }
            
            #perf-graph {
                width: 100%;
                background: rgba(0, 0, 0, 0.3);
                border-radius: 4px;
                margin-bottom: 8px;
            }
            
            .perf-stats {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 8px;
                margin-bottom: 8px;
            }
            
            .perf-stat {
                display: flex;
                flex-direction: column;
            }
            
            .stat-label {
                font-size: 9px;
                color: #666;
                text-transform: uppercase;
            }
            
            .stat-value {
                font-size: 12px;
                color: #67d4e4;
            }
            
            .perf-device {
                display: flex;
                justify-content: space-between;
                font-size: 10px;
                color: #555;
                padding-top: 8px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }
            
            .perf-preset {
                text-transform: capitalize;
                color: #67d4e4;
            }
            
            @media (max-width: 400px) {
                #settings-menu {
                    width: 95%;
                    max-height: 90vh;
                }
                
                .quality-presets {
                    grid-template-columns: repeat(2, 1fr);
                }
            }
        `;
        document.head.appendChild(style);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UI EVENTS
    // ═══════════════════════════════════════════════════════════════════════
    
    bindMenuEvents() {
        // Close button
        this.menuContainer.querySelector('.settings-close').addEventListener('click', () => {
            this.hideMenu();
        });
        
        // Preset buttons
        this.menuContainer.querySelectorAll('.preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const preset = btn.dataset.preset;
                if (preset === 'auto') {
                    this.adaptiveEnabled = true;
                    this.setPreset(this.deviceProfile.defaultPreset);
                } else {
                    this.adaptiveEnabled = false;
                    this.setPreset(preset);
                }
                this.updateUI();
            });
        });
        
        // Feature toggles
        const toggles = {
            'setting-postprocessing': 'postProcessing',
            'setting-particles': 'particles',
            'setting-shadows': 'shadows',
            'setting-audio': 'audio',
            'setting-adaptive': 'adaptive',
            'setting-perfoverlay': 'perfOverlay'
        };
        
        Object.entries(toggles).forEach(([id, key]) => {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('change', () => {
                    if (key === 'adaptive') {
                        this.adaptiveEnabled = el.checked;
                        this.saveSettings();
                    } else if (key === 'perfOverlay') {
                        if (el.checked) {
                            this.showPerfOverlay();
                        } else {
                            this.hidePerfOverlay();
                        }
                    } else {
                        this.setSetting(key, el.checked);
                    }
                });
            }
        });
        
        // Click outside to close
        document.addEventListener('click', (e) => {
            if (!this.menuContainer.contains(e.target) && 
                !document.getElementById('settings-button').contains(e.target) &&
                !this.menuContainer.classList.contains('hidden')) {
                this.hideMenu();
            }
        });
        
        // ESC to close
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.menuContainer.classList.contains('hidden')) {
                this.hideMenu();
            }
        });
        
        // Clear data button
        const clearBtn = document.getElementById('clear-data-btn');
        if (clearBtn) {
            clearBtn.addEventListener('click', () => {
                this.showClearDataConfirm();
            });
        }
    }
    
    /**
     * Show confirmation dialog for clearing data
     */
    showClearDataConfirm() {
        // Create confirmation overlay
        const overlay = document.createElement('div');
        overlay.className = 'confirm-overlay';
        overlay.innerHTML = `
            <div class="confirm-dialog">
                <h3>Clear All Data?</h3>
                <p>This will reset your journey progress, settings, and preferences. This action cannot be undone.</p>
                <div class="confirm-buttons">
                    <button class="confirm-cancel">Cancel</button>
                    <button class="confirm-clear">Clear Data</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        
        // Bind events
        overlay.querySelector('.confirm-cancel').addEventListener('click', () => {
            overlay.remove();
        });
        
        overlay.querySelector('.confirm-clear').addEventListener('click', () => {
            this.clearAllData();
            overlay.remove();
        });
        
        // Click outside to cancel
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) {
                overlay.remove();
            }
        });
    }
    
    /**
     * Clear all localStorage data and reload
     */
    clearAllData() {
        try {
            localStorage.removeItem('kagami-museum');
            localStorage.removeItem('museum-settings');
            localStorage.removeItem('museum-accessibility');
            console.log('🗑️ All data cleared');
            window.location.reload();
        } catch (err) {
            console.error('Failed to clear data:', err);
        }
    }
    
    /**
     * Update journey stats in settings
     */
    updateJourneyStats(stats) {
        const patentsEl = document.getElementById('stat-patents');
        const wingsEl = document.getElementById('stat-wings');
        const timeEl = document.getElementById('stat-time');
        
        if (patentsEl && stats.patentsViewed !== undefined) {
            patentsEl.textContent = `${stats.patentsViewed}/${stats.totalPatents || 54}`;
        }
        if (wingsEl && stats.visitedWingCount !== undefined) {
            wingsEl.textContent = `${stats.visitedWingCount}/${stats.totalWings || 8}`;
        }
        if (timeEl && stats.totalTime !== undefined) {
            timeEl.textContent = stats.totalTime;
        }
    }
    
    updateUI() {
        if (!this.menuContainer) return;
        
        // Update preset buttons
        this.menuContainer.querySelectorAll('.preset-btn').forEach(btn => {
            const preset = btn.dataset.preset;
            const isActive = (preset === 'auto' && this.adaptiveEnabled) ||
                           (preset === this.currentPreset && !this.adaptiveEnabled);
            btn.classList.toggle('active', isActive);
        });
        
        // Update toggles
        const postEl = document.getElementById('setting-postprocessing');
        if (postEl) postEl.checked = this.settings.postProcessing !== false;
        
        const particlesEl = document.getElementById('setting-particles');
        if (particlesEl) particlesEl.checked = this.settings.particles !== false;
        
        const shadowsEl = document.getElementById('setting-shadows');
        if (shadowsEl) shadowsEl.checked = this.settings.shadows !== false;
        
        const audioEl = document.getElementById('setting-audio');
        if (audioEl) audioEl.checked = this.settings.audio !== false;
        
        const adaptiveEl = document.getElementById('setting-adaptive');
        if (adaptiveEl) adaptiveEl.checked = this.adaptiveEnabled;
        
        // Update FPS in menu
        const fpsValue = this.menuContainer.querySelector('.fps-value');
        if (fpsValue) {
            fpsValue.textContent = Math.round(this.currentFps);
            fpsValue.className = 'fps-value ' + this.getFpsClass(this.currentFps);
        }
        
        // Update perf overlay preset
        if (this.perfOverlay) {
            this.perfOverlay.querySelector('.perf-preset').textContent = this.currentPreset;
        }
    }
    
    getFpsClass(fps) {
        if (fps >= 50) return '';
        if (fps >= 30) return 'warning';
        return 'critical';
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // MENU VISIBILITY
    // ═══════════════════════════════════════════════════════════════════════
    
    toggleMenu() {
        if (this.menuContainer.classList.contains('hidden')) {
            this.showMenu();
        } else {
            this.hideMenu();
        }
    }
    
    showMenu() {
        this.menuContainer.classList.remove('hidden');
        this.updateUI();
        
        // Fetch journey stats from tracker
        this.fetchJourneyStats();
    }
    
    /**
     * Fetch and display journey stats from the journey tracker
     */
    fetchJourneyStats() {
        try {
            // Try to get journey tracker
            const stored = localStorage.getItem('kagami-museum');
            if (stored) {
                const data = JSON.parse(stored);
                const stats = {
                    patentsViewed: data.viewedPatents?.length || 0,
                    totalPatents: 54,
                    visitedWingCount: Object.values(data.visitedWings || {}).filter(v => v).length,
                    totalWings: 8,
                    totalTime: this.formatDuration(data.totalTimeSeconds || 0)
                };
                this.updateJourneyStats(stats);
            }
        } catch (err) {
            console.log('Could not fetch journey stats:', err);
        }
    }
    
    /**
     * Format duration in human-readable format
     */
    formatDuration(seconds) {
        if (seconds < 60) return `${Math.round(seconds)}s`;
        if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
        const hours = Math.floor(seconds / 3600);
        const mins = Math.round((seconds % 3600) / 60);
        return `${hours}h ${mins}m`;
    }
    
    hideMenu() {
        this.menuContainer.classList.add('hidden');
    }
    
    showPerfOverlay() {
        if (!this.perfOverlay) {
            this.createPerfOverlay();
        }
        this.perfOverlay.classList.remove('hidden');
    }
    
    hidePerfOverlay() {
        if (this.perfOverlay) {
            this.perfOverlay.classList.add('hidden');
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PERFORMANCE VISUALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    updatePerfOverlay(rendererInfo) {
        if (!this.perfOverlay || this.perfOverlay.classList.contains('hidden')) return;
        
        // Update FPS
        const fpsEl = this.perfOverlay.querySelector('.perf-fps');
        if (fpsEl) {
            fpsEl.textContent = Math.round(this.currentFps);
            fpsEl.className = 'perf-fps ' + this.getFpsClass(this.currentFps);
        }
        
        // Update stats
        const ftEl = document.getElementById('stat-frametime');
        if (ftEl) ftEl.textContent = this.currentFrameTime.toFixed(1) + 'ms';
        
        const dcEl = document.getElementById('stat-drawcalls');
        if (dcEl) dcEl.textContent = rendererInfo?.render?.calls || 0;
        
        const triEl = document.getElementById('stat-triangles');
        if (triEl) {
            const tris = rendererInfo?.render?.triangles || 0;
            triEl.textContent = tris >= 1000 ? (tris/1000).toFixed(1) + 'K' : tris;
        }
        
        // Draw FPS graph
        this.drawPerfGraph(this.perfCtx, this.perfCanvas);
    }
    
    updateMiniGraph() {
        const canvas = document.getElementById('mini-perf-graph');
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        this.drawPerfGraph(ctx, canvas);
    }
    
    drawPerfGraph(ctx, canvas) {
        if (!ctx || !canvas) return;
        
        const w = canvas.width;
        const h = canvas.height;
        
        // Clear
        ctx.fillStyle = 'rgba(0, 0, 0, 0.3)';
        ctx.fillRect(0, 0, w, h);
        
        // Draw FPS history
        ctx.beginPath();
        ctx.strokeStyle = '#67d4e4';
        ctx.lineWidth = 1.5;
        
        const samples = Math.min(60, this.fpsHistory.length);
        for (let i = 0; i < samples; i++) {
            const idx = (this.historyIndex - samples + i + 120) % 120;
            const fps = this.fpsHistory[idx];
            const x = (i / (samples - 1)) * w;
            const y = h - (Math.min(fps, 60) / 60) * h;
            
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
        ctx.stroke();
        
        // Draw target line (60fps)
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(125, 184, 126, 0.3)';
        ctx.setLineDash([2, 2]);
        ctx.moveTo(0, 0);
        ctx.lineTo(w, 0);
        ctx.stroke();
        ctx.setLineDash([]);
        
        // Draw min acceptable line (30fps)
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(245, 158, 11, 0.3)';
        ctx.setLineDash([2, 2]);
        ctx.moveTo(0, h / 2);
        ctx.lineTo(w, h / 2);
        ctx.stroke();
        ctx.setLineDash([]);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PUBLIC UPDATE (call from render loop)
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime, rendererInfo) {
        this.updatePerformance(deltaTime);
        this.updatePerfOverlay(rendererInfo);
        
        // Update mini graph in menu every 10 frames
        if (this.frameCount % 10 === 0) {
            this.updateMiniGraph();
            this.updateUI();
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// SINGLETON
// ═══════════════════════════════════════════════════════════════════════════

let settingsManagerInstance = null;

export function getSettingsManager() {
    if (!settingsManagerInstance) {
        settingsManagerInstance = new SettingsManager();
    }
    return settingsManagerInstance;
}
