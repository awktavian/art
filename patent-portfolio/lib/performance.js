/**
 * Performance Manager
 * ===================
 * 
 * Adaptive quality system for mobile and desktop performance optimization.
 * Detects device capabilities and applies appropriate quality presets.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// QUALITY PRESETS
// ═══════════════════════════════════════════════════════════════════════════

export const QUALITY_PRESETS = {
    low: {
        name: 'Low',
        shadowMapSize: 512,
        shadowsEnabled: false,
        particleCount: 100,
        dustParticles: 50,
        postProcessing: false,
        bloomEnabled: false,
        pixelRatio: 1.0,
        antialiasing: false,
        fogDensityMultiplier: 0.7,
        maxLights: 4,
        drawDistance: 50,
        lodBias: 2.0
    },
    medium: {
        name: 'Medium',
        shadowMapSize: 1024,
        shadowsEnabled: true,
        particleCount: 250,
        dustParticles: 150,
        postProcessing: true,
        bloomEnabled: true,
        pixelRatio: 1.5,
        antialiasing: true,
        fogDensityMultiplier: 0.85,
        maxLights: 8,
        drawDistance: 80,
        lodBias: 1.0
    },
    high: {
        name: 'High',
        shadowMapSize: 2048,
        shadowsEnabled: true,
        particleCount: 500,
        dustParticles: 300,
        postProcessing: true,
        bloomEnabled: true,
        pixelRatio: 2.0,
        antialiasing: true,
        fogDensityMultiplier: 1.0,
        maxLights: 16,
        drawDistance: 120,
        lodBias: 0.5
    },
    ultra: {
        name: 'Ultra',
        shadowMapSize: 4096,
        shadowsEnabled: true,
        particleCount: 1000,
        dustParticles: 500,
        postProcessing: true,
        bloomEnabled: true,
        pixelRatio: null, // Use device pixel ratio
        antialiasing: true,
        fogDensityMultiplier: 1.0,
        maxLights: 32,
        drawDistance: 200,
        lodBias: 0
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// GPU TIER DETECTION
// ═══════════════════════════════════════════════════════════════════════════

const GPU_TIERS = {
    0: 'low',      // Integrated/mobile GPU
    1: 'medium',   // Low-end discrete
    2: 'high',     // Mid-range discrete
    3: 'ultra'     // High-end discrete
};

const KNOWN_LOW_END_GPUS = [
    'intel hd',
    'intel uhd',
    'intel iris',
    'mali-',
    'adreno 3',
    'adreno 4',
    'adreno 5',
    'powervr',
    'apple gpu' // Older iPhones
];

const KNOWN_HIGH_END_GPUS = [
    'nvidia geforce rtx',
    'nvidia geforce gtx 10',
    'nvidia geforce gtx 16',
    'nvidia geforce gtx 20',
    'nvidia geforce gtx 30',
    'nvidia geforce gtx 40',
    'amd radeon rx 5',
    'amd radeon rx 6',
    'amd radeon rx 7',
    'apple m1',
    'apple m2',
    'apple m3'
];

function detectGPUTier() {
    const gl = document.createElement('canvas').getContext('webgl');
    if (!gl) return 0;
    
    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
    if (!debugInfo) return 1; // Default to medium if can't detect
    
    const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL).toLowerCase();
    const vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL).toLowerCase();
    
    console.log('GPU Detected:', renderer, vendor);
    
    // Check for high-end GPUs
    for (const pattern of KNOWN_HIGH_END_GPUS) {
        if (renderer.includes(pattern.toLowerCase())) {
            return 3; // Ultra
        }
    }
    
    // Check for low-end GPUs
    for (const pattern of KNOWN_LOW_END_GPUS) {
        if (renderer.includes(pattern.toLowerCase())) {
            return 0; // Low
        }
    }
    
    // Check for mid-range NVIDIA
    if (renderer.includes('nvidia')) {
        if (renderer.includes('gtx 9') || renderer.includes('gtx 10')) {
            return 2; // High
        }
        return 2; // Default NVIDIA to high
    }
    
    // Check for mid-range AMD
    if (renderer.includes('amd') || renderer.includes('radeon')) {
        return 2; // High
    }
    
    // Default based on vendor
    if (vendor.includes('nvidia') || vendor.includes('amd')) {
        return 2; // High
    }
    
    return 1; // Medium (unknown)
}

// ═══════════════════════════════════════════════════════════════════════════
// DEVICE DETECTION
// ═══════════════════════════════════════════════════════════════════════════

function detectDevice() {
    const ua = navigator.userAgent.toLowerCase();
    
    const isMobile = /android|iphone|ipad|ipod|webos|blackberry|windows phone/i.test(ua);
    const isTablet = /ipad|android(?!.*mobile)/i.test(ua);
    const isIOS = /iphone|ipad|ipod/i.test(ua);
    const isAndroid = /android/i.test(ua);
    const isQuest = /oculus|quest/i.test(ua);
    
    // Detect memory (if available)
    const memory = navigator.deviceMemory || 4;
    const hardwareConcurrency = navigator.hardwareConcurrency || 4;
    
    return {
        isMobile,
        isTablet,
        isIOS,
        isAndroid,
        isQuest,
        isDesktop: !isMobile && !isTablet,
        memory,
        cores: hardwareConcurrency,
        touchScreen: 'ontouchstart' in window,
        pixelRatio: window.devicePixelRatio || 1
    };
}

// ═══════════════════════════════════════════════════════════════════════════
// PERFORMANCE MANAGER CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class PerformanceManager {
    constructor() {
        this.device = detectDevice();
        this.gpuTier = detectGPUTier();
        this.currentPreset = null;
        this.preset = null;
        
        // FPS monitoring
        this.frameCount = 0;
        this.lastTime = performance.now();
        this.fps = 60;
        this.fpsHistory = [];
        this.adaptiveEnabled = false;
        
        // References to managed objects
        this.renderer = null;
        this.scene = null;
        this.postProcessing = null;
        this.lighting = null;
        
        // Auto-detect best preset
        this.autoDetectPreset();
        
        console.log('Performance Manager initialized:', {
            device: this.device,
            gpuTier: this.gpuTier,
            preset: this.currentPreset
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PRESET DETECTION
    // ═══════════════════════════════════════════════════════════════════════
    
    autoDetectPreset() {
        // Mobile devices get lower presets
        if (this.device.isMobile) {
            if (this.device.memory < 4) {
                this.currentPreset = 'low';
            } else if (this.device.isIOS || this.device.memory >= 6) {
                this.currentPreset = 'medium';
            } else {
                this.currentPreset = 'low';
            }
        }
        // Quest gets medium
        else if (this.device.isQuest) {
            this.currentPreset = 'medium';
        }
        // Desktop based on GPU tier
        else {
            this.currentPreset = GPU_TIERS[this.gpuTier] || 'medium';
        }
        
        this.preset = QUALITY_PRESETS[this.currentPreset];
    }
    
    getPreset() {
        return this.preset;
    }
    
    getPresetName() {
        return this.currentPreset;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // APPLY PRESET
    // ═══════════════════════════════════════════════════════════════════════
    
    setRenderer(renderer) {
        this.renderer = renderer;
        this.applyRendererSettings();
    }
    
    setScene(scene) {
        this.scene = scene;
    }
    
    setPostProcessing(postProcessing) {
        this.postProcessing = postProcessing;
        this.applyPostProcessingSettings();
    }
    
    setLighting(lighting) {
        this.lighting = lighting;
    }
    
    applyPreset(presetName) {
        if (!QUALITY_PRESETS[presetName]) {
            console.warn(`Unknown preset: ${presetName}`);
            return;
        }
        
        this.currentPreset = presetName;
        this.preset = QUALITY_PRESETS[presetName];
        
        console.log(`Applying quality preset: ${presetName}`);
        
        this.applyRendererSettings();
        this.applyPostProcessingSettings();
        this.applySceneSettings();
    }
    
    applyRendererSettings() {
        if (!this.renderer || !this.preset) return;
        
        // Pixel ratio
        const pixelRatio = this.preset.pixelRatio || Math.min(window.devicePixelRatio, 2);
        this.renderer.setPixelRatio(pixelRatio);
        
        // Shadows
        this.renderer.shadowMap.enabled = this.preset.shadowsEnabled;
        if (this.preset.shadowsEnabled) {
            this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        }
        
        console.log(`Renderer: pixelRatio=${pixelRatio}, shadows=${this.preset.shadowsEnabled}`);
    }
    
    applyPostProcessingSettings() {
        if (!this.postProcessing || !this.preset) return;
        
        // Enable/disable post-processing
        if (typeof this.postProcessing.toggle === 'function') {
            if (!this.preset.postProcessing) {
                this.postProcessing.enabled = false;
            } else {
                this.postProcessing.enabled = true;
            }
        }
        
        // Bloom settings
        if (this.postProcessing.passes?.bloom) {
            this.postProcessing.passes.bloom.enabled = this.preset.bloomEnabled;
        }
        
        console.log(`PostProcessing: enabled=${this.preset.postProcessing}, bloom=${this.preset.bloomEnabled}`);
    }
    
    applySceneSettings() {
        if (!this.scene || !this.preset) return;
        
        // Update fog
        if (this.scene.fog) {
            // Store original fog density if not stored
            if (!this.scene.userData.originalFogDensity) {
                this.scene.userData.originalFogDensity = this.scene.fog.density;
            }
            this.scene.fog.density = this.scene.userData.originalFogDensity * this.preset.fogDensityMultiplier;
        }
        
        // Update draw distance (camera far plane)
        this.scene.traverse(obj => {
            if (obj.isCamera) {
                obj.far = this.preset.drawDistance;
                obj.updateProjectionMatrix();
            }
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SHADOW MAP CONFIGURATION
    // ═══════════════════════════════════════════════════════════════════════
    
    configureShadowMap(light) {
        if (!this.preset || !this.preset.shadowsEnabled) {
            light.castShadow = false;
            return;
        }
        
        light.castShadow = true;
        light.shadow.mapSize.width = this.preset.shadowMapSize;
        light.shadow.mapSize.height = this.preset.shadowMapSize;
        light.shadow.camera.near = 0.5;
        light.shadow.camera.far = 50;
        light.shadow.bias = -0.0001;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PARTICLE COUNT
    // ═══════════════════════════════════════════════════════════════════════
    
    getParticleCount() {
        return this.preset?.particleCount || 250;
    }
    
    getDustParticleCount() {
        return this.preset?.dustParticles || 150;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FPS MONITORING
    // ═══════════════════════════════════════════════════════════════════════
    
    update() {
        this.frameCount++;
        const now = performance.now();
        const delta = now - this.lastTime;
        
        // Update FPS every second
        if (delta >= 1000) {
            this.fps = Math.round((this.frameCount * 1000) / delta);
            this.frameCount = 0;
            this.lastTime = now;
            
            // Store FPS history
            this.fpsHistory.push(this.fps);
            if (this.fpsHistory.length > 10) {
                this.fpsHistory.shift();
            }
            
            // Adaptive quality
            if (this.adaptiveEnabled) {
                this.adaptQuality();
            }
        }
    }
    
    getFPS() {
        return this.fps;
    }
    
    getAverageFPS() {
        if (this.fpsHistory.length === 0) return 60;
        return Math.round(this.fpsHistory.reduce((a, b) => a + b, 0) / this.fpsHistory.length);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ADAPTIVE QUALITY
    // ═══════════════════════════════════════════════════════════════════════
    
    enableAdaptiveQuality(enabled = true) {
        this.adaptiveEnabled = enabled;
    }
    
    adaptQuality() {
        const avgFPS = this.getAverageFPS();
        const presets = ['low', 'medium', 'high', 'ultra'];
        const currentIndex = presets.indexOf(this.currentPreset);
        
        // If FPS is too low, reduce quality
        if (avgFPS < 25 && currentIndex > 0) {
            console.log(`Low FPS (${avgFPS}), reducing quality`);
            this.applyPreset(presets[currentIndex - 1]);
        }
        // If FPS is consistently high, increase quality
        else if (avgFPS > 55 && currentIndex < presets.length - 1 && this.fpsHistory.length >= 10) {
            const allHigh = this.fpsHistory.every(fps => fps > 50);
            if (allHigh) {
                console.log(`Stable high FPS (${avgFPS}), increasing quality`);
                this.applyPreset(presets[currentIndex + 1]);
                this.fpsHistory = []; // Reset history
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UTILITY
    // ═══════════════════════════════════════════════════════════════════════
    
    isMobile() {
        return this.device.isMobile;
    }
    
    isTouch() {
        return this.device.touchScreen;
    }
    
    getDeviceInfo() {
        return this.device;
    }
    
    getGPUTier() {
        return this.gpuTier;
    }
    
    // Get recommended settings for a specific component
    getRecommendedSettings(component) {
        const settings = {};
        
        switch (component) {
            case 'particles':
                settings.count = this.preset.particleCount;
                settings.dustCount = this.preset.dustParticles;
                break;
            case 'shadows':
                settings.enabled = this.preset.shadowsEnabled;
                settings.mapSize = this.preset.shadowMapSize;
                break;
            case 'postProcessing':
                settings.enabled = this.preset.postProcessing;
                settings.bloom = this.preset.bloomEnabled;
                break;
            case 'renderer':
                settings.pixelRatio = this.preset.pixelRatio || Math.min(window.devicePixelRatio, 2);
                settings.antialiasing = this.preset.antialiasing;
                break;
        }
        
        return settings;
    }
    
    // Create debug overlay
    createDebugOverlay() {
        const overlay = document.createElement('div');
        overlay.id = 'perf-overlay';
        overlay.style.cssText = `
            position: fixed;
            top: 10px;
            right: 10px;
            background: rgba(0, 0, 0, 0.8);
            color: #67D4E4;
            padding: 10px;
            font-family: monospace;
            font-size: 12px;
            z-index: 9999;
            border-radius: 4px;
        `;
        
        document.body.appendChild(overlay);
        
        // Update every second
        setInterval(() => {
            overlay.innerHTML = `
                FPS: ${this.fps}<br>
                Avg: ${this.getAverageFPS()}<br>
                Preset: ${this.currentPreset}<br>
                GPU Tier: ${this.gpuTier}<br>
                Mobile: ${this.device.isMobile}
            `;
        }, 1000);
        
        return overlay;
    }
}

export default PerformanceManager;
