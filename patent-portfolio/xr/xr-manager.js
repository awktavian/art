/**
 * XR Manager
 * ==========
 * 
 * Centralized WebXR session lifecycle management for VR and AR.
 * Handles session creation, reference spaces, and frame updates.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// XR SUPPORT DETECTION
// ═══════════════════════════════════════════════════════════════════════════

export async function checkXRSupport() {
    if (!navigator.xr) {
        return { vr: false, ar: false };
    }
    
    const [vrSupport, arSupport] = await Promise.all([
        navigator.xr.isSessionSupported('immersive-vr').catch(() => false),
        navigator.xr.isSessionSupported('immersive-ar').catch(() => false)
    ]);
    
    return { vr: vrSupport, ar: arSupport };
}

// ═══════════════════════════════════════════════════════════════════════════
// XR MANAGER CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class XRManager {
    constructor(renderer, scene, camera) {
        this.renderer = renderer;
        this.scene = scene;
        this.camera = camera;
        
        // Session state
        this.session = null;
        this.sessionType = null; // 'vr' | 'ar' | null
        this.referenceSpace = null;
        this.referenceSpaceType = null;
        
        // Controllers (managed by XRControllers class)
        this.controllers = null;
        
        // AR-specific
        this.hitTestSource = null;
        this.hitTestResults = [];
        this.arAnchors = null; // XRARAnchors instance
        this.domOverlayElement = null;
        
        // Callbacks
        this.onSessionStart = null;
        this.onSessionEnd = null;
        this.onFrame = null;
        this.onError = null;
        
        // State
        this.isPresenting = false;
        this.frameCallbacks = [];
        
        // Enable XR on renderer
        this.renderer.xr.enabled = true;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // VR SESSION
    // ═══════════════════════════════════════════════════════════════════════
    
    async startVR() {
        if (this.session) {
            console.warn('XR session already active');
            return false;
        }
        
        try {
            // Request VR session with optional features
            const sessionInit = {
                optionalFeatures: [
                    'local-floor',
                    'bounded-floor',
                    'hand-tracking',
                    'layers'
                ]
            };
            
            this.session = await navigator.xr.requestSession('immersive-vr', sessionInit);
            this.sessionType = 'vr';
            
            await this.setupSession();
            
            // Try to get the best reference space available
            await this.setupReferenceSpace(['bounded-floor', 'local-floor', 'local']);
            
            console.log(`VR session started with ${this.referenceSpaceType} reference space`);
            
            if (this.onSessionStart) {
                this.onSessionStart('vr');
            }
            
            return true;
        } catch (error) {
            console.error('Failed to start VR session:', error);
            if (this.onError) {
                this.onError(error, 'vr');
            }
            return false;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // AR SESSION
    // ═══════════════════════════════════════════════════════════════════════
    
    async startAR() {
        if (this.session) {
            console.warn('XR session already active');
            return false;
        }
        
        try {
            // Request AR session with hit-test for surface detection
            const sessionInit = {
                requiredFeatures: ['hit-test'],
                optionalFeatures: [
                    'dom-overlay',
                    'anchors',
                    'plane-detection',
                    'light-estimation'
                ],
                domOverlay: { root: document.getElementById('ar-overlay') }
            };
            
            this.session = await navigator.xr.requestSession('immersive-ar', sessionInit);
            this.sessionType = 'ar';
            
            await this.setupSession();
            
            // AR uses viewer reference space
            await this.setupReferenceSpace(['local-floor', 'local']);
            
            // Request hit test source for surface detection
            await this.setupHitTesting();
            
            // Connect touch events for AR interactions if domOverlay is available
            this.domOverlayElement = document.getElementById('ar-overlay');
            if (this.domOverlayElement && this.arAnchors) {
                this.arAnchors.connectTouchEvents(this.domOverlayElement);
            }
            
            console.log(`AR session started with ${this.referenceSpaceType} reference space`);
            
            if (this.onSessionStart) {
                this.onSessionStart('ar');
            }
            
            return true;
        } catch (error) {
            console.error('Failed to start AR session:', error);
            if (this.onError) {
                this.onError(error, 'ar');
            }
            return false;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SESSION SETUP
    // ═══════════════════════════════════════════════════════════════════════
    
    async setupSession() {
        if (!this.session) return;
        
        // Configure renderer for XR
        await this.renderer.xr.setSession(this.session);
        this.isPresenting = true;
        
        // Session end handler
        this.session.addEventListener('end', () => this.handleSessionEnd());
        
        // Visibility change handler
        this.session.addEventListener('visibilitychange', (e) => {
            console.log('XR visibility changed:', e.session.visibilityState);
        });
        
        // Input source change handler
        this.session.addEventListener('inputsourceschange', (e) => {
            console.log('Input sources changed:', e.added.length, 'added,', e.removed.length, 'removed');
        });
    }
    
    async setupReferenceSpace(preferredTypes) {
        for (const type of preferredTypes) {
            try {
                this.referenceSpace = await this.session.requestReferenceSpace(type);
                this.referenceSpaceType = type;
                
                // Set reference space on renderer
                this.renderer.xr.setReferenceSpace(this.referenceSpace);
                
                return;
            } catch (e) {
                console.log(`Reference space '${type}' not available`);
            }
        }
        
        throw new Error('No suitable reference space available');
    }
    
    async setupHitTesting() {
        if (!this.session || this.sessionType !== 'ar') return;
        
        try {
            // Request hit test source from viewer's perspective
            const viewerSpace = await this.session.requestReferenceSpace('viewer');
            this.hitTestSource = await this.session.requestHitTestSource({
                space: viewerSpace
            });
            
            console.log('Hit test source established');
        } catch (error) {
            console.warn('Hit testing not available:', error);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SESSION END
    // ═══════════════════════════════════════════════════════════════════════
    
    handleSessionEnd() {
        console.log('XR session ended');
        
        // Clean up hit test source
        if (this.hitTestSource) {
            this.hitTestSource.cancel();
            this.hitTestSource = null;
        }
        
        // Disconnect touch events for AR
        if (this.domOverlayElement && this.arAnchors) {
            this.arAnchors.disconnectTouchEvents(this.domOverlayElement);
        }
        
        // Reset state
        this.session = null;
        this.sessionType = null;
        this.referenceSpace = null;
        this.referenceSpaceType = null;
        this.isPresenting = false;
        this.hitTestResults = [];
        this.domOverlayElement = null;
        
        // Notify listeners
        if (this.onSessionEnd) {
            this.onSessionEnd();
        }
    }
    
    async endSession() {
        if (this.session) {
            await this.session.end();
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FRAME UPDATE
    // ═══════════════════════════════════════════════════════════════════════
    
    update(time, frame) {
        if (!this.session || !frame) return;
        
        // Update hit test results for AR
        if (this.sessionType === 'ar' && this.hitTestSource) {
            this.hitTestResults = frame.getHitTestResults(this.hitTestSource);
        }
        
        // Call registered frame callbacks
        this.frameCallbacks.forEach(callback => {
            try {
                callback(time, frame, this);
            } catch (error) {
                console.error('XR frame callback error:', error);
            }
        });
        
        // Main frame callback
        if (this.onFrame) {
            this.onFrame(time, frame);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UTILITY METHODS
    // ═══════════════════════════════════════════════════════════════════════
    
    addFrameCallback(callback) {
        this.frameCallbacks.push(callback);
        return () => {
            const index = this.frameCallbacks.indexOf(callback);
            if (index > -1) {
                this.frameCallbacks.splice(index, 1);
            }
        };
    }
    
    getHitTestResults() {
        return this.hitTestResults;
    }
    
    getHitPose(index = 0) {
        if (this.hitTestResults.length > index && this.referenceSpace) {
            return this.hitTestResults[index].getPose(this.referenceSpace);
        }
        return null;
    }
    
    // Get current input sources
    getInputSources() {
        return this.session ? Array.from(this.session.inputSources) : [];
    }
    
    // Check if specific feature is supported
    hasFeature(feature) {
        if (!this.session) return false;
        return this.session.enabledFeatures?.includes(feature) ?? false;
    }
    
    // Set AR anchors instance for touch event handling
    setARAnchors(arAnchors) {
        this.arAnchors = arAnchors;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // BUTTON CREATION
    // ═══════════════════════════════════════════════════════════════════════
    
    createVRButton() {
        const button = document.createElement('button');
        button.className = 'xr-button';
        button.textContent = 'Enter VR';
        button.id = 'vr-button';
        
        button.addEventListener('click', async () => {
            if (this.isPresenting) {
                await this.endSession();
            } else {
                await this.startVR();
            }
        });
        
        // Update button text based on state
        const updateButton = () => {
            button.textContent = this.isPresenting ? 'Exit VR' : 'Enter VR';
        };
        
        // Preserve existing callbacks
        const originalOnStart = this.onSessionStart;
        const originalOnEnd = this.onSessionEnd;
        
        this.onSessionStart = (type) => {
            if (type === 'vr') updateButton();
            if (originalOnStart) originalOnStart(type);
        };
        this.onSessionEnd = () => {
            updateButton();
            if (originalOnEnd) originalOnEnd();
        };
        
        return button;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // VISION PRO SPECIFIC FEATURES
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Detect if running on Apple Vision Pro
     * Vision Pro uses WebXR with specific capabilities
     */
    isVisionPro() {
        // Vision Pro detection heuristics:
        // 1. Check for visionOS user agent
        // 2. Check for Safari with WebXR support
        // 3. Check for hand tracking without controllers
        const ua = navigator.userAgent.toLowerCase();
        const isVisionOS = ua.includes('visionos') || ua.includes('xros');
        const isSafariWebXR = ua.includes('safari') && 'xr' in navigator;
        
        return isVisionOS || (isSafariWebXR && window.XRHand !== undefined);
    }
    
    /**
     * Request Vision Pro-optimized VR session
     * Uses natural input (eye tracking + hand pinch) instead of controllers
     */
    async startVisionProSession() {
        if (this.session) {
            console.warn('XR session already active');
            return false;
        }
        
        try {
            // Vision Pro features: hand tracking is the primary input
            // No traditional controllers, uses eye tracking for gaze
            const sessionInit = {
                optionalFeatures: [
                    'local-floor',
                    'hand-tracking',       // Primary input method
                    'layers',              // For high-quality rendering
                    'depth-sensing',       // For occlusion
                    'mesh-detection'       // For room understanding
                ]
            };
            
            // Vision Pro may support either immersive-vr or immersive-ar
            // Try VR first (fully immersive) then fall back to AR (passthrough)
            try {
                this.session = await navigator.xr.requestSession('immersive-vr', sessionInit);
                this.sessionType = 'vr';
            } catch (vrError) {
                console.log('Full VR not available, trying AR passthrough');
                sessionInit.requiredFeatures = ['hand-tracking'];
                this.session = await navigator.xr.requestSession('immersive-ar', sessionInit);
                this.sessionType = 'ar';
            }
            
            await this.setupSession();
            await this.setupReferenceSpace(['local-floor', 'local']);
            
            // Configure for high-quality rendering on Vision Pro
            this.configureVisionProRenderer();
            
            console.log(`Vision Pro session started (${this.sessionType})`);
            
            if (this.onSessionStart) {
                this.onSessionStart(this.sessionType);
            }
            
            return true;
        } catch (error) {
            console.error('Failed to start Vision Pro session:', error);
            if (this.onError) {
                this.onError(error, 'visionpro');
            }
            return false;
        }
    }
    
    /**
     * Configure renderer for Vision Pro's display characteristics
     */
    configureVisionProRenderer() {
        if (!this.renderer) return;
        
        // Vision Pro has high pixel density display
        // Use high-quality settings but be mindful of performance
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2.0));
        
        // Enable tone mapping for better HDR
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.0;
        
        // Vision Pro benefits from higher quality shadows
        this.renderer.shadowMap.enabled = true;
        this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
        
        // Output encoding for sRGB display
        this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    }
    
    /**
     * Create Vision Pro-appropriate UI button
     * Detects device and shows appropriate label
     */
    createVisionProButton() {
        const button = document.createElement('button');
        button.className = 'xr-button vision-pro-button';
        button.id = 'visionpro-button';
        
        // Set label based on detection
        const isVP = this.isVisionPro();
        button.textContent = isVP ? 'Open in Vision Pro' : 'Enter VR';
        button.innerHTML = isVP 
            ? '🥽 Open in Vision Pro' 
            : '🎮 Enter VR';
        
        button.style.cssText = `
            background: linear-gradient(135deg, #2C3E50, #1A1A1A);
            border: 1px solid rgba(103, 212, 228, 0.5);
            color: #E0E0E0;
            padding: 12px 24px;
            border-radius: 8px;
            font-family: -apple-system, BlinkMacSystemFont, 'IBM Plex Sans', sans-serif;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s ease;
        `;
        
        button.addEventListener('mouseover', () => {
            button.style.borderColor = '#67D4E4';
            button.style.boxShadow = '0 0 20px rgba(103, 212, 228, 0.3)';
        });
        
        button.addEventListener('mouseout', () => {
            button.style.borderColor = 'rgba(103, 212, 228, 0.5)';
            button.style.boxShadow = 'none';
        });
        
        button.addEventListener('click', async () => {
            if (this.isPresenting) {
                await this.endSession();
            } else if (isVP) {
                await this.startVisionProSession();
            } else {
                await this.startVR();
            }
        });
        
        // Update button on session changes
        const updateButton = () => {
            if (this.isPresenting) {
                button.innerHTML = '✕ Exit Immersive';
            } else {
                button.innerHTML = isVP 
                    ? '🥽 Open in Vision Pro' 
                    : '🎮 Enter VR';
            }
        };
        
        // Preserve existing callbacks
        const originalOnStart = this.onSessionStart;
        const originalOnEnd = this.onSessionEnd;
        
        this.onSessionStart = (type) => {
            updateButton();
            if (originalOnStart) originalOnStart(type);
        };
        this.onSessionEnd = () => {
            updateButton();
            if (originalOnEnd) originalOnEnd();
        };
        
        return button;
    }
    
    createARButton() {
        const button = document.createElement('button');
        button.className = 'xr-button';
        button.textContent = 'Enter AR';
        button.id = 'ar-button';
        
        button.addEventListener('click', async () => {
            if (this.isPresenting) {
                await this.endSession();
            } else {
                await this.startAR();
            }
        });
        
        // Update button text based on state
        const updateButton = () => {
            button.textContent = this.isPresenting ? 'Exit AR' : 'Enter AR';
        };
        
        const originalOnStart = this.onSessionStart;
        const originalOnEnd = this.onSessionEnd;
        
        this.onSessionStart = (type) => {
            if (type === 'ar') updateButton();
            if (originalOnStart) originalOnStart(type);
        };
        this.onSessionEnd = () => {
            updateButton();
            if (originalOnEnd) originalOnEnd();
        };
        
        return button;
    }
    
    async createButtons(container) {
        const support = await checkXRSupport();
        
        if (support.vr) {
            container.appendChild(this.createVRButton());
        }
        
        if (support.ar) {
            container.appendChild(this.createARButton());
        }
        
        if (!support.vr && !support.ar) {
            const notice = document.createElement('span');
            notice.className = 'xr-notice';
            notice.textContent = 'WebXR not available';
            notice.style.cssText = 'color: var(--text-tertiary); font-size: 12px;';
            container.appendChild(notice);
        }
        
        return support;
    }
}

export default XRManager;
