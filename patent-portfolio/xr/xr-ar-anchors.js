/**
 * XR AR Anchors
 * =============
 * 
 * AR hit testing and anchor placement for real-world surface detection.
 * Supports museum placement, scaling, and rotation in AR mode.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// CONSTANTS
// ═══════════════════════════════════════════════════════════════════════════

const AR_CONFIG = {
    // Reticle
    reticleSize: 0.15,
    reticleColor: 0x67D4E4,
    reticleColorActive: 0x00FF88,
    
    // Scale constraints
    minScale: 0.01,
    maxScale: 1.0,
    defaultScale: 0.1,
    
    // Placement
    placementAnimationDuration: 0.5
};

// ═══════════════════════════════════════════════════════════════════════════
// XR AR ANCHORS CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class XRARAnchos {
    constructor(scene, xrManager) {
        this.scene = scene;
        this.xrManager = xrManager;
        
        // State
        this.isPlacementMode = true;
        this.isPlaced = false;
        this.currentScale = AR_CONFIG.defaultScale;
        
        // Placed content
        this.contentGroup = null;
        this.anchor = null;
        
        // Visual components
        this.reticle = null;
        this.reticleVisible = false;
        
        // Touch state for gestures
        this.touchState = {
            startDistance: 0,
            startScale: 0,
            startRotation: 0,
            isPinching: false,
            isRotating: false
        };
        
        // Callbacks
        this.onPlace = null;
        this.onScale = null;
        this.onRotate = null;
        
        this.init();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    init() {
        this.createReticle();
        this.createContentGroup();
        this.setupTouchHandlers();
    }
    
    createReticle() {
        const group = new THREE.Group();
        group.name = 'ar-reticle';
        
        // Outer ring
        const outerRingGeo = new THREE.RingGeometry(
            AR_CONFIG.reticleSize * 0.8,
            AR_CONFIG.reticleSize,
            32
        );
        const outerRingMat = new THREE.MeshBasicMaterial({
            color: AR_CONFIG.reticleColor,
            transparent: true,
            opacity: 0.8,
            side: THREE.DoubleSide
        });
        const outerRing = new THREE.Mesh(outerRingGeo, outerRingMat);
        outerRing.rotation.x = -Math.PI / 2;
        group.add(outerRing);
        
        // Inner dot
        const dotGeo = new THREE.CircleGeometry(AR_CONFIG.reticleSize * 0.2, 16);
        const dotMat = new THREE.MeshBasicMaterial({
            color: AR_CONFIG.reticleColor,
            transparent: true,
            opacity: 0.6,
            side: THREE.DoubleSide
        });
        const dot = new THREE.Mesh(dotGeo, dotMat);
        dot.rotation.x = -Math.PI / 2;
        dot.position.y = 0.001;
        group.add(dot);
        
        // Crosshairs
        const crosshairMat = new THREE.LineBasicMaterial({
            color: AR_CONFIG.reticleColor,
            transparent: true,
            opacity: 0.5
        });
        
        // Horizontal line
        const hLineGeo = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(-AR_CONFIG.reticleSize * 1.5, 0, 0),
            new THREE.Vector3(-AR_CONFIG.reticleSize * 1.1, 0, 0)
        ]);
        const hLine = new THREE.Line(hLineGeo, crosshairMat);
        group.add(hLine);
        
        const hLine2Geo = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(AR_CONFIG.reticleSize * 1.1, 0, 0),
            new THREE.Vector3(AR_CONFIG.reticleSize * 1.5, 0, 0)
        ]);
        const hLine2 = new THREE.Line(hLine2Geo, crosshairMat);
        group.add(hLine2);
        
        // Vertical line
        const vLineGeo = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, -AR_CONFIG.reticleSize * 1.5),
            new THREE.Vector3(0, 0, -AR_CONFIG.reticleSize * 1.1)
        ]);
        const vLine = new THREE.Line(vLineGeo, crosshairMat);
        group.add(vLine);
        
        const vLine2Geo = new THREE.BufferGeometry().setFromPoints([
            new THREE.Vector3(0, 0, AR_CONFIG.reticleSize * 1.1),
            new THREE.Vector3(0, 0, AR_CONFIG.reticleSize * 1.5)
        ]);
        const vLine2 = new THREE.Line(vLine2Geo, crosshairMat);
        group.add(vLine2);
        
        this.reticle = group;
        this.reticle.visible = false;
        this.reticle.matrixAutoUpdate = false;
        this.scene.add(this.reticle);
    }
    
    createContentGroup() {
        this.contentGroup = new THREE.Group();
        this.contentGroup.name = 'ar-content';
        this.contentGroup.visible = false;
        this.scene.add(this.contentGroup);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // TOUCH HANDLERS FOR GESTURES
    // ═══════════════════════════════════════════════════════════════════════
    
    setupTouchHandlers() {
        // These will be connected to the DOM overlay in AR mode
        this.handleTouchStart = this.handleTouchStart.bind(this);
        this.handleTouchMove = this.handleTouchMove.bind(this);
        this.handleTouchEnd = this.handleTouchEnd.bind(this);
    }
    
    connectTouchEvents(element) {
        element.addEventListener('touchstart', this.handleTouchStart, { passive: false });
        element.addEventListener('touchmove', this.handleTouchMove, { passive: false });
        element.addEventListener('touchend', this.handleTouchEnd, { passive: false });
    }
    
    disconnectTouchEvents(element) {
        element.removeEventListener('touchstart', this.handleTouchStart);
        element.removeEventListener('touchmove', this.handleTouchMove);
        element.removeEventListener('touchend', this.handleTouchEnd);
    }
    
    handleTouchStart(event) {
        if (!this.isPlaced) {
            // Single tap to place
            if (event.touches.length === 1) {
                this.placeContent();
            }
            return;
        }
        
        // Two-finger gesture for scale/rotate
        if (event.touches.length === 2) {
            event.preventDefault();
            
            const touch1 = event.touches[0];
            const touch2 = event.touches[1];
            
            // Calculate initial distance for pinch-to-scale
            this.touchState.startDistance = this.getTouchDistance(touch1, touch2);
            this.touchState.startScale = this.currentScale;
            this.touchState.isPinching = true;
            
            // Calculate initial angle for rotation
            this.touchState.startRotation = this.getTouchAngle(touch1, touch2);
            this.touchState.startContentRotation = this.contentGroup.rotation.y;
            this.touchState.isRotating = true;
        }
    }
    
    handleTouchMove(event) {
        if (!this.isPlaced) return;
        
        if (event.touches.length === 2 && (this.touchState.isPinching || this.touchState.isRotating)) {
            event.preventDefault();
            
            const touch1 = event.touches[0];
            const touch2 = event.touches[1];
            
            // Pinch-to-scale
            if (this.touchState.isPinching) {
                const currentDistance = this.getTouchDistance(touch1, touch2);
                const scaleFactor = currentDistance / this.touchState.startDistance;
                let newScale = this.touchState.startScale * scaleFactor;
                
                // Clamp scale
                newScale = Math.max(AR_CONFIG.minScale, Math.min(AR_CONFIG.maxScale, newScale));
                
                this.setScale(newScale);
            }
            
            // Two-finger rotation
            if (this.touchState.isRotating) {
                const currentAngle = this.getTouchAngle(touch1, touch2);
                const angleDelta = currentAngle - this.touchState.startRotation;
                
                this.contentGroup.rotation.y = this.touchState.startContentRotation + angleDelta;
                
                if (this.onRotate) {
                    this.onRotate(this.contentGroup.rotation.y);
                }
            }
        }
    }
    
    handleTouchEnd(event) {
        if (event.touches.length < 2) {
            this.touchState.isPinching = false;
            this.touchState.isRotating = false;
        }
    }
    
    getTouchDistance(touch1, touch2) {
        const dx = touch1.clientX - touch2.clientX;
        const dy = touch1.clientY - touch2.clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }
    
    getTouchAngle(touch1, touch2) {
        return Math.atan2(
            touch2.clientY - touch1.clientY,
            touch2.clientX - touch1.clientX
        );
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PLACEMENT
    // ═══════════════════════════════════════════════════════════════════════
    
    placeContent() {
        if (!this.reticleVisible || !this.reticle.visible) {
            console.log('Cannot place: no valid surface detected');
            return false;
        }
        
        // Copy reticle position to content
        this.contentGroup.position.copy(this.reticle.position);
        this.contentGroup.quaternion.copy(this.reticle.quaternion);
        this.contentGroup.visible = true;
        
        // Apply scale
        this.setScale(this.currentScale);
        
        // Create anchor if supported
        this.createAnchor();
        
        this.isPlaced = true;
        this.isPlacementMode = false;
        
        // Hide reticle
        this.reticle.visible = false;
        
        // Update reticle color to indicate placement
        this.setReticleColor(AR_CONFIG.reticleColorActive);
        
        // Animate placement
        this.animatePlacement();
        
        if (this.onPlace) {
            this.onPlace(this.contentGroup.position.clone());
        }
        
        console.log('Content placed at:', this.contentGroup.position);
        return true;
    }
    
    async createAnchor() {
        if (!this.xrManager.session || !this.xrManager.hasFeature('anchors')) {
            return;
        }
        
        try {
            // Create anchor at current position
            const pose = new XRRigidTransform(
                { 
                    x: this.contentGroup.position.x,
                    y: this.contentGroup.position.y,
                    z: this.contentGroup.position.z
                },
                { x: 0, y: 0, z: 0, w: 1 }
            );
            
            this.anchor = await this.xrManager.session.createAnchor(
                pose,
                this.xrManager.referenceSpace
            );
            
            console.log('AR anchor created');
        } catch (error) {
            console.warn('Could not create anchor:', error);
        }
    }
    
    animatePlacement() {
        // Simple scale-up animation
        const targetScale = this.currentScale;
        this.contentGroup.scale.setScalar(0.01);
        
        const startTime = performance.now();
        const duration = AR_CONFIG.placementAnimationDuration * 1000;
        
        const animate = () => {
            const elapsed = performance.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            
            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const scale = 0.01 + (targetScale - 0.01) * eased;
            
            this.contentGroup.scale.setScalar(scale);
            
            if (progress < 1) {
                requestAnimationFrame(animate);
            }
        };
        
        animate();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SCALE CONTROL
    // ═══════════════════════════════════════════════════════════════════════
    
    setScale(scale) {
        this.currentScale = Math.max(AR_CONFIG.minScale, Math.min(AR_CONFIG.maxScale, scale));
        
        if (this.contentGroup) {
            this.contentGroup.scale.setScalar(this.currentScale);
        }
        
        if (this.onScale) {
            this.onScale(this.currentScale);
        }
    }
    
    getScale() {
        return this.currentScale;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CONTENT MANAGEMENT
    // ═══════════════════════════════════════════════════════════════════════
    
    setContent(object) {
        // Clear existing content
        while (this.contentGroup.children.length > 0) {
            this.contentGroup.remove(this.contentGroup.children[0]);
        }
        
        // Add new content
        this.contentGroup.add(object);
    }
    
    getContentGroup() {
        return this.contentGroup;
    }
    
    reset() {
        this.isPlaced = false;
        this.isPlacementMode = true;
        this.contentGroup.visible = false;
        this.reticle.visible = true;
        this.setReticleColor(AR_CONFIG.reticleColor);
        
        if (this.anchor) {
            this.anchor.delete();
            this.anchor = null;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // RETICLE CONTROL
    // ═══════════════════════════════════════════════════════════════════════
    
    setReticleColor(color) {
        this.reticle.traverse(child => {
            if (child.material) {
                child.material.color.setHex(color);
            }
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UPDATE LOOP
    // ═══════════════════════════════════════════════════════════════════════
    
    update(time, frame) {
        if (!this.xrManager.isPresenting || this.xrManager.sessionType !== 'ar') {
            return;
        }
        
        // Update reticle position from hit test
        if (this.isPlacementMode && !this.isPlaced) {
            const hitPose = this.xrManager.getHitPose();
            
            if (hitPose) {
                this.reticle.visible = true;
                this.reticleVisible = true;
                
                // Update reticle transform
                this.reticle.matrix.fromArray(hitPose.transform.matrix);
                
                // Animate reticle
                this.animateReticle(time);
            } else {
                this.reticle.visible = false;
                this.reticleVisible = false;
            }
        }
        
        // Update anchor position if available
        if (this.isPlaced && this.anchor && frame) {
            const anchorPose = frame.getPose(this.anchor.anchorSpace, this.xrManager.referenceSpace);
            if (anchorPose) {
                this.contentGroup.matrix.fromArray(anchorPose.transform.matrix);
                this.contentGroup.matrix.decompose(
                    this.contentGroup.position,
                    this.contentGroup.quaternion,
                    new THREE.Vector3() // We manage scale separately
                );
                this.contentGroup.scale.setScalar(this.currentScale);
            }
        }
    }
    
    animateReticle(time) {
        // Pulse animation
        const pulse = 0.9 + Math.sin(time * 3) * 0.1;
        this.reticle.scale.setScalar(pulse);
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
        
        if (this.contentGroup) {
            this.scene.remove(this.contentGroup);
        }
        
        if (this.anchor) {
            this.anchor.delete();
        }
    }
}

export default XRARAnchos;
