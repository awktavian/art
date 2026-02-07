/**
 * GPU Particle System for Patent Museum
 * ======================================
 * 
 * High-performance particle system using:
 * - GPU instanced rendering
 * - Vertex shader animation
 * - Minimal CPU overhead
 * 
 * Features:
 * - Dust motes
 * - God rays
 * - Ambient atmosphere
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';

// ═══════════════════════════════════════════════════════════════════════════
// SHADERS
// ═══════════════════════════════════════════════════════════════════════════

const DUST_VERTEX_SHADER = `
    uniform float uTime;
    uniform float uSpeed;
    uniform float uTurbulence;
    uniform vec3 uBoundsMin;
    uniform vec3 uBoundsMax;
    
    attribute float aScale;
    attribute float aPhase;
    attribute vec3 aVelocity;
    
    varying float vAlpha;
    varying float vDepth;
    
    // Pseudo-random function
    float rand(vec2 co) {
        return fract(sin(dot(co.xy, vec2(12.9898, 78.233))) * 43758.5453);
    }
    
    void main() {
        // Base position
        vec3 pos = position;
        
        // Add time-based movement
        float t = uTime * uSpeed + aPhase;
        
        // Gentle floating motion
        pos.y += sin(t + pos.x * 0.5) * 0.3;
        pos.x += sin(t * 0.7 + pos.z * 0.3) * uTurbulence;
        pos.z += cos(t * 0.5 + pos.y * 0.2) * uTurbulence;
        
        // Add velocity
        pos += aVelocity * fract(t * 0.1) * 10.0;
        
        // Wrap within bounds
        vec3 boundsSize = uBoundsMax - uBoundsMin;
        pos = mod(pos - uBoundsMin, boundsSize) + uBoundsMin;
        
        // Transform to clip space
        vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
        gl_Position = projectionMatrix * mvPosition;
        
        // Point size with distance attenuation
        float sizeAttenuation = 1.0 / -mvPosition.z;
        gl_PointSize = aScale * 200.0 * sizeAttenuation;
        gl_PointSize = clamp(gl_PointSize, 1.0, 10.0);
        
        // Fade based on distance
        vDepth = -mvPosition.z;
        vAlpha = smoothstep(100.0, 10.0, vDepth) * 0.6;
        
        // Fade near bounds edges
        vec3 edgeDist = min(pos - uBoundsMin, uBoundsMax - pos);
        float edgeFade = smoothstep(0.0, 5.0, min(min(edgeDist.x, edgeDist.y), edgeDist.z));
        vAlpha *= edgeFade;
    }
`;

const DUST_FRAGMENT_SHADER = `
    uniform vec3 uColor;
    
    varying float vAlpha;
    varying float vDepth;
    
    void main() {
        // Soft circular particle
        vec2 center = gl_PointCoord - 0.5;
        float dist = length(center);
        
        if (dist > 0.5) discard;
        
        float alpha = smoothstep(0.5, 0.0, dist) * vAlpha;
        
        gl_FragColor = vec4(uColor, alpha);
    }
`;

const GODRAY_VERTEX_SHADER = `
    uniform float uTime;
    
    attribute float aScale;
    attribute float aPhase;
    attribute float aSpeed;
    
    varying float vAlpha;
    
    void main() {
        vec3 pos = position;
        
        // Gentle drift
        float t = uTime * aSpeed + aPhase;
        pos.y += sin(t) * 0.5;
        pos.x += sin(t * 0.3) * 0.3;
        
        vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
        gl_Position = projectionMatrix * mvPosition;
        
        // Large, soft particles
        gl_PointSize = aScale * 500.0 / -mvPosition.z;
        gl_PointSize = clamp(gl_PointSize, 5.0, 100.0);
        
        // Alpha based on phase for variation
        vAlpha = (sin(t * 0.5) * 0.5 + 0.5) * 0.15;
    }
`;

const GODRAY_FRAGMENT_SHADER = `
    uniform vec3 uColor;
    
    varying float vAlpha;
    
    void main() {
        vec2 center = gl_PointCoord - 0.5;
        float dist = length(center);
        
        if (dist > 0.5) discard;
        
        // Very soft falloff for ethereal look
        float alpha = pow(1.0 - dist * 2.0, 3.0) * vAlpha;
        
        gl_FragColor = vec4(uColor, alpha);
    }
`;

// ═══════════════════════════════════════════════════════════════════════════
// GPU DUST SYSTEM
// ═══════════════════════════════════════════════════════════════════════════

export class GPUDustSystem {
    constructor(options = {}) {
        this.count = options.count || 300;  // Reduced from 500 for performance
        this.bounds = options.bounds || {
            min: new THREE.Vector3(-50, 0, -50),
            max: new THREE.Vector3(50, 15, 50)
        };
        this.color = options.color || new THREE.Color(0xF5F0E8);
        this.speed = options.speed || 0.1;
        this.turbulence = options.turbulence || 0.2;
        
        this.points = null;
        this.material = null;
        
        this.create();
    }
    
    create() {
        // Geometry with instanced attributes
        const geometry = new THREE.BufferGeometry();
        
        const positions = new Float32Array(this.count * 3);
        const scales = new Float32Array(this.count);
        const phases = new Float32Array(this.count);
        const velocities = new Float32Array(this.count * 3);
        
        const boundsSize = new THREE.Vector3().subVectors(this.bounds.max, this.bounds.min);
        
        for (let i = 0; i < this.count; i++) {
            // Random position within bounds
            positions[i * 3] = this.bounds.min.x + Math.random() * boundsSize.x;
            positions[i * 3 + 1] = this.bounds.min.y + Math.random() * boundsSize.y;
            positions[i * 3 + 2] = this.bounds.min.z + Math.random() * boundsSize.z;
            
            // Random scale (0.5 to 1.5)
            scales[i] = 0.5 + Math.random();
            
            // Random phase offset
            phases[i] = Math.random() * Math.PI * 2;
            
            // Random slow velocity
            velocities[i * 3] = (Math.random() - 0.5) * 0.2;
            velocities[i * 3 + 1] = Math.random() * 0.1; // Slight upward bias
            velocities[i * 3 + 2] = (Math.random() - 0.5) * 0.2;
        }
        
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('aScale', new THREE.BufferAttribute(scales, 1));
        geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
        geometry.setAttribute('aVelocity', new THREE.BufferAttribute(velocities, 3));
        
        // Shader material - using NormalBlending to reduce overbright flicker
        this.material = new THREE.ShaderMaterial({
            uniforms: {
                uTime: { value: 0 },
                uSpeed: { value: this.speed },
                uTurbulence: { value: this.turbulence },
                uColor: { value: this.color },
                uBoundsMin: { value: this.bounds.min },
                uBoundsMax: { value: this.bounds.max }
            },
            vertexShader: DUST_VERTEX_SHADER,
            fragmentShader: DUST_FRAGMENT_SHADER,
            transparent: true,
            depthWrite: false,
            blending: THREE.NormalBlending  // Changed from Additive to reduce flicker
        });
        
        this.points = new THREE.Points(geometry, this.material);
        this.points.frustumCulled = false; // Always render (particles move)
    }
    
    update(time) {
        if (this.material) {
            this.material.uniforms.uTime.value = time;
        }
    }
    
    setColor(color) {
        if (this.material) {
            this.material.uniforms.uColor.value.set(color);
        }
    }
    
    setVisible(visible) {
        if (this.points) {
            this.points.visible = visible;
        }
    }
    
    dispose() {
        if (this.points) {
            this.points.geometry.dispose();
            this.material.dispose();
        }
    }
    
    get mesh() {
        return this.points;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// GPU GODRAY SYSTEM
// ═══════════════════════════════════════════════════════════════════════════

export class GPUGodraySystem {
    constructor(options = {}) {
        this.count = options.count || 50;
        this.position = options.position || new THREE.Vector3(0, 20, 0);
        this.spread = options.spread || 10;
        this.color = options.color || new THREE.Color(0xFFFAF0);
        
        this.points = null;
        this.material = null;
        
        this.create();
    }
    
    create() {
        const geometry = new THREE.BufferGeometry();
        
        const positions = new Float32Array(this.count * 3);
        const scales = new Float32Array(this.count);
        const phases = new Float32Array(this.count);
        const speeds = new Float32Array(this.count);
        
        for (let i = 0; i < this.count; i++) {
            // Position around light source
            const angle = Math.random() * Math.PI * 2;
            const radius = Math.random() * this.spread;
            
            positions[i * 3] = this.position.x + Math.cos(angle) * radius;
            positions[i * 3 + 1] = this.position.y - Math.random() * 15; // Below light
            positions[i * 3 + 2] = this.position.z + Math.sin(angle) * radius;
            
            scales[i] = 1 + Math.random() * 2;
            phases[i] = Math.random() * Math.PI * 2;
            speeds[i] = 0.1 + Math.random() * 0.2;
        }
        
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('aScale', new THREE.BufferAttribute(scales, 1));
        geometry.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
        geometry.setAttribute('aSpeed', new THREE.BufferAttribute(speeds, 1));
        
        this.material = new THREE.ShaderMaterial({
            uniforms: {
                uTime: { value: 0 },
                uColor: { value: this.color }
            },
            vertexShader: GODRAY_VERTEX_SHADER,
            fragmentShader: GODRAY_FRAGMENT_SHADER,
            transparent: true,
            depthWrite: false,
            blending: THREE.NormalBlending  // Changed from Additive to reduce flickering
        });
        
        this.points = new THREE.Points(geometry, this.material);
        this.points.frustumCulled = false;
    }
    
    update(time) {
        if (this.material) {
            this.material.uniforms.uTime.value = time;
        }
    }
    
    setColor(color) {
        if (this.material) {
            this.material.uniforms.uColor.value.set(color);
        }
    }
    
    setVisible(visible) {
        if (this.points) {
            this.points.visible = visible;
        }
    }
    
    dispose() {
        if (this.points) {
            this.points.geometry.dispose();
            this.material.dispose();
        }
    }
    
    get mesh() {
        return this.points;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// PARTICLE MANAGER
// ═══════════════════════════════════════════════════════════════════════════

export class GPUParticleManager {
    constructor(scene, options = {}) {
        this.scene = scene;
        this.enabled = true;
        
        // Systems
        this.dustSystem = null;
        this.godraySystem = null;
        
        // Initialize based on options
        if (options.dust !== false) {
            this.dustSystem = new GPUDustSystem({
                count: options.dustCount || 300,
                bounds: options.dustBounds,
                color: options.dustColor
            });
            scene.add(this.dustSystem.mesh);
        }
        
        if (options.godrays !== false) {
            this.godraySystem = new GPUGodraySystem({
                count: options.godrayCount || 30,
                position: options.godrayPosition,
                color: options.godrayColor
            });
            scene.add(this.godraySystem.mesh);
        }
    }
    
    update(time) {
        if (!this.enabled) return;
        
        if (this.dustSystem) {
            this.dustSystem.update(time);
        }
        
        if (this.godraySystem) {
            this.godraySystem.update(time);
        }
    }
    
    setEnabled(enabled) {
        this.enabled = enabled;
        
        if (this.dustSystem) {
            this.dustSystem.setVisible(enabled);
        }
        if (this.godraySystem) {
            this.godraySystem.setVisible(enabled);
        }
    }
    
    setDustColor(color) {
        if (this.dustSystem) {
            this.dustSystem.setColor(color);
        }
    }
    
    setGodrayColor(color) {
        if (this.godraySystem) {
            this.godraySystem.setColor(color);
        }
    }
    
    dispose() {
        if (this.dustSystem) {
            this.scene.remove(this.dustSystem.mesh);
            this.dustSystem.dispose();
        }
        if (this.godraySystem) {
            this.scene.remove(this.godraySystem.mesh);
            this.godraySystem.dispose();
        }
    }
}
