/**
 * Museum Interaction System
 * =========================
 * 
 * Exploratorium-inspired interactive experiences:
 * - Sparking: Quick, delightful micro-interactions
 * - Sustaining: Deeper explorations that reveal layers
 * - Discovery: Hidden features that reward curiosity
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// INTERACTION TYPES
// ═══════════════════════════════════════════════════════════════════════════

export const InteractionType = {
    SPARK: 'spark',         // Quick delight (< 3 seconds)
    SUSTAIN: 'sustain',     // Deeper exploration (> 10 seconds)
    DISCOVER: 'discover',   // Hidden easter egg
    LEARN: 'learn'          // Educational reveal
};

// ═══════════════════════════════════════════════════════════════════════════
// INTERACTION REGISTRY
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Defines interactive behaviors for each artwork
 */
export const ARTWORK_INTERACTIONS = {
    // P1-001: EFE-CBF Safety Optimizer
    'P1-001': {
        sparks: [
            {
                trigger: 'hover',
                target: 'landscape',
                action: 'ripple',
                description: 'Safety landscape responds to your presence'
            },
            {
                trigger: 'click',
                target: 'agent',
                action: 'pathPreview',
                description: 'Preview possible paths from clicked point'
            }
        ],
        sustains: [
            {
                trigger: 'dwell',
                duration: 5000,
                target: 'dangerZone',
                action: 'explainBarrier',
                description: 'Learn why h(x) ≥ 0 matters for safety'
            }
        ],
        discoveries: [
            {
                trigger: 'sequence',
                pattern: ['edge', 'edge', 'center'],
                action: 'revealMath',
                description: 'See the mathematical formulation'
            }
        ]
    },
    
    // P1-002: Fano Consensus
    'P1-002': {
        sparks: [
            {
                trigger: 'hover',
                target: 'node',
                action: 'highlightConnections',
                description: 'See this colony\'s consensus partners'
            },
            {
                trigger: 'click',
                target: 'node',
                action: 'initiateConsensus',
                description: 'Start a consensus vote'
            }
        ],
        sustains: [
            {
                trigger: 'dwell',
                duration: 8000,
                target: 'structure',
                action: 'explainByzantine',
                description: 'Understand Byzantine fault tolerance'
            }
        ],
        discoveries: [
            {
                trigger: 'click',
                count: 7,
                target: 'allNodes',
                action: 'unanimousConsensus',
                description: 'Achieve unanimous agreement'
            }
        ]
    },
    
    // P1-003: E8 Lattice
    'P1-003': {
        sparks: [
            {
                trigger: 'hover',
                target: 'sphere',
                action: 'showNeighbors',
                description: 'See the 240 kissing spheres'
            },
            {
                trigger: 'scroll',
                target: 'lattice',
                action: 'rotateProjection',
                description: 'Rotate through 8D projections'
            }
        ],
        sustains: [
            {
                trigger: 'dwell',
                duration: 10000,
                target: 'center',
                action: 'unfoldDimensions',
                description: 'Watch 8D unfold into 3D'
            }
        ]
    },
    
    // P1-004: S15 Hopf Fibration
    'P1-004': {
        sparks: [
            {
                trigger: 'hover',
                target: 'fiber',
                action: 'highlightFiber',
                description: 'See individual S7 fibers'
            }
        ],
        sustains: [
            {
                trigger: 'click',
                target: 'fiber',
                action: 'rideTheFiber',
                description: 'Take a journey along the fiber'
            }
        ],
        discoveries: [
            {
                trigger: 'gesture',
                pattern: 'figure8',
                action: 'revealOctonions',
                description: 'Discover the octonionic structure'
            }
        ]
    },
    
    // P1-005: OrganismRSSM
    'P1-005': {
        sparks: [
            {
                trigger: 'hover',
                target: 'stochasticCloud',
                action: 'perturbParticles',
                description: 'See stochastic state uncertainty'
            },
            {
                trigger: 'click',
                target: 'colony',
                action: 'highlightColonyRole',
                description: 'Learn each colony\'s function'
            }
        ],
        sustains: [
            {
                trigger: 'click',
                target: 'imagination',
                action: 'runImagination',
                description: 'Watch the model predict the future'
            }
        ]
    },
    
    // P1-006: Quantum-Safe Crypto
    'P1-006': {
        sparks: [
            {
                trigger: 'hover',
                target: 'lattice',
                action: 'showNoise',
                description: 'See the LWE noise that protects data'
            }
        ],
        sustains: [
            {
                trigger: 'input',
                target: 'encryptBox',
                action: 'encryptMessage',
                description: 'Encrypt your own message'
            }
        ],
        discoveries: [
            {
                trigger: 'type',
                text: 'quantum',
                action: 'simulateQuantumAttack',
                description: 'Watch a quantum attack fail'
            }
        ]
    }
};

/**
 * Patent-specific hover/action text (replaces generic "View Patent")
 */
export const CONTEXT_PROMPTS = {
    'P1-001': { action: 'Explore the safety landscape', hint: 'See h(x) ≥ 0 and the barrier' },
    'P1-002': { action: 'Touch a colony node', hint: 'Seven nodes, unanimous consensus' },
    'P1-003': { action: 'Rotate the 8D projection', hint: '240 roots in 8 dimensions' },
    'P1-004': { action: 'Ride the S7 fiber', hint: 'Octonion structure' },
    'P1-005': { action: 'Run the imagination', hint: 'World model prediction' },
    'P1-006': { action: 'Encrypt your message', hint: 'Quantum-safe LWE' },
    'P2-A1': { action: 'Explore G2 layers', hint: '14-dimensional root system' },
    'P2-B1': { action: 'See the 3-tier barrier', hint: 'Concentric safety shells' },
    'P2-C1': { action: 'Watch CRDT healing', hint: 'Cross-hub sync' },
    'P2-D1': { action: 'Trace the bifurcation', hint: 'Catastrophe KAN' },
    'P2-I2': { action: 'Enter the audit chamber', hint: '6 parallel judges' }
};

// ═══════════════════════════════════════════════════════════════════════════
// INTERACTION EFFECTS
// ═══════════════════════════════════════════════════════════════════════════

export class InteractionEffects {
    constructor(scene, camera) {
        this.scene = scene;
        this.camera = camera;
        this.activeEffects = [];
        this.particlePool = [];
        
        this.init();
    }
    
    init() {
        // Pre-create particle pool for effects
        this.createParticlePool();
    }
    
    createParticlePool() {
        const particleGeo = new THREE.SphereGeometry(0.02, 8, 8);
        const particleMat = new THREE.MeshBasicMaterial({
            color: 0xFFFFFF,
            transparent: true,
            opacity: 0.8
        });
        
        for (let i = 0; i < 100; i++) {
            const particle = new THREE.Mesh(particleGeo, particleMat.clone());
            particle.visible = false;
            particle.userData.velocity = new THREE.Vector3();
            particle.userData.life = 0;
            this.particlePool.push(particle);
            this.scene.add(particle);
        }
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // SPARK EFFECTS
    // ─────────────────────────────────────────────────────────────────────────
    
    /**
     * Ripple effect on surface
     */
    createRipple(position, color = 0x67D4E4, radius = 1.0) {
        const rippleGeo = new THREE.RingGeometry(0.1, 0.15, 32);
        const rippleMat = new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity: 0.8,
            side: THREE.DoubleSide
        });
        
        const ripple = new THREE.Mesh(rippleGeo, rippleMat);
        ripple.position.copy(position);
        ripple.position.y += 0.01;
        ripple.rotation.x = -Math.PI / 2;
        
        this.scene.add(ripple);
        
        this.activeEffects.push({
            type: 'ripple',
            mesh: ripple,
            startTime: performance.now(),
            duration: 1500,
            maxRadius: radius,
            update: (effect, progress) => {
                const scale = 1 + progress * (effect.maxRadius / 0.15);
                effect.mesh.scale.setScalar(scale);
                effect.mesh.material.opacity = 0.8 * (1 - progress);
            },
            cleanup: (effect) => {
                this.scene.remove(effect.mesh);
                effect.mesh.geometry.dispose();
                effect.mesh.material.dispose();
            }
        });
    }
    
    /**
     * Particle burst effect
     */
    createBurst(position, color = 0xFFFFFF, count = 20) {
        const usedParticles = [];
        
        for (let i = 0; i < count && i < this.particlePool.length; i++) {
            const particle = this.particlePool[i];
            if (!particle.visible) {
                particle.position.copy(position);
                particle.material.color.setHex(color);
                particle.material.opacity = 1.0;
                particle.visible = true;
                
                // Random velocity
                const theta = Math.random() * Math.PI * 2;
                const phi = Math.random() * Math.PI;
                const speed = 0.5 + Math.random() * 1.5;
                
                particle.userData.velocity.set(
                    Math.sin(phi) * Math.cos(theta) * speed,
                    Math.cos(phi) * speed + 1,
                    Math.sin(phi) * Math.sin(theta) * speed
                );
                particle.userData.life = 1.0;
                
                usedParticles.push(particle);
            }
        }
        
        this.activeEffects.push({
            type: 'burst',
            particles: usedParticles,
            startTime: performance.now(),
            duration: 2000,
            update: (effect, progress) => {
                const dt = 0.016; // Approximate 60fps
                effect.particles.forEach(p => {
                    p.position.addScaledVector(p.userData.velocity, dt);
                    p.userData.velocity.y -= 9.8 * dt * 0.1; // Gravity
                    p.userData.life -= dt * 0.5;
                    p.material.opacity = Math.max(0, p.userData.life);
                    
                    if (p.userData.life <= 0) {
                        p.visible = false;
                    }
                });
            },
            cleanup: (effect) => {
                effect.particles.forEach(p => {
                    p.visible = false;
                });
            }
        });
    }
    
    /**
     * Glow pulse effect
     */
    createGlowPulse(object, color = 0x67D4E4, intensity = 2.0) {
        if (!object.material) return;
        
        const originalEmissive = object.material.emissive?.clone() || new THREE.Color(0x000000);
        const originalIntensity = object.material.emissiveIntensity || 0;
        
        this.activeEffects.push({
            type: 'glowPulse',
            object,
            originalEmissive,
            originalIntensity,
            targetColor: new THREE.Color(color),
            startTime: performance.now(),
            duration: 800,
            intensity,
            update: (effect, progress) => {
                const pulse = Math.sin(progress * Math.PI);
                if (effect.object.material.emissive) {
                    effect.object.material.emissive.lerpColors(
                        effect.originalEmissive,
                        effect.targetColor,
                        pulse
                    );
                    effect.object.material.emissiveIntensity = 
                        effect.originalIntensity + pulse * effect.intensity;
                }
            },
            cleanup: (effect) => {
                if (effect.object.material.emissive) {
                    effect.object.material.emissive.copy(effect.originalEmissive);
                    effect.object.material.emissiveIntensity = effect.originalIntensity;
                }
            }
        });
    }
    
    /**
     * Connection line effect
     */
    createConnection(from, to, color = 0x67D4E4, duration = 2000) {
        const curve = new THREE.CatmullRomCurve3([
            from,
            new THREE.Vector3(
                (from.x + to.x) / 2,
                Math.max(from.y, to.y) + 0.5,
                (from.z + to.z) / 2
            ),
            to
        ]);
        
        const geo = new THREE.TubeGeometry(curve, 20, 0.02, 8, false);
        const mat = new THREE.MeshBasicMaterial({
            color,
            transparent: true,
            opacity: 0
        });
        const line = new THREE.Mesh(geo, mat);
        this.scene.add(line);
        
        this.activeEffects.push({
            type: 'connection',
            mesh: line,
            startTime: performance.now(),
            duration,
            update: (effect, progress) => {
                // Fade in, hold, fade out
                if (progress < 0.2) {
                    effect.mesh.material.opacity = progress / 0.2;
                } else if (progress > 0.8) {
                    effect.mesh.material.opacity = (1 - progress) / 0.2;
                } else {
                    effect.mesh.material.opacity = 1.0;
                }
            },
            cleanup: (effect) => {
                this.scene.remove(effect.mesh);
                effect.mesh.geometry.dispose();
                effect.mesh.material.dispose();
            }
        });
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // SUSTAIN EFFECTS
    // ─────────────────────────────────────────────────────────────────────────
    
    /**
     * Reveal panel with information
     */
    createInfoReveal(position, text, options = {}) {
        const {
            width = 2,
            height = 1.5,
            bgColor = 0x0A1628,
            textColor = 0x67D4E4,
            duration = 5000
        } = options;
        
        // Background panel
        const canvas = document.createElement('canvas');
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        canvas.width = Math.round(width * 256 * dpr);
        canvas.height = Math.round(height * 256 * dpr);
        const ctx = canvas.getContext('2d');
        ctx.scale(dpr, dpr);
        const cw = width * 256, ch = height * 256;

        const bgHex = '#' + bgColor.toString(16).padStart(6, '0');
        ctx.fillStyle = bgHex;
        ctx.fillRect(0, 0, cw, ch);

        ctx.fillStyle = '#' + textColor.toString(16).padStart(6, '0');
        ctx.font = `${Math.round(ch * 0.06)}px 'IBM Plex Sans', sans-serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';

        const maxLineWidth = cw * 0.85;
        const words = text.split(' ');
        const lines = [];
        let currentLine = '';
        for (const word of words) {
            const test = currentLine ? currentLine + ' ' + word : word;
            if (ctx.measureText(test).width > maxLineWidth && currentLine) {
                lines.push(currentLine);
                currentLine = word;
            } else {
                currentLine = test;
            }
        }
        if (currentLine) lines.push(currentLine);

        const lineHeight = ch * 0.08;
        const startY = ch / 2 - ((lines.length - 1) * lineHeight) / 2;
        lines.forEach((line, i) => {
            ctx.fillText(line, cw / 2, startY + i * lineHeight);
        });

        const tex = new THREE.CanvasTexture(canvas);
        tex.minFilter = THREE.LinearFilter;

        const panelGeo = new THREE.PlaneGeometry(width, height);
        const panelMat = new THREE.MeshBasicMaterial({
            map: tex,
            transparent: true,
            opacity: 0,
            side: THREE.DoubleSide
        });
        const panel = new THREE.Mesh(panelGeo, panelMat);
        panel.position.copy(position);
        panel.lookAt(this.camera.position);
        
        this.scene.add(panel);
        
        this.activeEffects.push({
            type: 'infoReveal',
            mesh: panel,
            text,
            startTime: performance.now(),
            duration,
            update: (effect, progress) => {
                // Slide in and fade
                if (progress < 0.1) {
                    effect.mesh.material.opacity = progress / 0.1;
                    effect.mesh.scale.y = progress / 0.1;
                } else if (progress > 0.9) {
                    effect.mesh.material.opacity = (1 - progress) / 0.1;
                } else {
                    effect.mesh.material.opacity = 0.95;
                    effect.mesh.scale.y = 1;
                }
                
                // Keep facing camera
                effect.mesh.lookAt(this.camera.position);
            },
            cleanup: (effect) => {
                this.scene.remove(effect.mesh);
                effect.mesh.geometry.dispose();
                effect.mesh.material.dispose();
            }
        });
        
        return panel;
    }
    
    /**
     * Progressive reveal effect
     */
    createProgressiveReveal(objects, interval = 200) {
        objects.forEach((obj, i) => {
            setTimeout(() => {
                this.createGlowPulse(obj, 0x67D4E4, 1.5);
            }, i * interval);
        });
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // DISCOVERY EFFECTS
    // ─────────────────────────────────────────────────────────────────────────
    
    /**
     * Celebration effect for discoveries
     */
    createCelebration(position, color = 0xFFD700) {
        // Multiple bursts
        for (let i = 0; i < 3; i++) {
            setTimeout(() => {
                this.createBurst(
                    position.clone().add(new THREE.Vector3(
                        (Math.random() - 0.5) * 0.5,
                        i * 0.3,
                        (Math.random() - 0.5) * 0.5
                    )),
                    color,
                    30
                );
            }, i * 200);
        }
        
        // Rising sparkles
        for (let i = 0; i < 20; i++) {
            const delay = Math.random() * 1000;
            setTimeout(() => {
                const p = this.particlePool.find(p => !p.visible);
                if (p) {
                    p.position.copy(position).add(new THREE.Vector3(
                        (Math.random() - 0.5) * 1,
                        0,
                        (Math.random() - 0.5) * 1
                    ));
                    p.material.color.setHex(color);
                    p.visible = true;
                    p.userData.velocity.set(
                        (Math.random() - 0.5) * 0.5,
                        2 + Math.random() * 2,
                        (Math.random() - 0.5) * 0.5
                    );
                    p.userData.life = 1.5;
                }
            }, delay);
        }
    }
    
    // ─────────────────────────────────────────────────────────────────────────
    // UPDATE
    // ─────────────────────────────────────────────────────────────────────────
    
    update(deltaTime) {
        const now = performance.now();
        
        // Update active effects
        for (let i = this.activeEffects.length - 1; i >= 0; i--) {
            const effect = this.activeEffects[i];
            const elapsed = now - effect.startTime;
            const progress = Math.min(1, elapsed / effect.duration);
            
            if (effect.update) {
                effect.update(effect, progress);
            }
            
            if (progress >= 1) {
                if (effect.cleanup) {
                    effect.cleanup(effect);
                }
                this.activeEffects.splice(i, 1);
            }
        }
        
        // Update floating particles (for discoveries)
        this.particlePool.forEach(p => {
            if (p.visible && p.userData.life > 0) {
                p.position.addScaledVector(p.userData.velocity, deltaTime);
                p.userData.velocity.y -= 2 * deltaTime;
                p.userData.life -= deltaTime;
                p.material.opacity = Math.max(0, p.userData.life);
                
                if (p.userData.life <= 0) {
                    p.visible = false;
                }
            }
        });
    }
    
    dispose() {
        // Cleanup all active effects
        this.activeEffects.forEach(effect => {
            if (effect.cleanup) {
                effect.cleanup(effect);
            }
        });
        this.activeEffects = [];
        
        // Dispose particle pool
        this.particlePool.forEach(p => {
            this.scene.remove(p);
            p.geometry.dispose();
            p.material.dispose();
        });
        this.particlePool = [];
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// INTERACTION MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export class InteractionManager {
    constructor(scene, camera, renderer) {
        this.scene = scene;
        this.camera = camera;
        this.renderer = renderer;
        
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        
        this.effects = new InteractionEffects(scene, camera);
        
        // Tracking
        this.hoveredObject = null;
        this.dwellStartTime = 0;
        this.dwellTarget = null;
        this.clickSequence = [];
        this.lastClickTime = 0;
        
        // Discovery tracking
        this.discoveries = new Set();
        
        // Hover state machine: idle -> approaching -> hover -> engaged
        this.hoverState = 'idle';
        this.hoverStateTimer = 0;
        
        this.init();
    }
    
    init() {
        // Mouse events
        this.renderer.domElement.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.renderer.domElement.addEventListener('click', (e) => this.onClick(e));
        
        // Touch events for mobile
        this.renderer.domElement.addEventListener('touchstart', (e) => this.onTouchStart(e));
    }
    
    onMouseMove(event) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        
        // Throttle hover raycasting to max 15fps (67ms) for performance
        const now = performance.now();
        if (now - (this._lastHoverCheck || 0) < 67) return;
        this._lastHoverCheck = now;
        
        this.checkHover();
    }
    
    onClick(event) {
        const rect = this.renderer.domElement.getBoundingClientRect();
        this.mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
        this.mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
        
        this.handleClick();
    }
    
    onTouchStart(event) {
        if (event.touches.length > 0) {
            const rect = this.renderer.domElement.getBoundingClientRect();
            this.mouse.x = ((event.touches[0].clientX - rect.left) / rect.width) * 2 - 1;
            this.mouse.y = -((event.touches[0].clientY - rect.top) / rect.height) * 2 + 1;
            
            this.handleClick();
        }
    }
    
    /**
     * Rebuild the cached interactable objects list.
     * Call this after loading new gallery content.
     */
    rebuildInteractableCache() {
        this._cachedInteractables = [];
        this.scene.traverse(obj => {
            if (obj.userData?.interactive) {
                this._cachedInteractables.push(obj);
            }
        });
    }
    
    checkHover() {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        
        // Use cached interactables — rebuild every 5 seconds or on demand
        const now = performance.now();
        if (!this._cachedInteractables || now - (this._lastCacheRebuild || 0) > 5000) {
            this.rebuildInteractableCache();
            this._lastCacheRebuild = now;
        }
        
        const intersects = this.raycaster.intersectObjects(this._cachedInteractables, true);
        
        if (intersects.length > 0) {
            const newHovered = intersects[0].object;
            
            if (newHovered !== this.hoveredObject) {
                // Exit previous
                if (this.hoveredObject) {
                    this.onHoverExit(this.hoveredObject);
                }
                
                // Enter new
                this.hoveredObject = newHovered;
                this.onHoverEnter(this.hoveredObject, intersects[0]);
                
                // Start dwell timer
                this.dwellStartTime = performance.now();
                this.dwellTarget = this.hoveredObject;
            }
        } else if (this.hoveredObject) {
            this.onHoverExit(this.hoveredObject);
            this.hoveredObject = null;
            this.dwellTarget = null;
        }
    }
    
    onHoverEnter(object, intersection) {
        this.hoverState = 'approaching';
        this.hoverStateTimer = 0;
        
        // Visual: subtle glow pulse
        this.effects.createGlowPulse(object, 0x67D4E4, 0.5);
        
        // Cursor
        document.body.style.cursor = 'pointer';
        
        // Mobile haptics: subtle tap on hover
        if (navigator.vibrate) navigator.vibrate([10]);
        
        // Transition to 'hover' after 150ms
        setTimeout(() => {
            if (this.hoveredObject === object) {
                this.hoverState = 'hover';
            }
        }, 150);
    }
    
    onHoverExit(object) {
        this.hoverState = 'idle';
        this.hoverStateTimer = 0;
        document.body.style.cursor = 'default';
    }
    
    handleClick() {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        
        const interactables = [];
        this.scene.traverse(obj => {
            if (obj.userData?.interactive) {
                interactables.push(obj);
            }
        });
        
        const intersects = this.raycaster.intersectObjects(interactables, true);
        
        if (intersects.length > 0) {
            // Click feedback: scale bounce
            const clickedObj = intersects[0].object;
            if (clickedObj.scale) {
                const origScale = clickedObj.scale.clone();
                clickedObj.scale.multiplyScalar(0.95);
                setTimeout(() => clickedObj.scale.multiplyScalar(1.05 / 0.95), 80);
                setTimeout(() => clickedObj.scale.copy(origScale), 200);
            }
            
            // Mobile haptics: click pattern
            if (navigator.vibrate) navigator.vibrate([20, 10, 20]);
            
            const clicked = intersects[0].object;
            const point = intersects[0].point;
            
            // Spark: click feedback
            this.effects.createRipple(point, 0x67D4E4, 0.5);
            this.effects.createBurst(point, 0xFFFFFF, 10);
            
            // Track click sequence for discoveries
            this.trackClickSequence(clicked);
            
            // Call artwork's onClick if it exists
            const artwork = this.findParentArtwork(clicked);
            if (artwork && typeof artwork.onClick === 'function') {
                artwork.onClick(intersects[0]);
            }
        }
    }
    
    findParentArtwork(object) {
        let current = object;
        while (current) {
            if (current.userData?.patentId) {
                return current;
            }
            current = current.parent;
        }
        return null;
    }
    
    trackClickSequence(object) {
        const now = performance.now();
        
        // Reset sequence if too much time has passed
        if (now - this.lastClickTime > 2000) {
            this.clickSequence = [];
        }
        
        this.clickSequence.push({
            object,
            time: now
        });
        
        this.lastClickTime = now;
        
        // Keep last 10 clicks
        if (this.clickSequence.length > 10) {
            this.clickSequence.shift();
        }
        
        // Check for discovery patterns
        this.checkDiscoveryPatterns();
    }
    
    checkDiscoveryPatterns() {
        // Check for 7 consecutive clicks on different nodes (Fano achievement)
        const recentClicks = this.clickSequence.slice(-7);
        if (recentClicks.length === 7) {
            const uniqueObjects = new Set(recentClicks.map(c => c.object));
            if (uniqueObjects.size === 7) {
                const artwork = this.findParentArtwork(recentClicks[0].object);
                if (artwork?.userData?.patentId === 'P1-002' && !this.discoveries.has('fano-unanimous')) {
                    this.discoveries.add('fano-unanimous');
                    this.effects.createCelebration(artwork.position);
                    console.log('🎉 Discovery: Unanimous Fano Consensus!');
                }
            }
        }
    }
    
    update(deltaTime) {
        this.effects.update(deltaTime);
        
        // Check dwell time for sustained interactions
        if (this.dwellTarget && this.dwellStartTime) {
            const dwellTime = performance.now() - this.dwellStartTime;
            
            // Trigger sustained interaction after 5 seconds
            if (dwellTime > 5000) {
                const artwork = this.findParentArtwork(this.dwellTarget);
                if (artwork?.userData?.patentId) {
                    const patentId = artwork.userData.patentId;
                    const interactions = ARTWORK_INTERACTIONS[patentId];
                    
                    if (interactions?.sustains) {
                        interactions.sustains.forEach(sustain => {
                            if (sustain.trigger === 'dwell' && dwellTime > sustain.duration) {
                                // Trigger sustained interaction
                                console.log(`Sustained: ${sustain.description}`);
                                this.effects.createInfoReveal(
                                    this.dwellTarget.position.clone().add(new THREE.Vector3(0, 1, 0)),
                                    sustain.description
                                );
                            }
                        });
                    }
                }
                
                // Reset to avoid repeated triggers
                this.dwellStartTime = performance.now();
            }
        }
    }
    
    dispose() {
        this.effects.dispose();
        this.renderer.domElement.removeEventListener('mousemove', this.onMouseMove);
        this.renderer.domElement.removeEventListener('click', this.onClick);
        this.renderer.domElement.removeEventListener('touchstart', this.onTouchStart);
    }
}

export default {
    InteractionType,
    ARTWORK_INTERACTIONS,
    InteractionEffects,
    InteractionManager
};
