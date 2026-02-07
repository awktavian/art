/**
 * Kagami XR Library
 * ==================
 * 
 * WebXR session management, controller input, and hand tracking abstraction.
 * Based on platform-xr-unified/SKILL.md design guidelines.
 * 
 * Supports: Meta Quest, Apple Vision Pro, Android XR, WebXR browsers
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { XRControllerModelFactory } from 'three/addons/webxr/XRControllerModelFactory.js';
import { XRHandModelFactory } from 'three/addons/webxr/XRHandModelFactory.js';
import { XR, DURATION_S, COLONY_COLORS } from './design-tokens.js';

// ═══════════════════════════════════════════════════════════════════════════
// XR MANAGER CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class KagamiXR {
    constructor(renderer, options = {}) {
        this.renderer = renderer;
        this.options = options;
        
        // State
        this.isVRSupported = false;
        this.isARSupported = false;
        this.activeSession = null;
        this.sessionMode = null;
        
        // Controllers
        this.controllers = [];
        this.controllerGrips = [];
        this.hands = [];
        
        // Factories
        this.controllerModelFactory = new XRControllerModelFactory();
        this.handModelFactory = new XRHandModelFactory();
        
        // Raycasting
        this.raycaster = new THREE.Raycaster();
        this.tempMatrix = new THREE.Matrix4();
        
        // Interaction state
        this.hoveredObject = null;
        this.selectedObject = null;
        this.grabState = { left: null, right: null };
        
        // Callbacks
        this.onSessionStart = options.onSessionStart || null;
        this.onSessionEnd = options.onSessionEnd || null;
        this.onSelect = options.onSelect || null;
        this.onSelectStart = options.onSelectStart || null;
        this.onSelectEnd = options.onSelectEnd || null;
        this.onHover = options.onHover || null;
        this.onHoverEnd = options.onHoverEnd || null;
        this.onGrab = options.onGrab || null;
        this.onRelease = options.onRelease || null;
        
        // Interactable objects
        this.interactables = [];
        
        // Initialize
        this.init();
    }
    
    async init() {
        if (!navigator.xr) {
            console.warn('WebXR not supported');
            return;
        }
        
        // Check support
        try {
            this.isVRSupported = await navigator.xr.isSessionSupported('immersive-vr');
        } catch (e) {
            this.isVRSupported = false;
        }
        
        try {
            this.isARSupported = await navigator.xr.isSessionSupported('immersive-ar');
        } catch (e) {
            this.isARSupported = false;
        }
        
        console.log(`WebXR Support - VR: ${this.isVRSupported}, AR: ${this.isARSupported}`);
        
        // Configure renderer for XR
        this.renderer.xr.enabled = true;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SESSION MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Start a VR session
     */
    async startVR(referenceSpace = 'local-floor') {
        if (!this.isVRSupported) {
            console.error('VR not supported');
            return false;
        }
        
        try {
            const session = await navigator.xr.requestSession('immersive-vr', {
                requiredFeatures: [referenceSpace],
                optionalFeatures: ['hand-tracking', 'layers']
            });
            
            await this.setupSession(session, 'immersive-vr');
            return true;
        } catch (e) {
            console.error('Failed to start VR session:', e);
            return false;
        }
    }
    
    /**
     * Start an AR session
     */
    async startAR(referenceSpace = 'local-floor') {
        if (!this.isARSupported) {
            console.error('AR not supported');
            return false;
        }
        
        try {
            const session = await navigator.xr.requestSession('immersive-ar', {
                requiredFeatures: [referenceSpace],
                optionalFeatures: ['hand-tracking', 'hit-test', 'dom-overlay'],
                domOverlay: this.options.domOverlay ? { root: this.options.domOverlay } : undefined
            });
            
            await this.setupSession(session, 'immersive-ar');
            return true;
        } catch (e) {
            console.error('Failed to start AR session:', e);
            return false;
        }
    }
    
    /**
     * End the current XR session
     */
    async endSession() {
        if (this.activeSession) {
            await this.activeSession.end();
        }
    }
    
    /**
     * Setup session internals
     */
    async setupSession(session, mode) {
        this.activeSession = session;
        this.sessionMode = mode;
        
        await this.renderer.xr.setSession(session);
        
        session.addEventListener('end', () => {
            this.activeSession = null;
            this.sessionMode = null;
            if (this.onSessionEnd) this.onSessionEnd();
        });
        
        if (this.onSessionStart) this.onSessionStart(session, mode);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CONTROLLER SETUP
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Setup controllers and hands for a scene
     */
    setupControllers(scene) {
        // Controller 0 (left)
        const controller0 = this.renderer.xr.getController(0);
        controller0.addEventListener('selectstart', (e) => this.handleSelectStart(e, 0));
        controller0.addEventListener('selectend', (e) => this.handleSelectEnd(e, 0));
        controller0.addEventListener('squeezestart', (e) => this.handleSqueezeStart(e, 0));
        controller0.addEventListener('squeezeend', (e) => this.handleSqueezeEnd(e, 0));
        controller0.addEventListener('connected', (e) => this.handleControllerConnected(e, 0));
        controller0.addEventListener('disconnected', (e) => this.handleControllerDisconnected(e, 0));
        scene.add(controller0);
        this.controllers[0] = controller0;
        
        // Controller 1 (right)
        const controller1 = this.renderer.xr.getController(1);
        controller1.addEventListener('selectstart', (e) => this.handleSelectStart(e, 1));
        controller1.addEventListener('selectend', (e) => this.handleSelectEnd(e, 1));
        controller1.addEventListener('squeezestart', (e) => this.handleSqueezeStart(e, 1));
        controller1.addEventListener('squeezeend', (e) => this.handleSqueezeEnd(e, 1));
        controller1.addEventListener('connected', (e) => this.handleControllerConnected(e, 1));
        controller1.addEventListener('disconnected', (e) => this.handleControllerDisconnected(e, 1));
        scene.add(controller1);
        this.controllers[1] = controller1;
        
        // Controller grips (physical models)
        const controllerGrip0 = this.renderer.xr.getControllerGrip(0);
        controllerGrip0.add(this.controllerModelFactory.createControllerModel(controllerGrip0));
        scene.add(controllerGrip0);
        this.controllerGrips[0] = controllerGrip0;
        
        const controllerGrip1 = this.renderer.xr.getControllerGrip(1);
        controllerGrip1.add(this.controllerModelFactory.createControllerModel(controllerGrip1));
        scene.add(controllerGrip1);
        this.controllerGrips[1] = controllerGrip1;
        
        // Add ray visual to controllers
        this.controllers.forEach(controller => {
            controller.add(this.createRayVisual());
        });
        
        // Setup hands (if supported)
        this.setupHands(scene);
        
        return { controllers: this.controllers, controllerGrips: this.controllerGrips, hands: this.hands };
    }
    
    /**
     * Setup hand tracking
     */
    setupHands(scene) {
        for (let i = 0; i < 2; i++) {
            const hand = this.renderer.xr.getHand(i);
            hand.add(this.handModelFactory.createHandModel(hand, 'mesh'));
            
            hand.addEventListener('pinchstart', (e) => this.handlePinchStart(e, i));
            hand.addEventListener('pinchend', (e) => this.handlePinchEnd(e, i));
            
            scene.add(hand);
            this.hands[i] = hand;
        }
    }
    
    /**
     * Create a ray visual for controllers
     */
    createRayVisual() {
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.Float32BufferAttribute([0, 0, 0, 0, 0, -1], 3));
        geometry.setAttribute('color', new THREE.Float32BufferAttribute([0.5, 0.5, 0.5, 0, 0, 0], 3));
        
        const material = new THREE.LineBasicMaterial({
            vertexColors: true,
            blending: THREE.AdditiveBlending
        });
        
        const line = new THREE.Line(geometry, material);
        line.name = 'rayLine';
        line.scale.z = 5;
        
        return line;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CONTROLLER EVENT HANDLERS
    // ═══════════════════════════════════════════════════════════════════════
    
    handleControllerConnected(event, index) {
        const controller = this.controllers[index];
        controller.userData.inputSource = event.data;
        controller.userData.handedness = event.data.handedness;
        console.log(`Controller ${index} connected: ${event.data.handedness}`);
    }
    
    handleControllerDisconnected(event, index) {
        const controller = this.controllers[index];
        controller.userData.inputSource = null;
        controller.userData.handedness = null;
        console.log(`Controller ${index} disconnected`);
    }
    
    handleSelectStart(event, index) {
        const controller = this.controllers[index];
        const intersects = this.getControllerIntersections(controller);
        
        if (intersects.length > 0) {
            this.selectedObject = intersects[0].object;
            
            if (this.onSelectStart) {
                this.onSelectStart(this.selectedObject, controller, index);
            }
        }
    }
    
    handleSelectEnd(event, index) {
        const controller = this.controllers[index];
        
        if (this.selectedObject) {
            if (this.onSelect) {
                this.onSelect(this.selectedObject, controller, index);
            }
            
            if (this.onSelectEnd) {
                this.onSelectEnd(this.selectedObject, controller, index);
            }
        }
        
        this.selectedObject = null;
    }
    
    handleSqueezeStart(event, index) {
        const controller = this.controllers[index];
        const intersects = this.getControllerIntersections(controller);
        
        if (intersects.length > 0) {
            const object = intersects[0].object;
            const handedness = index === 0 ? 'left' : 'right';
            this.grabState[handedness] = object;
            
            // Attach to controller
            controller.attach(object);
            
            if (this.onGrab) {
                this.onGrab(object, controller, index);
            }
        }
    }
    
    handleSqueezeEnd(event, index) {
        const controller = this.controllers[index];
        const handedness = index === 0 ? 'left' : 'right';
        const object = this.grabState[handedness];
        
        if (object) {
            // Detach from controller (return to scene)
            const scene = controller.parent;
            if (scene) {
                scene.attach(object);
            }
            
            if (this.onRelease) {
                this.onRelease(object, controller, index);
            }
            
            this.grabState[handedness] = null;
        }
    }
    
    handlePinchStart(event, index) {
        // Hand tracking pinch acts like select
        const hand = this.hands[index];
        const intersects = this.getHandIntersections(hand);
        
        if (intersects.length > 0) {
            this.selectedObject = intersects[0].object;
            
            if (this.onSelectStart) {
                this.onSelectStart(this.selectedObject, hand, index);
            }
        }
    }
    
    handlePinchEnd(event, index) {
        const hand = this.hands[index];
        
        if (this.selectedObject) {
            if (this.onSelect) {
                this.onSelect(this.selectedObject, hand, index);
            }
        }
        
        this.selectedObject = null;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // RAYCASTING & INTERSECTION
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Register an object as interactable
     */
    addInteractable(object) {
        if (!this.interactables.includes(object)) {
            this.interactables.push(object);
        }
    }
    
    /**
     * Remove an interactable
     */
    removeInteractable(object) {
        const index = this.interactables.indexOf(object);
        if (index > -1) {
            this.interactables.splice(index, 1);
        }
    }
    
    /**
     * Get intersections from a controller
     */
    getControllerIntersections(controller) {
        this.tempMatrix.identity().extractRotation(controller.matrixWorld);
        
        this.raycaster.ray.origin.setFromMatrixPosition(controller.matrixWorld);
        this.raycaster.ray.direction.set(0, 0, -1).applyMatrix4(this.tempMatrix);
        
        return this.raycaster.intersectObjects(this.interactables, true);
    }
    
    /**
     * Get intersections from a hand (uses index finger tip)
     */
    getHandIntersections(hand) {
        // Get index finger tip joint if available
        const indexTip = hand.joints['index-finger-tip'];
        if (!indexTip) return [];
        
        this.raycaster.ray.origin.copy(indexTip.position);
        this.raycaster.ray.direction.set(0, 0, -1).applyQuaternion(indexTip.quaternion);
        
        return this.raycaster.intersectObjects(this.interactables, true);
    }
    
    /**
     * Update hover state (call in render loop)
     */
    updateHover() {
        let newHovered = null;
        
        // Check both controllers
        for (const controller of this.controllers) {
            if (!controller.userData.inputSource) continue;
            
            const intersects = this.getControllerIntersections(controller);
            
            if (intersects.length > 0) {
                newHovered = intersects[0].object;
                
                // Update ray visual
                const ray = controller.getObjectByName('rayLine');
                if (ray) {
                    ray.scale.z = intersects[0].distance;
                }
                
                break;
            }
        }
        
        // Handle hover state change
        if (newHovered !== this.hoveredObject) {
            if (this.hoveredObject && this.onHoverEnd) {
                this.onHoverEnd(this.hoveredObject);
            }
            
            this.hoveredObject = newHovered;
            
            if (this.hoveredObject && this.onHover) {
                this.onHover(this.hoveredObject);
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SPATIAL UTILITIES
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Get camera position in XR (works for both VR and non-VR)
     */
    getCameraPosition(camera) {
        if (this.renderer.xr.isPresenting) {
            const xrCamera = this.renderer.xr.getCamera();
            return xrCamera.position.clone();
        }
        return camera.position.clone();
    }
    
    /**
     * Get camera forward direction
     */
    getCameraForward(camera) {
        const direction = new THREE.Vector3(0, 0, -1);
        
        if (this.renderer.xr.isPresenting) {
            const xrCamera = this.renderer.xr.getCamera();
            direction.applyQuaternion(xrCamera.quaternion);
        } else {
            direction.applyQuaternion(camera.quaternion);
        }
        
        return direction;
    }
    
    /**
     * Position object in front of user
     */
    placeInFrontOfUser(object, camera, distance = 2) {
        const position = this.getCameraPosition(camera);
        const forward = this.getCameraForward(camera);
        
        position.add(forward.multiplyScalar(distance));
        position.y = Math.max(position.y, 0.5); // Keep above ground
        
        object.position.copy(position);
        object.lookAt(this.getCameraPosition(camera));
    }
    
    /**
     * Get proxemic zone for object distance
     */
    getProxemicZone(object, camera) {
        const distance = this.getCameraPosition(camera).distanceTo(object.position);
        
        for (const [zone, config] of Object.entries(XR.proxemicZones)) {
            if (distance >= config.min && (config.max === null || distance < config.max)) {
                return { zone, distance, ...config };
            }
        }
        
        return { zone: 'public', distance, ...XR.proxemicZones.public };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // HAPTICS
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Trigger haptic feedback
     */
    triggerHaptic(controllerIndex, intensity = 0.5, duration = 50) {
        const controller = this.controllers[controllerIndex];
        if (!controller?.userData?.inputSource?.gamepad) return;
        
        const gamepad = controller.userData.inputSource.gamepad;
        const hapticActuator = gamepad.hapticActuators?.[0] || gamepad.vibrationActuator;
        
        if (hapticActuator) {
            if (hapticActuator.pulse) {
                hapticActuator.pulse(intensity, duration);
            } else if (hapticActuator.playEffect) {
                hapticActuator.playEffect('dual-rumble', {
                    duration,
                    strongMagnitude: intensity,
                    weakMagnitude: intensity * 0.5
                });
            }
        }
    }
    
    /**
     * Trigger haptic on both controllers
     */
    triggerHapticBoth(intensity = 0.5, duration = 50) {
        this.triggerHaptic(0, intensity, duration);
        this.triggerHaptic(1, intensity, duration);
    }
    
    /**
     * Predefined haptic patterns
     */
    hapticPatterns = {
        confirm: () => this.triggerHapticBoth(0.6, 50),
        error: () => {
            this.triggerHapticBoth(0.8, 100);
            setTimeout(() => this.triggerHapticBoth(0.8, 100), 150);
        },
        hover: () => this.triggerHapticBoth(0.3, 20),
        grab: () => this.triggerHapticBoth(0.7, 100),
        release: () => this.triggerHapticBoth(0.4, 50)
    };
}

// ═══════════════════════════════════════════════════════════════════════════
// XR BUTTON COMPONENT
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create VR/AR entry buttons
 */
export function createXRButtons(kagamiXR, container) {
    const buttonsDiv = document.createElement('div');
    buttonsDiv.style.cssText = `
        position: fixed;
        bottom: 20px;
        left: 50%;
        transform: translateX(-50%);
        display: flex;
        gap: 12px;
        z-index: 1000;
    `;
    
    const buttonStyle = `
        padding: 12px 24px;
        font-family: 'Orbitron', 'Space Mono', monospace;
        font-size: 14px;
        font-weight: 600;
        letter-spacing: 0.1em;
        border: 2px solid;
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.233s ease;
        text-transform: uppercase;
    `;
    
    // VR Button
    if (kagamiXR.isVRSupported) {
        const vrButton = document.createElement('button');
        vrButton.textContent = 'ENTER VR';
        vrButton.style.cssText = buttonStyle + `
            background: rgba(103, 212, 228, 0.1);
            border-color: #67D4E4;
            color: #67D4E4;
        `;
        
        vrButton.addEventListener('mouseenter', () => {
            vrButton.style.background = 'rgba(103, 212, 228, 0.3)';
            vrButton.style.transform = 'scale(1.05)';
        });
        
        vrButton.addEventListener('mouseleave', () => {
            vrButton.style.background = 'rgba(103, 212, 228, 0.1)';
            vrButton.style.transform = 'scale(1)';
        });
        
        vrButton.addEventListener('click', async () => {
            if (kagamiXR.activeSession) {
                await kagamiXR.endSession();
                vrButton.textContent = 'ENTER VR';
            } else {
                await kagamiXR.startVR();
                vrButton.textContent = 'EXIT VR';
            }
        });
        
        buttonsDiv.appendChild(vrButton);
    }
    
    // AR Button
    if (kagamiXR.isARSupported) {
        const arButton = document.createElement('button');
        arButton.textContent = 'ENTER AR';
        arButton.style.cssText = buttonStyle + `
            background: rgba(255, 107, 53, 0.1);
            border-color: #FF6B35;
            color: #FF6B35;
        `;
        
        arButton.addEventListener('mouseenter', () => {
            arButton.style.background = 'rgba(255, 107, 53, 0.3)';
            arButton.style.transform = 'scale(1.05)';
        });
        
        arButton.addEventListener('mouseleave', () => {
            arButton.style.background = 'rgba(255, 107, 53, 0.1)';
            arButton.style.transform = 'scale(1)';
        });
        
        arButton.addEventListener('click', async () => {
            if (kagamiXR.activeSession) {
                await kagamiXR.endSession();
                arButton.textContent = 'ENTER AR';
            } else {
                await kagamiXR.startAR();
                arButton.textContent = 'EXIT AR';
            }
        });
        
        buttonsDiv.appendChild(arButton);
    }
    
    // No XR message
    if (!kagamiXR.isVRSupported && !kagamiXR.isARSupported) {
        const noXRMsg = document.createElement('div');
        noXRMsg.textContent = 'WebXR not available';
        noXRMsg.style.cssText = `
            color: #9E9994;
            font-family: 'Space Mono', monospace;
            font-size: 12px;
            padding: 8px 16px;
            border: 1px solid rgba(158, 153, 148, 0.3);
            border-radius: 4px;
        `;
        buttonsDiv.appendChild(noXRMsg);
    }
    
    (container || document.body).appendChild(buttonsDiv);
    
    return buttonsDiv;
}

// ═══════════════════════════════════════════════════════════════════════════
// SPATIAL AUDIO HELPER
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create a spatial audio source attached to a 3D object
 */
export function createSpatialAudio(listener, audioUrl, options = {}) {
    const sound = new THREE.PositionalAudio(listener);
    
    const audioLoader = new THREE.AudioLoader();
    audioLoader.load(audioUrl, (buffer) => {
        sound.setBuffer(buffer);
        sound.setRefDistance(options.refDistance || 1);
        sound.setRolloffFactor(options.rolloff || 1);
        sound.setDistanceModel(options.distanceModel || 'inverse');
        sound.setLoop(options.loop !== false);
        sound.setVolume(options.volume || 0.5);
        
        if (options.autoplay) {
            sound.play();
        }
    });
    
    return sound;
}

/**
 * Create an audio listener for the camera
 */
export function createAudioListener(camera) {
    const listener = new THREE.AudioListener();
    camera.add(listener);
    return listener;
}

// ═══════════════════════════════════════════════════════════════════════════
// TELEPORTATION HELPER
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Create a simple teleportation system
 */
export class TeleportationSystem {
    constructor(camera, scene, floor) {
        this.camera = camera;
        this.scene = scene;
        this.floor = floor;
        
        this.raycaster = new THREE.Raycaster();
        this.marker = this.createMarker();
        scene.add(this.marker);
        this.marker.visible = false;
        
        this.targetPosition = new THREE.Vector3();
    }
    
    createMarker() {
        const geometry = new THREE.RingGeometry(0.15, 0.2, 32);
        const material = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.8,
            side: THREE.DoubleSide
        });
        
        const ring = new THREE.Mesh(geometry, material);
        ring.rotation.x = -Math.PI / 2;
        
        return ring;
    }
    
    update(controller) {
        if (!controller) {
            this.marker.visible = false;
            return;
        }
        
        const tempMatrix = new THREE.Matrix4();
        tempMatrix.identity().extractRotation(controller.matrixWorld);
        
        this.raycaster.ray.origin.setFromMatrixPosition(controller.matrixWorld);
        this.raycaster.ray.direction.set(0, 0, -1).applyMatrix4(tempMatrix);
        
        const intersects = this.raycaster.intersectObject(this.floor);
        
        if (intersects.length > 0) {
            this.targetPosition.copy(intersects[0].point);
            this.marker.position.copy(this.targetPosition);
            this.marker.position.y += 0.01;
            this.marker.visible = true;
        } else {
            this.marker.visible = false;
        }
    }
    
    teleport(cameraRig) {
        if (this.marker.visible && cameraRig) {
            cameraRig.position.copy(this.targetPosition);
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORT
// ═══════════════════════════════════════════════════════════════════════════

export default {
    KagamiXR,
    createXRButtons,
    createSpatialAudio,
    createAudioListener,
    TeleportationSystem
};
