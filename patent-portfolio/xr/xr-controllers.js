/**
 * XR Controllers
 * ==============
 * 
 * VR controller input handling with pose tracking, button events,
 * haptic feedback, and visual representation.
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
            inputSource: null
        };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    init() {
        // Create controllers for both hands
        this.setupController(0); // Usually right
        this.setupController(1); // Usually left
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
        
        console.log(`Controller connected: ${hand}`, inputSource);
        
        // Update state
        this.state[hand].connected = true;
        this.state[hand].inputSource = inputSource;
        
        // Show ray
        if (this.rays[hand]) {
            this.rays[hand].visible = true;
        }
        
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
