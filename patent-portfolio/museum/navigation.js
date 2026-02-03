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
        this.canJump = true;
        
        // Physics
        this.velocity = new THREE.Vector3();
        this.direction = new THREE.Vector3();
        this.playerHeight = 1.7; // meters
        this.moveSpeed = 100;
        this.friction = 10;
        
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
        // Set initial position (in vestibule)
        this.camera.position.set(0, this.playerHeight, -35);
        this.camera.lookAt(0, this.playerHeight, 0);
        
        if (this.isMobile) {
            this.initTouchControls();
        } else {
            this.initPointerLockControls();
        }
        
        this.initTeleportSystem();
        this.initKeyboardControls();
        
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
        this.controls = new PointerLockControls(this.camera, this.renderer.domElement);
        
        this.controls.addEventListener('lock', () => {
            this.isLocked = true;
            this.hideInstructions();
        });
        
        this.controls.addEventListener('unlock', () => {
            this.isLocked = false;
            this.showInstructions();
        });
        
        // Click to lock
        this.renderer.domElement.addEventListener('click', () => {
            if (!this.isLocked) {
                this.controls.lock();
            }
        });
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
                    if (this.canJump) {
                        this.velocity.y = 10;
                        this.canJump = false;
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
            { name: 'Vestibule', position: new THREE.Vector3(0, 0, -35) },
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
    // UPDATE LOOP
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        if (!this.isLocked && !this.isMobile) return;
        
        // Apply friction
        this.velocity.x -= this.velocity.x * this.friction * deltaTime;
        this.velocity.z -= this.velocity.z * this.friction * deltaTime;
        
        // Calculate direction
        this.direction.z = Number(this.moveForward) - Number(this.moveBackward);
        this.direction.x = Number(this.moveRight) - Number(this.moveLeft);
        this.direction.normalize();
        
        // Apply movement
        if (this.moveForward || this.moveBackward) {
            this.velocity.z -= this.direction.z * this.moveSpeed * deltaTime;
        }
        if (this.moveLeft || this.moveRight) {
            this.velocity.x -= this.direction.x * this.moveSpeed * deltaTime;
        }
        
        // Gravity
        this.velocity.y -= 30 * deltaTime;
        
        // Move with controls
        if (this.controls && !this.isMobile) {
            this.controls.moveRight(-this.velocity.x * deltaTime);
            this.controls.moveForward(-this.velocity.z * deltaTime);
        } else if (this.isMobile) {
            // Manual movement for mobile
            const forward = new THREE.Vector3();
            this.camera.getWorldDirection(forward);
            forward.y = 0;
            forward.normalize();
            
            const right = new THREE.Vector3();
            right.crossVectors(forward, new THREE.Vector3(0, 1, 0));
            
            this.camera.position.addScaledVector(forward, -this.velocity.z * deltaTime);
            this.camera.position.addScaledVector(right, -this.velocity.x * deltaTime);
        }
        
        // Apply gravity
        this.camera.position.y += this.velocity.y * deltaTime;
        
        // Floor collision
        if (this.camera.position.y < this.playerHeight) {
            this.velocity.y = 0;
            this.camera.position.y = this.playerHeight;
            this.canJump = true;
        }
        
        // Simple boundary collision (keep inside museum)
        const maxDist = 80;
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
            background: rgba(7, 6, 11, 0.95);
            display: flex;
            align-items: center;
            justify-content: center;
            z-index: 2000;
            cursor: pointer;
            transition: opacity 0.3s;
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
        instructions.addEventListener('click', () => {
            if (this.isMobile) {
                // Mobile: just hide instructions (no pointer lock)
                this.hideInstructions();
            } else if (!this.isLocked && this.controls) {
                // Desktop: trigger pointer lock which calls hideInstructions
                this.controls.lock();
            }
        });
        
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
