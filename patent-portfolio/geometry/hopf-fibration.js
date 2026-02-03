/**
 * S15 Hopf Fibration Visualization
 * ==================================
 * 
 * Visualizes the octonionic Hopf fibration: S⁷ → S¹⁵ → S⁸
 * 
 * The 15-sphere decomposes into:
 * - S⁸ base (8D semantic content)
 * - S⁷ fiber (7D routing, matches 7 colonies)
 * 
 * Represented as animated torus knot with flowing energy.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import {
    COLONY_ORDER,
    COLONY_COLORS,
    VOID_COLORS,
    DURATION_S
} from '../../lib/design-tokens.js';

// Helper to get colony color as THREE.Color
function getColonyColor(name) {
    return new THREE.Color(COLONY_COLORS[name].num);
}

// ═══════════════════════════════════════════════════════════════════════════
// HOPF FIBRATION SHADERS
// ═══════════════════════════════════════════════════════════════════════════

const HopfVertexShader = `
    uniform float time;
    uniform float flowSpeed;
    
    varying vec2 vUv;
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying float vFlow;
    
    void main() {
        vUv = uv;
        vPosition = position;
        vNormal = normalize(normalMatrix * normal);
        
        // Flow animation along the fiber direction
        vFlow = fract(uv.x * 7.0 - time * flowSpeed);
        
        // Slight pulsing displacement
        float pulse = sin(time * 2.0 + uv.x * 6.28318) * 0.02;
        vec3 displaced = position + normal * pulse;
        
        gl_Position = projectionMatrix * modelViewMatrix * vec4(displaced, 1.0);
    }
`;

const HopfFragmentShader = `
    uniform float time;
    uniform vec3 baseColor;
    uniform vec3 fiberColor;
    uniform float opacity;
    uniform float glowIntensity;
    
    varying vec2 vUv;
    varying vec3 vPosition;
    varying vec3 vNormal;
    varying float vFlow;
    
    // Colony colors for 7-fiber representation
    vec3 colonyColors[7];
    
    void main() {
        // Initialize colony colors
        colonyColors[0] = vec3(1.0, 0.42, 0.21);   // Spark
        colonyColors[1] = vec3(0.83, 0.69, 0.22);  // Forge
        colonyColors[2] = vec3(0.31, 0.80, 0.77);  // Flow
        colonyColors[3] = vec3(0.61, 0.49, 0.74);  // Nexus
        colonyColors[4] = vec3(0.96, 0.62, 0.04);  // Beacon
        colonyColors[5] = vec3(0.49, 0.72, 0.50);  // Grove
        colonyColors[6] = vec3(0.40, 0.83, 0.89);  // Crystal
        
        // Determine which fiber we're on (7 fibers for S7)
        float fiberIndex = floor(vUv.x * 7.0);
        float fiberBlend = fract(vUv.x * 7.0);
        
        // Get colony colors for this fiber
        int idx1 = int(mod(fiberIndex, 7.0));
        int idx2 = int(mod(fiberIndex + 1.0, 7.0));
        
        vec3 fiber1 = colonyColors[idx1];
        vec3 fiber2 = colonyColors[idx2];
        
        // Blend between fibers smoothly
        vec3 fiberCol = mix(fiber1, fiber2, smoothstep(0.4, 0.6, fiberBlend));
        
        // Flow pulse (energy traveling along fibers)
        float flowPulse = smoothstep(0.0, 0.3, vFlow) * smoothstep(1.0, 0.7, vFlow);
        flowPulse = pow(flowPulse, 2.0);
        
        // Base to fiber gradient (represents S8 → S7 decomposition)
        float baseToFiber = smoothstep(0.0, 1.0, vUv.y);
        vec3 structureColor = mix(baseColor, fiberCol, baseToFiber);
        
        // Add glow based on flow
        vec3 glowColor = fiberCol * glowIntensity * flowPulse;
        
        // Fresnel rim glow
        vec3 viewDir = normalize(cameraPosition - vPosition);
        float fresnel = pow(1.0 - max(dot(vNormal, viewDir), 0.0), 3.0);
        vec3 rimGlow = fiberCol * fresnel * 0.5;
        
        // Final color
        vec3 finalColor = structureColor + glowColor + rimGlow;
        
        // Subtle animation variation
        float sparkle = sin(vUv.x * 50.0 + time * 5.0) * sin(vUv.y * 50.0 + time * 3.0);
        sparkle = max(0.0, sparkle) * 0.1;
        finalColor += sparkle * fiberCol;
        
        gl_FragColor = vec4(finalColor, opacity * (0.7 + flowPulse * 0.3));
    }
`;

// ═══════════════════════════════════════════════════════════════════════════
// HOPF FIBRATION CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class HopfFibration extends THREE.Group {
    constructor(options = {}) {
        super();
        
        this.options = {
            radius: options.radius || 4,
            tube: options.tube || 0.3,
            tubularSegments: options.tubularSegments || 256,
            radialSegments: options.radialSegments || 16,
            p: options.p || 2,  // Torus knot p parameter
            q: options.q || 3,  // Torus knot q parameter
            flowSpeed: options.flowSpeed || 0.5,
            opacity: options.opacity || 0.7,
            rotationSpeed: options.rotationSpeed || 0.1,
            showFibers: options.showFibers !== false,
            showCore: options.showCore !== false,
            ...options
        };
        
        // Animation state
        this.time = 0;
        
        // Build geometry
        this.createMainStructure();
        
        if (this.options.showFibers) {
            this.createFiberStrands();
        }
        
        if (this.options.showCore) {
            this.createCore();
        }
        
        this.name = 'HopfFibration';
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // MAIN STRUCTURE
    // ═══════════════════════════════════════════════════════════════════════
    
    createMainStructure() {
        const { radius, tube, tubularSegments, radialSegments, p, q } = this.options;
        
        // Torus knot represents the fibration structure
        const geometry = new THREE.TorusKnotGeometry(
            radius,
            tube,
            tubularSegments,
            radialSegments,
            p,
            q
        );
        
        // Custom shader material
        this.mainMaterial = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                flowSpeed: { value: this.options.flowSpeed },
                baseColor: { value: new THREE.Color(0x4ECDC4) }, // Flow (S8 base)
                fiberColor: { value: new THREE.Color(0x67D4E4) }, // Crystal (S7 fiber)
                opacity: { value: this.options.opacity },
                glowIntensity: { value: 1.5 },
                cameraPosition: { value: new THREE.Vector3() }
            },
            vertexShader: HopfVertexShader,
            fragmentShader: HopfFragmentShader,
            transparent: true,
            side: THREE.DoubleSide,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        
        this.mainMesh = new THREE.Mesh(geometry, this.mainMaterial);
        this.add(this.mainMesh);
        
        // Wireframe overlay for structure
        const wireframeMaterial = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            wireframe: true,
            transparent: true,
            opacity: 0.1
        });
        
        this.wireframe = new THREE.Mesh(geometry.clone(), wireframeMaterial);
        this.wireframe.scale.setScalar(1.01);
        this.add(this.wireframe);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FIBER STRANDS (7 distinct fibers for S7)
    // ═══════════════════════════════════════════════════════════════════════
    
    createFiberStrands() {
        this.fibers = [];
        
        // Create 7 thin fiber lines representing S7
        for (let i = 0; i < 7; i++) {
            const fiberPoints = this.generateFiberCurve(i);
            const fiberGeometry = new THREE.TubeGeometry(
                new THREE.CatmullRomCurve3(fiberPoints),
                64,
                0.05,
                8,
                true  // Closed curve
            );
            
            const colonyName = COLONY_ORDER[i];
            const fiberMaterial = new THREE.MeshBasicMaterial({
                color: getColonyColor(colonyName),
                transparent: true,
                opacity: 0.6,
                blending: THREE.AdditiveBlending
            });
            
            const fiber = new THREE.Mesh(fiberGeometry, fiberMaterial);
            fiber.userData = { colonyIndex: i, colonyName };
            
            this.add(fiber);
            this.fibers.push(fiber);
        }
    }
    
    generateFiberCurve(index) {
        const points = [];
        const segments = 64;
        const radius = this.options.radius * 0.8;
        const offset = (index / 7) * Math.PI * 2;
        
        for (let i = 0; i <= segments; i++) {
            const t = (i / segments) * Math.PI * 2;
            
            // Parametric curve on the torus that represents one fiber
            const phi = t + offset;
            const theta = t * 3 + offset * 2; // Wind around 3 times
            
            const x = (radius + Math.cos(theta) * 0.5) * Math.cos(phi);
            const y = Math.sin(theta) * 0.5;
            const z = (radius + Math.cos(theta) * 0.5) * Math.sin(phi);
            
            points.push(new THREE.Vector3(x, y, z));
        }
        
        return points;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CORE (Center represents the base point)
    // ═══════════════════════════════════════════════════════════════════════
    
    createCore() {
        // Glowing core sphere
        const coreGeometry = new THREE.SphereGeometry(0.3, 32, 32);
        const coreMaterial = new THREE.MeshBasicMaterial({
            color: 0xFFFFFF,
            transparent: true,
            opacity: 0.9
        });
        
        this.core = new THREE.Mesh(coreGeometry, coreMaterial);
        this.add(this.core);
        
        // Outer glow
        const glowGeometry = new THREE.SphereGeometry(0.5, 32, 32);
        const glowMaterial = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                color: { value: new THREE.Color(0x67D4E4) }
            },
            vertexShader: `
                varying vec3 vNormal;
                void main() {
                    vNormal = normalize(normalMatrix * normal);
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform float time;
                uniform vec3 color;
                varying vec3 vNormal;
                
                void main() {
                    float intensity = pow(0.7 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 2.0);
                    float pulse = 0.8 + 0.2 * sin(time * 3.0);
                    gl_FragColor = vec4(color * intensity * pulse, intensity * 0.6);
                }
            `,
            transparent: true,
            side: THREE.BackSide,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        
        this.coreGlow = new THREE.Mesh(glowGeometry, glowMaterial);
        this.add(this.coreGlow);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION UPDATE
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime, camera) {
        this.time += deltaTime;
        
        // Update main material uniforms
        if (this.mainMaterial.uniforms) {
            this.mainMaterial.uniforms.time.value = this.time;
            if (camera) {
                this.mainMaterial.uniforms.cameraPosition.value.copy(camera.position);
            }
        }
        
        // Update core glow
        if (this.coreGlow?.material?.uniforms) {
            this.coreGlow.material.uniforms.time.value = this.time;
        }
        
        // Rotate structure
        const rotSpeed = this.options.rotationSpeed;
        this.mainMesh.rotation.x = this.time * rotSpeed * 0.3;
        this.mainMesh.rotation.y = this.time * rotSpeed;
        
        this.wireframe.rotation.copy(this.mainMesh.rotation);
        
        // Animate fiber opacities
        if (this.fibers) {
            this.fibers.forEach((fiber, i) => {
                const phase = (i / 7) * Math.PI * 2;
                const pulse = 0.4 + 0.3 * Math.sin(this.time * 2 + phase);
                fiber.material.opacity = pulse;
                
                // Slight individual rotation
                fiber.rotation.y = this.time * rotSpeed + phase * 0.1;
            });
        }
        
        // Core pulse
        if (this.core) {
            const pulse = 1.0 + 0.1 * Math.sin(this.time * 3);
            this.core.scale.setScalar(pulse);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Set flow speed
     */
    setFlowSpeed(speed) {
        this.options.flowSpeed = speed;
        if (this.mainMaterial.uniforms) {
            this.mainMaterial.uniforms.flowSpeed.value = speed;
        }
    }
    
    /**
     * Highlight a specific fiber (colony)
     */
    highlightFiber(colonyIndex, highlight = true) {
        if (!this.fibers) return;
        
        this.fibers.forEach((fiber, i) => {
            if (i === colonyIndex) {
                fiber.material.opacity = highlight ? 1.0 : 0.6;
                fiber.scale.setScalar(highlight ? 1.2 : 1.0);
            } else {
                fiber.material.opacity = highlight ? 0.2 : 0.6;
            }
        });
    }
    
    /**
     * Reset fiber highlights
     */
    resetHighlights() {
        if (!this.fibers) return;
        
        this.fibers.forEach(fiber => {
            fiber.material.opacity = 0.6;
            fiber.scale.setScalar(1.0);
        });
    }
    
    /**
     * Set base and fiber colors
     */
    setColors(baseColor, fiberColor) {
        if (this.mainMaterial.uniforms) {
            if (baseColor) {
                this.mainMaterial.uniforms.baseColor.value.set(baseColor);
            }
            if (fiberColor) {
                this.mainMaterial.uniforms.fiberColor.value.set(fiberColor);
            }
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DISPOSAL
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        if (this.mainMesh) {
            this.mainMesh.geometry.dispose();
            this.mainMesh.material.dispose();
        }
        
        if (this.wireframe) {
            this.wireframe.geometry.dispose();
            this.wireframe.material.dispose();
        }
        
        if (this.fibers) {
            this.fibers.forEach(fiber => {
                fiber.geometry.dispose();
                fiber.material.dispose();
            });
        }
        
        if (this.core) {
            this.core.geometry.dispose();
            this.core.material.dispose();
        }
        
        if (this.coreGlow) {
            this.coreGlow.geometry.dispose();
            this.coreGlow.material.dispose();
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FACTORY FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

export function createHopfFibration(options = {}) {
    return new HopfFibration(options);
}

export default HopfFibration;
