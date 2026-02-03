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
import { TurrellLighting } from './museum/lighting.js';
import { PostProcessingManager } from './lib/post-processing.js';
import { CompleteSoundManager } from './lib/sound-design.js';
import { XRManager } from './xr/xr-manager.js';
import { XRControllers } from './xr/xr-controllers.js';
import { XRTeleport } from './xr/xr-teleport.js';
import { PerformanceManager } from './lib/performance.js';

// ═══════════════════════════════════════════════════════════════════════════
// MAIN APPLICATION
// ═══════════════════════════════════════════════════════════════════════════

class PatentMuseum {
    constructor() {
        this.container = document.getElementById('canvas-container');
        this.clock = new THREE.Clock();
        this.time = 0;
        
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
        this._warpActive = false;
        
        // XR System
        this.xrManager = null;
        this.xrControllers = null;
        this.xrTeleport = null;
        this.xrSession = null; // Keep for backward compatibility
        
        this.init();
    }
    
    async init() {
        try {
            // Start loading screen animation
            this.initLoadingScreen();
            this.updateLoadingProgress(10);

            // Create scene
            this.initScene();
            this.updateLoadingProgress(20);

            // Create renderer
            this.initRenderer();
            this.updateLoadingProgress(30);

            // Create camera
            this.initCamera();
            this.updateLoadingProgress(40);

            // Create lighting
            this.initLighting();
            this.lightColonyDot(0); // Spark
            this.updateLoadingProgress(50);

            // Create post-processing
            this.initPostProcessing();
            this.lightColonyDot(1); // Forge
            this.updateLoadingProgress(60);

            // Build museum
            this.buildMuseum();
            this.lightColonyDot(2); // Flow
            this.lightColonyDot(3); // Nexus
            this.updateLoadingProgress(70);

            // Load gallery artworks
            this.loadGalleries();
            this.lightColonyDot(4); // Beacon
            this.updateLoadingProgress(85);

            // Initialize navigation
            this.initNavigation();
            this.lightColonyDot(5); // Grove
            this.updateLoadingProgress(90);

            // Initialize audio (will activate on first click)
            this.initAudio();

            // Initialize minimap
            this.initMinimap();

            // Setup event listeners
            this.initEventListeners();

            // Check for XR support (with timeout protection)
            await this.initXR();
            this.lightColonyDot(6); // Crystal
            this.updateLoadingProgress(100);

            // Start render loop
            this.animate();

            console.log('🏛️ Patent Museum initialized');
            console.log('   54 innovations · h(x) ≥ 0 always');

        } catch (error) {
            console.error('Museum initialization error:', error);
        } finally {
            // Cache DOM elements for render loop (avoid per-frame queries)
            this._crosshairEl = document.getElementById('crosshair');
            this._interactionPromptEl = document.getElementById('interaction-prompt');
            this._locationIndicatorEl = document.getElementById('location-indicator');

            // Cache interactable objects list
            this._rebuildInteractables();

            // Dramatic fade out — loading screen CSS handles the 1.2s transition
            const loadingScreen = document.getElementById('loading-screen');
            if (loadingScreen) {
                loadingScreen.classList.add('hidden');
                loadingScreen.setAttribute('aria-hidden', 'true');

                const cleanup = () => {
                    loadingScreen.removeEventListener('transitionend', cleanup);
                    // Clean up loading animations
                    if (this._loadingAnimFrame) {
                        cancelAnimationFrame(this._loadingAnimFrame);
                        this._loadingAnimFrame = null;
                    }
                    if (this._poemInterval) {
                        clearInterval(this._poemInterval);
                        this._poemInterval = null;
                    }

                    // Arrival transition: hold, then reveal museum
                    const arrival = document.getElementById('arrival-overlay');
                    if (arrival) {
                        setTimeout(() => {
                            arrival.classList.add('revealed');
                            // Remove from DOM after transition
                            arrival.addEventListener('transitionend', () => {
                                if (arrival.parentNode) arrival.parentNode.removeChild(arrival);
                            }, { once: true });
                        }, 400);
                    }
                };
                loadingScreen.addEventListener('transitionend', cleanup, { once: true });

                // Fallback if transitionend doesn't fire
                setTimeout(() => cleanup(), 1500);
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    initScene() {
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x07060B);
        this.scene.fog = new THREE.FogExp2(0x07060B, 0.015);
    }
    
    initRenderer() {
        // Initialize performance manager first
        this.performanceManager = new PerformanceManager();
        const preset = this.performanceManager.getPreset();
        
        console.log(`Performance preset: ${this.performanceManager.getPresetName()}`);
        console.log(`  Device: ${this.performanceManager.isMobile() ? 'Mobile' : 'Desktop'}`);
        console.log(`  GPU Tier: ${this.performanceManager.getGPUTier()}`);
        
        this.renderer = new THREE.WebGLRenderer({
            antialias: preset.antialiasing,
            powerPreference: 'high-performance'
        });
        this.renderer.setSize(window.innerWidth, window.innerHeight);
        
        // Use performance-appropriate pixel ratio
        const pixelRatio = preset.pixelRatio || Math.min(window.devicePixelRatio, 2);
        this.renderer.setPixelRatio(pixelRatio);
        
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.0;
        
        // Configure shadows based on preset
        this.renderer.shadowMap.enabled = preset.shadowsEnabled;
        if (preset.shadowsEnabled) {
            this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        }
        
        this.container.appendChild(this.renderer.domElement);
        
        // Register renderer with performance manager
        this.performanceManager.setRenderer(this.renderer);
    }
    
    initCamera() {
        this.camera = new THREE.PerspectiveCamera(
            70,
            window.innerWidth / window.innerHeight,
            0.1,
            500
        );
        this.camera.position.set(0, 1.7, -35);
    }
    
    initLighting() {
        // Use Turrell-inspired mono-frequency lighting system
        // Each wing bathes visitors in its colony's characteristic light
        // Inspired by James Turrell's Skyspaces and Olafur Eliasson's mono-frequency rooms
        this.turrellLighting = new TurrellLighting(this.scene, this.camera);
        
        // Main directional for shadows (kept minimal to let zone lights dominate)
        const mainLight = new THREE.DirectionalLight(0xF5F0E8, 0.3);
        mainLight.position.set(0, 50, 0);
        mainLight.castShadow = true;
        mainLight.shadow.mapSize.width = 2048;
        mainLight.shadow.mapSize.height = 2048;
        mainLight.shadow.camera.near = 1;
        mainLight.shadow.camera.far = 100;
        mainLight.shadow.camera.left = -50;
        mainLight.shadow.camera.right = 50;
        mainLight.shadow.camera.top = 50;
        mainLight.shadow.camera.bottom = -50;
        this.scene.add(mainLight);
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
        this.postProcessing = new PostProcessingManager(
            this.renderer,
            this.scene,
            this.camera
        );
        
        // Store reference for legacy code
        this.composer = this.postProcessing.composer;
        
        // Register with performance manager
        if (this.performanceManager) {
            this.performanceManager.setPostProcessing(this.postProcessing);
        }
    }
    
    buildMuseum() {
        // Create entire museum structure
        this.museum = createMuseum();
        this.scene.add(this.museum);
        
        // Get references to animated elements
        const rotunda = this.museum.userData.rotunda;
        if (rotunda) {
            this.fanoSculpture = rotunda.getObjectByName('fano-sculpture');
            const dome = rotunda.getObjectByName('dome');
            if (dome) {
                this.hopfProjection = dome.getObjectByName('hopf-projection');
            }
        }
        
        // Add atmospheric particles
        this.addAtmosphericParticles();
    }
    
    loadGalleries() {
        this.galleryLoader = new GalleryLoader(this.scene);
        this.galleryLoader.loadAllGalleries();
        // Gallery loading is synchronous — _rebuildInteractables() in finally block
        // will capture all gallery objects since it runs after this returns.
    }
    
    addAtmosphericParticles() {
        // Dust particles floating in museum — colony-colored near wings
        const particleCount = 700;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        const sizes = new Float32Array(particleCount);

        const colonyRGB = {
            spark:   [1.0, 0.42, 0.21],
            forge:   [0.83, 0.69, 0.22],
            flow:    [0.31, 0.80, 0.77],
            nexus:   [0.61, 0.49, 0.74],
            beacon:  [0.96, 0.62, 0.04],
            grove:   [0.49, 0.72, 0.50],
            crystal: [0.40, 0.83, 0.89]
        };

        for (let i = 0; i < particleCount; i++) {
            const radius = Math.random() * 80;
            const theta = Math.random() * Math.PI * 2;
            const y = Math.random() * 22;
            const x = Math.cos(theta) * radius;
            const z = Math.sin(theta) * radius;

            positions[i * 3] = x;
            positions[i * 3 + 1] = y;
            positions[i * 3 + 2] = z;

            // Check proximity to colony wings and tint accordingly
            let tinted = false;
            COLONY_ORDER.forEach(colony => {
                const data = COLONY_DATA[colony];
                const wingX = Math.cos(data.wingAngle) * (DIMENSIONS.rotunda.radius + DIMENSIONS.wing.length / 2);
                const wingZ = Math.sin(data.wingAngle) * (DIMENSIONS.rotunda.radius + DIMENSIONS.wing.length / 2);
                const dx = x - wingX;
                const dz = z - wingZ;
                const dist = Math.sqrt(dx * dx + dz * dz);

                if (dist < 20 && !tinted) {
                    const rgb = colonyRGB[colony];
                    const blend = 0.3 + Math.random() * 0.4;
                    colors[i * 3]     = rgb[0] * blend + 0.96 * (1 - blend);
                    colors[i * 3 + 1] = rgb[1] * blend + 0.94 * (1 - blend);
                    colors[i * 3 + 2] = rgb[2] * blend + 0.91 * (1 - blend);
                    tinted = true;
                }
            });

            if (!tinted) {
                colors[i * 3]     = 0.96;
                colors[i * 3 + 1] = 0.94;
                colors[i * 3 + 2] = 0.91;
            }

            sizes[i] = 0.03 + Math.random() * 0.06;
        }

        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));

        geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

        const material = new THREE.PointsMaterial({
            size: 0.05,
            vertexColors: true,
            transparent: true,
            opacity: 0.35,
            blending: THREE.AdditiveBlending,
            sizeAttenuation: true
        });

        this.dustParticles = new THREE.Points(geometry, material);
        this.scene.add(this.dustParticles);
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
        this.soundDesign = new CompleteSoundManager();
        
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
            right: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
            z-index: 1000;
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
        
        // Mouse move for raycasting
        window.addEventListener('mousemove', (e) => {
            this.mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
            this.mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
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
        
        // Gallery menu buttons
        const galleryMenu = document.getElementById('gallery-menu');
        this._galleryMenuPrevFocus = null;
        document.querySelectorAll('.wing-button').forEach(btn => {
            btn.addEventListener('click', () => {
                const wing = btn.dataset.wing;
                this.teleportToWing(wing);
                this._closeGalleryMenu(galleryMenu);
            });
        });

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
    
    _rebuildInteractables() {
        this._interactables = [];
        this.scene.traverse((obj) => {
            if (obj.userData?.interactive || obj.userData?.type === 'fano-node' || obj.userData?.artwork) {
                this._interactables.push(obj);
            }
        });
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

        const intersects = this.raycaster.intersectObjects(this._interactables, true);
        
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
        // Show interaction prompt (cached element)
        if (this._interactionPromptEl) {
            this._interactionPromptEl.classList.add('visible');
        }
        
        // Play hover sound (subtle)
        if (this.soundDesign) {
            this.soundDesign.playInteraction('hover');
        }
        
        // Highlight effect
        if (obj.material && obj.material.emissive) {
            obj.userData.originalEmissive = obj.material.emissiveIntensity;
            obj.material.emissiveIntensity = 1.0;
        }
    }
    
    onHoverEnd(obj) {
        if (this._interactionPromptEl) {
            this._interactionPromptEl.classList.remove('visible');
        }
        
        // Remove highlight
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
            
            // Fano node interaction
            if (obj.userData?.type === 'fano-node') {
                this.showColonyInfo(obj.userData.colony);
            }
            
            // Artwork interaction
            if (obj.userData?.artwork) {
                this.showArtworkPanel(obj.userData.artwork);
            }
        }
    }
    
    showColonyInfo(colony) {
        const data = COLONY_DATA[colony];
        console.log(`Colony: ${data.name}`, data);
        
        // Play colony-specific note
        if (this.soundDesign) {
            this.soundDesign.playColonyNote(colony, 0.3);
        }
        // TODO: Show info panel
    }
    
    showArtworkPanel(artwork) {
        console.log('Artwork:', artwork);

        // Play discovery sound
        if (this.soundDesign) {
            this.soundDesign.playInteraction('discovery');
        }

        // Dispatch to the InfoPanel system
        if (artwork?.patentId || artwork?.id) {
            window.dispatchEvent(new CustomEvent('patent-select', {
                detail: { patentId: artwork.patentId || artwork.id }
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
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION LOOP
    // ═══════════════════════════════════════════════════════════════════════
    
    animate() {
        this.renderer.setAnimationLoop(() => this.render());
    }
    
    render() {
        const delta = this.clock.getDelta();
        this.time += delta;
        
        // Update performance monitoring
        if (this.performanceManager) {
            this.performanceManager.update();
        }
        
        // Update navigation
        if (this.navigation) {
            this.navigation.update(delta);
        }
        
        // Update Turrell lighting (zone detection & transitions)
        if (this.turrellLighting) {
            this.turrellLighting.update(delta, this.time);
        }
        
        // Animate Fano sculpture
        if (this.fanoSculpture) {
            animateFanoSculpture(this.fanoSculpture, this.time);
        }
        
        // Animate Hopf projection
        if (this.hopfProjection) {
            animateHopfProjection(this.hopfProjection, this.time);
        }
        
        // Update gallery artworks
        if (this.galleryLoader) {
            this.galleryLoader.update(delta);
        }
        
        // Animate dust particles (with zone-colored tinting)
        if (this.dustParticles) {
            this.dustParticles.rotation.y = this.time * 0.01;
            
            // Gentle vertical drift
            const positions = this.dustParticles.geometry.attributes.position.array;
            for (let i = 0; i < positions.length; i += 3) {
                positions[i + 1] += Math.sin(this.time + i) * 0.001;
                if (positions[i + 1] > 25) positions[i + 1] = 0;
                if (positions[i + 1] < 0) positions[i + 1] = 25;
            }
            this.dustParticles.geometry.attributes.position.needsUpdate = true;
        }
        
        // Update hover state
        this.updateHover();
        
        // Update location
        this.updateLocation();
        
        // Update post-processing (film grain time, etc.)
        if (this.postProcessing) {
            this.postProcessing.update(delta);
        }
        
        // Update spatial audio listener position
        if (this.soundDesign && this.soundDesign.isInitialized) {
            const forward = new THREE.Vector3(0, 0, -1);
            forward.applyQuaternion(this.camera.quaternion);
            const up = new THREE.Vector3(0, 1, 0);
            this.soundDesign.updateListenerPosition(this.camera.position, forward, up);
        }
        
        // Update minimap (every 3rd frame for performance)
        if (this.minimapCtx && Math.floor(this.time * 60) % 3 === 0) {
            this.renderMinimap();
        }

        // Update crosshair awareness (cached DOM element)
        if (this._crosshairEl) {
            if (this.hoveredObject) {
                this._crosshairEl.classList.add('near-artwork');
            } else {
                this._crosshairEl.classList.remove('near-artwork');
            }
        }

        // Render
        if (this.xrSession) {
            // VR mode: render directly (disable post-processing effects that don't work in VR)
            if (this.postProcessing) {
                this.postProcessing.setVRMode(true);
            }
            this.renderer.render(this.scene, this.camera);
        } else {
            // Desktop/mobile: use full post-processing
            if (this.postProcessing) {
                this.postProcessing.setVRMode(false);
                this.postProcessing.render();
            } else {
                this.renderer.render(this.scene, this.camera);
            }
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

        // Particle constellation on loading canvas
        const canvas = document.getElementById('loading-particles');
        if (canvas) {
            const ctx = canvas.getContext('2d');
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;

            const particles = [];
            const COLONY_HEX = [
                '#FF6B35', '#D4AF37', '#4ECDC4',
                '#9B7EBD', '#F59E0B', '#7EB77F', '#67D4E4'
            ];

            for (let i = 0; i < 60; i++) {
                particles.push({
                    x: Math.random() * canvas.width,
                    y: Math.random() * canvas.height,
                    vx: (Math.random() - 0.5) * 0.3,
                    vy: (Math.random() - 0.5) * 0.3,
                    r: 1 + Math.random() * 1.5,
                    color: COLONY_HEX[Math.floor(Math.random() * 7)],
                    alpha: 0.15 + Math.random() * 0.35
                });
            }

            const drawParticles = () => {
                ctx.clearRect(0, 0, canvas.width, canvas.height);

                // Draw connections
                for (let i = 0; i < particles.length; i++) {
                    for (let j = i + 1; j < particles.length; j++) {
                        const dx = particles[i].x - particles[j].x;
                        const dy = particles[i].y - particles[j].y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        if (dist < 120) {
                            ctx.beginPath();
                            ctx.moveTo(particles[i].x, particles[i].y);
                            ctx.lineTo(particles[j].x, particles[j].y);
                            ctx.strokeStyle = `rgba(103, 212, 228, ${0.06 * (1 - dist / 120)})`;
                            ctx.lineWidth = 0.5;
                            ctx.stroke();
                        }
                    }
                }

                // Draw particles
                for (const p of particles) {
                    p.x += p.vx;
                    p.y += p.vy;
                    if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
                    if (p.y < 0 || p.y > canvas.height) p.vy *= -1;

                    ctx.beginPath();
                    ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                    ctx.fillStyle = p.color;
                    ctx.globalAlpha = p.alpha;
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
    // MINIMAP
    // ═══════════════════════════════════════════════════════════════════════

    initMinimap() {
        const container = document.getElementById('minimap');
        if (!container) return;

        const canvas = document.createElement('canvas');
        canvas.width = 300;
        canvas.height = 300;
        container.appendChild(canvas);
        this.minimapCanvas = canvas;
        this.minimapCtx = canvas.getContext('2d');
    }

    renderMinimap() {
        if (!this.minimapCtx) return;
        const ctx = this.minimapCtx;
        const w = 300, h = 300;
        const cx = w / 2, cy = h / 2;
        const scale = 2.8;

        ctx.clearRect(0, 0, w, h);

        // Background
        ctx.fillStyle = 'rgba(7, 6, 11, 0.95)';
        ctx.fillRect(0, 0, w, h);

        const colonyColors = {
            spark: '#FF6B35', forge: '#D4AF37', flow: '#4ECDC4',
            nexus: '#9B7EBD', beacon: '#F59E0B', grove: '#7EB77F', crystal: '#67D4E4'
        };

        // Draw rotunda circle
        ctx.beginPath();
        ctx.arc(cx, cy, DIMENSIONS.rotunda.radius * scale, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(103, 212, 228, 0.25)';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Draw wings
        COLONY_ORDER.forEach(colony => {
            const data = COLONY_DATA[colony];
            const angle = data.wingAngle;
            const startR = DIMENSIONS.rotunda.radius * scale;
            const endR = startR + DIMENSIONS.wing.length * scale;

            const x1 = cx + Math.cos(angle) * startR;
            const y1 = cy + Math.sin(angle) * startR;
            const x2 = cx + Math.cos(angle) * endR;
            const y2 = cy + Math.sin(angle) * endR;

            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.strokeStyle = colonyColors[colony] || '#67D4E4';
            ctx.lineWidth = 3;
            ctx.globalAlpha = 0.5;
            ctx.stroke();
            ctx.globalAlpha = 1;

            // Wing tip dot
            ctx.beginPath();
            ctx.arc(x2, y2, 3, 0, Math.PI * 2);
            ctx.fillStyle = colonyColors[colony];
            ctx.globalAlpha = 0.6;
            ctx.fill();
            ctx.globalAlpha = 1;
        });

        // Draw player position
        const px = cx + this.camera.position.x * scale;
        const py = cy + this.camera.position.z * scale;

        // View direction cone
        const forward = new THREE.Vector3(0, 0, -1);
        forward.applyQuaternion(this.camera.quaternion);
        const viewAngle = Math.atan2(forward.z, forward.x);
        const coneLen = 12;
        const coneSpread = 0.35;

        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(
            px + Math.cos(viewAngle - coneSpread) * coneLen,
            py + Math.sin(viewAngle - coneSpread) * coneLen
        );
        ctx.lineTo(
            px + Math.cos(viewAngle + coneSpread) * coneLen,
            py + Math.sin(viewAngle + coneSpread) * coneLen
        );
        ctx.closePath();
        ctx.fillStyle = 'rgba(103, 212, 228, 0.15)';
        ctx.fill();

        // Player dot
        ctx.beginPath();
        ctx.arc(px, py, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#67D4E4';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(px, py, 6, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(103, 212, 228, 0.4)';
        ctx.lineWidth = 1;
        ctx.stroke();
    }

    // ═══════════════════════════════════════════════════════════════════════
    // LOADING PROGRESS
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
