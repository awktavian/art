/**
 * XR Controllers
 * ==============
 * 
 * VR controller and hand tracking input handling.
 * Supports both traditional controllers (Quest, Index) and
 * hand tracking (Vision Pro, Quest hand tracking).
 * 
 * Vision Pro uses eye tracking + hand pinch gestures.
 * Quest supports both controllers and hand tracking.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

const CONTROLLER_COLORS = {
    left: 0x4ECDC4,   // Flow (teal)
    right: 0xFF6B35   // Spark (orange)
};

const RAY_LENGTH = 10;
const RAY_WIDTH = 0.002;

// Hand joint indices (WebXR Hand Input)
// Full 25-joint hand model per WebXR spec
const HAND_JOINTS = {
    WRIST: 0,
    // Thumb (4 joints)
    THUMB_METACARPAL: 1,
    THUMB_PHALANX_PROXIMAL: 2,
    THUMB_PHALANX_DISTAL: 3,
    THUMB_TIP: 4,
    // Index finger (5 joints)
    INDEX_FINGER_METACARPAL: 5,
    INDEX_FINGER_PHALANX_PROXIMAL: 6,
    INDEX_FINGER_PHALANX_INTERMEDIATE: 7,  // PIP joint
    INDEX_FINGER_PHALANX_DISTAL: 8,
    INDEX_FINGER_TIP: 9,
    // Middle finger (5 joints)
    MIDDLE_FINGER_METACARPAL: 10,
    MIDDLE_FINGER_PHALANX_PROXIMAL: 11,
    MIDDLE_FINGER_PHALANX_INTERMEDIATE: 12,
    MIDDLE_FINGER_PHALANX_DISTAL: 13,
    MIDDLE_FINGER_TIP: 14,
    // Ring finger (5 joints)
    RING_FINGER_METACARPAL: 15,
    RING_FINGER_PHALANX_PROXIMAL: 16,
    RING_FINGER_PHALANX_INTERMEDIATE: 17,
    RING_FINGER_PHALANX_DISTAL: 18,
    RING_FINGER_TIP: 19,
    // Pinky finger (5 joints)
    PINKY_FINGER_METACARPAL: 20,
    PINKY_FINGER_PHALANX_PROXIMAL: 21,
    PINKY_FINGER_PHALANX_INTERMEDIATE: 22,
    PINKY_FINGER_PHALANX_DISTAL: 23,
    PINKY_FINGER_TIP: 24
};

// Gesture thresholds (meters)
const PINCH_THRESHOLD = 0.025;        // 2.5cm for pinch detection
const PINCH_THRESHOLD_ADAPTIVE_MIN = 0.015;  // 1.5cm (can be calibrated)
const PINCH_THRESHOLD_ADAPTIVE_MAX = 0.035;  // 3.5cm

// Gesture recognition config
const GESTURE_CONFIG = {
    // Pinch
    pinchThreshold: 0.025,
    
    // Point (extended index finger, others curled)
    pointIndexMinAngle: 150,      // degrees - index finger nearly straight
    pointOtherMaxAngle: 90,       // degrees - other fingers curled
    
    // Grab (all fingers curled)
    grabAngleThreshold: 80,       // degrees - all fingers bent this much
    
    // Swipe detection
    swipeMinDistance: 0.15,       // meters
    swipeMaxDuration: 500,        // ms
    swipeMinSpeed: 0.3,           // m/s
    
    // Calibration
    calibrationSamples: 10,       // samples for threshold calibration
}

// ═══════════════════════════════════════════════════════════════════════════
// XR CONTROLLERS CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class XRControllers {
    constructor(renderer, scene, xrManager) {
        this.renderer = renderer;
        this.scene = scene;
        this.xrManager = xrManager;
        
        // Controller instances
        this.controllers = {
            left: null,
            right: null
        };
        
        // Controller grips (for hand models)
        this.grips = {
            left: null,
            right: null
        };
        
        // Controller state
        this.state = {
            left: this.createControllerState(),
            right: this.createControllerState()
        };
        
        // Ray visuals
        this.rays = {
            left: null,
            right: null
        };
        
        // Hand tracking (Vision Pro, Quest hand tracking)
        this.hands = {
            left: null,
            right: null
        };
        this.handModels = {
            left: null,
            right: null
        };
        this.handState = {
            left: this.createHandState(),
            right: this.createHandState()
        };
        
        // Interaction callbacks
        this.onSelect = null;
        this.onSelectStart = null;
        this.onSelectEnd = null;
        this.onSqueeze = null;
        this.onSqueezeStart = null;
        this.onSqueezeEnd = null;
        this.onThumbstick = null;
        
        // Raycasting
        this.raycaster = new THREE.Raycaster();
        this.tempMatrix = new THREE.Matrix4();
        
        // Interactive objects
        this.interactiveObjects = [];
        this.hoveredObject = null;
        
        this.init();
    }
    
    createControllerState() {
        return {
            connected: false,
            selecting: false,
            squeezing: false,
            thumbstick: { x: 0, y: 0 },
            buttons: [],
            pose: null,
            gripPose: null,
            inputSource: null,
            isHandTracking: false
        };
    }
    
    createHandState() {
        return {
            connected: false,
            pinching: false,
            pinchStrength: 0,
            thumbTip: new THREE.Vector3(),
            indexTip: new THREE.Vector3(),
            wristPosition: new THREE.Vector3(),
            wristRotation: new THREE.Quaternion(),
            joints: new Map(),
            
            // Extended gesture recognition
            gestures: {
                pointing: false,
                grabbing: false,
                openPalm: false
            },
            
            // Swipe tracking
            swipe: {
                tracking: false,
                startPosition: new THREE.Vector3(),
                startTime: 0,
                direction: null  // 'left', 'right', 'up', 'down'
            },
            
            // Calibration
            calibration: {
                pinchSamples: [],
                calibratedThreshold: GESTURE_CONFIG.pinchThreshold
            }
        };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    init() {
        // Create controllers for both hands
        this.setupController(0); // Usually right
        this.setupController(1); // Usually left
        
        // Set up hand tracking (for Vision Pro, Quest hand tracking mode)
        this.setupHandTracking();
    }
    
    setupHandTracking() {
        // Hand tracking is detected when an XRInputSource with hand property connects
        // Set up hand models that will be shown when hand tracking is active
        
        ['left', 'right'].forEach(handedness => {
            const handModel = this.createHandModel(handedness);
            handModel.visible = false;
            this.handModels[handedness] = handModel;
            this.scene.add(handModel);
        });
    }
    
    createHandModel(handedness) {
        const group = new THREE.Group();
        group.name = `hand-model-${handedness}`;
        
        const color = CONTROLLER_COLORS[handedness];
        
        // Create spheres for each joint (25 joints per hand)
        const jointGeo = new THREE.SphereGeometry(0.006, 8, 8);
        const jointMat = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.7
        });
        
        // Store joints by index
        group.userData.joints = [];
        
        for (let i = 0; i < 25; i++) {
            const joint = new THREE.Mesh(jointGeo, jointMat.clone());
            joint.name = `joint-${i}`;
            group.userData.joints.push(joint);
            group.add(joint);
        }
        
        // Finger tip highlights (larger spheres for tips)
        const tipIndices = [
            HAND_JOINTS.THUMB_TIP,
            HAND_JOINTS.INDEX_FINGER_TIP,
            HAND_JOINTS.MIDDLE_FINGER_TIP,
            HAND_JOINTS.RING_FINGER_TIP,
            HAND_JOINTS.PINKY_FINGER_TIP
        ];
        
        tipIndices.forEach(idx => {
            if (group.userData.joints[idx]) {
                group.userData.joints[idx].scale.setScalar(1.5);
            }
        });
        
        // Pinch indicator (sphere between thumb and index)
        const pinchGeo = new THREE.SphereGeometry(0.01, 16, 16);
        const pinchMat = new THREE.MeshBasicMaterial({
            color: 0x00FF88,
            transparent: true,
            opacity: 0
        });
        const pinchIndicator = new THREE.Mesh(pinchGeo, pinchMat);
        pinchIndicator.name = 'pinch-indicator';
        group.userData.pinchIndicator = pinchIndicator;
        group.add(pinchIndicator);
        
        // Ray from index finger
        const rayGeo = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(0, 0, -RAY_LENGTH)
        ]);
        const rayMat = new THREE.LineBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.5,
            blending: THREE.AdditiveBlending
        });
        const ray = new THREE.Line(rayGeo, rayMat);
        ray.name = 'hand-ray';
        ray.visible = false;
        group.userData.ray = ray;
        group.add(ray);
        
        return group;
    }
    
    setupController(index) {
        const controller = this.renderer.xr.getController(index);
        const grip = this.renderer.xr.getControllerGrip(index);
        
        // Event listeners
        controller.addEventListener('connected', (e) => this.onConnected(index, e));
        controller.addEventListener('disconnected', (e) => this.onDisconnected(index, e));
        
        controller.addEventListener('selectstart', (e) => this.handleSelectStart(index, e));
        controller.addEventListener('selectend', (e) => this.handleSelectEnd(index, e));
        controller.addEventListener('select', (e) => this.handleSelect(index, e));
        
        controller.addEventListener('squeezestart', (e) => this.handleSqueezeStart(index, e));
        controller.addEventListener('squeezeend', (e) => this.handleSqueezeEnd(index, e));
        controller.addEventListener('squeeze', (e) => this.handleSqueeze(index, e));
        
        // Add ray visual
        const ray = this.createRay(index === 1 ? 'left' : 'right');
        controller.add(ray);
        
        // Add controller model (simple geometry for now)
        const model = this.createControllerModel(index === 1 ? 'left' : 'right');
        grip.add(model);
        
        // Add to scene
        this.scene.add(controller);
        this.scene.add(grip);
        
        // Store references
        const hand = index === 1 ? 'left' : 'right';
        this.controllers[hand] = controller;
        this.grips[hand] = grip;
        this.rays[hand] = ray;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // VISUAL COMPONENTS
    // ═══════════════════════════════════════════════════════════════════════
    
    createRay(hand) {
        const color = CONTROLLER_COLORS[hand];
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.Float32BufferAttribute([
            0, 0, 0,
            0, 0, -RAY_LENGTH
        ], 3));
        
        const material = new THREE.LineBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.6,
            blending: THREE.AdditiveBlending
        });
        
        const ray = new THREE.Line(geometry, material);
        ray.name = `${hand}-ray`;
        ray.visible = false; // Show when controller connects
        
        return ray;
    }
    
    createControllerModel(hand) {
        const color = CONTROLLER_COLORS[hand];
        
        const group = new THREE.Group();
        group.name = `${hand}-model`;
        
        // Simple controller body
        const bodyGeo = new THREE.CylinderGeometry(0.015, 0.02, 0.1, 8);
        const bodyMat = new THREE.MeshStandardMaterial({
            color: 0x333333,
            metalness: 0.8,
            roughness: 0.3
        });
        const body = new THREE.Mesh(bodyGeo, bodyMat);
        body.rotation.x = Math.PI / 2;
        body.position.z = -0.05;
        group.add(body);
        
        // Trigger
        const triggerGeo = new THREE.BoxGeometry(0.015, 0.02, 0.03);
        const triggerMat = new THREE.MeshStandardMaterial({
            color: color,
            emissive: color,
            emissiveIntensity: 0.3
        });
        const trigger = new THREE.Mesh(triggerGeo, triggerMat);
        trigger.position.set(0, -0.015, -0.03);
        trigger.name = 'trigger';
        group.add(trigger);
        
        // Thumbstick base
        const stickGeo = new THREE.CylinderGeometry(0.008, 0.008, 0.01, 8);
        const stickMat = new THREE.MeshStandardMaterial({
            color: 0x666666,
            metalness: 0.5,
            roughness: 0.5
        });
        const stick = new THREE.Mesh(stickGeo, stickMat);
        stick.position.set(0, 0.015, -0.04);
        stick.name = 'thumbstick';
        group.add(stick);
        
        return group;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CONNECTION EVENTS
    // ═══════════════════════════════════════════════════════════════════════
    
    onConnected(index, event) {
        const inputSource = event.data;
        const hand = inputSource.handedness || (index === 1 ? 'left' : 'right');
        
        // Check if this is hand tracking (Vision Pro, Quest hand tracking)
        const isHandTracking = !!inputSource.hand;
        
        if (isHandTracking) {
            console.log(`Hand tracking connected: ${hand}`, inputSource);
            this.hands[hand] = inputSource.hand;
            this.handState[hand].connected = true;
            this.state[hand].isHandTracking = true;
            
            // Show hand model, hide controller
            if (this.handModels[hand]) {
                this.handModels[hand].visible = true;
            }
            if (this.rays[hand]) {
                this.rays[hand].visible = false;
            }
            if (this.grips[hand]) {
                this.grips[hand].visible = false;
            }
        } else {
            console.log(`Controller connected: ${hand}`, inputSource);
            this.state[hand].isHandTracking = false;
            
            // Show controller, hide hand model
            if (this.handModels[hand]) {
                this.handModels[hand].visible = false;
            }
            if (this.rays[hand]) {
                this.rays[hand].visible = true;
            }
            if (this.grips[hand]) {
                this.grips[hand].visible = true;
            }
        }
        
        // Update state
        this.state[hand].connected = true;
        this.state[hand].inputSource = inputSource;
        
        // Update controller reference based on actual handedness
        if (hand === 'left' && index === 0) {
            // Swap if needed
            [this.controllers.left, this.controllers.right] = 
                [this.controllers.right, this.controllers.left];
        }
    }
    
    onDisconnected(index, event) {
        const hand = index === 1 ? 'left' : 'right';
        
        console.log(`Controller disconnected: ${hand}`);
        
        // Reset state
        this.state[hand] = this.createControllerState();
        
        // Hide ray
        if (this.rays[hand]) {
            this.rays[hand].visible = false;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INPUT EVENTS
    // ═══════════════════════════════════════════════════════════════════════
    
    handleSelectStart(index, event) {
        const hand = this.getHand(index, event);
        this.state[hand].selecting = true;
        
        const intersection = this.getIntersection(hand);
        
        if (this.onSelectStart) {
            this.onSelectStart(hand, intersection, event);
        }
        
        // Visual feedback
        this.pulseHaptic(hand, 0.3, 50);
    }
    
    handleSelectEnd(index, event) {
        const hand = this.getHand(index, event);
        this.state[hand].selecting = false;
        
        const intersection = this.getIntersection(hand);
        
        if (this.onSelectEnd) {
            this.onSelectEnd(hand, intersection, event);
        }
    }
    
    handleSelect(index, event) {
        const hand = this.getHand(index, event);
        const intersection = this.getIntersection(hand);
        
        if (this.onSelect) {
            this.onSelect(hand, intersection, event);
        }
        
        // Haptic feedback on successful selection
        if (intersection) {
            this.pulseHaptic(hand, 0.5, 100);
        }
    }
    
    handleSqueezeStart(index, event) {
        const hand = this.getHand(index, event);
        this.state[hand].squeezing = true;
        
        if (this.onSqueezeStart) {
            this.onSqueezeStart(hand, event);
        }
        
        this.pulseHaptic(hand, 0.2, 30);
    }
    
    handleSqueezeEnd(index, event) {
        const hand = this.getHand(index, event);
        this.state[hand].squeezing = false;
        
        if (this.onSqueezeEnd) {
            this.onSqueezeEnd(hand, event);
        }
    }
    
    handleSqueeze(index, event) {
        const hand = this.getHand(index, event);
        
        if (this.onSqueeze) {
            this.onSqueeze(hand, event);
        }
    }
    
    getHand(index, event) {
        const inputSource = event?.data || event?.inputSource;
        if (inputSource?.handedness) {
            return inputSource.handedness;
        }
        return index === 1 ? 'left' : 'right';
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // THUMBSTICK INPUT
    // ═══════════════════════════════════════════════════════════════════════
    
    updateThumbsticks() {
        ['left', 'right'].forEach(hand => {
            const state = this.state[hand];
            if (!state.connected || !state.inputSource) return;
            
            const gamepad = state.inputSource.gamepad;
            if (!gamepad) return;
            
            // Thumbstick is typically axes 2 and 3 on Quest controllers
            const axes = gamepad.axes;
            if (axes.length >= 4) {
                const newX = Math.abs(axes[2]) > 0.1 ? axes[2] : 0;
                const newY = Math.abs(axes[3]) > 0.1 ? axes[3] : 0;
                
                if (newX !== state.thumbstick.x || newY !== state.thumbstick.y) {
                    state.thumbstick.x = newX;
                    state.thumbstick.y = newY;
                    
                    if (this.onThumbstick && (newX !== 0 || newY !== 0)) {
                        this.onThumbstick(hand, state.thumbstick);
                    }
                }
            }
            
            // Store button states
            state.buttons = gamepad.buttons.map(b => ({
                pressed: b.pressed,
                touched: b.touched,
                value: b.value
            }));
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // RAYCASTING
    // ═══════════════════════════════════════════════════════════════════════
    
    setInteractiveObjects(objects) {
        this.interactiveObjects = objects;
    }
    
    addInteractiveObject(object) {
        if (!this.interactiveObjects.includes(object)) {
            this.interactiveObjects.push(object);
        }
    }
    
    removeInteractiveObject(object) {
        const index = this.interactiveObjects.indexOf(object);
        if (index > -1) {
            this.interactiveObjects.splice(index, 1);
        }
    }
    
    getIntersection(hand) {
        const controller = this.controllers[hand];
        if (!controller || this.interactiveObjects.length === 0) return null;
        
        // Set up raycaster from controller
        this.tempMatrix.identity().extractRotation(controller.matrixWorld);
        this.raycaster.ray.origin.setFromMatrixPosition(controller.matrixWorld);
        this.raycaster.ray.direction.set(0, 0, -1).applyMatrix4(this.tempMatrix);
        
        // Find intersections
        const intersections = this.raycaster.intersectObjects(this.interactiveObjects, true);
        
        if (intersections.length > 0) {
            return intersections[0];
        }
        
        return null;
    }
    
    updateHover() {
        let newHovered = null;
        
        ['left', 'right'].forEach(hand => {
            if (!this.state[hand].connected) return;
            
            const intersection = this.getIntersection(hand);
            if (intersection) {
                newHovered = intersection.object;
                
                // Update ray length to hit point
                const ray = this.rays[hand];
                if (ray) {
                    const positions = ray.geometry.attributes.position.array;
                    positions[5] = -intersection.distance;
                    ray.geometry.attributes.position.needsUpdate = true;
                }
            } else {
                // Reset ray length
                const ray = this.rays[hand];
                if (ray) {
                    const positions = ray.geometry.attributes.position.array;
                    positions[5] = -RAY_LENGTH;
                    ray.geometry.attributes.position.needsUpdate = true;
                }
            }
        });
        
        // Handle hover changes
        if (newHovered !== this.hoveredObject) {
            // Hover exit
            if (this.hoveredObject && this.hoveredObject.userData?.onHoverEnd) {
                this.hoveredObject.userData.onHoverEnd();
            }
            
            // Hover enter
            if (newHovered && newHovered.userData?.onHoverStart) {
                newHovered.userData.onHoverStart();
            }
            
            this.hoveredObject = newHovered;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // HAPTIC FEEDBACK
    // ═══════════════════════════════════════════════════════════════════════
    
    pulseHaptic(hand, intensity = 0.5, duration = 100) {
        const state = this.state[hand];
        if (!state.connected || !state.inputSource) return;
        
        const gamepad = state.inputSource.gamepad;
        if (!gamepad?.hapticActuators?.length) return;
        
        try {
            gamepad.hapticActuators[0].pulse(intensity, duration);
        } catch (e) {
            // Haptics not available
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UPDATE LOOP
    // ═══════════════════════════════════════════════════════════════════════
    
    update(time, frame) {
        this.updateThumbsticks();
        this.updateHover();
        
        // Update hand tracking
        if (frame) {
            this.updateHandTracking(frame);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // HAND TRACKING UPDATE
    // ═══════════════════════════════════════════════════════════════════════
    
    updateHandTracking(frame) {
        const referenceSpace = this.xrManager?.referenceSpace;
        if (!referenceSpace) return;
        
        ['left', 'right'].forEach(handedness => {
            const hand = this.hands[handedness];
            const handModel = this.handModels[handedness];
            const state = this.handState[handedness];
            
            if (!hand || !handModel || !state.connected) return;
            
            // Update joint positions
            const jointSpaces = hand.values ? Array.from(hand.values()) : [];
            
            jointSpaces.forEach((jointSpace, index) => {
                const pose = frame.getJointPose?.(jointSpace, referenceSpace);
                if (pose && handModel.userData.joints[index]) {
                    const joint = handModel.userData.joints[index];
                    joint.position.set(
                        pose.transform.position.x,
                        pose.transform.position.y,
                        pose.transform.position.z
                    );
                    joint.quaternion.set(
                        pose.transform.orientation.x,
                        pose.transform.orientation.y,
                        pose.transform.orientation.z,
                        pose.transform.orientation.w
                    );
                    
                    // Store key positions
                    if (index === HAND_JOINTS.THUMB_TIP) {
                        state.thumbTip.copy(joint.position);
                    } else if (index === HAND_JOINTS.INDEX_FINGER_TIP) {
                        state.indexTip.copy(joint.position);
                    } else if (index === HAND_JOINTS.WRIST) {
                        state.wristPosition.copy(joint.position);
                        state.wristRotation.copy(joint.quaternion);
                    }
                    
                    state.joints.set(index, {
                        position: joint.position.clone(),
                        rotation: joint.quaternion.clone()
                    });
                }
            });
            
            // Detect pinch gesture (with calibrated threshold)
            const pinchDistance = state.thumbTip.distanceTo(state.indexTip);
            const wasPinching = state.pinching;
            const threshold = state.calibration?.calibratedThreshold || GESTURE_CONFIG.pinchThreshold;
            state.pinching = pinchDistance < threshold;
            state.pinchStrength = Math.max(0, 1 - (pinchDistance / threshold));
            
            // Detect additional gestures
            this.detectGestures(handedness, state);
            
            // Update pinch indicator visual
            if (handModel.userData.pinchIndicator) {
                const indicator = handModel.userData.pinchIndicator;
                indicator.position.lerpVectors(state.thumbTip, state.indexTip, 0.5);
                indicator.material.opacity = state.pinchStrength * 0.8;
                indicator.scale.setScalar(0.5 + state.pinchStrength * 0.5);
                
                // Change color based on pinch state
                if (state.pinching) {
                    indicator.material.color.setHex(0x00FF88);
                } else {
                    indicator.material.color.setHex(CONTROLLER_COLORS[handedness]);
                }
            }
            
            // Update hand ray from index finger
            if (handModel.userData.ray && state.joints.has(HAND_JOINTS.INDEX_FINGER_TIP)) {
                const ray = handModel.userData.ray;
                const indexTip = state.indexTip;
                const indexBase = state.joints.get(HAND_JOINTS.INDEX_FINGER_METACARPAL)?.position;
                
                if (indexBase) {
                    ray.position.copy(indexTip);
                    ray.lookAt(
                        indexTip.x + (indexTip.x - indexBase.x) * 10,
                        indexTip.y + (indexTip.y - indexBase.y) * 10,
                        indexTip.z + (indexTip.z - indexBase.z) * 10
                    );
                    ray.visible = state.pinchStrength > 0.3;
                }
            }
            
            // Fire pinch events (like select)
            if (state.pinching && !wasPinching) {
                this.handlePinchStart(handedness);
            } else if (!state.pinching && wasPinching) {
                this.handlePinchEnd(handedness);
            }
        });
    }
    
    handlePinchStart(hand) {
        console.log(`Pinch start: ${hand}`);
        
        // Get intersection at pinch point
        const state = this.handState[hand];
        const intersection = this.getHandIntersection(hand);
        
        // Fire select callbacks
        if (this.onSelectStart) {
            this.onSelectStart(hand, intersection, { isHandTracking: true });
        }
        
        // Haptic feedback (if supported)
        // Note: Most hand tracking doesn't have haptics
    }
    
    handlePinchEnd(hand) {
        console.log(`Pinch end: ${hand}`);
        
        const intersection = this.getHandIntersection(hand);
        
        if (this.onSelectEnd) {
            this.onSelectEnd(hand, intersection, { isHandTracking: true });
        }
        
        if (this.onSelect) {
            this.onSelect(hand, intersection, { isHandTracking: true });
        }
    }
    
    getHandIntersection(hand) {
        const state = this.handState[hand];
        if (!state.connected || this.interactiveObjects.length === 0) return null;
        
        // Cast ray from index finger
        const indexTip = state.indexTip;
        const indexBase = state.joints.get(HAND_JOINTS.INDEX_FINGER_METACARPAL)?.position;
        
        if (!indexBase) return null;
        
        const direction = new THREE.Vector3()
            .subVectors(indexTip, indexBase)
            .normalize();
        
        this.raycaster.set(indexTip, direction);
        const intersections = this.raycaster.intersectObjects(this.interactiveObjects, true);
        
        return intersections.length > 0 ? intersections[0] : null;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // HAND TRACKING UTILITY
    // ═══════════════════════════════════════════════════════════════════════
    
    isHandTracking(hand) {
        return this.state[hand]?.isHandTracking || false;
    }
    
    isPinching(hand) {
        return this.handState[hand]?.pinching || false;
    }
    
    getPinchStrength(hand) {
        return this.handState[hand]?.pinchStrength || 0;
    }
    
    getHandJointPosition(hand, jointIndex) {
        return this.handState[hand]?.joints.get(jointIndex)?.position || null;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // GESTURE RECOGNITION
    // ═══════════════════════════════════════════════════════════════════════
    
    detectGestures(hand, state) {
        if (!state.gestures) return;
        
        // Get joint positions
        const indexTip = state.joints.get(HAND_JOINTS.INDEX_FINGER_TIP)?.position;
        const indexMid = state.joints.get(HAND_JOINTS.INDEX_FINGER_PHALANX_INTERMEDIATE)?.position;
        const indexBase = state.joints.get(HAND_JOINTS.INDEX_FINGER_METACARPAL)?.position;
        
        const middleTip = state.joints.get(HAND_JOINTS.MIDDLE_FINGER_TIP)?.position;
        const middleBase = state.joints.get(HAND_JOINTS.MIDDLE_FINGER_METACARPAL)?.position;
        
        const ringTip = state.joints.get(HAND_JOINTS.RING_FINGER_TIP)?.position;
        const ringBase = state.joints.get(HAND_JOINTS.RING_FINGER_METACARPAL)?.position;
        
        const pinkyTip = state.joints.get(HAND_JOINTS.PINKY_FINGER_TIP)?.position;
        const pinkyBase = state.joints.get(HAND_JOINTS.PINKY_FINGER_METACARPAL)?.position;
        
        const wrist = state.joints.get(HAND_JOINTS.WRIST)?.position;
        
        if (!indexTip || !middleTip || !wrist) return;
        
        // Calculate finger extension (distance from tip to base relative to wrist)
        const indexExtension = indexTip.distanceTo(indexBase) / (wrist.distanceTo(indexBase) + 0.001);
        const middleExtension = middleTip?.distanceTo(middleBase) / (wrist?.distanceTo(middleBase) + 0.001) || 0;
        const ringExtension = ringTip?.distanceTo(ringBase) / (wrist?.distanceTo(ringBase) + 0.001) || 0;
        const pinkyExtension = pinkyTip?.distanceTo(pinkyBase) / (wrist?.distanceTo(pinkyBase) + 0.001) || 0;
        
        // POINTING: Index extended, others curled
        const wasPointing = state.gestures.pointing;
        state.gestures.pointing = 
            indexExtension > 1.5 &&
            middleExtension < 1.2 &&
            ringExtension < 1.2 &&
            pinkyExtension < 1.2;
        
        if (state.gestures.pointing && !wasPointing) {
            console.log(`👆 Point gesture detected: ${hand}`);
            if (this.onPointStart) this.onPointStart(hand);
        } else if (!state.gestures.pointing && wasPointing) {
            if (this.onPointEnd) this.onPointEnd(hand);
        }
        
        // GRABBING: All fingers curled
        const wasGrabbing = state.gestures.grabbing;
        state.gestures.grabbing = 
            indexExtension < 1.0 &&
            middleExtension < 1.0 &&
            ringExtension < 1.0 &&
            pinkyExtension < 1.0;
        
        if (state.gestures.grabbing && !wasGrabbing) {
            console.log(`✊ Grab gesture detected: ${hand}`);
            if (this.onGrabStart) this.onGrabStart(hand);
        } else if (!state.gestures.grabbing && wasGrabbing) {
            if (this.onGrabEnd) this.onGrabEnd(hand);
        }
        
        // OPEN PALM: All fingers extended
        state.gestures.openPalm = 
            indexExtension > 1.5 &&
            middleExtension > 1.5 &&
            ringExtension > 1.3 &&
            pinkyExtension > 1.2;
        
        // Swipe detection (using index tip velocity)
        this.detectSwipe(hand, state);
    }
    
    detectSwipe(hand, state) {
        if (!state.swipe) return;
        
        const indexTip = state.indexTip;
        
        if (!state.swipe.tracking) {
            // Start tracking
            state.swipe.startPosition.copy(indexTip);
            state.swipe.startTime = performance.now();
            state.swipe.tracking = true;
        } else {
            const displacement = new THREE.Vector3().subVectors(indexTip, state.swipe.startPosition);
            const distance = displacement.length();
            const elapsed = performance.now() - state.swipe.startTime;
            
            // Check for swipe completion
            if (distance > GESTURE_CONFIG.swipeMinDistance && 
                elapsed < GESTURE_CONFIG.swipeMaxDuration) {
                
                const speed = distance / (elapsed / 1000);
                
                if (speed > GESTURE_CONFIG.swipeMinSpeed) {
                    // Determine swipe direction
                    let direction;
                    if (Math.abs(displacement.x) > Math.abs(displacement.y)) {
                        direction = displacement.x > 0 ? 'right' : 'left';
                    } else {
                        direction = displacement.y > 0 ? 'up' : 'down';
                    }
                    
                    console.log(`👋 Swipe ${direction} detected: ${hand}`);
                    if (this.onSwipe) {
                        this.onSwipe(hand, direction, { distance, speed, elapsed });
                    }
                    
                    // Reset tracking
                    state.swipe.tracking = false;
                }
            } else if (elapsed > GESTURE_CONFIG.swipeMaxDuration) {
                // Reset if too slow
                state.swipe.tracking = false;
            }
        }
    }
    
    // Calibrate pinch threshold based on user samples
    calibratePinchThreshold(hand) {
        const state = this.handState[hand];
        if (!state?.calibration) return;
        
        // Add current pinch distance to samples
        const currentDistance = state.thumbTip.distanceTo(state.indexTip);
        state.calibration.pinchSamples.push(currentDistance);
        
        // Keep only recent samples
        if (state.calibration.pinchSamples.length > GESTURE_CONFIG.calibrationSamples) {
            state.calibration.pinchSamples.shift();
        }
        
        // Calculate calibrated threshold (mean + 1 std dev)
        if (state.calibration.pinchSamples.length >= GESTURE_CONFIG.calibrationSamples) {
            const mean = state.calibration.pinchSamples.reduce((a, b) => a + b, 0) / 
                state.calibration.pinchSamples.length;
            
            const variance = state.calibration.pinchSamples.reduce((sum, val) => 
                sum + Math.pow(val - mean, 2), 0) / state.calibration.pinchSamples.length;
            const stdDev = Math.sqrt(variance);
            
            // Clamp to reasonable range
            state.calibration.calibratedThreshold = Math.max(
                PINCH_THRESHOLD_ADAPTIVE_MIN,
                Math.min(PINCH_THRESHOLD_ADAPTIVE_MAX, mean + stdDev * 0.5)
            );
            
            console.log(`Calibrated pinch threshold for ${hand}: ${state.calibration.calibratedThreshold.toFixed(4)}m`);
        }
    }
    
    // Get detected gestures
    getGestures(hand) {
        return this.handState[hand]?.gestures || null;
    }
    
    isPointing(hand) {
        return this.handState[hand]?.gestures?.pointing || false;
    }
    
    isGrabbing(hand) {
        return this.handState[hand]?.gestures?.grabbing || false;
    }
    
    isOpenPalm(hand) {
        return this.handState[hand]?.gestures?.openPalm || false;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UTILITY
    // ═══════════════════════════════════════════════════════════════════════
    
    getState(hand) {
        return this.state[hand];
    }
    
    getController(hand) {
        return this.controllers[hand];
    }
    
    getGrip(hand) {
        return this.grips[hand];
    }
    
    isConnected(hand) {
        return this.state[hand].connected;
    }
    
    isSelecting(hand) {
        return this.state[hand].selecting;
    }
    
    isSqueezing(hand) {
        return this.state[hand].squeezing;
    }
    
    getThumbstick(hand) {
        return this.state[hand].thumbstick;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CLEANUP
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        ['left', 'right'].forEach(hand => {
            if (this.controllers[hand]) {
                this.scene.remove(this.controllers[hand]);
            }
            if (this.grips[hand]) {
                this.scene.remove(this.grips[hand]);
            }
        });
    }
}

export default XRControllers;
