/**
 * Museum Navigation System
 * ========================
 * 
 * First-person navigation with WASD/mouse controls,
 * teleportation, and VR locomotion support.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';

// ═══════════════════════════════════════════════════════════════════════════
// NAVIGATION CONTROLLER
// ═══════════════════════════════════════════════════════════════════════════

export class MuseumNavigation {
    constructor(camera, renderer, scene) {
        this.camera = camera;
        this.renderer = renderer;
        this.scene = scene;
        
        // Movement state
        this.moveForward = false;
        this.moveBackward = false;
        this.moveLeft = false;
        this.moveRight = false;
        this.moveUp = false;
        this.moveDown = false;
        this.canJump = true;
        
        // Debug state
        this.noclipEnabled = false;
        this.currentZone = 'vestibule';
        
        // Physics
        this.velocity = new THREE.Vector3();
        this.direction = new THREE.Vector3();
        this.playerHeight = 1.7; // meters
        this.moveSpeed = 100;
        this.friction = 10;
        
        // Cached vectors for performance (avoid allocations in update loop)
        this._forward = new THREE.Vector3();
        this._right = new THREE.Vector3();
        this._upVector = new THREE.Vector3(0, 1, 0);
        this._moveVector = new THREE.Vector3();
        this._rightSlide = new THREE.Vector3();
        this._leftSlide = new THREE.Vector3();
        this._collisionOrigin = new THREE.Vector3();
        this._collisionDir = new THREE.Vector3();
        
        // Collision
        this.raycaster = new THREE.Raycaster();
        this.collisionDistance = 0.5;
        
        // Controls
        this.controls = null;
        this.isLocked = false;
        
        // Teleport
        this.teleportMarker = null;
        this.teleportPoints = [];
        
        // Touch controls
        this.touchJoystick = null;
        this.touchLook = { x: 0, y: 0 };
        this.isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
        
        // Minimap
        this.minimapCamera = null;
        this.minimapRenderer = null;
        
        this.init();
    }
    
    init() {
        // Set initial position (closer to rotunda for better visibility)
        this.camera.position.set(0, this.playerHeight, -20);  // was -35, now -20
        this.camera.lookAt(0, this.playerHeight, 0);
        
        if (this.isMobile) {
            this.initTouchControls();
        } else {
            this.initPointerLockControls();
        }
        
        this.initTeleportSystem();
        this.initKeyboardControls();
        
        // Initialize collision detection
        this.initCollisionSystem();
        
        // Rebuild collision objects after a short delay to ensure scene is loaded
        setTimeout(() => this.rebuildCollisionObjects(), 500);
        
        // Create instructions overlay
        this.createInstructions();
        
        // Initialize gallery menu buttons
        this.initGalleryMenuButtons();
    }
    
    initGalleryMenuButtons() {
        // Wait for DOM to be ready
        const initButtons = () => {
            const wingButtons = document.querySelectorAll('.wing-button');
            const colonies = ['rotunda', 'spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];
            
            wingButtons.forEach(button => {
                const wing = button.dataset.wing;
                
                button.addEventListener('click', () => {
                    if (wing === 'rotunda') {
                        this.teleportToRotunda();
                    } else {
                        const index = colonies.indexOf(wing) - 1; // -1 because rotunda is index 0
                        if (index >= 0) {
                            this.teleportToWing(index);
                        }
                    }
                    
                    // Hide menu after teleport
                    this.hideGalleryMenu();
                });
            });
        };
        
        // Run immediately if DOM ready, otherwise wait
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', initButtons);
        } else {
            initButtons();
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // POINTER LOCK (Desktop)
    // ═══════════════════════════════════════════════════════════════════════
    
    initPointerLockControls() {
        try {
            this.controls = new PointerLockControls(this.camera, this.renderer.domElement);
            
            this.controls.addEventListener('lock', () => {
                console.log('🔒 Pointer lock acquired - WASD to move');
                this.isLocked = true;
                this.hideInstructions();
                // Reset movement state on lock
                this.moveForward = false;
                this.moveBackward = false;
                this.moveLeft = false;
                this.moveRight = false;
                this.velocity.set(0, 0, 0);
            });
            
            this.controls.addEventListener('unlock', () => {
                console.log('🔓 Pointer lock released - click to resume');
                this.isLocked = false;
                // Reset movement state on unlock
                this.moveForward = false;
                this.moveBackward = false;
                this.moveLeft = false;
                this.moveRight = false;
                this.velocity.set(0, 0, 0);
            });
            
            // Add error handler - enable navigation even if pointer lock fails
            document.addEventListener('pointerlockerror', () => {
                console.warn('⚠️ Pointer lock error - enabling keyboard navigation without mouse look');
                this.hideInstructions();
                this.isLocked = true;  // Enable keyboard movement at least
            });
            
            // Click to lock
            this.renderer.domElement.addEventListener('click', () => {
                if (!this.isLocked && this.controls) {
                    this.controls.lock();
                }
            });
            
            console.log('✅ Pointer lock controls initialized');
        } catch (err) {
            console.error('❌ Failed to initialize pointer lock:', err);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // TOUCH CONTROLS (Mobile)
    // ═══════════════════════════════════════════════════════════════════════
    
    initTouchControls() {
        // Create joystick container
        const joystickContainer = document.createElement('div');
        joystickContainer.id = 'joystick-container';
        joystickContainer.innerHTML = `
            <div id="joystick-base">
                <div id="joystick-stick"></div>
            </div>
        `;
        joystickContainer.style.cssText = `
            position: fixed;
            bottom: 40px;
            left: 40px;
            z-index: 1000;
            touch-action: none;
        `;
        document.body.appendChild(joystickContainer);
        
        const base = document.getElementById('joystick-base');
        const stick = document.getElementById('joystick-stick');
        
        base.style.cssText = `
            width: 120px;
            height: 120px;
            background: rgba(103, 212, 228, 0.2);
            border: 2px solid rgba(103, 212, 228, 0.5);
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        `;
        
        stick.style.cssText = `
            width: 50px;
            height: 50px;
            background: rgba(103, 212, 228, 0.8);
            border-radius: 50%;
            transition: transform 0.1s;
        `;
        
        // Joystick touch handling
        let joystickActive = false;
        let joystickOrigin = { x: 0, y: 0 };
        
        base.addEventListener('touchstart', (e) => {
            joystickActive = true;
            const touch = e.touches[0];
            const rect = base.getBoundingClientRect();
            joystickOrigin.x = rect.left + rect.width / 2;
            joystickOrigin.y = rect.top + rect.height / 2;
        });
        
        base.addEventListener('touchmove', (e) => {
            if (!joystickActive) return;
            e.preventDefault();
            
            const touch = e.touches[0];
            let dx = touch.clientX - joystickOrigin.x;
            let dy = touch.clientY - joystickOrigin.y;
            
            const maxDist = 40;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist > maxDist) {
                dx = (dx / dist) * maxDist;
                dy = (dy / dist) * maxDist;
            }
            
            stick.style.transform = `translate(${dx}px, ${dy}px)`;
            
            // Update movement
            this.moveForward = dy < -10;
            this.moveBackward = dy > 10;
            this.moveLeft = dx < -10;
            this.moveRight = dx > 10;
        });
        
        const endJoystick = () => {
            joystickActive = false;
            stick.style.transform = 'translate(0, 0)';
            this.moveForward = false;
            this.moveBackward = false;
            this.moveLeft = false;
            this.moveRight = false;
        };
        
        base.addEventListener('touchend', endJoystick);
        base.addEventListener('touchcancel', endJoystick);
        
        // Look controls (touch on main canvas)
        let lookActive = false;
        let lastTouch = { x: 0, y: 0 };
        
        this.renderer.domElement.addEventListener('touchstart', (e) => {
            if (e.touches.length === 1 && e.target === this.renderer.domElement) {
                lookActive = true;
                lastTouch.x = e.touches[0].clientX;
                lastTouch.y = e.touches[0].clientY;
            }
        });
        
        this.renderer.domElement.addEventListener('touchmove', (e) => {
            if (!lookActive) return;
            e.preventDefault();
            
            const touch = e.touches[0];
            const dx = touch.clientX - lastTouch.x;
            const dy = touch.clientY - lastTouch.y;
            
            // Rotate camera
            this.camera.rotation.y -= dx * 0.005;
            this.camera.rotation.x -= dy * 0.005;
            this.camera.rotation.x = Math.max(-Math.PI / 2, Math.min(Math.PI / 2, this.camera.rotation.x));
            
            lastTouch.x = touch.clientX;
            lastTouch.y = touch.clientY;
        });
        
        this.renderer.domElement.addEventListener('touchend', () => {
            lookActive = false;
        });
        
        this.isLocked = true; // Always "locked" on mobile
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // KEYBOARD CONTROLS
    // ═══════════════════════════════════════════════════════════════════════
    
    initKeyboardControls() {
        document.addEventListener('keydown', (e) => {
            switch (e.code) {
                case 'KeyW':
                case 'ArrowUp':
                    this.moveForward = true;
                    break;
                case 'KeyS':
                case 'ArrowDown':
                    this.moveBackward = true;
                    break;
                case 'KeyA':
                case 'ArrowLeft':
                    this.moveLeft = true;
                    break;
                case 'KeyD':
                case 'ArrowRight':
                    this.moveRight = true;
                    break;
                case 'Space':
                    if (this.noclipEnabled) {
                        this.moveUp = true;
                    } else if (this.canJump) {
                        this.velocity.y = 10;
                        this.canJump = false;
                    }
                    break;
                case 'ShiftLeft':
                case 'ShiftRight':
                    if (this.noclipEnabled) {
                        this.moveDown = true;
                    }
                    break;
                case 'Tab':
                    e.preventDefault();
                    this.showGalleryMenu();
                    break;
                case 'Digit1':
                case 'Digit2':
                case 'Digit3':
                case 'Digit4':
                case 'Digit5':
                case 'Digit6':
                case 'Digit7':
                    const wingIndex = parseInt(e.code.slice(-1)) - 1;
                    this.teleportToWing(wingIndex);
                    break;
                case 'Digit0':
                    this.teleportToRotunda();
                    break;
            }
        });
        
        document.addEventListener('keyup', (e) => {
            switch (e.code) {
                case 'KeyW':
                case 'ArrowUp':
                    this.moveForward = false;
                    break;
                case 'KeyS':
                case 'ArrowDown':
                    this.moveBackward = false;
                    break;
                case 'KeyA':
                case 'ArrowLeft':
                    this.moveLeft = false;
                    break;
                case 'KeyD':
                case 'ArrowRight':
                    this.moveRight = false;
                    break;
                case 'Space':
                    this.moveUp = false;
                    break;
                case 'ShiftLeft':
                case 'ShiftRight':
                    this.moveDown = false;
                    break;
            }
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // TELEPORTATION SYSTEM
    // ═══════════════════════════════════════════════════════════════════════
    
    initTeleportSystem() {
        // Create teleport marker (shown when pointing at floor)
        const markerGeo = new THREE.RingGeometry(0.3, 0.5, 32);
        const markerMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.7,
            side: THREE.DoubleSide
        });
        this.teleportMarker = new THREE.Mesh(markerGeo, markerMat);
        this.teleportMarker.rotation.x = -Math.PI / 2;
        this.teleportMarker.visible = false;
        this.scene.add(this.teleportMarker);
        
        // Define teleport points for each area
        this.teleportPoints = [
            { name: 'Vestibule', position: new THREE.Vector3(0, 0, -20) },
            { name: 'Rotunda Center', position: new THREE.Vector3(0, 0, 0) },
            { name: 'Spark Wing', position: new THREE.Vector3(0, 0, 35) },
            { name: 'Forge Wing', position: new THREE.Vector3(28, 0, 17) },
            { name: 'Flow Wing', position: new THREE.Vector3(28, 0, -17) },
            { name: 'Nexus Wing', position: new THREE.Vector3(-17, 0, 28) },
            { name: 'Beacon Wing', position: new THREE.Vector3(-28, 0, 0) },
            { name: 'Grove Wing', position: new THREE.Vector3(-17, 0, -28) },
            { name: 'Crystal Wing', position: new THREE.Vector3(0, 0, -20) }
        ];
    }
    
    teleportToWing(index) {
        const colonies = ['spark', 'forge', 'flow', 'nexus', 'beacon', 'grove', 'crystal'];
        const wingNames = ['Spark Wing', 'Forge Wing', 'Flow Wing', 'Nexus Wing', 'Beacon Wing', 'Grove Wing', 'Crystal Wing'];
        
        if (index >= 0 && index < colonies.length) {
            // Calculate wing entrance position
            const angle = (index / 7) * Math.PI * 2;
            const distance = 25;
            const x = Math.cos(angle) * distance;
            const z = Math.sin(angle) * distance;
            
            this.teleportTo(new THREE.Vector3(x, this.playerHeight, z), wingNames[index]);
        }
    }
    
    teleportToRotunda() {
        this.teleportTo(new THREE.Vector3(0, this.playerHeight, 0), 'Rotunda');
    }
    
    teleportTo(position, wingName = null) {
        // Enhanced teleport with warp effect
        const overlay = document.getElementById('teleport-overlay');
        
        if (overlay) {
            // Show destination preview if provided
            if (wingName) {
                this.showTeleportPreview(wingName);
            }
            
            // Add warp animation class
            overlay.classList.add('warping');
            overlay.style.opacity = '1';
            
            setTimeout(() => {
                this.camera.position.set(position.x, this.playerHeight, position.z);
                
                // Brief pause at destination
                setTimeout(() => {
                    overlay.classList.remove('warping');
                    overlay.style.opacity = '0';
                    this.hideTeleportPreview();
                }, 100);
            }, 250);
        } else {
            this.camera.position.set(position.x, this.playerHeight, position.z);
        }
    }
    
    showTeleportPreview(wingName) {
        let preview = document.getElementById('teleport-preview');
        if (!preview) {
            preview = document.createElement('div');
            preview.id = 'teleport-preview';
            preview.style.cssText = `
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-family: 'Orbitron', sans-serif;
                font-size: 32px;
                color: #67D4E4;
                text-transform: uppercase;
                letter-spacing: 0.2em;
                z-index: 3001;
                opacity: 0;
                transition: opacity 0.2s ease;
                text-shadow: 0 0 20px rgba(103, 212, 228, 0.8);
            `;
            document.body.appendChild(preview);
        }
        preview.textContent = wingName;
        requestAnimationFrame(() => {
            preview.style.opacity = '1';
        });
    }
    
    hideTeleportPreview() {
        const preview = document.getElementById('teleport-preview');
        if (preview) {
            preview.style.opacity = '0';
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // COLLISION SYSTEM
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Initialize collision detection system
     * Sets up collision parameters - objects will be collected after scene loads
     */
    initCollisionSystem() {
        this.collisionObjects = [];
        this.collisionMargin = 0.5; // Distance to keep from walls (increased for better feel)
        this.collisionRays = 8; // Number of rays to cast around player
        this._collisionEnabled = true; // Explicit flag — can be toggled by debug
        
        // Note: Don't call rebuildCollisionObjects() here - scene isn't populated yet
        // It will be called via setTimeout in init() and can be triggered manually
        // via forceRebuildCollision() after museum is fully loaded
    }
    
    /**
     * Rebuild collision object list from scene
     * Call this after loading new content
     */
    rebuildCollisionObjects() {
        this.collisionObjects = [];
        
        this.scene.traverse((object) => {
            // Skip non-mesh objects early
            if (!object.isMesh) return;
            
            // Skip floor/ceiling objects - we only need walls for horizontal collision
            const skipNames = ['floor', 'ceiling', 'skylight', 'inlay', 'pool', 'line'];
            const nameLower = (object.name || '').toLowerCase();
            if (skipNames.some(skip => nameLower.includes(skip))) {
                return;
            }
            
            // Check for explicit collidable flag or wall-type names
            const isCollidable = 
                object.userData?.collidable || 
                object.userData?.isWall ||
                nameLower.includes('wall') ||
                nameLower.includes('pillar') ||
                nameLower.includes('column') ||
                nameLower.includes('portal') ||
                nameLower.includes('pedestal') ||
                nameLower.includes('artwork') ||
                nameLower.includes('exhibit') ||
                nameLower.includes('kiosk');
            
            if (isCollidable) {
                this.collisionObjects.push(object);
            }
        });
        
        console.log(`Collision system: ${this.collisionObjects.length} collidable objects found`);
        
        // Debug: log object names
        if (this.collisionObjects.length > 0 && this.collisionObjects.length < 30) {
            console.log('  Walls:', this.collisionObjects.map(o => o.name).slice(0, 10).join(', '));
        }
    }
    
    /**
     * Public method to force rebuild collision objects
     * Call this from main application after museum is fully loaded
     */
    forceRebuildCollision() {
        this.rebuildCollisionObjects();
        this._rebuildFloorObjects();
        return this.collisionObjects.length;
    }
    
    /**
     * Check for collision in movement direction
     * Returns true if movement is blocked
     */
    checkCollision(moveDirection, distance) {
        if (!this.collisionObjects || this.collisionObjects.length === 0) return false;
        if (!moveDirection || distance <= 0) return false;
        
        // Set up raycaster at player position (reuse cached vector)
        this._collisionOrigin.copy(this.camera.position);
        this._collisionOrigin.y -= 0.5; // Cast from body center, not eyes
        
        // Normalize direction (reuse cached vector)
        this._collisionDir.copy(moveDirection).normalize();
        
        // Validate direction isn't NaN
        if (isNaN(this._collisionDir.x) || isNaN(this._collisionDir.z)) {
            return false;
        }
        
        this.raycaster.set(this._collisionOrigin, this._collisionDir);
        this.raycaster.far = distance + this.collisionMargin;
        
        // Check for intersections
        const intersections = this.raycaster.intersectObjects(this.collisionObjects, false);
        
        if (intersections.length > 0) {
            const closest = intersections[0];
            return closest.distance < (distance + this.collisionMargin);
        }
        
        return false;
    }
    
    /**
     * Calculate slide direction along wall
     * Returns adjusted movement vector that slides along obstacles
     */
    calculateSlideMovement(originalMove, blockedDirection) {
        // Project movement onto the plane perpendicular to blocked direction
        const dot = originalMove.dot(blockedDirection);
        const slideMove = originalMove.clone().sub(
            blockedDirection.clone().multiplyScalar(dot)
        );
        
        // Reduce slide speed slightly for more realistic feel
        slideMove.multiplyScalar(0.8);
        
        return slideMove;
    }
    
    /**
     * Find ground height at a given XZ position using raycasting
     * Returns 0 if no ground found (default floor level)
     */
    findGroundHeight(x, z) {
        // Use cached raycaster or create one
        if (!this._groundRaycaster) {
            this._groundRaycaster = new THREE.Raycaster();
            this._groundOrigin = new THREE.Vector3();
            this._groundDir = new THREE.Vector3(0, -1, 0);  // Straight down
        }

        // Cache floor objects (only rebuild when explicitly requested)
        if (!this._floorObjects) {
            this._rebuildFloorObjects();
        }

        // Cast ray from high above downward
        this._groundOrigin.set(x, 20, z);  // Start from ceiling
        this._groundRaycaster.set(this._groundOrigin, this._groundDir);
        this._groundRaycaster.far = 25;  // Max fall distance

        if (this._floorObjects.length === 0) {
            return 0;  // Default floor at Y=0
        }

        const intersections = this._groundRaycaster.intersectObjects(this._floorObjects, false);

        if (intersections.length > 0) {
            // Return the Y position of the highest floor below us
            return intersections[0].point.y;
        }

        return 0;  // Default floor at Y=0
    }

    /**
     * Rebuild cached floor objects list
     * Called lazily on first use and can be forced via forceRebuildCollision()
     */
    _rebuildFloorObjects() {
        this._floorObjects = [];
        this.scene.traverse((object) => {
            if (object.isMesh) {
                const nameLower = (object.name || '').toLowerCase();
                // Include floors, platforms, and any horizontal surfaces
                if (nameLower.includes('floor') ||
                    nameLower.includes('platform') ||
                    nameLower.includes('base') ||
                    nameLower.includes('ground') ||
                    object.rotation.x === -Math.PI / 2) {  // Horizontal planes
                    this._floorObjects.push(object);
                }
            }
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UPDATE LOOP
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        // Validate deltaTime
        if (!deltaTime || deltaTime <= 0 || deltaTime > 0.1) {
            deltaTime = 0.016; // Default to ~60fps
        }
        
        if (!this.isLocked && !this.isMobile) return;
        
        // NOCLIP MODE - Simple direct movement without physics or collision
        if (this.noclipEnabled) {
            const speed = 8 * deltaTime;
            if (this.moveForward) this.controls?.moveForward(speed);
            if (this.moveBackward) this.controls?.moveForward(-speed);
            if (this.moveLeft) this.controls?.moveRight(-speed);
            if (this.moveRight) this.controls?.moveRight(speed);
            // Allow vertical movement with Space/Shift in noclip
            if (this.moveUp) this.camera.position.y += speed;
            if (this.moveDown) this.camera.position.y -= speed;
            return;
        }
        
        // Apply friction
        this.velocity.x -= this.velocity.x * this.friction * deltaTime;
        this.velocity.z -= this.velocity.z * this.friction * deltaTime;
        
        // Calculate input direction (use local variable, NOT this.direction)
        const inputZ = Number(this.moveForward) - Number(this.moveBackward);
        const inputX = Number(this.moveRight) - Number(this.moveLeft);
        
        // Apply movement from keyboard input
        if (this.moveForward || this.moveBackward) {
            this.velocity.z -= inputZ * this.moveSpeed * deltaTime;
        }
        if (this.moveLeft || this.moveRight) {
            this.velocity.x -= inputX * this.moveSpeed * deltaTime;
        }
        
        // Gravity (gentle)
        this.velocity.y -= 20 * deltaTime;
        
        // Clamp velocity to prevent crazy speeds
        const maxVel = 15;
        this.velocity.x = Math.max(-maxVel, Math.min(maxVel, this.velocity.x));
        this.velocity.z = Math.max(-maxVel, Math.min(maxVel, this.velocity.z));
        
        // ─────────────────────────────────────────────────────────────────────
        // MOVEMENT APPLICATION
        // ─────────────────────────────────────────────────────────────────────
        
        // Calculate intended movement
        const moveX = -this.velocity.x * deltaTime;
        const moveZ = -this.velocity.z * deltaTime;
        
        // Get world-space movement direction (reuse cached vectors)
        this.camera.getWorldDirection(this._forward);
        this._forward.y = 0;
        if (this._forward.lengthSq() > 0.001) {
            this._forward.normalize();
        }
        
        this._right.crossVectors(this._forward, this._upVector);
        if (this._right.lengthSq() > 0.001) {
            this._right.normalize();
        }
        
        // Calculate total movement vector (reuse cached vector)
        this._moveVector.set(0, 0, 0);
        this._moveVector.addScaledVector(this._forward, moveZ);
        this._moveVector.addScaledVector(this._right, moveX);
        
        const moveDistance = this._moveVector.length();
        
        // Apply movement - ALWAYS use direct position updates for reliability
        if (moveDistance > 0.001) {
            // Skip collision if disabled or no objects
            const collisionEnabled = this.collisionObjects && 
                                    this.collisionObjects.length > 0 &&
                                    this._collisionEnabled !== false;
            
            if (collisionEnabled) {
                this._collisionDir.copy(this._moveVector).normalize();
                const hasCollision = this.checkCollision(this._collisionDir, moveDistance);
                
                if (!hasCollision) {
                    // No collision - direct position update
                    this.camera.position.addScaledVector(this._forward, moveZ);
                    this.camera.position.addScaledVector(this._right, moveX);
                } else {
                    // Wall sliding: project movement onto wall-parallel plane
                    const slideMove = this.calculateSlideMovement(this._moveVector, this._collisionDir);
                    const slideDistance = slideMove.length();
                    
                    if (slideDistance > 0.001) {
                        const slideDirNorm = slideMove.clone().normalize();
                        if (!this.checkCollision(slideDirNorm, slideDistance)) {
                            this.camera.position.add(slideMove);
                        }
                    }
                }
            } else {
                // No collision - direct position update
                this.camera.position.addScaledVector(this._forward, moveZ);
                this.camera.position.addScaledVector(this._right, moveX);
            }
        }
        
        // Apply vertical velocity (gravity was already applied at line 730)
        this.camera.position.y += this.velocity.y * deltaTime;
        
        // Ground raycast for proper floor detection
        const groundY = this.findGroundHeight(this.camera.position.x, this.camera.position.z);
        const targetY = groundY + this.playerHeight;
        
        // Floor collision - ALWAYS keep player above ground
        if (this.camera.position.y < targetY) {
            this.velocity.y = 0;
            this.camera.position.y = targetY;
            this.canJump = true;
        }
        
        // SAFETY: Never let Y go negative (absolute floor)
        if (this.camera.position.y < this.playerHeight) {
            this.velocity.y = 0;
            this.camera.position.y = this.playerHeight;
            this.canJump = true;
        }
        
        // Ceiling collision
        if (this.camera.position.y > 20) {
            this.velocity.y = 0;
            this.camera.position.y = 20;
        }
        
        // Simple boundary collision (keep inside museum)
        const maxDist = 100;  // Increased for larger museum
        const dist = Math.sqrt(
            this.camera.position.x ** 2 + 
            this.camera.position.z ** 2
        );
        if (dist > maxDist) {
            const scale = maxDist / dist;
            this.camera.position.x *= scale;
            this.camera.position.z *= scale;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UI HELPERS
    // ═══════════════════════════════════════════════════════════════════════
    
    createInstructions() {
        const instructions = document.createElement('div');
        instructions.id = 'navigation-instructions';
        instructions.innerHTML = `
            <div class="instructions-content">
                <h2>鏡 Patent Museum</h2>
                <p>Click to begin exploring</p>
                <div class="controls-grid">
                    <div><kbd>W</kbd><kbd>A</kbd><kbd>S</kbd><kbd>D</kbd> Move</div>
                    <div><kbd>Mouse</kbd> Look around</div>
                    <div><kbd>1</kbd>-<kbd>7</kbd> Teleport to wings</div>
                    <div><kbd>0</kbd> Return to rotunda</div>
                    <div><kbd>Tab</kbd> Gallery menu</div>
                    <div><kbd>Esc</kbd> Release mouse</div>
                </div>
            </div>
        `;
        instructions.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: linear-gradient(
                to bottom,
                rgba(7, 6, 11, 0.7) 0%,
                rgba(7, 6, 11, 0.5) 40%,
                rgba(7, 6, 11, 0.5) 60%,
                rgba(7, 6, 11, 0.7) 100%
            );
            backdrop-filter: blur(3px);
            -webkit-backdrop-filter: blur(3px);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 6000;
            cursor: pointer;
            transition: opacity 0.5s ease-out;
            pointer-events: auto;
        `;
        
        const style = document.createElement('style');
        style.textContent = `
            #navigation-instructions .instructions-content {
                text-align: center;
                color: #F5F0E8;
                font-family: 'IBM Plex Sans', sans-serif;
            }
            #navigation-instructions h2 {
                font-family: 'Orbitron', sans-serif;
                font-size: 48px;
                color: #67D4E4;
                margin-bottom: 20px;
            }
            #navigation-instructions p {
                font-size: 18px;
                color: #9E9994;
                margin-bottom: 40px;
            }
            #navigation-instructions .controls-grid {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 16px;
                max-width: 500px;
                margin: 0 auto;
                text-align: left;
            }
            #navigation-instructions kbd {
                display: inline-block;
                background: rgba(103, 212, 228, 0.2);
                border: 1px solid rgba(103, 212, 228, 0.5);
                border-radius: 4px;
                padding: 4px 8px;
                font-family: 'IBM Plex Mono', monospace;
                font-size: 12px;
                margin-right: 4px;
            }
            #teleport-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: radial-gradient(circle at center, #07060B 0%, #0D0A14 100%);
                pointer-events: none;
                opacity: 0;
                transition: opacity 0.25s ease;
                z-index: 3000;
            }
            
            #teleport-overlay.warping {
                background: radial-gradient(circle at center, 
                    rgba(103, 212, 228, 0.2) 0%, 
                    #07060B 30%, 
                    #0D0A14 100%);
                animation: warpPulse 0.35s ease-out;
            }
            
            @keyframes warpPulse {
                0% {
                    background: radial-gradient(circle at center, 
                        rgba(103, 212, 228, 0.5) 0%, 
                        #07060B 20%, 
                        #0D0A14 100%);
                }
                50% {
                    background: radial-gradient(circle at center, 
                        rgba(103, 212, 228, 0.3) 0%, 
                        rgba(103, 212, 228, 0.1) 40%, 
                        #07060B 60%, 
                        #0D0A14 100%);
                }
                100% {
                    background: radial-gradient(circle at center, 
                        rgba(103, 212, 228, 0.1) 0%, 
                        #07060B 30%, 
                        #0D0A14 100%);
                }
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(instructions);
        
        // Click handler to dismiss instructions and start exploring
        // CRITICAL: This MUST work regardless of pointer lock status
        const startExploring = () => {
            console.log('🚀 Starting exploration!');
            
            // 1. Hide the instructions overlay immediately
            instructions.style.opacity = '0';
            instructions.style.pointerEvents = 'none';
            setTimeout(() => {
                instructions.style.display = 'none';
            }, 300);
            
            // 2. Enable keyboard navigation (works without pointer lock)
            this.isLocked = true;
            
            // 3. Try pointer lock for mouse look (optional, may fail)
            if (!this.isMobile && this.controls) {
                try {
                    this.controls.lock();
                } catch (err) {
                    console.log('ℹ️ Pointer lock not available - using keyboard only');
                }
            }
            
            // 4. Initialize audio on user gesture
            this.initAudioOnGesture();
            
            console.log('✅ Navigation enabled - use WASD to move, 1-7 to teleport');
        };
        
        // Handle click
        instructions.addEventListener('click', startExploring);
        
        // Also handle touch for mobile
        instructions.addEventListener('touchend', (e) => {
            e.preventDefault();
            startExploring();
        });
        
        // WASD keyboard fallback - auto-activate on first movement key
        // This fixes cases where click doesn't register due to z-index issues
        const keyboardFallback = (e) => {
            if (['w','a','s','d','W','A','S','D',' '].includes(e.key) && !this.isLocked) {
                console.log('🎮 WASD fallback activation');
                startExploring();
                document.removeEventListener('keydown', keyboardFallback);
            }
        };
        document.addEventListener('keydown', keyboardFallback);
        
        // Auto-activate after a short timeout if nothing else works
        // This ensures users can always move even if click/touch fails
        setTimeout(() => {
            if (!this.isLocked) {
                console.log('⏱️ Auto-activation timeout (2s)');
                startExploring();
            }
        }, 2000);  // 2 seconds - faster fallback for better UX
        
        // Teleport overlay
        const overlay = document.createElement('div');
        overlay.id = 'teleport-overlay';
        document.body.appendChild(overlay);
    }
    
    hideInstructions() {
        const instructions = document.getElementById('navigation-instructions');
        if (instructions) {
            instructions.style.opacity = '0';
            setTimeout(() => {
                instructions.style.display = 'none';
            }, 300);
        }
    }
    
    initAudioOnGesture() {
        // Initialize audio context on user gesture (required by browsers)
        try {
            const AudioContext = window.AudioContext || window.webkitAudioContext;
            if (AudioContext && !window._audioContextInitialized) {
                const ctx = new AudioContext();
                if (ctx.state === 'suspended') {
                    ctx.resume();
                }
                window._audioContextInitialized = true;
                console.log('🔊 Audio context initialized on user gesture');
            }
        } catch (err) {
            console.log('ℹ️ Audio context not available');
        }
    }
    
    showInstructions() {
        const instructions = document.getElementById('navigation-instructions');
        if (instructions) {
            instructions.style.display = 'flex';
            setTimeout(() => {
                instructions.style.opacity = '1';
            }, 10);
        }
    }
    
    showGalleryMenu() {
        this.toggleGalleryMenu();
    }
    
    toggleGalleryMenu() {
        const menu = document.getElementById('gallery-menu');
        if (!menu) return;

        const isVisible = menu.classList.contains('visible');

        if (isVisible) {
            // Hide menu and restore focus
            menu.classList.remove('visible');
            if (this._galleryMenuPrevFocus && this._galleryMenuPrevFocus.focus) {
                this._galleryMenuPrevFocus.focus();
            }

            // Re-lock pointer if on desktop
            if (!this.isMobile && this.controls) {
                this.controls.lock();
            }
        } else {
            // Show menu and move focus into it
            this._galleryMenuPrevFocus = document.activeElement;
            menu.classList.add('visible');
            requestAnimationFrame(() => menu.focus());

            // Unlock pointer to allow menu interaction
            if (!this.isMobile && this.controls) {
                this.controls.unlock();
            }
        }
    }

    hideGalleryMenu() {
        const menu = document.getElementById('gallery-menu');
        if (menu) {
            menu.classList.remove('visible');
            if (this._galleryMenuPrevFocus && this._galleryMenuPrevFocus.focus) {
                this._galleryMenuPrevFocus.focus();
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DISPOSAL
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        if (this.controls) {
            this.controls.dispose();
        }
        
        const instructions = document.getElementById('navigation-instructions');
        if (instructions) instructions.remove();
        
        const joystick = document.getElementById('joystick-container');
        if (joystick) joystick.remove();
        
        const overlay = document.getElementById('teleport-overlay');
        if (overlay) overlay.remove();
    }
}

export default MuseumNavigation;
