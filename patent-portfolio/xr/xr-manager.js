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
        
        // Reset state
        this.session = null;
        this.sessionType = null;
        this.referenceSpace = null;
        this.referenceSpaceType = null;
        this.isPresenting = false;
        this.hitTestResults = [];
        
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
        
        this.onSessionStart = (type) => {
            if (type === 'vr') updateButton();
        };
        this.onSessionEnd = () => updateButton();
        
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
