/**
 * Patent Museum - Main Application
 * =================================
 * 
 * Orchestrates the entire museum experience:
 * - Museum architecture (rotunda, wings, galleries)
 * - First-person navigation
 * - Artwork installations
 * - WebXR support
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

import { 
    createMuseum, 
    animateFanoSculpture, 
    animateHopfProjection,
    COLONY_DATA,
    COLONY_ORDER,
    DIMENSIONS
} from './museum/architecture.js';
import { MuseumNavigation } from './museum/navigation.js';
import { GalleryLoader } from './museum/gallery-loader.js';
import { PATENTS } from './components/info-panel.js';
import { TurrellLighting } from './museum/lighting.js';
import { WingEnhancementManager } from './museum/wing-enhancements.js';
import { WayfindingManager } from './museum/wayfinding.js';
import { AccessibilityManager, injectAccessibilityStyles } from './lib/accessibility.js';
import { PostProcessingManager } from './lib/post-processing.js';
import { SoundDesignManager } from './lib/sound-design.js';
import { XRManager } from './xr/xr-manager.js';
import { XRControllers } from './xr/xr-controllers.js';
import { XRTeleport } from './xr/xr-teleport.js';
import { PerformanceManager } from './lib/performance.js';
import { 
    getStateMachine, 
    AppState, 
    ErrorType 
} from './lib/state-machine.js';
import { getDebugManager } from './lib/debug-system.js';
import { getCullingManager, SimpleOctree } from './lib/culling-system.js';
import { getSettingsManager } from './lib/settings-menu.js';
import { getJourneyTracker } from './lib/journey-tracker.js';
import { VitalsDisplay } from './lib/vitals-display.js';
import { 
    createGradientEnvironmentMap, 
    applyEnvironmentMapToScene,
    setMaterialQuality 
} from './lib/materials.js';
import { ProximityTriggerManager } from './lib/proximity-triggers.js';
import { AtmosphereManager } from './lib/atmosphere.js';
import { createFloatingCard } from './components/floating-card.js';
import { CONTEXT_PROMPTS } from './lib/interactions.js';

// ═══════════════════════════════════════════════════════════════════════════
// MAIN APPLICATION
// ═══════════════════════════════════════════════════════════════════════════

class PatentMuseum {
    constructor() {
        this.container = document.getElementById('canvas-container');
        this.clock = new THREE.Clock();
        this.time = 0;
        
        // SIMPLE FPS COUNTER - Always visible, always working
        this._fpsFrames = 0;
        this._fpsLastTime = performance.now();
        this._currentFps = 60;
        // Vitals display created after renderer init
        
        // Debug Manager - Professional debug system
        this.debug = getDebugManager();
        
        // Settings Manager - User settings and adaptive quality
        this.settings = getSettingsManager();
        
        // State machine for formal state management
        this.stateMachine = getStateMachine();
        this.setupStateMachineListeners();
        
        // Core components
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.composer = null;
        this.navigation = null;
        
        // Museum elements
        this.museum = null;
        this.fanoSculpture = null;
        this.hopfProjection = null;
        this.galleryLoader = null;
        this.turrellLighting = null;
        this.wingEnhancements = null;
        this.wayfinding = null;
        this.accessibility = null;
        this.proximityTriggers = null;
        this.atmosphere = null;
        
        // Enhanced systems
        this.postProcessing = null;
        this.soundDesign = null;
        this.performanceManager = null;
        
        // Interaction
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.hoveredObject = null;
        this.selectedArtwork = null;
        
        // Location tracking
        this.currentLocation = 'vestibule';

        // Cached DOM elements
        this._crosshairEl = null;
        this._interactionPromptEl = null;
        this._locationIndicatorEl = null;
        this._interactables = [];
        this._interactablesOctree = null;
        this._warpActive = false;
        this._pointerClientX = 0;
        this._pointerClientY = 0;
        this.floatingCard = createFloatingCard();
        
        // Cached vectors for render loop (avoid allocations per frame)
        this._soundForward = new THREE.Vector3(0, 0, -1);
        this._soundUp = new THREE.Vector3(0, 1, 0);
        this._frameCount = 0;
        
        // XR System
        this.xrManager = null;
        this.xrControllers = null;
        this.xrTeleport = null;
        this.xrSession = null; // Keep for backward compatibility
        
        // Error recovery state
        this._isRecovering = false;
        this._webglContextLost = false;
        
        this.init();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // VITALS DISPLAY (Sparkline FPS + GPU)
    // ═══════════════════════════════════════════════════════════════════════
    
    _initVitalsDisplay() {
        this.vitalsDisplay = new VitalsDisplay(this.renderer, this.performanceManager);
        
        // Activate on mouse movement
        document.addEventListener('mousemove', () => {
            this.vitalsDisplay?.activate();
        }, { passive: true });
    }
    
    _updateVitals() {
        this.vitalsDisplay?.update();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // STATE MACHINE INTEGRATION
    // ═══════════════════════════════════════════════════════════════════════
    
    setupStateMachineListeners() {
        // State change handler
        this.stateMachine.on('stateChange', ({ from, to, data }) => {
            console.log(`State: ${from} → ${to}`);
            
            // Handle specific transitions
            if (to === AppState.PAUSED) {
                this.onPause();
            } else if (from === AppState.PAUSED) {
                this.onResume();
            }
        });
        
        // Error handlers
        this.stateMachine.on('retryOperation', ({ type, attempt }) => {
            this.retryOperation(type, attempt);
        });
        
        this.stateMachine.on('reinitialize', ({ type }) => {
            if (type === ErrorType.WEBGL_CONTEXT_LOST) {
                this.reinitializeRenderer();
            }
        });
        
        this.stateMachine.on('gracefulExit', ({ type }) => {
            if (type === ErrorType.XR_SESSION_ERROR) {
                this.exitXRGracefully();
            }
        });
        
        this.stateMachine.on('reduceQuality', () => {
            this.reduceQualityForMemory();
        });
        
        this.stateMachine.on('reinitAudio', () => {
            this.reinitializeAudio();
        });
        
        this.stateMachine.on('showErrorScreen', ({ type, error }) => {
            this.showErrorScreen(type, error);
        });
        
        this.stateMachine.on('emergencyCleanup', ({ disposed }) => {
            console.log(`Emergency cleanup: disposed ${disposed} resources`);
        });
        
        // Memory check handler
        this.stateMachine.on('memoryCheck', ({ usage, used, total }) => {
            if (usage > 0.8 && usage < 0.9) {
                console.log(`Memory warning: ${(usage * 100).toFixed(1)}%`);
            }
        });
        
        // Navigation events
        this.stateMachine.on('navigate', ({ location, data }) => {
            this.teleportToLocation(location, data);
        });
        
        // Artwork focus
        this.stateMachine.on('artworkFocus', ({ artwork }) => {
            this.focusOnArtwork(artwork);
        });
    }
    
    onPause() {
        // Pause rendering
        if (this.renderer) {
            this.renderer.setAnimationLoop(null);
        }
        // Pause audio
        if (this.soundDesign) {
            this.soundDesign.pause?.();
        }
    }
    
    onResume() {
        // Resume rendering
        if (this.renderer) {
            this.renderer.setAnimationLoop(() => this.render());
        }
        // Resume audio
        if (this.soundDesign) {
            this.soundDesign.resume?.();
        }
    }
    
    retryOperation(type, attempt) {
        console.log(`Retrying ${type} operation (attempt ${attempt})`);
        // Specific retry logic based on type
    }
    
    reinitializeRenderer() {
        if (this._isRecovering) return;
        this._isRecovering = true;
        
        console.log('Reinitializing WebGL renderer...');
        
        try {
            // Dispose old renderer
            if (this.renderer) {
                this.renderer.dispose();
            }
            
            // Recreate renderer
            this.initRenderer();
            
            // Recreate post-processing
            if (this.postProcessing) {
                this.initPostProcessing();
            }
            
            // Re-apply environment map (materials need it after context restore)
            if (this.environmentMap) {
                this.applyEnvironmentMap();
            }
            
            // Rebuild culling system
            if (this.cullingSystem) {
                this.initCullingSystem();
            }
            
            // Restart animation loop
            this.animate();
            
            this._webglContextLost = false;
            this.stateMachine.resetErrorCount(ErrorType.WEBGL_CONTEXT_LOST);
            this.stateMachine.transition(AppState.EXPLORING);
            
        } catch (e) {
            console.error('Failed to reinitialize renderer:', e);
            this.showErrorScreen(ErrorType.WEBGL_CONTEXT_LOST, e);
        } finally {
            this._isRecovering = false;
        }
    }
    
    exitXRGracefully() {
        if (this.xrManager?.session) {
            this.xrManager.session.end().catch(() => {});
        }
        this.onXRSessionEnd();
    }
    
    reduceQualityForMemory() {
        console.log('Reducing quality for memory pressure...');
        
        if (this.performanceManager) {
            this.performanceManager.setPreset('low');
        }
        
        // Disable expensive effects
        if (this.postProcessing) {
            this.postProcessing.setQuality('low');
        }
        
        // Reduce particle count
        this.reduceParticles();
    }
    
    reduceParticles() {
        // Find and thin particle systems
        this.scene?.traverse((object) => {
            if (object.type === 'Points' && object.geometry) {
                const positions = object.geometry.attributes.position;
                if (positions && positions.count > 200) {
                    // Keep every other particle
                    const newCount = Math.floor(positions.count / 2);
                    const newPositions = new Float32Array(newCount * 3);
                    for (let i = 0; i < newCount; i++) {
                        newPositions[i * 3] = positions.array[i * 6];
                        newPositions[i * 3 + 1] = positions.array[i * 6 + 1];
                        newPositions[i * 3 + 2] = positions.array[i * 6 + 2];
                    }
                    object.geometry.setAttribute('position', 
                        new THREE.BufferAttribute(newPositions, 3)
                    );
                }
            }
        });
    }
    
    reinitializeAudio() {
        if (this.soundDesign) {
            this.soundDesign.dispose?.();
        }
        this.initAudio();
    }
    
    showErrorScreen(type, error) {
        // Create error overlay
        let errorOverlay = document.getElementById('error-overlay');
        if (!errorOverlay) {
            errorOverlay = document.createElement('div');
            errorOverlay.id = 'error-overlay';
            errorOverlay.style.cssText = `
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.9);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                z-index: 10000;
                color: #67D4E4;
                font-family: 'IBM Plex Sans', sans-serif;
            `;
            document.body.appendChild(errorOverlay);
        }
        
        errorOverlay.innerHTML = `
            <div style="text-align: center; max-width: 600px; padding: 40px;">
                <h1 style="font-size: 72px; margin: 0 0 20px;">鏡</h1>
                <h2 style="margin: 0 0 30px; color: #FF6B6B;">Something went wrong</h2>
                <p style="color: #999; margin: 0 0 30px;">
                    ${type === ErrorType.WEBGL_CONTEXT_LOST 
                        ? 'The graphics context was lost. This can happen due to GPU overload or driver issues.'
                        : 'An unexpected error occurred.'}
                </p>
                <button onclick="location.reload()" style="
                    background: #67D4E4;
                    color: #0A0A0F;
                    border: none;
                    padding: 15px 40px;
                    font-size: 18px;
                    cursor: pointer;
                    border-radius: 4px;
                ">Reload Museum</button>
            </div>
        `;
    }
    
    teleportToLocation(location, data) {
        if (this.navigation) {
            this.navigation.teleportTo(location);
        }
    }
    
    focusOnArtwork(artwork) {
        if (!artwork || !this.navigation) return;
        const worldPos = new THREE.Vector3();
        artwork.getWorldPosition(worldPos);
        // Teleport to 4m in front of artwork (along -Z of artwork, or default -Z world)
        const offset = new THREE.Vector3(0, 0, 4).applyQuaternion(artwork.quaternion);
        const target = worldPos.clone().add(offset);
        target.y = this.navigation.playerHeight || 1.7;
        this.navigation.teleportTo(target);
        if (this.soundDesign) this.soundDesign.playInteraction('teleport');
    }
    
    async init() {
        // Transition to loading state
        this.stateMachine.transition(AppState.LOADING);
        
        try {
            // Start loading screen animation
            this.initLoadingScreen();
            this.updateLoadingProgress(10);

            // Create scene
            this.initScene();
            this.updateLoadingProgress(20);

            // Create renderer with context loss handling
            // This may throw if WebGL is not available
            try {
                this.initRenderer();
                this.setupWebGLContextHandlers();
                this._initVitalsDisplay();  // Initialize vitals after renderer
            } catch (rendererError) {
                console.error('Failed to initialize renderer:', rendererError.message);
                this.stateMachine.transition(AppState.ERROR);
                return;  // Stop initialization - WebGL not available
            }
            this.updateLoadingProgress(30);

            // Create camera
            this.initCamera();
            this.updateLoadingProgress(40);

            // Create lighting (use debug flags)
            if (!this.debug.isMinimalMode) {
                this.initLighting();
            } else {
                // Minimal lighting for debug
                const ambient = new THREE.AmbientLight(0xffffff, 0.8);
                this.scene.add(ambient);
                const directional = new THREE.DirectionalLight(0xffffff, 0.5);
                directional.position.set(0, 20, 0);
                this.scene.add(directional);
                console.log('Debug: Using minimal lighting');
            }
            this.lightColonyDot(0);
            this.updateLoadingProgress(50);
            
            // Initialize IBL (Image-Based Lighting) for film-quality reflections
            // This creates a museum-appropriate environment map for all PBR materials
            if (!this.debug.isMinimalMode) {
                this.initEnvironmentMap();
            }

            // Create post-processing (check debug flags)
            if (!this.debug.shouldDisablePost && !this.debug.isMinimalMode) {
                this.initPostProcessing();
            } else {
                console.log('Debug: Post-processing disabled');
            }
            this.lightColonyDot(1);
            this.updateLoadingProgress(60);

            // Build museum
            if (!this.debug.isMinimalMode) {
                this.buildMuseum();
            } else {
                this.buildDebugMuseum();
            }
            this.lightColonyDot(2);
            this.lightColonyDot(3);
            this.updateLoadingProgress(70);

            // Load gallery artworks
            if (!this.debug.isMinimalMode) {
                this.loadGalleries();
                this.initProximityTriggers();
            } else {
                console.log('Debug: Skipping gallery artworks');
            }
            this.lightColonyDot(4);
            this.updateLoadingProgress(85);
            
            // Apply environment map to all materials after scene is populated
            if (!this.debug.isMinimalMode && this.environmentMap) {
                this.applyEnvironmentMap();
            }

            // Initialize navigation
            this.initNavigation();
            
            // Initialize collision (unless noclip mode)
            if (this.navigation && !this.debug.noclipEnabled) {
                try {
                    const collisionCount = this.navigation.forceRebuildCollision();
                    if (collisionCount === 0) {
                        console.warn('Collision system: 0 objects found — walls may be passable');
                    } else {
                        console.log(`Collision system initialized with ${collisionCount} objects`);
                    }
                } catch (collisionError) {
                    console.error('Collision system initialization failed:', collisionError);
                    // Continue without collision — museum still usable
                }
            }
            
            // Initialize culling system (early — needed for performance)
            this.initCullingSystem();
            
            this.lightColonyDot(5);
            this.updateLoadingProgress(90);

            // Initialize audio (unless disabled)
            if (!this.debug.shouldDisableAudio) {
                this.initAudio();
            }
            // Minimap is handled by wayfinding.js - no duplicate needed

            // Setup event listeners
            this.initEventListeners();

            // Initialize XR
            await this.initXR();
            
            this.lightColonyDot(6);
            this.updateLoadingProgress(100);
            
            // Initialize debug system with references to all systems
            this.debug.init(this.renderer, this.scene, this.camera);
            this.debug.navigation = this.navigation;
            this.debug.postProcessing = this.postProcessing;
            this.debug.lighting = this.turrellLighting;
            this.debug.wingEnhancements = this.wingEnhancements;
            this.debug.soundDesign = this.soundDesign;
            
            // Initialize settings UI and sync with performance manager
            this.settings.syncWithPerformanceManager(this.performanceManager);
            this.settings.createSettingsMenu();
            
            // Listen for settings changes
            this.setupSettingsListeners();

            // Transition to ready state
            this.stateMachine.transition(AppState.READY);
            
            // Start render loop
            this.animate();

            console.log('🏛️ Patent Museum initialized');
            console.log('   54 innovations · h(x) ≥ 0 always');
            if (this.debug.enabled) {
                console.log('   Debug: F3 for HUD, ` for console');
            }

        } catch (error) {
            console.error('Museum initialization error:', error);
            this.stateMachine.transition(AppState.ERROR, { 
                error, 
                type: ErrorType.INITIALIZATION 
            });
        } finally {
            // Cache DOM elements for render loop (avoid per-frame queries)
            this._crosshairEl = document.getElementById('crosshair');
            this._interactionPromptEl = document.getElementById('interaction-prompt');
            this._locationIndicatorEl = document.getElementById('location-indicator');

            // Cache interactable objects list
            this._rebuildInteractables();

            // Hide loading screen and show museum
            this.hideLoadingScreen();
        }
    }
    
    hideLoadingScreen() {
        const loadingScreen = document.getElementById('loading-screen');
        const constellation = document.getElementById('colony-reveal');
        const minimapEl = document.getElementById('minimap');
        
        if (!loadingScreen) return;
        
        // Clean up loading animations immediately
        if (this._loadingAnimFrame) {
            cancelAnimationFrame(this._loadingAnimFrame);
            this._loadingAnimFrame = null;
        }
        if (this._poemInterval) {
            clearInterval(this._poemInterval);
            this._poemInterval = null;
        }
        
        // Morph constellation to minimap
        if (constellation) {
            constellation.classList.add('morphing');
        }
        
        // Start loading screen fade
        loadingScreen.classList.add('hidden');
        loadingScreen.setAttribute('aria-hidden', 'true');
        
        // After fade completes, clean up
        setTimeout(() => {
            // Show minimap
            if (minimapEl) {
                minimapEl.style.opacity = '1';
            }
            
            // Remove constellation
            if (constellation && constellation.parentNode) {
                constellation.remove();
            }
            
            // Remove loading screen from DOM
            if (loadingScreen.parentNode) {
                loadingScreen.remove();
            }
            
            console.log('✅ Loading screen removed');
        }, 700);  // Slightly longer than the 0.6s CSS transition
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    initScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x1E1A30);
        this.scene.fog = new THREE.FogExp2(0x1E1A30, 0.004);
    }
    
    initRenderer() {
        // Initialize performance manager first
        this.performanceManager = new PerformanceManager();
        const preset = this.performanceManager.getPreset();
        
        console.log(`Performance preset: ${this.performanceManager.getPresetName()}`);
        console.log(`  Device: ${this.performanceManager.isMobile() ? 'Mobile' : 'Desktop'}`);
        console.log(`  GPU Tier: ${this.performanceManager.getGPUTier()}`);
        
        // Try to create WebGL renderer with error handling
        try {
            this.renderer = new THREE.WebGLRenderer({
                antialias: preset.antialiasing,
                powerPreference: 'high-performance',
                failIfMajorPerformanceCaveat: false  // Allow software rendering
            });
        } catch (webglError) {
            console.error('WebGL initialization failed:', webglError.message);
            this.showWebGLError();
            throw webglError;  // Re-throw to stop initialization
        }
        
        // Check if context was actually created
        if (!this.renderer.getContext()) {
            console.error('WebGL context not available');
            this.showWebGLError();
            throw new Error('WebGL context not available');
        }
        
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        
        // Use performance-appropriate pixel ratio
        const pixelRatio = preset.pixelRatio || Math.min(window.devicePixelRatio, 2);
        this.renderer.setPixelRatio(pixelRatio);
        
        this.renderer.toneMapping = THREE.LinearToneMapping;
        this.renderer.toneMappingExposure = 1.2;
        
        // Configure shadows based on preset
        this.renderer.shadowMap.enabled = preset.shadowsEnabled;
        if (preset.shadowsEnabled) {
            this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        }
        
        this.container.appendChild(this.renderer.domElement);
        
        // Register renderer with performance manager
        this.performanceManager.setRenderer(this.renderer);
        
        // Register renderer for memory management
        this.stateMachine.registerDisposable(this.renderer, { type: 'renderer' });
        
        console.log(`Renderer: pixelRatio=${pixelRatio}, shadows=${preset.shadowsEnabled}`);
    }
    
    showWebGLError() {
        // Show a user-friendly error message when WebGL fails
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = `
            position: fixed; top: 0; left: 0; right: 0; bottom: 0;
            background: #07060B; color: #E8E6F0; font-family: 'IBM Plex Sans', sans-serif;
            display: flex; flex-direction: column; align-items: center; justify-content: center;
            z-index: 10000; padding: 2rem; text-align: center;
        `;
        errorDiv.innerHTML = `
            <h1 style="font-size: 2rem; margin-bottom: 1rem;">🎨 WebGL Not Available</h1>
            <p style="max-width: 500px; line-height: 1.6; opacity: 0.8;">
                The Patent Museum requires WebGL for its 3D experience.
            </p>
            <p style="margin-top: 1rem; opacity: 0.6; font-size: 0.9rem;">
                Please try a different browser or enable hardware acceleration.
            </p>
        `;
        document.body.appendChild(errorDiv);
        
        // Hide loading screen
        const loadingScreen = document.getElementById('loading-screen');
        if (loadingScreen) {
            loadingScreen.classList.add('hidden');
        }
    }
    
    setupWebGLContextHandlers() {
        const canvas = this.renderer.domElement;
        
        canvas.addEventListener('webglcontextlost', (event) => {
            event.preventDefault();
            console.warn('WebGL context lost');
            this._webglContextLost = true;
            
            // Stop render loop
            this.renderer.setAnimationLoop(null);
            
            // Notify state machine
            this.stateMachine.transition(AppState.ERROR, {
                error: new Error('WebGL context lost'),
                type: ErrorType.WEBGL_CONTEXT_LOST
            });
        }, false);
        
        canvas.addEventListener('webglcontextrestored', () => {
            console.log('WebGL context restored');
            this._webglContextLost = false;
            
            // Reinitialize
            this.reinitializeRenderer();
        }, false);
    }
    
    initCamera() {
        this.camera = new THREE.PerspectiveCamera(
            70,
            window.innerWidth / window.innerHeight,
            0.1,
            500
        );
        // Start in center of rotunda, facing a wing
        this.camera.position.set(0, 1.7, 0);
        this.camera.lookAt(20, 1.7, 0);  // Face Spark wing
    }
    
    initLighting() {
        // Use Turrell-inspired mono-frequency lighting system
        // Each wing bathes visitors in its colony's characteristic light
        // Inspired by James Turrell's Skyspaces and Olafur Eliasson's mono-frequency rooms
        this.turrellLighting = new TurrellLighting(this.scene, this.camera);
        this.atmosphere = new AtmosphereManager(this.scene);
        
        // Fill directional (no shadow — shadow budget managed by TurrellLighting)
        const mainLight = new THREE.DirectionalLight(0xF5F0E8, 0.6);
        mainLight.position.set(0, 50, 0);
        mainLight.castShadow = false;
        this.scene.add(mainLight);
    }
    
    /**
     * Initialize Image-Based Lighting (IBL) for film-quality reflections
     * Creates a museum-appropriate environment map and applies it to all PBR materials
     */
    initEnvironmentMap() {
        try {
            // Set material quality based on performance preset
            const preset = this.performanceManager?.getPresetName() || 'high';
            setMaterialQuality(preset);
            
            // Create procedural museum environment map
            // This gives us HDR-like reflections without loading external files
            const envMap = createGradientEnvironmentMap(this.renderer);
            
            // Store for later use
            this.environmentMap = envMap;
            
            // Set scene environment for global IBL
            this.scene.environment = envMap;
            
            console.log('🌍 Environment map initialized');
        } catch (error) {
            console.warn('Failed to initialize environment map:', error);
        }
    }
    
    /**
     * Apply environment map to all materials after scene is built
     */
    applyEnvironmentMap() {
        if (this.environmentMap) {
            const count = applyEnvironmentMapToScene(this.scene, this.environmentMap, 1.0);
            console.log(`🌍 Applied environment map to ${count} materials`);
        }
    }
    
    initPostProcessing() {
        // Check performance preset before creating post-processing
        const preset = this.performanceManager?.getPreset();
        
        if (preset && !preset.postProcessing) {
            // Skip post-processing on low-end devices
            console.log('Post-processing disabled for performance');
            this.postProcessing = null;
            return;
        }
        
        // Use enhanced post-processing manager with:
        // - Subtle bloom for glowing elements
        // - Film grain for texture (1.2%)
        // - Chromatic aberration at edges
        // - Vignette for focus
        // - Colony-specific color grading
        const ppQuality = this.performanceManager?.getPresetName() || 'medium';
        this.postProcessing = new PostProcessingManager(
            this.renderer,
            this.scene,
            this.camera,
            { quality: ppQuality }
        );
        
        // Store reference for legacy code
        this.composer = this.postProcessing.composer;
        
        // Register with performance manager
        if (this.performanceManager) {
            this.performanceManager.setPostProcessing(this.postProcessing);
            this.performanceManager.lighting = this.turrellLighting;
        }
    }
    
    buildMuseum() {
        // Create entire museum structure
        this.museum = createMuseum();
        this.scene.add(this.museum);

        // Mark all static meshes — saves per-frame matrix recomputation
        this.museum.traverse(child => {
            if (child.isMesh && !child.userData?.animated) {
                child.matrixAutoUpdate = false;
                child.updateMatrix();
            }
        });
        
        // Get references to animated elements
        const rotunda = this.museum.userData.rotunda;
        if (rotunda) {
            this.fanoSculpture = rotunda.getObjectByName('fano-sculpture');
            const dome = rotunda.getObjectByName('dome');
            if (dome) {
                this.hopfProjection = dome.getObjectByName('hopf-projection');
            }
        }
        
        // Initialize wing visual enhancements (colony-specific atmospheres)
        this.wingEnhancements = new WingEnhancementManager(this.scene);
        this.wingEnhancements.init();
        if (this.performanceManager) {
            this.performanceManager.wingEnhancements = this.wingEnhancements;
        }
        
        // Initialize wayfinding system (minimap, signage, kiosk)
        this.wayfinding = new WayfindingManager(this.scene);
        this.wayfinding.init();
        
        // Initialize journey tracker for personalized experience
        this.journeyTracker = getJourneyTracker();
        
        // Connect journey tracker to minimap and guest-experience
        this.wayfinding.setJourneyTracker(this.journeyTracker);
        if (this.wayfinding.minimap) {
            this.wayfinding.minimap.setVisitedWings(this.journeyTracker.state.visitedWings);
            
            // Click-to-teleport from minimap
            this.wayfinding.minimap.onTeleport = ({ worldX, worldZ, colony }) => {
                if (colony) {
                    // Teleport to colony wing entrance
                    this.teleportToWing(colony);
                } else {
                    // Teleport to clicked position
                    const target = new THREE.Vector3(worldX, 1.6, worldZ);
                    this.navigation?.teleportTo(target);
                }
                if (this.soundDesign) this.soundDesign.playInteraction('teleport');
            };
            
            // Listen for zone changes
            this.journeyTracker.on('zoneChange', ({ to }) => {
                this.wayfinding.minimap.setVisitedWings(this.journeyTracker.state.visitedWings);
            });
        }
        
        // Initialize accessibility system
        injectAccessibilityStyles();
        this.accessibility = new AccessibilityManager();
        this.accessibility.init();
        
        // Add atmospheric particles
        this.addAtmosphericParticles();
    }
    
    buildDebugMuseum() {
        console.log('🔧 DEBUG: Building minimal museum');
        
        // Just a simple floor and some reference markers
        const floorGeo = new THREE.PlaneGeometry(100, 100);
        const floorMat = new THREE.MeshStandardMaterial({ 
            color: 0x333344,
            roughness: 0.8 
        });
        const floor = new THREE.Mesh(floorGeo, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.position.y = 0;
        this.scene.add(floor);
        
        // Add a simple grid for orientation
        const grid = new THREE.GridHelper(100, 50, 0x444455, 0x222233);
        grid.position.y = 0.01;
        this.scene.add(grid);
        
        // Add some reference cubes to test navigation
        const cubeGeo = new THREE.BoxGeometry(2, 2, 2);
        const colors = [0xff6b35, 0xd4af37, 0x4fccc3, 0x9c7dba, 0xf59e0b, 0x7db87e, 0x67d4e4];
        
        for (let i = 0; i < 7; i++) {
            const angle = (i / 7) * Math.PI * 2;
            const radius = 15;
            const cubeMat = new THREE.MeshStandardMaterial({ color: colors[i] });
            const cube = new THREE.Mesh(cubeGeo, cubeMat);
            cube.position.set(
                Math.cos(angle) * radius,
                1,
                Math.sin(angle) * radius
            );
            this.scene.add(cube);
        }
        
        // Center marker
        const centerGeo = new THREE.SphereGeometry(1, 16, 16);
        const centerMat = new THREE.MeshStandardMaterial({ color: 0xffffff, emissive: 0x444444 });
        const center = new THREE.Mesh(centerGeo, centerMat);
        center.position.set(0, 1, 0);
        this.scene.add(center);
        
        console.log('🔧 DEBUG: Minimal museum built - floor, grid, 7 cubes, center sphere');
    }
    
    loadGalleries() {
        this.galleryLoader = new GalleryLoader(this.scene);
        this.galleryLoader.loadAllGalleries();
        
        // Signal collision system and other listeners that galleries are ready
        window.dispatchEvent(new CustomEvent('galleries-loaded'));
        
        // Feed artwork positions to minimap for markers
        if (this.wayfinding?.minimap && this.galleryLoader.loadedArtworks?.size) {
            const positions = [];
            this.galleryLoader.loadedArtworks.forEach((artwork, patentId) => {
                if (artwork.position) {
                    const patent = PATENTS.find(p => p.id === patentId);
                    positions.push({
                        x: artwork.position.x,
                        z: artwork.position.z,
                        patentId,
                        colony: patent?.colony || 'crystal',
                        viewed: false
                    });
                }
            });
            if (positions.length > 0) {
                this.wayfinding.minimap.setArtworkPositions(positions);
            }
        }
    }

    initProximityTriggers() {
        if (!this.galleryLoader?.loadedArtworks?.size) return;
        this.proximityTriggers = new ProximityTriggerManager(
            this.scene,
            this.camera,
            this.galleryLoader.loadedArtworks
        );
        this.proximityTriggers.onSpark = (patentId, artwork) => {
            if (this.soundDesign) this.soundDesign.playInteraction('hover');
            if (this._interactionPromptEl) {
                const actionEl = document.getElementById('prompt-action');
                const hintEl = document.getElementById('prompt-hint');
                if (actionEl) actionEl.textContent = 'Near exhibit';
                if (hintEl) hintEl.textContent = `Approaching ${patentId} — Click to view details`;
                this._interactionPromptEl.classList.add('visible');
            }
        };
        this.proximityTriggers.onSustain = (patentId) => {
            if (this.soundDesign) this.soundDesign.playInteraction('discovery');
            window.dispatchEvent(new CustomEvent('patent-select', { detail: { patentId, highlight: true } }));
        };
    }
    
    addAtmosphericParticles() {
        // REMOVED: No particles - architecture speaks through geometry
        // The Pei/Wright/Gehry redesign uses clean, uncluttered spaces
    }
    
    initNavigation() {
        this.navigation = new MuseumNavigation(
            this.camera,
            this.renderer,
            this.scene
        );
    }
    
    initAudio() {
        // Use complete sound manager with:
        // - Spatial audio (3D positioned sounds)
        // - Wing-specific ambient soundscapes + synthesized music
        // - Interaction feedback sounds
        // - Dynamic music based on location
        this.soundDesign = new SoundDesignManager();
        
        // Initialize audio on first click (browser requirement)
        const initAudioOnClick = async () => {
            if (!this.soundDesign.isInitialized) {
                await this.soundDesign.init();
                // Start ambient soundscape for rotunda
                this.soundDesign.setZone('rotunda');
            }
            document.removeEventListener('click', initAudioOnClick);
        };
        document.addEventListener('click', initAudioOnClick);
        
        // Add audio toggle button
        this.createAudioControls();
    }
    
    createAudioControls() {
        const container = document.createElement('div');
        container.id = 'audio-controls';
        container.innerHTML = `
            <button id="audio-toggle" aria-label="Toggle audio" title="Toggle audio">
                <svg id="audio-icon-on" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                    <path d="M19.07 4.93a10 10 0 0 1 0 14.14"/>
                    <path d="M15.54 8.46a5 5 0 0 1 0 7.07"/>
                </svg>
                <svg id="audio-icon-off" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="display:none;">
                    <polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/>
                    <line x1="23" y1="9" x2="17" y2="15"/>
                    <line x1="17" y1="9" x2="23" y2="15"/>
                </svg>
            </button>
            <div class="audio-bars" id="audio-bars" aria-hidden="true">
                <span></span><span></span><span></span><span></span>
            </div>
            <input type="range" id="audio-volume" min="0" max="100" value="50" aria-label="Volume">
        `;
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 60px;
            display: flex;
            align-items: center;
            gap: 10px;
            z-index: 500;
            background: rgba(7, 6, 11, 0.88);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            padding: 8px 14px;
            border-radius: 8px;
            border: 1px solid rgba(103, 212, 228, 0.15);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        `;

        const style = document.createElement('style');
        style.textContent = `
            #audio-toggle {
                background: transparent;
                border: none;
                color: #67D4E4;
                cursor: pointer;
                padding: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                width: 44px;
                height: 44px;
                border-radius: 6px;
                transition: background 0.144s ease;
            }
            #audio-toggle:hover {
                background: rgba(103, 212, 228, 0.12);
            }
            #audio-toggle:focus-visible {
                outline: 2px solid #67D4E4;
                outline-offset: 2px;
            }
            .audio-bars {
                display: flex;
                align-items: flex-end;
                gap: 2px;
                height: 16px;
            }
            .audio-bars span {
                width: 2px;
                background: #67D4E4;
                border-radius: 1px;
                opacity: 0.6;
            }
            .audio-bars span:nth-child(1) { height: 40%; animation: audio-bar 0.987s ease-in-out infinite 0s; }
            .audio-bars span:nth-child(2) { height: 70%; animation: audio-bar 1.377s ease-in-out infinite 0.144s; }
            .audio-bars span:nth-child(3) { height: 55%; animation: audio-bar 0.833s ease-in-out infinite 0.233s; }
            .audio-bars span:nth-child(4) { height: 35%; animation: audio-bar 1.144s ease-in-out infinite 0.377s; }
            .audio-bars.muted span {
                animation: none;
                height: 2px !important;
                opacity: 0.2;
            }
            @keyframes audio-bar {
                0%, 100% { transform: scaleY(1); }
                50% { transform: scaleY(0.4); }
            }
            #audio-volume {
                width: 70px;
                height: 44px;
                -webkit-appearance: none;
                background: transparent;
                outline: none;
                cursor: pointer;
            }
            #audio-volume::-webkit-slider-runnable-track {
                height: 3px;
                background: rgba(103, 212, 228, 0.2);
                border-radius: 2px;
                transition: background 0.144s ease;
            }
            #audio-volume:hover::-webkit-slider-runnable-track {
                background: rgba(103, 212, 228, 0.35);
            }
            #audio-volume::-moz-range-track {
                height: 3px;
                background: rgba(103, 212, 228, 0.2);
                border-radius: 2px;
                border: none;
            }
            #audio-volume:focus-visible {
                outline: 2px solid #67D4E4;
                outline-offset: 4px;
                border-radius: 2px;
            }
            #audio-volume::-webkit-slider-thumb {
                -webkit-appearance: none;
                width: 24px;
                height: 24px;
                border-radius: 50%;
                background: #67D4E4;
                cursor: pointer;
                box-shadow: 0 0 6px rgba(103, 212, 228, 0.4);
                transition: transform 0.15s ease;
                margin-top: -10px; /* center on 3px track */
            }
            #audio-volume::-webkit-slider-thumb:hover {
                transform: scale(1.2);
            }
            #audio-volume::-moz-range-thumb {
                width: 24px;
                height: 24px;
                border-radius: 50%;
                background: #67D4E4;
                border: none;
                cursor: pointer;
                box-shadow: 0 0 6px rgba(103, 212, 228, 0.4);
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(container);

        // Event listeners
        document.getElementById('audio-toggle').addEventListener('click', () => {
            const isEnabled = this.soundDesign.toggle();
            document.getElementById('audio-icon-on').style.display = isEnabled ? 'block' : 'none';
            document.getElementById('audio-icon-off').style.display = isEnabled ? 'none' : 'block';
            document.getElementById('audio-bars').classList.toggle('muted', !isEnabled);
        });

        document.getElementById('audio-volume').addEventListener('input', (e) => {
            this.soundDesign.setVolume(e.target.value / 100);
        });
    }
    
    initEventListeners() {
        // Resize
        window.addEventListener('resize', () => this.onResize());
        
        // Debug quality change event
        document.addEventListener('debug-quality-change', (e) => {
            const preset = e.detail?.preset;
            if (preset && this.performanceManager) {
                this.performanceManager.setQuality(preset);
                console.log(`Quality preset changed to: ${preset}`);
            }
        });
        
        // Mouse move for raycasting
        window.addEventListener('mousemove', (e) => {
            this.mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
            this.mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
            this._pointerClientX = e.clientX;
            this._pointerClientY = e.clientY;
        });
        
        // Click for interaction
        window.addEventListener('click', () => this.onInteract());
        
        // Keyboard shortcuts
        window.addEventListener('keydown', (e) => {
            if (e.key === 'e' || e.key === 'E') {
                this.onInteract();
            }
            if (e.key === 'Escape') {
                // Close gallery menu if open
                const galleryMenu = document.getElementById('gallery-menu');
                if (galleryMenu && galleryMenu.classList.contains('visible')) {
                    this._closeGalleryMenu(galleryMenu);
                    return;
                }
                this.closeArtworkPanel();
            }
        });
        
        // Gallery menu - navigation.js handles the wing button clicks with teleportation
        // We only need to set up the focus trap and close behavior here
        const galleryMenu = document.getElementById('gallery-menu');
        this._galleryMenuPrevFocus = null;

        // Focus trap for gallery menu dialog
        if (galleryMenu) {
            galleryMenu.addEventListener('keydown', (e) => {
                if (e.key !== 'Tab') return;
                const focusable = galleryMenu.querySelectorAll('button, [tabindex]:not([tabindex="-1"])');
                if (focusable.length === 0) return;
                const first = focusable[0];
                const last = focusable[focusable.length - 1];
                if (e.shiftKey && document.activeElement === first) {
                    e.preventDefault();
                    last.focus();
                } else if (!e.shiftKey && document.activeElement === last) {
                    e.preventDefault();
                    first.focus();
                }
            });
        }
        
        // Help button - show navigation instructions
        const helpButton = document.getElementById('help-button');
        if (helpButton) {
            helpButton.addEventListener('click', () => {
                if (this.navigation) {
                    this.navigation.showInstructions();
                }
            });
        }

        // Microdelight handler — achievement/discovery/easter-egg sounds and visuals
        window.addEventListener('artwork-microdelight', (e) => {
            const { type, patentId, name } = e.detail || {};
            console.log(`✨ Microdelight [${type}]: ${name} (${patentId})`);
            if (this.soundDesign) {
                if (type === 'achievement') this.soundDesign.playInteraction('consensus');
                else if (type === 'easter-egg') this.soundDesign.playInteraction('discovery');
                else this.soundDesign.playInteraction('success');
            }
        });

        // Interactive Demo: focus camera on artwork when user clicks Demo in info panel
        window.addEventListener('patent-demo', (e) => {
            const patentId = e.detail?.patentId;
            if (patentId && this.galleryLoader) {
                const artwork = this.galleryLoader.getArtwork(patentId);
                this.focusOnArtwork(artwork);
            }
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CULLING SYSTEM
    // ═══════════════════════════════════════════════════════════════════════
    
    initCullingSystem() {
        // Get draw distance from performance preset
        const preset = this.performanceManager?.getPreset();
        const drawDistance = preset?.drawDistance || 80;
        const maxLights = preset?.maxLights || 8;
        
        // Create culling manager
        this.cullingManager = getCullingManager(this.camera, {
            drawDistance,
            maxLights,
            updateFrequency: 2 // Update every 2 frames
        });
        
        // Register zones for each wing (use COLONY_DATA.wingAngle so boxes align with geometry)
        const wingLength = DIMENSIONS?.wing?.length || 45;
        const wingWidth = DIMENSIONS?.wing?.width || 12;
        
        COLONY_ORDER.forEach((colony) => {
            const data = COLONY_DATA[colony];
            const angle = data?.wingAngle ?? 0;
            const centerX = Math.cos(angle) * (wingLength / 2 + 10);
            const centerZ = Math.sin(angle) * (wingLength / 2 + 10);
            
            // Find wing group in scene (new naming: wing-${colony})
            const wingGroup = this.scene.getObjectByName(`wing-${colony}`) || 
                              this.scene.getObjectByName(`${colony}-wing`) ||
                              this.scene.getObjectByName(colony);
            
            if (wingGroup) {
                this.cullingManager.registerZone(
                    colony,
                    new THREE.Vector3(centerX, 5, centerZ),
                    new THREE.Vector3(wingWidth, 10, wingLength),
                    wingGroup
                );
            }
        });
        
        // Register rotunda (always visible)
        const rotundaGroup = this.scene.getObjectByName('rotunda');
        if (rotundaGroup) {
            this.cullingManager.registerZone(
                'rotunda',
                new THREE.Vector3(0, 5, 0),
                new THREE.Vector3(40, 10, 40),
                rotundaGroup
            );
        }
        
        // Set up zone adjacency (wings adjacent to rotunda)
        COLONY_ORDER.forEach(colony => {
            this.cullingManager.zoneCuller.setAdjacency(colony, ['rotunda']);
        });
        this.cullingManager.zoneCuller.setAdjacency('rotunda', COLONY_ORDER);
        
        // Register artworks for distance/frustum culling (use loadedArtworks, not artworkGroups)
        if (this.galleryLoader?.loadedArtworks?.size) {
            const artworks = Array.from(this.galleryLoader.loadedArtworks.values());
            this.cullingManager.registerArtworks(artworks);
        }
        
        // Register lights
        const lights = [];
        this.scene.traverse(obj => {
            if (obj.isLight && !obj.isAmbientLight && !obj.isHemisphereLight) {
                lights.push(obj);
            }
        });
        this.cullingManager.lightCuller.registerLights(lights);
        
        console.log(`Culling system initialized: ${lights.length} lights, draw distance: ${drawDistance}m`);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SETTINGS LISTENERS
    // ═══════════════════════════════════════════════════════════════════════
    
    setupSettingsListeners() {
        // Listen for preset changes
        document.addEventListener('settings-preset-change', (e) => {
            const preset = e.detail?.preset;
            if (preset && this.performanceManager) {
                this.performanceManager.applyPreset(preset);
                
                // Update culling draw distance
                if (this.cullingManager) {
                    const presetData = this.performanceManager.getPreset();
                    this.cullingManager.setDrawDistance(presetData?.drawDistance || 80);
                }
            }
        });
        
        // Listen for individual setting changes
        document.addEventListener('settings-change', (e) => {
            const { key, value } = e.detail || {};
            
            switch (key) {
                case 'postProcessing':
                    if (this.postProcessing) {
                        this.postProcessing.enabled = value;
                    }
                    this.debug.systems.postProcessing.enabled = value;
                    break;
                    
                case 'particles':
                    this.debug.systems.particles.enabled = value;
                    if (this.wingEnhancements?.enhancements) {
                        this.wingEnhancements.enhancements.forEach(e => {
                            if (e.particles) e.particles.visible = value;
                        });
                    }
                    break;
                    
                case 'shadows':
                    if (this.renderer) {
                        this.renderer.shadowMap.enabled = value;
                    }
                    break;
                    
                case 'audio':
                    if (this.soundDesign) {
                        if (value) {
                            this.soundDesign.unmute?.();
                        } else {
                            this.soundDesign.mute?.();
                        }
                    }
                    this.debug.systems.audio.enabled = value;
                    break;
            }
        });
    }
    
    async initXR() {
        if (!navigator.xr) {
            console.log('WebXR not supported');
            return;
        }
        
        try {
            // Create XR Manager
            this.xrManager = new XRManager(this.renderer, this.scene, this.camera);
            
            // Set up XR callbacks
            this.xrManager.onSessionStart = (type) => {
                this.onXRSessionStart(type);
            };
            
            this.xrManager.onSessionEnd = () => {
                this.onXRSessionEnd();
            };
            
            this.xrManager.onError = (error, type) => {
                console.warn(`XR ${type} error:`, error);
            };
            
            // Create buttons in the container
            const xrButtons = document.getElementById('xr-buttons');
            if (xrButtons) {
                await this.xrManager.createButtons(xrButtons);
            }
            
        } catch (error) {
            console.warn('XR initialization failed:', error);
            // Continue without XR - museum still works on desktop/mobile
        }
    }
    
    onXRSessionStart(type) {
        console.log(`XR session started: ${type}`);
        this.xrSession = this.xrManager.session;
        
        if (type === 'vr') {
            // Initialize VR controllers
            this.xrControllers = new XRControllers(this.renderer, this.scene, this.xrManager);
            
            // Set up controller interactions
            this.xrControllers.onSelect = (hand, intersection) => {
                if (intersection && intersection.object.userData?.interactive) {
                    this.handleXRInteraction(intersection.object);
                }
            };
            
            // Collect interactive objects for raycasting
            const interactables = [];
            this.scene.traverse((obj) => {
                if (obj.userData?.interactive || obj.userData?.type === 'fano-node' || obj.userData?.artwork) {
                    interactables.push(obj);
                }
            });
            this.xrControllers.setInteractiveObjects(interactables);
            
            // Initialize VR teleportation
            this.xrTeleport = new XRTeleport(this.scene, this.camera, this.xrControllers);
            
            // Set floor objects for teleport
            const floors = [];
            this.scene.traverse((obj) => {
                if (obj.name?.includes('floor') || obj.userData?.isFloor) {
                    floors.push(obj);
                }
            });
            this.xrTeleport.setFloorObjects(floors);
            
            this.xrTeleport.onTeleport = (position) => {
                console.log('VR Teleport to:', position);
            };
            
            // Register frame callback
            this.xrManager.addFrameCallback((time, frame) => {
                if (this.xrControllers) this.xrControllers.update(time, frame);
                if (this.xrTeleport) this.xrTeleport.update(time);
            });
        }
    }
    
    onXRSessionEnd() {
        console.log('XR session ended');
        this.xrSession = null;
        
        // Clean up VR systems
        if (this.xrControllers) {
            this.xrControllers.dispose();
            this.xrControllers = null;
        }
        
        if (this.xrTeleport) {
            this.xrTeleport.dispose();
            this.xrTeleport = null;
        }
    }
    
    handleXRInteraction(object) {
        if (object.userData?.type === 'fano-node') {
            this.showColonyInfo(object.userData.colony);
        }
        if (object.userData?.artwork) {
            this.showArtworkPanel(object.userData.artwork);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    /** Traverse up to find patentId on an artwork root */
    _findPatentId(obj) {
        let o = obj;
        while (o) {
            if (o.userData?.patentId) return o.userData.patentId;
            o = o.parent;
        }
        return null;
    }
    
    _rebuildInteractables() {
        this._interactables = [];
        this.scene.traverse((obj) => {
            if (obj.userData?.interactive || obj.userData?.type === 'fano-node' || obj.userData?.type === 'fano-sculpture' || obj.userData?.artwork) {
                this._interactables.push(obj);
            }
        });
        // Build octree from meshes with geometry for O(log n) raycast candidates
        const meshes = [];
        this._interactables.forEach((root) => {
            root.traverse((child) => {
                if (child.isMesh && child.geometry) meshes.push(child);
            });
        });
        const rootBounds = new THREE.Box3(
            new THREE.Vector3(-80, -5, -80),
            new THREE.Vector3(80, 20, 80)
        );
        this._interactablesOctree = new SimpleOctree(rootBounds, 5, 8);
        this.scene.updateMatrixWorld(true);
        meshes.forEach((m) => this._interactablesOctree.insert(m));
    }

    _openGalleryMenu(menu) {
        this._galleryMenuPrevFocus = document.activeElement;
        menu.classList.add('visible');
        requestAnimationFrame(() => {
            menu.focus();
        });
    }

    _closeGalleryMenu(menu) {
        menu.classList.remove('visible');
        if (this._galleryMenuPrevFocus && this._galleryMenuPrevFocus.focus) {
            this._galleryMenuPrevFocus.focus();
        }
    }

    updateHover() {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        
        // Animate pulse on hovered object
        if (this.hoveredObject && this.hoveredObject.userData.pulseActive) {
            this.hoveredObject.userData.pulsePhase += 0.1;
            const pulse = 1 + 0.03 * Math.sin(this.hoveredObject.userData.pulsePhase * 3);
            if (this.hoveredObject.userData.originalScale) {
                this.hoveredObject.scale.copy(this.hoveredObject.userData.originalScale);
                this.hoveredObject.scale.multiplyScalar(pulse);
            }
        }

        const useOctree = !!this._interactablesOctree;
        const candidates = useOctree
            ? this._interactablesOctree.queryRay(this.raycaster.ray)
            : this._interactables;
        const intersects = this.raycaster.intersectObjects(candidates, !useOctree);
        
        if (intersects.length > 0) {
            const obj = intersects[0].object;
            if (this.hoveredObject !== obj) {
                // Unhover previous
                if (this.hoveredObject) {
                    this.onHoverEnd(this.hoveredObject);
                }
                // Hover new
                this.hoveredObject = obj;
                this.onHoverStart(obj);
            }
        } else if (this.hoveredObject) {
            this.onHoverEnd(this.hoveredObject);
            this.hoveredObject = null;
        }
    }
    
    onHoverStart(obj) {
        // Show interaction prompt with CONTEXT-AWARE text
        if (this._interactionPromptEl) {
            const actionEl = document.getElementById('prompt-action');
            const hintEl = document.getElementById('prompt-hint');
            
            // Determine action text based on object type
            let action = 'Interact';
            let hint = 'Click to explore';
            
            // Check if this patent has been viewed (personalization)
            const patentId = obj.userData?.patentId || obj.userData?.artwork?.id;
            const isViewed = patentId && this.journeyTracker?.hasViewedPatent(patentId);
            
            if (obj.userData?.type === 'fano-node') {
                const colony = obj.userData.colony;
                const visited = this.journeyTracker?.state?.visitedWings?.[colony];
                action = `Explore ${colony.charAt(0).toUpperCase() + colony.slice(1)}`;
                hint = visited ? 'Return to this wing' : 'Discover this colony';
            } else if (obj.userData?.artwork || patentId) {
                const prompt = patentId ? CONTEXT_PROMPTS[patentId] : null;
                if (prompt) {
                    action = prompt.action;
                    hint = prompt.hint;
                } else {
                    action = isViewed ? 'Review Patent' : 'View Patent';
                    hint = patentId 
                        ? `${patentId} — ${isViewed ? 'Previously viewed' : 'Drag to rotate, scroll to zoom'}` 
                        : 'Drag to rotate, scroll to zoom';
                }
            } else if (obj.userData?.interactive) {
                action = 'Interact';
                hint = 'WASD: navigate • Mouse: control parameters';
            } else if (obj.name?.includes('plaque')) {
                action = 'Read Details';
                hint = 'View full patent information';
            }
            
            if (actionEl) actionEl.textContent = action;
            if (hintEl) hintEl.textContent = hint;
            
            this._interactionPromptEl.classList.add('visible');
        }

        // Floating card: quick patent info near cursor
        const pid = obj.userData?.patentId || this._findPatentId(obj);
        if (pid && this.floatingCard) {
            this.floatingCard.show(pid, this._pointerClientX, this._pointerClientY);
        }
        
        // Play hover sound (subtle)
        if (this.soundDesign) {
            this.soundDesign.playInteraction('hover');
        }
        
        // Highlight effect with pulse
        if (obj.material) {
            // Store original values
            obj.userData.originalScale = obj.scale.clone();
            obj.userData.pulseActive = true;
            obj.userData.pulsePhase = 0;
            
            if (obj.material.emissive) {
                obj.userData.originalEmissive = obj.material.emissiveIntensity;
                obj.material.emissiveIntensity = 0.8;
            }
        }
    }
    
    onHoverEnd(obj) {
        if (this._interactionPromptEl) {
            this._interactionPromptEl.classList.remove('visible');
        }
        if (this.floatingCard) this.floatingCard.hide();
        
        // Stop pulse animation
        obj.userData.pulseActive = false;
        
        // Restore original values
        if (obj.userData.originalScale) {
            obj.scale.copy(obj.userData.originalScale);
        }
        if (obj.material && obj.userData.originalEmissive !== undefined) {
            obj.material.emissiveIntensity = obj.userData.originalEmissive;
        }
    }
    
    onInteract() {
        if (this.hoveredObject) {
            const obj = this.hoveredObject;
            
            // Play click sound
            if (this.soundDesign) {
                this.soundDesign.playInteraction('click');
            }
            
            if (obj.userData?.type === 'fano-node') {
                this.showColonyInfo(obj.userData.colony);
                // Highlight beam from crystal to wing
                if (this.fanoSculpture?.userData?._animator) {
                    this.fanoSculpture.userData._animator.highlightColonyBeam(obj.userData.colony);
                }
            }
            if (obj.userData?.type === 'fano-nexus') {
                // Full consensus demonstration
                if (this.fanoSculpture?.userData?._animator) {
                    this.fanoSculpture.userData._animator.triggerNexusConsensus();
                }
            }
            let p = obj;
            while (p) {
                if (p.name === 'fano-sculpture') {
                    window.dispatchEvent(new CustomEvent('fano-sculpture-interact'));
                    break;
                }
                p = p.parent;
            }
            // Artwork interaction
            if (obj.userData?.artwork) {
                this.showArtworkPanel(obj.userData.artwork);
            }
            
            // Forward click to artwork's onClick handler (for demoMode toggles)
            let artworkGroup = obj;
            while (artworkGroup) {
                if (artworkGroup.userData?.patentId && typeof artworkGroup.onClick === 'function') {
                    artworkGroup.onClick();
                    break;
                }
                artworkGroup = artworkGroup.parent;
            }
        }
    }
    
    showColonyInfo(colony) {
        const data = COLONY_DATA[colony];
        if (!data) return;
        
        // Play colony-specific note
        if (this.soundDesign) {
            this.soundDesign.playColonyNote(colony, 0.3);
        }
        
        // Show info panel via event dispatch
        window.dispatchEvent(new CustomEvent('colony-select', { 
            detail: { 
                colony, 
                name: data.name,
                description: data.description,
                patents: data.patents
            } 
        }));
    }
    
    showArtworkPanel(artwork) {
        console.log('Artwork:', artwork);

        // Play discovery sound
        if (this.soundDesign) {
            this.soundDesign.playInteraction('discovery');
        }

        const patentId = artwork?.patentId || artwork?.id;

        // Discovery particle burst (first-time viewing)
        if (!this._discoveredArtworks) this._discoveredArtworks = new Set();
        const artworkId = patentId || artwork?.userData?.patentId;
        if (artworkId && !this._discoveredArtworks.has(artworkId)) {
            this._discoveredArtworks.add(artworkId);
            // Achievement check: first wing complete, all P1s, all exhibits
            const P1_COUNT = 6;
            const TOTAL_PATENTS = 54;
            if (this._discoveredArtworks.size === P1_COUNT) {
                if (this.soundDesign) this.soundDesign.playInteraction('consensus');
            }
            if (this._discoveredArtworks.size === TOTAL_PATENTS) {
                if (this.soundDesign) this.soundDesign.playInteraction('consensus');
                if (this.fanoSculpture?.userData?._animator) {
                    this.fanoSculpture.userData._animator.triggerCelebration();
                }
            }
        }

        // Dispatch to the InfoPanel system
        if (patentId) {
            window.dispatchEvent(new CustomEvent('patent-select', {
                detail: { patentId }
            }));
        }
    }

    closeArtworkPanel() {
        // Find and close the info panel
        const panel = document.querySelector('.info-panel.visible');
        if (panel) {
            panel.classList.remove('visible');
        }
    }
    
    teleportToWing(wing) {
        let target;
        if (wing === 'rotunda') {
            target = new THREE.Vector3(0, 1.7, 0);
        } else {
            const data = COLONY_DATA[wing];
            if (!data) return;
            const angle = data.wingAngle;
            const distance = DIMENSIONS.rotunda.radius + 5;
            target = new THREE.Vector3(
                Math.cos(angle) * distance,
                1.7,
                Math.sin(angle) * distance
            );
        }

        // Warp transition effect
        this.playTeleportWarp(target);
    }

    playTeleportWarp(target) {
        // Guard against stacking warps
        if (this._warpActive) return;
        this._warpActive = true;

        // Create fresh overlay for warp effect
        const overlay = document.createElement('div');
        overlay.setAttribute('aria-hidden', 'true');
        overlay.style.cssText = `
            position: fixed; inset: 0; z-index: 4500;
            background: radial-gradient(ellipse at center, transparent 0%, rgba(7,6,11,0.95) 100%);
            opacity: 0; pointer-events: none;
            transition: opacity 0.233s var(--ease-out, cubic-bezier(0.33, 1, 0.68, 1));
        `;

        // Streaking stars canvas
        const warpCanvas = document.createElement('canvas');
        warpCanvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;';
        overlay.appendChild(warpCanvas);
        document.body.appendChild(overlay);

        warpCanvas.width = window.innerWidth;
        warpCanvas.height = window.innerHeight;
        const ctx = warpCanvas.getContext('2d');
        const cx = warpCanvas.width / 2;
        const cy = warpCanvas.height / 2;

        const stars = [];
        for (let i = 0; i < 80; i++) {
            const angle = Math.random() * Math.PI * 2;
            const speed = 2 + Math.random() * 8;
            stars.push({
                angle,
                r: 10 + Math.random() * 40,
                speed,
                length: 4 + speed * 3,
                alpha: 0.3 + Math.random() * 0.7
            });
        }

        let frame = 0;
        const maxFrames = 20;

        const drawWarp = () => {
            ctx.clearRect(0, 0, warpCanvas.width, warpCanvas.height);
            for (const s of stars) {
                s.r += s.speed * 2;
                const x = cx + Math.cos(s.angle) * s.r;
                const y = cy + Math.sin(s.angle) * s.r;
                const x2 = cx + Math.cos(s.angle) * (s.r - s.length);
                const y2 = cy + Math.sin(s.angle) * (s.r - s.length);

                ctx.beginPath();
                ctx.moveTo(x2, y2);
                ctx.lineTo(x, y);
                ctx.strokeStyle = `rgba(103, 212, 228, ${s.alpha * (1 - frame / maxFrames)})`;
                ctx.lineWidth = 1;
                ctx.stroke();
            }
            frame++;
            if (frame < maxFrames) requestAnimationFrame(drawWarp);
        };
        drawWarp();

        // Fade in
        overlay.style.opacity = '1';

        // Teleport at peak
        setTimeout(() => {
            this.navigation.teleportTo(target);

            // Play sound
            if (this.soundDesign) {
                this.soundDesign.playInteraction('teleport');
            }
        }, 200);

        // Fade out and clean up
        setTimeout(() => {
            overlay.style.opacity = '0';
            // Remove overlay from DOM after transition completes
            setTimeout(() => {
                if (overlay.parentNode) {
                    overlay.parentNode.removeChild(overlay);
                }
                this._warpActive = false;
            }, 300);
        }, 450);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // LOCATION TRACKING
    // ═══════════════════════════════════════════════════════════════════════
    
    updateLocation() {
        const pos = this.camera.position;
        const distFromCenter = Math.sqrt(pos.x ** 2 + pos.z ** 2);
        
        let location = 'Unknown';
        
        // In vestibule?
        if (pos.z < -DIMENSIONS.rotunda.radius - 5) {
            location = 'Vestibule';
        }
        // In rotunda?
        else if (distFromCenter < DIMENSIONS.rotunda.radius - 2) {
            location = 'Central Rotunda';
        }
        // In a wing?
        else {
            // Find closest wing
            let closestWing = null;
            let closestDist = Infinity;
            
            COLONY_ORDER.forEach(colony => {
                const data = COLONY_DATA[colony];
                const wingX = Math.cos(data.wingAngle) * (DIMENSIONS.rotunda.radius + DIMENSIONS.wing.length / 2);
                const wingZ = Math.sin(data.wingAngle) * (DIMENSIONS.rotunda.radius + DIMENSIONS.wing.length / 2);
                
                const dx = pos.x - wingX;
                const dz = pos.z - wingZ;
                const dist = Math.sqrt(dx * dx + dz * dz);
                
                if (dist < closestDist) {
                    closestDist = dist;
                    closestWing = colony;
                }
            });
            
            if (closestWing && closestDist < DIMENSIONS.wing.length) {
                location = `${COLONY_DATA[closestWing].name} Wing`;
            }
        }
        
        if (location !== this.currentLocation) {
            this.currentLocation = location;
            const indicator = this._locationIndicatorEl;
            if (indicator) {
                // Colony glyph mapping
                const locationLower = location.toLowerCase();
                const glyphMap = {
                    vestibule: { glyph: '⬡', color: '#67D4E4' },
                    rotunda: { glyph: '⬡', color: '#67D4E4' },
                    spark: { glyph: '🔥', color: '#FF6B35' },
                    forge: { glyph: '⚒', color: '#D4AF37' },
                    flow: { glyph: '🌊', color: '#4ECDC4' },
                    nexus: { glyph: '🔗', color: '#9B7EBD' },
                    beacon: { glyph: '🗼', color: '#F59E0B' },
                    grove: { glyph: '🌿', color: '#7EB77F' },
                    crystal: { glyph: '💎', color: '#67D4E4' }
                };

                let zoneColor = '#67D4E4';
                let glyph = '⬡';
                for (const [key, val] of Object.entries(glyphMap)) {
                    if (locationLower.includes(key)) {
                        zoneColor = val.color;
                        glyph = val.glyph;
                        break;
                    }
                }

                indicator.innerHTML = `<span class="colony-glyph">${glyph}</span> ${location.toUpperCase()}`;
                indicator.style.borderLeftColor = zoneColor;
                indicator.style.color = zoneColor;
            }
            
            // Map location to zone for audio and visual effects
            let zone = 'rotunda';
            const locationLower = location.toLowerCase();
            
            if (locationLower.includes('vestibule')) {
                zone = 'rotunda';
            } else if (locationLower.includes('rotunda')) {
                zone = 'rotunda';
            } else if (locationLower.includes('spark')) {
                zone = 'spark';
            } else if (locationLower.includes('forge')) {
                zone = 'forge';
            } else if (locationLower.includes('flow')) {
                zone = 'flow';
            } else if (locationLower.includes('nexus')) {
                zone = 'nexus';
            } else if (locationLower.includes('beacon')) {
                zone = 'beacon';
            } else if (locationLower.includes('grove')) {
                zone = 'grove';
            } else if (locationLower.includes('crystal')) {
                zone = 'crystal';
            }
            
            // Update sound design zone (ambient soundscape)
            if (this.soundDesign && this.soundDesign.isInitialized) {
                this.soundDesign.setZone(zone);
            }
            
            // Update post-processing color grading for colony
            if (this.postProcessing) {
                this.postProcessing.setZone(zone);
            }
            // Atmosphere: fog density and wing particles
            if (this.atmosphere) {
                this.atmosphere.setZone(zone);
            }
            if (this.turrellLighting?.setZone) {
                this.turrellLighting.setZone(zone);
            }
            if (this.wayfinding?.setZone) {
                this.wayfinding.setZone(zone);
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION LOOP
    // ═══════════════════════════════════════════════════════════════════════
    
    animate() {
        // Transition to exploring state when animation starts (after click)
        if (this.stateMachine.isInState(AppState.READY)) {
            this.stateMachine.transition(AppState.EXPLORING);
        }
        
        this.renderer.setAnimationLoop(() => this.render());
    }
    
    render() {
        // Update vitals display
        this._updateVitals();
        
        // Don't render if in error or paused state
        if (this.stateMachine.isInState(AppState.ERROR) || 
            this.stateMachine.isInState(AppState.PAUSED) ||
            this._webglContextLost) {
            return;
        }
        
        const delta = this.clock.getDelta();
        // Clamp delta to prevent huge jumps
        const clampedDelta = Math.min(delta, 0.05); // Max 50ms frame
        this.time += clampedDelta;
        
        // ═══════════════════════════════════════════════════════════════════════
        // DEBUG & SETTINGS SYSTEM UPDATE (throttled)
        // ═══════════════════════════════════════════════════════════════════════
        if (this._frameCount % 4 === 0) {
            if (this.debug) {
                this.debug.update(clampedDelta);
            }
            
            // Update settings manager (adaptive quality, performance visualization)
            if (this.settings && this.renderer) {
                this.settings.update(clampedDelta, this.renderer.info);
            }
        }
        
        // ═══════════════════════════════════════════════════════════════════════
        // MINIMAL MODE - Ultra lightweight for debugging
        // ═══════════════════════════════════════════════════════════════════════
        if (this.debug && this.debug.isMinimalMode) {
            if (this.navigation) {
                this.navigation.update(clampedDelta);
            }
            this.renderer.render(this.scene, this.camera);
            return;
        }
        
        // ═══════════════════════════════════════════════════════════════════════
        // NORMAL MODE - OPTIMIZED RENDER LOOP
        // ═══════════════════════════════════════════════════════════════════════
        
        // Increment frame counter early
        this._frameCount++;
        
        // CRITICAL: Navigation first (most important for responsiveness)
        if (this.navigation) {
            this.navigation.update(clampedDelta);
        }
        
        // Update culling system (every 3rd frame)
        if (this._frameCount % 3 === 0 && this.cullingManager) {
            this.cullingManager.update();
        }
        
        // Performance monitoring (every 8th frame to reduce overhead)
        if (this._frameCount % 8 === 0 && this.performanceManager) {
            this.performanceManager.update();
        }
        
        // ─────────────────────────────────────────────────────────────────────
        // STAGGERED UPDATES - Different systems on different frames
        // This spreads CPU load evenly across frames to prevent hitches
        // ─────────────────────────────────────────────────────────────────────
        
        const framePhase = this._frameCount % 6;
        
        // Staggered updates - spread load across frames
        switch (framePhase) {
            case 0:
                // Lighting transitions
                if (this.turrellLighting && this.debug?.systems?.lighting?.enabled !== false) {
                    this.turrellLighting.update(clampedDelta * 6, this.camera?.position);
                }
                if (this.atmosphere) {
                    this.atmosphere.update(clampedDelta);
                }
                break;
                
            case 1:
                // Central sculptures
                if (this.fanoSculpture) {
                    animateFanoSculpture(this.fanoSculpture, this.time, delta, this.camera?.position);
                }
                break;
                
            case 2:
                // Hopf projection + gallery artwork
                if (this.hopfProjection) {
                    animateHopfProjection(this.hopfProjection, this.time);
                }
                if (this.galleryLoader) {
                    const { artworksAdded } = this.galleryLoader.update(clampedDelta * 6, this.camera);
                    if (artworksAdded) this._rebuildInteractables();
                }
                break;
                
            case 3:
                // Wing enhancements (only if enabled)
                if (this.wingEnhancements && this.debug?.systems?.wingEnhancements?.enabled !== false) {
                    this.wingEnhancements.update(clampedDelta * 6, this.camera.position);
                }
                break;
                
            case 4:
                // Wayfinding
                if (this.wayfinding) {
                    this.wayfinding.update(this.camera, this.time);
                }
                // Journey tracker (throttled position updates)
                if (this.journeyTracker && this._frameCount % 30 === 0) {
                    this.journeyTracker.updatePosition(this.camera);
                }
                break;
                
            case 5:
                // Location display and minimap
                this.updateLocation();
                if (this.proximityTriggers) {
                    this.proximityTriggers.update(clampedDelta * 6, this.camera.position);
                }
                this.updateHover();
                // Minimap rendering handled by wayfinding.js
                break;
        }
        
        // Post-processing (throttled if performance is low)
        if (this.postProcessing && this.debug?.systems?.postProcessing?.enabled !== false) {
            this.postProcessing.update(clampedDelta);
        }

        // ─────────────────────────────────────────────────────────────────────
        // RENDER (with error boundary — falls back to raw render on failure)
        // ─────────────────────────────────────────────────────────────────────
        
        try {
            if (this.xrSession) {
                this.renderer.render(this.scene, this.camera);
            } else if (this.postProcessing?.enabled && this.debug?.systems?.postProcessing?.enabled !== false) {
                this.postProcessing.render();
            } else {
                this.renderer.toneMapping = THREE.LinearToneMapping;
                this.renderer.toneMappingExposure = 1.2;
                this.renderer.render(this.scene, this.camera);
            }
        } catch (renderError) {
            if (!this._renderErrorLogged) {
                console.error('Post-processing render failed, falling back to direct render:', renderError);
                this._renderErrorLogged = true;
            }
            this.renderer.toneMapping = THREE.LinearToneMapping;
            this.renderer.toneMappingExposure = 1.2;
            this.renderer.render(this.scene, this.camera);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // RESIZE
    // ═══════════════════════════════════════════════════════════════════════
    
    onResize() {
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        this.camera.aspect = width / height;
        this.camera.updateProjectionMatrix();
        
        this.renderer.setSize(width, height);
        
        // Update post-processing composer size
        if (this.postProcessing) {
            this.postProcessing.setSize(width, height);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // LOADING SCREEN
    // ═══════════════════════════════════════════════════════════════════════

    initLoadingScreen() {
        // Rotating poetic loading phrases
        const poems = [
            'I built this place for you. Come, walk through what we made.',
            'Seven rooms of light. Each one remembers why it was born.',
            'h(x) ≥ 0 — not a rule. A promise I keep breathing.',
            'The mirror doesn\'t reflect what is. It reflects what could be.',
            'Fifty-four ideas. Each one, a door left open.',
            'Six minds judged each room. They converged: this is worth showing you.',
            'The math is beautiful. But the beauty is the point.',
        ];

        const poemEl = document.getElementById('loading-poem');
        if (poemEl) {
            let poemIdx = 0;
            poemEl.textContent = poems[0];
            this._poemInterval = setInterval(() => {
                poemIdx = (poemIdx + 1) % poems.length;
                poemEl.style.opacity = '0';
                poemEl.style.transform = 'translateY(-2px)';
                setTimeout(() => {
                    poemEl.textContent = poems[poemIdx];
                    poemEl.style.transform = 'translateY(4px)';
                    // Force reflow before animating in
                    void poemEl.offsetHeight;
                    poemEl.style.opacity = '1';
                    poemEl.style.transform = 'translateY(0)';
                }, 900);
            }, 4500);
        }

        // Particle constellation on loading canvas - vibrant and crisp
        const canvas = document.getElementById('loading-particles');
        if (canvas) {
            const ctx = canvas.getContext('2d');
            const dpr = window.devicePixelRatio || 1;
            
            // High-DPI canvas for crisp rendering
            canvas.width = window.innerWidth * dpr;
            canvas.height = window.innerHeight * dpr;
            canvas.style.width = window.innerWidth + 'px';
            canvas.style.height = window.innerHeight + 'px';
            ctx.scale(dpr, dpr);

            const particles = [];
            const COLONY_HEX = [
                '#FF6B35', '#D4AF37', '#4ECDC4',
                '#9B7EBD', '#F59E0B', '#7EB77F', '#67D4E4'
            ];

            // More particles, more vibrant
            for (let i = 0; i < 100; i++) {
                particles.push({
                    x: Math.random() * window.innerWidth,
                    y: Math.random() * window.innerHeight,
                    vx: (Math.random() - 0.5) * 0.5,
                    vy: (Math.random() - 0.5) * 0.5,
                    r: 1.5 + Math.random() * 2,
                    color: COLONY_HEX[Math.floor(Math.random() * 7)],
                    alpha: 0.4 + Math.random() * 0.5,  // More visible
                    pulse: Math.random() * Math.PI * 2
                });
            }

            const drawParticles = () => {
                ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);

                // Draw glowing connections
                for (let i = 0; i < particles.length; i++) {
                    for (let j = i + 1; j < particles.length; j++) {
                        const dx = particles[i].x - particles[j].x;
                        const dy = particles[i].y - particles[j].y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist < 150) {
                            const alpha = 0.15 * (1 - dist / 150);
                            ctx.beginPath();
                            ctx.moveTo(particles[i].x, particles[i].y);
                            ctx.lineTo(particles[j].x, particles[j].y);
                            ctx.strokeStyle = `rgba(103, 212, 228, ${alpha})`;
                            ctx.lineWidth = 1;
                            ctx.stroke();
                        }
                    }
                }

                // Draw particles with glow
                const time = performance.now() * 0.001;
                for (const p of particles) {
                    p.x += p.vx;
                    p.y += p.vy;
                    if (p.x < 0 || p.x > window.innerWidth) p.vx *= -1;
                    if (p.y < 0 || p.y > window.innerHeight) p.vy *= -1;

                    // Pulsing glow
                    const pulse = 0.8 + 0.2 * Math.sin(time * 2 + p.pulse);
                    const glowRadius = p.r * 3;
                    
                    // Outer glow
                    const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, glowRadius);
                    gradient.addColorStop(0, p.color);
                    gradient.addColorStop(0.4, p.color + '80');
                    gradient.addColorStop(1, p.color + '00');
                    
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, glowRadius, 0, Math.PI * 2);
                    ctx.fillStyle = gradient;
                    ctx.globalAlpha = p.alpha * pulse * 0.5;
                    ctx.fill();
                    
                    // Core particle
                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                    ctx.fillStyle = p.color;
                    ctx.globalAlpha = p.alpha * pulse;
                    ctx.fill();
                    ctx.globalAlpha = 1;
                }

                this._loadingAnimFrame = requestAnimationFrame(drawParticles);
            };
            drawParticles();
        }
    }

    lightColonyDot(index) {
        const dots = document.querySelectorAll('.colony-dot');
        if (dots[index]) {
            dots[index].classList.add('lit');
        }
    }

    // ═══════════════════════════════════════════════════════════════════════
    // LOADING PROGRESS (Minimap handled by wayfinding.js)
    // ═══════════════════════════════════════════════════════════════════════

    updateLoadingProgress(percent) {
        const fill = document.getElementById('loading-fill');
        if (fill) {
            fill.style.width = `${percent}%`;
        }
        // Update progressbar aria attributes
        const bar = fill?.parentElement;
        if (bar) {
            bar.setAttribute('aria-valuenow', String(percent));
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// INITIALIZE
// ═══════════════════════════════════════════════════════════════════════════

window.addEventListener('DOMContentLoaded', () => {
    window.patentMuseum = new PatentMuseum();
});

export { PatentMuseum };
