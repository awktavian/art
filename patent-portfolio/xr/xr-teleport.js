/**
 * XR Teleport
 * ===========
 * 
 * VR teleportation system with parabolic arc visualization,
 * landing marker, and boundary constraints.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

const TELEPORT_CONFIG = {
    // Arc physics
    gravity: -9.8,
    initialVelocity: 8,
    arcSegments: 30,
    maxDistance: 15,
    
    // Visual
    arcColor: 0x67D4E4,
    arcColorInvalid: 0xFF4444,
    arcWidth: 0.02,
    markerRadius: 0.3,
    markerRingCount: 3,
    
    // Floor detection
    floorY: 0,
    floorTolerance: 0.5,
    
    // Bounds
    minX: -100,
    maxX: 100,
    minZ: -100,
    maxZ: 100
};

// ═══════════════════════════════════════════════════════════════════════════
// XR TELEPORT CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class XRTeleport {
    constructor(scene, camera, xrControllers) {
        this.scene = scene;
        this.camera = camera;
        this.xrControllers = xrControllers;
        
        // State
        this.isAiming = false;
        this.aimingHand = null;
        this.targetPosition = new THREE.Vector3();
        this.isValidTarget = false;
        
        // Visual components
        this.arc = null;
        this.marker = null;
        
        // Raycaster for floor detection
        this.raycaster = new THREE.Raycaster();
        this.floorObjects = [];
        
        // Temp vectors
        this.tempVector = new THREE.Vector3();
        this.tempDirection = new THREE.Vector3();
        
        // Callbacks
        this.onTeleport = null;
        this.canTeleportTo = null; // Optional validation function
        
        this.init();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    init() {
        this.createArc();
        this.createMarker();
        this.setupControllerEvents();
    }
    
    createArc() {
        // Create line geometry for the arc
        const positions = new Float32Array(TELEPORT_CONFIG.arcSegments * 3);
        const colors = new Float32Array(TELEPORT_CONFIG.arcSegments * 3);
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const material = new THREE.LineBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending,
            linewidth: 2
        });
        
        this.arc = new THREE.Line(geometry, material);
        this.arc.visible = false;
        this.arc.name = 'teleport-arc';
        this.scene.add(this.arc);
    }
    
    createMarker() {
        const group = new THREE.Group();
        group.name = 'teleport-marker';
        
        // Central disc
        const discGeo = new THREE.CircleGeometry(TELEPORT_CONFIG.markerRadius, 32);
        const discMat = new THREE.MeshBasicMaterial({
            color: TELEPORT_CONFIG.arcColor,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        const disc = new THREE.Mesh(discGeo, discMat);
        disc.rotation.x = -Math.PI / 2;
        group.add(disc);
        
        // Concentric rings
        for (let i = 0; i < TELEPORT_CONFIG.markerRingCount; i++) {
            const radius = TELEPORT_CONFIG.markerRadius * (0.4 + i * 0.3);
            const ringGeo = new THREE.RingGeometry(radius - 0.02, radius, 32);
            const ringMat = new THREE.MeshBasicMaterial({
                color: TELEPORT_CONFIG.arcColor,
                transparent: true,
                opacity: 0.6 - i * 0.15,
                side: THREE.DoubleSide
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = -Math.PI / 2;
            ring.position.y = 0.01 + i * 0.005;
            ring.userData.ringIndex = i;
            group.add(ring);
        }
        
        // Direction indicator (arrow)
        const arrowGeo = new THREE.ConeGeometry(0.08, 0.2, 8);
        const arrowMat = new THREE.MeshBasicMaterial({
            color: TELEPORT_CONFIG.arcColor,
            transparent: true,
            opacity: 0.7
        });
        const arrow = new THREE.Mesh(arrowGeo, arrowMat);
        arrow.rotation.x = -Math.PI / 2;
        arrow.position.set(0, 0.02, TELEPORT_CONFIG.markerRadius * 0.6);
        group.add(arrow);
        
        this.marker = group;
        this.marker.visible = false;
        this.scene.add(this.marker);
    }
    
    setupControllerEvents() {
        if (!this.xrControllers) return;
        
        // Use squeeze to aim teleport
        this.xrControllers.onSqueezeStart = (hand) => {
            this.startAiming(hand);
        };
        
        this.xrControllers.onSqueezeEnd = (hand) => {
            if (this.isAiming && this.aimingHand === hand) {
                this.executeTeleport();
            }
        };
        
        // Also support thumbstick click for teleport
        const originalThumbstick = this.xrControllers.onThumbstick;
        this.xrControllers.onThumbstick = (hand, values) => {
            if (originalThumbstick) {
                originalThumbstick(hand, values);
            }
            
            // Thumbstick forward to aim
            if (values.y < -0.8 && !this.isAiming) {
                this.startAiming(hand);
            } else if (values.y > -0.3 && this.isAiming && this.aimingHand === hand) {
                this.executeTeleport();
            }
        };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FLOOR MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════════
    
    setFloorObjects(objects) {
        this.floorObjects = objects;
    }
    
    addFloorObject(object) {
        if (!this.floorObjects.includes(object)) {
            this.floorObjects.push(object);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // TELEPORT AIMING
    // ═══════════════════════════════════════════════════════════════════════
    
    startAiming(hand) {
        this.isAiming = true;
        this.aimingHand = hand;
        this.arc.visible = true;
        this.marker.visible = true;
    }
    
    stopAiming() {
        this.isAiming = false;
        this.aimingHand = null;
        this.arc.visible = false;
        this.marker.visible = false;
        this.isValidTarget = false;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ARC CALCULATION
    // ═══════════════════════════════════════════════════════════════════════
    
    calculateArc(controllerPosition, controllerDirection) {
        const positions = this.arc.geometry.attributes.position.array;
        const colors = this.arc.geometry.attributes.color.array;
        
        const { gravity, initialVelocity, arcSegments, maxDistance } = TELEPORT_CONFIG;
        
        // Calculate initial velocity vector
        const velocity = controllerDirection.clone().multiplyScalar(initialVelocity);
        const position = controllerPosition.clone();
        
        // Time step
        const totalTime = (2 * initialVelocity) / Math.abs(gravity);
        const dt = totalTime / arcSegments;
        
        let hitPoint = null;
        let hitIndex = arcSegments - 1;
        
        // Calculate arc points
        for (let i = 0; i < arcSegments; i++) {
            const t = i * dt;
            
            // Calculate position at time t
            const x = position.x + velocity.x * t;
            const y = position.y + velocity.y * t + 0.5 * gravity * t * t;
            const z = position.z + velocity.z * t;
            
            positions[i * 3] = x;
            positions[i * 3 + 1] = y;
            positions[i * 3 + 2] = z;
            
            // Check for floor intersection
            if (y <= TELEPORT_CONFIG.floorY + TELEPORT_CONFIG.floorTolerance && !hitPoint) {
                hitPoint = new THREE.Vector3(x, TELEPORT_CONFIG.floorY, z);
                hitIndex = i;
            }
            
            // Check max distance
            const distFromStart = new THREE.Vector3(x, 0, z).distanceTo(
                new THREE.Vector3(position.x, 0, position.z)
            );
            if (distFromStart > maxDistance && !hitPoint) {
                hitPoint = new THREE.Vector3(x, TELEPORT_CONFIG.floorY, z);
                hitIndex = i;
            }
        }
        
        // If no hit, use last point projected to floor
        if (!hitPoint) {
            hitPoint = new THREE.Vector3(
                positions[(arcSegments - 1) * 3],
                TELEPORT_CONFIG.floorY,
                positions[(arcSegments - 1) * 3 + 2]
            );
        }
        
        // Validate hit point
        this.isValidTarget = this.validateTarget(hitPoint);
        
        // Set colors based on validity
        const validColor = new THREE.Color(TELEPORT_CONFIG.arcColor);
        const invalidColor = new THREE.Color(TELEPORT_CONFIG.arcColorInvalid);
        const targetColor = this.isValidTarget ? validColor : invalidColor;
        
        for (let i = 0; i < arcSegments; i++) {
            const t = i / arcSegments;
            const fade = i > hitIndex ? 0 : 1 - t * 0.5;
            
            colors[i * 3] = targetColor.r * fade;
            colors[i * 3 + 1] = targetColor.g * fade;
            colors[i * 3 + 2] = targetColor.b * fade;
        }
        
        this.arc.geometry.attributes.position.needsUpdate = true;
        this.arc.geometry.attributes.color.needsUpdate = true;
        
        this.targetPosition.copy(hitPoint);
        
        return hitPoint;
    }
    
    validateTarget(position) {
        const { minX, maxX, minZ, maxZ } = TELEPORT_CONFIG;
        
        // Check bounds
        if (position.x < minX || position.x > maxX ||
            position.z < minZ || position.z > maxZ) {
            return false;
        }
        
        // Check floor intersection using raycast
        if (this.floorObjects.length > 0) {
            this.raycaster.set(
                new THREE.Vector3(position.x, position.y + 2, position.z),
                new THREE.Vector3(0, -1, 0)
            );
            
            const intersections = this.raycaster.intersectObjects(this.floorObjects, true);
            if (intersections.length === 0) {
                return false;
            }
        }
        
        // Custom validation callback
        if (this.canTeleportTo) {
            return this.canTeleportTo(position);
        }
        
        return true;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // TELEPORT EXECUTION
    // ═══════════════════════════════════════════════════════════════════════
    
    executeTeleport() {
        if (!this.isAiming || !this.isValidTarget) {
            this.stopAiming();
            return;
        }
        
        const targetPosition = this.targetPosition.clone();
        
        // Notify before teleport
        if (this.onTeleport) {
            this.onTeleport(targetPosition);
        }
        
        // Execute teleport via XR reference space offset
        this.teleportToPosition(targetPosition);
        
        // Haptic feedback
        if (this.xrControllers && this.aimingHand) {
            this.xrControllers.pulseHaptic(this.aimingHand, 0.6, 150);
        }
        
        this.stopAiming();
    }
    
    teleportToPosition(position) {
        // In WebXR, we need to offset the reference space
        // This is a simplified implementation that moves the camera rig
        
        // Get current camera position on the XZ plane
        const cameraPos = new THREE.Vector3();
        this.camera.getWorldPosition(cameraPos);
        
        // Calculate offset
        const offset = new THREE.Vector3(
            position.x - cameraPos.x,
            0, // Keep Y the same (floor level)
            position.z - cameraPos.z
        );
        
        // If there's a camera rig/parent, move that instead
        if (this.camera.parent && this.camera.parent !== this.scene) {
            this.camera.parent.position.add(offset);
        } else {
            this.camera.position.add(offset);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UPDATE LOOP
    // ═══════════════════════════════════════════════════════════════════════
    
    update(time) {
        if (!this.isAiming || !this.aimingHand) return;
        
        // Get controller position and direction
        const controller = this.xrControllers?.getController(this.aimingHand);
        if (!controller) {
            this.stopAiming();
            return;
        }
        
        const position = new THREE.Vector3();
        const direction = new THREE.Vector3(0, 0, -1);
        
        controller.getWorldPosition(position);
        direction.applyQuaternion(controller.quaternion);
        
        // Point slightly downward for better arc
        direction.y -= 0.3;
        direction.normalize();
        
        // Calculate arc
        const hitPoint = this.calculateArc(position, direction);
        
        // Update marker
        if (hitPoint) {
            this.marker.position.copy(hitPoint);
            this.marker.position.y += 0.01;
            
            // Rotate marker to face camera
            const cameraPos = new THREE.Vector3();
            this.camera.getWorldPosition(cameraPos);
            this.marker.lookAt(cameraPos.x, this.marker.position.y, cameraPos.z);
            
            // Update marker color based on validity
            const color = this.isValidTarget ? TELEPORT_CONFIG.arcColor : TELEPORT_CONFIG.arcColorInvalid;
            this.marker.traverse(child => {
                if (child.material) {
                    child.material.color.setHex(color);
                }
            });
            
            // Animate rings
            this.animateMarker(time);
        }
    }
    
    animateMarker(time) {
        this.marker.children.forEach(child => {
            if (child.userData.ringIndex !== undefined) {
                const i = child.userData.ringIndex;
                const scale = 1 + Math.sin(time * 3 + i * 0.5) * 0.1;
                child.scale.setScalar(scale);
            }
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CLEANUP
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        if (this.arc) {
            this.arc.geometry.dispose();
            this.arc.material.dispose();
            this.scene.remove(this.arc);
        }
        
        if (this.marker) {
            this.marker.traverse(child => {
                if (child.geometry) child.geometry.dispose();
                if (child.material) child.material.dispose();
            });
            this.scene.remove(this.marker);
        }
    }
}

export default XRTeleport;
