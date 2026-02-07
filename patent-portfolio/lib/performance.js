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
    // EMERGENCY preset - absolute minimum for severe performance issues
    emergency: {
        name: 'Emergency',
        shadowMapSize: 0,
        shadowsEnabled: false,
        particleCount: 30,
        dustParticles: 0,
        postProcessing: false,
        bloomEnabled: false,
        pixelRatio: 1.0,
        antialiasing: false,
        fogDensityMultiplier: 0.5,
        maxLights: 4,
        drawDistance: 30,
        lodBias: 4.0,
        disableWingEnhancements: true,
        disableParticles: true
    },
    low: {
        name: 'Low',
        shadowMapSize: 512,
        shadowsEnabled: false,
        particleCount: 50,
        dustParticles: 30,
        postProcessing: false,
        bloomEnabled: false,
        pixelRatio: 1.0,
        antialiasing: false,
        fogDensityMultiplier: 0.7,
        maxLights: 6,
        drawDistance: 50,
        lodBias: 2.0,
        disableWingEnhancements: false,
        disableParticles: false
    },
    medium: {
        name: 'Medium',
        shadowMapSize: 1024,
        shadowsEnabled: true,
        particleCount: 100,
        dustParticles: 50,
        postProcessing: true,
        bloomEnabled: true,
        pixelRatio: 1.5,
        antialiasing: true,
        fogDensityMultiplier: 0.85,
        maxLights: 8,
        drawDistance: 80,
        lodBias: 1.0,
        disableWingEnhancements: false,
        disableParticles: false
    },
    high: {
        name: 'High',
        shadowMapSize: 1024,
        shadowsEnabled: true,
        particleCount: 150,
        dustParticles: 100,
        postProcessing: true,
        bloomEnabled: true,
        pixelRatio: 1.5,
        antialiasing: true,
        fogDensityMultiplier: 1.0,
        maxLights: 12,
        drawDistance: 100,
        lodBias: 0.5,
        disableWingEnhancements: false,
        disableParticles: false
    },
    ultra: {
        name: 'Ultra',
        shadowMapSize: 2048,
        shadowsEnabled: true,
        particleCount: 200,
        dustParticles: 150,
        postProcessing: true,
        bloomEnabled: true,
        pixelRatio: 2.0,
        antialiasing: true,
        fogDensityMultiplier: 1.0,
        maxLights: 16,
        drawDistance: 150,
        lodBias: 0,
        disableWingEnhancements: false,
        disableParticles: false
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
    const canvas = document.createElement('canvas');
    const gl = canvas.getContext('webgl');
    if (!gl) return 0;
    
    let tier = 1; // Default to medium
    
    try {
        const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
        if (!debugInfo) return tier;
        
        const renderer = gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL).toLowerCase();
        const vendor = gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL).toLowerCase();
        
        console.log('GPU Detected:', renderer, vendor);
        
        // Check for high-end GPUs
        for (const pattern of KNOWN_HIGH_END_GPUS) {
            if (renderer.includes(pattern.toLowerCase())) {
                tier = 3; // Ultra
                break;
            }
        }
        
        // Check for low-end GPUs (only if not already high-end)
        if (tier === 1) {
            for (const pattern of KNOWN_LOW_END_GPUS) {
                if (renderer.includes(pattern.toLowerCase())) {
                    tier = 0; // Low
                    break;
                }
            }
        }
        
        // Check for mid-range NVIDIA (only if still default)
        if (tier === 1 && renderer.includes('nvidia')) {
            tier = 2; // High - default NVIDIA to high
        }
        
        // Check for mid-range AMD
        if (tier === 1 && (renderer.includes('amd') || renderer.includes('radeon'))) {
            tier = 2; // High
        }
        
        // Default based on vendor
        if (tier === 1 && (vendor.includes('nvidia') || vendor.includes('amd'))) {
            tier = 2; // High
        }
    } finally {
        // Clean up WebGL context to prevent memory leak
        const loseContext = gl.getExtension('WEBGL_lose_context');
        if (loseContext) {
            loseContext.loseContext();
        }
    }
    
    return tier;
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
                Mobile: ${this.device.isMobile}<br>
                Draw Calls: ${this.renderer?.info?.render?.calls || 0}<br>
                Triangles: ${this.renderer?.info?.render?.triangles || 0}<br>
                Textures: ${this.renderer?.info?.memory?.textures || 0}
            `;
        }, 1000);
        
        return overlay;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // LOD (LEVEL OF DETAIL) SYSTEM
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Create LOD group for an object with multiple detail levels
     * @param {THREE.Object3D[]} objects - Array of objects from high to low detail
     * @param {number[]} distances - Distances at which to switch
     * @returns {THREE.LOD}
     */
    createLOD(objects, distances) {
        const lod = new THREE.LOD();
        
        // Apply LOD bias from current preset
        const bias = this.preset?.lodBias || 1.0;
        
        objects.forEach((obj, i) => {
            const distance = (distances[i] || i * 20) * bias;
            lod.addLevel(obj, distance);
        });
        
        return lod;
    }
    
    /**
     * Apply LOD to all meshes in a group based on distance from camera
     * Simpler alternative to THREE.LOD - just hide distant objects
     */
    applyDistanceCulling(group, camera, maxDistance = null) {
        const distance = maxDistance || this.preset?.drawDistance || 100;
        
        group.traverse(obj => {
            if (obj.isMesh) {
                const dist = obj.position.distanceTo(camera.position);
                obj.visible = dist < distance;
                
                // Reduce material quality for distant objects
                if (obj.material && dist > distance * 0.5) {
                    if (obj.material.envMapIntensity !== undefined) {
                        obj.material.envMapIntensity = 0;
                    }
                }
            }
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // RAYCASTING THROTTLE
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Create a throttled raycaster that limits checks per frame
     * @param {number} maxChecksPerFrame - Max raycast operations per frame
     * @returns {Object} - Throttled raycaster wrapper
     */
    createThrottledRaycaster(maxChecksPerFrame = 4) {
        const raycaster = new THREE.Raycaster();
        let checksThisFrame = 0;
        let lastFrameTime = 0;
        
        return {
            raycaster,
            
            /**
             * Perform throttled raycast
             * @param {THREE.Vector3} origin
             * @param {THREE.Vector3} direction
             * @param {THREE.Object3D[]} objects
             * @returns {THREE.Intersection[]|null} - null if throttled
             */
            cast(origin, direction, objects) {
                const now = performance.now();
                
                // Reset counter each frame (~16ms)
                if (now - lastFrameTime > 16) {
                    checksThisFrame = 0;
                    lastFrameTime = now;
                }
                
                // Throttle
                if (checksThisFrame >= maxChecksPerFrame) {
                    return null;
                }
                
                checksThisFrame++;
                raycaster.set(origin, direction);
                return raycaster.intersectObjects(objects, false);
            },
            
            /**
             * Force a raycast regardless of throttle (for critical checks)
             */
            forceCast(origin, direction, objects) {
                raycaster.set(origin, direction);
                return raycaster.intersectObjects(objects, false);
            },
            
            /**
             * Set raycaster properties
             */
            setFar(far) {
                raycaster.far = far;
            }
        };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FRUSTUM CULLING HELPER
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Create frustum for manual culling checks
     * @param {THREE.Camera} camera
     * @returns {Object} - Frustum helper with update and check methods
     */
    createFrustumCuller(camera) {
        const frustum = new THREE.Frustum();
        const projScreenMatrix = new THREE.Matrix4();
        
        return {
            frustum,
            
            /**
             * Update frustum from camera
             */
            update() {
                projScreenMatrix.multiplyMatrices(
                    camera.projectionMatrix,
                    camera.matrixWorldInverse
                );
                frustum.setFromProjectionMatrix(projScreenMatrix);
            },
            
            /**
             * Check if object is in frustum
             * @param {THREE.Object3D} object
             * @returns {boolean}
             */
            isVisible(object) {
                if (object.geometry?.boundingSphere) {
                    // Check bounding sphere
                    const sphere = object.geometry.boundingSphere.clone();
                    sphere.applyMatrix4(object.matrixWorld);
                    return frustum.intersectsSphere(sphere);
                }
                return true; // Assume visible if no bounding sphere
            },
            
            /**
             * Apply frustum culling to a group
             */
            cullGroup(group) {
                group.traverse(obj => {
                    if (obj.isMesh) {
                        obj.visible = this.isVisible(obj);
                    }
                });
            }
        };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // MEMORY MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Dispose of Three.js object and its resources
     * @param {THREE.Object3D} object
     */
    disposeObject(object) {
        if (!object) return;
        
        // Dispose geometry
        if (object.geometry) {
            object.geometry.dispose();
        }
        
        // Dispose material(s)
        if (object.material) {
            if (Array.isArray(object.material)) {
                object.material.forEach(mat => this.disposeMaterial(mat));
            } else {
                this.disposeMaterial(object.material);
            }
        }
        
        // Recurse into children
        if (object.children) {
            object.children.forEach(child => this.disposeObject(child));
        }
    }
    
    /**
     * Dispose of material and its textures
     * @param {THREE.Material} material
     */
    disposeMaterial(material) {
        if (!material) return;
        
        // Dispose textures
        const textureProps = [
            'map', 'normalMap', 'bumpMap', 'roughnessMap', 'metalnessMap',
            'emissiveMap', 'aoMap', 'envMap', 'lightMap', 'alphaMap'
        ];
        
        textureProps.forEach(prop => {
            if (material[prop]) {
                material[prop].dispose();
            }
        });
        
        material.dispose();
    }
    
    /**
     * Get memory usage estimate
     * @returns {Object}
     */
    getMemoryUsage() {
        const info = this.renderer?.info;
        if (!info) return { textures: 0, geometries: 0 };
        
        return {
            textures: info.memory?.textures || 0,
            geometries: info.memory?.geometries || 0,
            programs: info.programs?.length || 0,
            drawCalls: info.render?.calls || 0,
            triangles: info.render?.triangles || 0,
            points: info.render?.points || 0
        };
    }
    
    /**
     * Clear unused resources (call periodically)
     */
    clearUnusedResources() {
        if (this.renderer) {
            this.renderer.info.reset();
        }
        
        // Suggest garbage collection (won't force it, but helps)
        if (window.gc) {
            window.gc();
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // GEOMETRY INSTANCING HELPER
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Create instanced mesh from a template geometry
     * @param {THREE.BufferGeometry} geometry
     * @param {THREE.Material} material
     * @param {THREE.Matrix4[]} matrices - Transform for each instance
     * @returns {THREE.InstancedMesh}
     */
    createInstancedMesh(geometry, material, matrices) {
        const mesh = new THREE.InstancedMesh(geometry, material, matrices.length);
        
        matrices.forEach((matrix, i) => {
            mesh.setMatrixAt(i, matrix);
        });
        
        mesh.instanceMatrix.needsUpdate = true;
        return mesh;
    }
    
    /**
     * Convert multiple similar meshes to instanced mesh
     * @param {THREE.Mesh[]} meshes - Array of similar meshes
     * @returns {THREE.InstancedMesh}
     */
    meshesToInstanced(meshes) {
        if (meshes.length === 0) return null;
        
        const template = meshes[0];
        const geometry = template.geometry;
        const material = template.material;
        
        const matrices = meshes.map(mesh => {
            mesh.updateMatrixWorld();
            return mesh.matrixWorld.clone();
        });
        
        return this.createInstancedMesh(geometry, material, matrices);
    }
}

export default PerformanceManager;
