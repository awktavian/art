/**
 * XR Gaze Input
 * =============
 * 
 * Gaze-based interaction for Vision Pro and other eye-tracking XR devices.
 * Implements dwell-to-select pattern and gaze reticle visualization.
 * 
 * Vision Pro input model:
 * - Eye tracking provides gaze direction
 * - Pinch gesture confirms selection (handled by xr-controllers.js hand tracking)
 * - Dwell-to-select as fallback for accessibility
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

const GAZE_CONFIG = {
    // Dwell timing (adaptive based on user familiarity)
    dwellDuration: {
        initial: 1500,            // ms for new users
        familiar: 800,            // ms for experienced users
        expert: 500               // ms for power users
    },
    dwellCancelDistance: 0.1,     // m - movement that cancels dwell
    adaptiveThreshold: 10,        // selections before reducing dwell time
    
    // Reticle appearance
    reticleInnerRadius: 0.005,
    reticleOuterRadius: 0.02,
    reticleColor: 0x67D4E4,
    reticleHoverColor: 0x00FF88,
    reticleSelectColor: 0xFFD700,
    
    // Reticle fade (idle state)
    idleTimeout: 3000,            // ms before reticle starts fading
    fadeDuration: 1000,           // ms to fully fade
    idleOpacity: 0.2,             // minimum opacity when idle
    
    // Ray length
    rayLength: 50,
    
    // Smoothing
    smoothingFactor: 0.15,        // Lerp factor for smooth gaze movement
    
    // Gaze prediction (anticipation)
    predictionEnabled: true,
    predictionWeight: 0.1         // How much to weight velocity for prediction
};

// ═══════════════════════════════════════════════════════════════════════════
// XR GAZE CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class XRGaze {
    constructor(scene, camera, xrManager) {
        this.scene = scene;
        this.camera = camera;
        this.xrManager = xrManager;
        
        // State
        this.enabled = false;
        this.gazeOrigin = new THREE.Vector3();
        this.gazeDirection = new THREE.Vector3(0, 0, -1);
        this.smoothedDirection = new THREE.Vector3(0, 0, -1);
        
        // Dwell state
        this.dwellTarget = null;
        this.dwellStartTime = 0;
        this.dwellProgress = 0;
        this.isDwelling = false;
        
        // Hover state
        this.hoveredObject = null;
        this.lastHoverPosition = new THREE.Vector3();
        
        // Gaze prediction
        this.lastGazeDirection = new THREE.Vector3(0, 0, -1);
        this.gazeVelocity = new THREE.Vector3();
        
        // Adaptive dwell timing
        this.successfulSelections = 0;
        this.currentDwellDuration = GAZE_CONFIG.dwellDuration.initial;
        
        // Idle state (reticle fade)
        this.lastInteractionTime = 0;
        this.reticleOpacity = 1.0;
        
        // Eye tracking support
        this.hasEyeTracking = false;
        this.leftEyePose = null;
        this.rightEyePose = null;
        
        // Visual components
        this.reticle = null;
        this.reticleRing = null;
        this.dwellIndicator = null;
        
        // Raycasting
        this.raycaster = new THREE.Raycaster();
        this.raycaster.far = GAZE_CONFIG.rayLength;
        
        // Interactive objects
        this.interactiveObjects = [];
        
        // Callbacks
        this.onGazeSelect = null;
        this.onGazeHoverStart = null;
        this.onGazeHoverEnd = null;
        this.onDwellStart = null;
        this.onDwellComplete = null;
        
        this.init();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    init() {
        this.createReticle();
        this.createDwellIndicator();
    }
    
    createReticle() {
        const group = new THREE.Group();
        group.name = 'gaze-reticle';
        
        // Inner dot
        const dotGeo = new THREE.CircleGeometry(GAZE_CONFIG.reticleInnerRadius, 16);
        const dotMat = new THREE.MeshBasicMaterial({
            color: GAZE_CONFIG.reticleColor,
            transparent: true,
            opacity: 0.9,
            side: THREE.DoubleSide,
            depthTest: false
        });
        const dot = new THREE.Mesh(dotGeo, dotMat);
        dot.name = 'reticle-dot';
        group.add(dot);
        
        // Outer ring
        const ringGeo = new THREE.RingGeometry(
            GAZE_CONFIG.reticleOuterRadius * 0.7,
            GAZE_CONFIG.reticleOuterRadius,
            32
        );
        const ringMat = new THREE.MeshBasicMaterial({
            color: GAZE_CONFIG.reticleColor,
            transparent: true,
            opacity: 0.5,
            side: THREE.DoubleSide,
            depthTest: false
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.name = 'reticle-ring';
        this.reticleRing = ring;
        group.add(ring);
        
        // Scale based on distance (will be updated in update())
        group.renderOrder = 999;
        group.visible = false;
        
        this.reticle = group;
        this.scene.add(this.reticle);
    }
    
    createDwellIndicator() {
        // Circular progress indicator for dwell selection
        const segments = 64;
        const positions = new Float32Array((segments + 1) * 3);
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        
        const material = new THREE.LineBasicMaterial({
            color: GAZE_CONFIG.reticleSelectColor,
            transparent: true,
            opacity: 0.8,
            depthTest: false
        });
        
        this.dwellIndicator = new THREE.Line(geometry, material);
        this.dwellIndicator.name = 'dwell-indicator';
        this.dwellIndicator.visible = false;
        this.dwellIndicator.renderOrder = 1000;
        
        this.reticle.add(this.dwellIndicator);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ENABLE / DISABLE
    // ═══════════════════════════════════════════════════════════════════════
    
    enable() {
        this.enabled = true;
        if (this.reticle) {
            this.reticle.visible = true;
        }
    }
    
    disable() {
        this.enabled = false;
        if (this.reticle) {
            this.reticle.visible = false;
        }
        this.cancelDwell();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTIVE OBJECTS
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
    
    // ═══════════════════════════════════════════════════════════════════════
    // GAZE UPDATE
    // ═══════════════════════════════════════════════════════════════════════
    
    update(time, frame) {
        if (!this.enabled) return;
        
        // Get gaze direction
        this.updateGazeDirection(frame);
        
        // Smooth the gaze direction
        this.smoothedDirection.lerp(this.gazeDirection, GAZE_CONFIG.smoothingFactor);
        this.smoothedDirection.normalize();
        
        // Update raycaster
        this.raycaster.set(this.gazeOrigin, this.smoothedDirection);
        
        // Check for intersections
        const intersections = this.raycaster.intersectObjects(this.interactiveObjects, true);
        
        // Update hover state
        this.updateHoverState(intersections);
        
        // Update dwell timer
        this.updateDwell(time);
        
        // Update idle state (reticle fade)
        this.updateIdleState(time);
        
        // Update reticle position and appearance
        this.updateReticle(intersections);
    }
    
    updateGazeDirection(frame) {
        // Store previous direction for velocity calculation
        const prevDirection = this.lastGazeDirection.clone();
        
        // Try to get gaze from XR frame (true eye tracking via getEyePoses)
        if (frame && this.xrManager?.session) {
            // First try: True eye tracking (Vision Pro, Quest Pro, etc.)
            if (typeof frame.getEyePoses === 'function' && this.xrManager.referenceSpace) {
                try {
                    const eyePoses = frame.getEyePoses(this.xrManager.referenceSpace);
                    if (eyePoses && eyePoses.length > 0) {
                        this.hasEyeTracking = true;
                        
                        // Average left and right eye gaze for combined direction
                        if (eyePoses.length >= 2) {
                            const leftPose = eyePoses[0];
                            const rightPose = eyePoses[1];
                            
                            // Store for potential use
                            this.leftEyePose = leftPose;
                            this.rightEyePose = rightPose;
                            
                            // Gaze origin (midpoint between eyes)
                            this.gazeOrigin.set(
                                (leftPose.transform.position.x + rightPose.transform.position.x) / 2,
                                (leftPose.transform.position.y + rightPose.transform.position.y) / 2,
                                (leftPose.transform.position.z + rightPose.transform.position.z) / 2
                            );
                            
                            // Gaze direction (average of both eyes' forward vectors)
                            const leftQuat = new THREE.Quaternion().setFromRotationMatrix(
                                new THREE.Matrix4().fromArray(leftPose.transform.matrix)
                            );
                            const rightQuat = new THREE.Quaternion().setFromRotationMatrix(
                                new THREE.Matrix4().fromArray(rightPose.transform.matrix)
                            );
                            
                            const leftDir = new THREE.Vector3(0, 0, -1).applyQuaternion(leftQuat);
                            const rightDir = new THREE.Vector3(0, 0, -1).applyQuaternion(rightQuat);
                            
                            this.gazeDirection.copy(leftDir).add(rightDir).normalize();
                        } else {
                            // Single eye tracking
                            const eyePose = eyePoses[0];
                            this.gazeOrigin.set(
                                eyePose.transform.position.x,
                                eyePose.transform.position.y,
                                eyePose.transform.position.z
                            );
                            
                            const quat = new THREE.Quaternion().setFromRotationMatrix(
                                new THREE.Matrix4().fromArray(eyePose.transform.matrix)
                            );
                            this.gazeDirection.set(0, 0, -1).applyQuaternion(quat);
                        }
                    }
                } catch (e) {
                    // Eye tracking not available, fall back
                    this.hasEyeTracking = false;
                }
            }
            
            // Fallback: Use viewer pose (head direction)
            if (!this.hasEyeTracking) {
                const viewerPose = frame.getViewerPose?.(this.xrManager.referenceSpace);
                
                if (viewerPose && viewerPose.views.length > 0) {
                    const view = viewerPose.views[0];
                    const transform = view.transform;
                    
                    this.gazeOrigin.set(
                        transform.position.x,
                        transform.position.y,
                        transform.position.z
                    );
                    
                    const quat = new THREE.Quaternion(
                        transform.orientation.x,
                        transform.orientation.y,
                        transform.orientation.z,
                        transform.orientation.w
                    );
                    
                    this.gazeDirection.set(0, 0, -1);
                    this.gazeDirection.applyQuaternion(quat);
                }
            }
        } else {
            // Non-XR fallback to camera
            this.camera.getWorldPosition(this.gazeOrigin);
            this.camera.getWorldDirection(this.gazeDirection);
        }
        
        // Calculate gaze velocity for prediction
        this.gazeVelocity.subVectors(this.gazeDirection, prevDirection);
        this.lastGazeDirection.copy(this.gazeDirection);
        
        // Apply gaze prediction (anticipation)
        if (GAZE_CONFIG.predictionEnabled && this.gazeVelocity.length() > 0.001) {
            const predictedDir = this.gazeDirection.clone()
                .add(this.gazeVelocity.clone().multiplyScalar(GAZE_CONFIG.predictionWeight));
            predictedDir.normalize();
            this.gazeDirection.copy(predictedDir);
        }
    }
    
    updateHoverState(intersections) {
        const newHoveredObject = intersections.length > 0 ? intersections[0].object : null;
        
        if (newHoveredObject !== this.hoveredObject) {
            // Hover exit
            if (this.hoveredObject) {
                if (this.onGazeHoverEnd) {
                    this.onGazeHoverEnd(this.hoveredObject);
                }
                if (this.hoveredObject.userData?.onGazeHoverEnd) {
                    this.hoveredObject.userData.onGazeHoverEnd();
                }
                
                // Cancel dwell when leaving object
                this.cancelDwell();
            }
            
            // Hover enter
            if (newHoveredObject) {
                if (this.onGazeHoverStart) {
                    this.onGazeHoverStart(newHoveredObject);
                }
                if (newHoveredObject.userData?.onGazeHoverStart) {
                    newHoveredObject.userData.onGazeHoverStart();
                }
                
                // Start dwell timer
                this.startDwell(newHoveredObject);
            }
            
            this.hoveredObject = newHoveredObject;
        } else if (newHoveredObject && intersections[0]) {
            // Check if gaze moved too much (cancel dwell)
            const currentPos = intersections[0].point;
            if (currentPos.distanceTo(this.lastHoverPosition) > GAZE_CONFIG.dwellCancelDistance) {
                this.restartDwell();
            }
            this.lastHoverPosition.copy(currentPos);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DWELL SELECTION
    // ═══════════════════════════════════════════════════════════════════════
    
    startDwell(object) {
        if (!object.userData?.dwellSelectable && !object.userData?.interactive) {
            return;
        }
        
        this.dwellTarget = object;
        this.dwellStartTime = performance.now();
        this.isDwelling = true;
        
        if (this.onDwellStart) {
            this.onDwellStart(object);
        }
    }
    
    restartDwell() {
        if (this.dwellTarget) {
            this.dwellStartTime = performance.now();
            this.dwellProgress = 0;
        }
    }
    
    cancelDwell() {
        this.dwellTarget = null;
        this.dwellStartTime = 0;
        this.dwellProgress = 0;
        this.isDwelling = false;
        
        if (this.dwellIndicator) {
            this.dwellIndicator.visible = false;
        }
    }
    
    updateDwell(time) {
        if (!this.isDwelling || !this.dwellTarget) {
            this.dwellProgress = 0;
            return;
        }
        
        const elapsed = performance.now() - this.dwellStartTime;
        this.dwellProgress = Math.min(1, elapsed / this.currentDwellDuration);
        
        // Update dwell indicator
        this.updateDwellIndicator();
        
        // Check for completion
        if (this.dwellProgress >= 1) {
            this.completeDwell();
        }
    }
    
    // Update adaptive dwell timing based on user experience
    updateAdaptiveDwell() {
        this.successfulSelections++;
        
        // Gradually reduce dwell time as user becomes experienced
        if (this.successfulSelections >= GAZE_CONFIG.adaptiveThreshold * 2) {
            this.currentDwellDuration = GAZE_CONFIG.dwellDuration.expert;
        } else if (this.successfulSelections >= GAZE_CONFIG.adaptiveThreshold) {
            this.currentDwellDuration = GAZE_CONFIG.dwellDuration.familiar;
        }
        
        console.log(`Adaptive dwell: ${this.currentDwellDuration}ms after ${this.successfulSelections} selections`);
    }
    
    // Update reticle idle state (fade when not interacting)
    updateIdleState(time) {
        const now = performance.now();
        
        // Reset interaction time when hovering
        if (this.hoveredObject) {
            this.lastInteractionTime = now;
            this.reticleOpacity = 1.0;
        } else {
            // Calculate idle time
            const idleTime = now - this.lastInteractionTime;
            
            if (idleTime > GAZE_CONFIG.idleTimeout) {
                // Fade out
                const fadeProgress = Math.min(1, (idleTime - GAZE_CONFIG.idleTimeout) / GAZE_CONFIG.fadeDuration);
                this.reticleOpacity = 1.0 - fadeProgress * (1.0 - GAZE_CONFIG.idleOpacity);
            } else {
                this.reticleOpacity = 1.0;
            }
        }
        
        // Apply opacity to reticle
        if (this.reticle) {
            this.reticle.children.forEach(child => {
                if (child.material && child.name !== 'dwell-indicator') {
                    child.material.opacity = child.material.opacity * this.reticleOpacity / 
                        (child.material._baseOpacity || child.material.opacity);
                    child.material._baseOpacity = child.material._baseOpacity || child.material.opacity;
                }
            });
        }
    }
    
    updateDwellIndicator() {
        if (!this.dwellIndicator) return;
        
        this.dwellIndicator.visible = this.dwellProgress > 0;
        
        // Update circular progress
        const positions = this.dwellIndicator.geometry.attributes.position.array;
        const segments = 64;
        const radius = GAZE_CONFIG.reticleOuterRadius * 1.3;
        const progressSegments = Math.floor(segments * this.dwellProgress);
        
        for (let i = 0; i <= segments; i++) {
            const angle = (i / segments) * Math.PI * 2 - Math.PI / 2;
            const visible = i <= progressSegments;
            
            positions[i * 3] = visible ? Math.cos(angle) * radius : 0;
            positions[i * 3 + 1] = visible ? Math.sin(angle) * radius : 0;
            positions[i * 3 + 2] = 0;
        }
        
        this.dwellIndicator.geometry.attributes.position.needsUpdate = true;
    }
    
    completeDwell() {
        const target = this.dwellTarget;
        
        console.log('Dwell selection complete:', target);
        
        if (this.onDwellComplete) {
            this.onDwellComplete(target);
        }
        
        if (this.onGazeSelect) {
            this.onGazeSelect(target);
        }
        
        if (target.userData?.onGazeSelect) {
            target.userData.onGazeSelect();
        }
        
        // Visual feedback
        this.flashReticle();
        
        // Update adaptive dwell timing
        this.updateAdaptiveDwell();
        
        // Reset dwell
        this.cancelDwell();
    }
    
    flashReticle() {
        if (!this.reticleRing) return;
        
        const originalColor = this.reticleRing.material.color.clone();
        this.reticleRing.material.color.setHex(GAZE_CONFIG.reticleSelectColor);
        
        setTimeout(() => {
            this.reticleRing.material.color.copy(originalColor);
        }, 200);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // RETICLE UPDATE
    // ═══════════════════════════════════════════════════════════════════════
    
    updateReticle(intersections) {
        if (!this.reticle) return;
        
        let distance = 3; // Default distance
        let hitPoint = null;
        
        if (intersections.length > 0) {
            distance = intersections[0].distance;
            hitPoint = intersections[0].point;
            
            // Change reticle color when hovering interactive object
            const isInteractive = intersections[0].object.userData?.interactive;
            const color = isInteractive ? GAZE_CONFIG.reticleHoverColor : GAZE_CONFIG.reticleColor;
            
            this.reticle.children.forEach(child => {
                if (child.material) {
                    child.material.color.setHex(color);
                }
            });
        } else {
            // Default color
            this.reticle.children.forEach(child => {
                if (child.material && child.name !== 'dwell-indicator') {
                    child.material.color.setHex(GAZE_CONFIG.reticleColor);
                }
            });
        }
        
        // Position reticle
        if (hitPoint) {
            this.reticle.position.copy(hitPoint);
        } else {
            this.reticle.position.copy(this.gazeOrigin)
                .add(this.smoothedDirection.clone().multiplyScalar(distance));
        }
        
        // Make reticle face camera
        this.reticle.lookAt(this.gazeOrigin);
        
        // Scale reticle based on distance (constant screen size)
        const scale = distance * 0.03;
        this.reticle.scale.setScalar(scale);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // MANUAL SELECTION (triggered by pinch or click)
    // ═══════════════════════════════════════════════════════════════════════
    
    triggerSelect() {
        if (!this.hoveredObject) return;
        
        console.log('Gaze select (manual trigger):', this.hoveredObject);
        
        if (this.onGazeSelect) {
            this.onGazeSelect(this.hoveredObject);
        }
        
        if (this.hoveredObject.userData?.onGazeSelect) {
            this.hoveredObject.userData.onGazeSelect();
        }
        
        this.flashReticle();
        this.cancelDwell();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UTILITY
    // ═══════════════════════════════════════════════════════════════════════
    
    getHoveredObject() {
        return this.hoveredObject;
    }
    
    getDwellProgress() {
        return this.dwellProgress;
    }
    
    isEnabled() {
        return this.enabled;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CLEANUP
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        if (this.reticle) {
            this.reticle.traverse(child => {
                if (child.geometry) child.geometry.dispose();
                if (child.material) child.material.dispose();
            });
            this.scene.remove(this.reticle);
        }
    }
}

export default XRGaze;
