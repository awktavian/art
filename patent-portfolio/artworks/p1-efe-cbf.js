/**
 * P1-001: EFE-CBF Safety Optimizer Artwork
 * ========================================
 * 
 * A Turrell-inspired immersive experience where visitors physically
 * enter the safety landscape. The entire installation bathes in
 * light that shifts from safety-green to danger-red based on h(x).
 * 
 * Inspired by:
 * - James Turrell's Skyspaces (light as medium)
 * - Olafur Eliasson's mono-frequency rooms
 * - Exploratorium's hands-on interactivity
 * 
 * Features:
 * - Light dome that responds to h(x) value
 * - Interactive agent placement (click to explore paths)
 * - Body immersion (visitor position affects nearby h(x))
 * - Danger fog rising from unsafe zones
 * - Floating EFE formula hologram
 * - Discovery reward at global optimum
 * 
 * h(x) ≥ 0 ALWAYS
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { PATENTS } from '../components/info-panel.js';

const PATENT = PATENTS.find(p => p.id === 'P1-001');

// Color palette - FILM QUALITY (colony-derived, less saturated)
const COLORS = {
    safe: new THREE.Color(0x6FA370),      // Grove green (refined)
    caution: new THREE.Color(0xE8940A),   // Beacon amber (refined)
    danger: new THREE.Color(0xE85A2F),    // Spark red (refined)
    crystal: new THREE.Color(0x5BC4D4),   // Crystal blue (refined)
    grove: new THREE.Color(0x7EB77F)      // Grove green
};

export class EFECBFArtwork extends THREE.Group {
    constructor() {
        super();
        this.name = 'artwork-efe-cbf';
        this.time = 0;
        
        // Interactive state
        this.agentPosition = new THREE.Vector3(0, 1.5, 0);
        this.currentHx = 1.0;
        this.discoveredOptimum = false;
        this.visitorInfluence = new THREE.Vector3();
        
        // Animation state
        this.heartbeatPhase = 0;
        this.dangerFogIntensity = 0;
        
        // Raycasting for interaction
        this.raycaster = new THREE.Raycaster();
        this.interactiveObjects = [];
        
        this.create();
    }
    
    create() {
        // === IMMERSIVE FOUNDATION ===
        this.createLightDome();
        this.createDecisionLandscape();
        
        // === INTERACTIVE ELEMENTS ===
        this.createAgentMarker();
        this.createSafePaths();
        this.createContourLines();
        
        // === ATMOSPHERIC EFFECTS ===
        this.createDangerFog();
        this.createEFEParticles();
        
        // === INFORMATION ===
        this.createFormulaHologram();
        this.createPlaque();
        
        // === DISCOVERY ===
        this.createOptimumReward();
        
        // Mark interactive
        this.userData.interactive = true;
        this.userData.artwork = PATENT;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // TURRELL-INSPIRED LIGHT DOME
    // ═══════════════════════════════════════════════════════════════════════
    
    createLightDome() {
        // Large dome that encompasses the entire installation
        // Color shifts based on current h(x) value
        
        const domeGeo = new THREE.SphereGeometry(8, 64, 32, 0, Math.PI * 2, 0, Math.PI / 2);
        
        this.domeMaterial = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                hxValue: { value: 1.0 },
                safeColor: { value: COLORS.safe },
                cautionColor: { value: COLORS.caution },
                dangerColor: { value: COLORS.danger },
                heartbeat: { value: 0 }
            },
            vertexShader: `
                varying vec3 vPosition;
                varying vec3 vNormal;
                varying vec2 vUv;
                
                void main() {
                    vPosition = position;
                    vNormal = normal;
                    vUv = uv;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform float time;
                uniform float hxValue;
                uniform vec3 safeColor;
                uniform vec3 cautionColor;
                uniform vec3 dangerColor;
                uniform float heartbeat;
                
                varying vec3 vPosition;
                varying vec3 vNormal;
                varying vec2 vUv;
                
                void main() {
                    // Calculate color based on h(x)
                    vec3 color;
                    if (hxValue > 0.5) {
                        color = mix(cautionColor, safeColor, (hxValue - 0.5) * 2.0);
                    } else {
                        color = mix(dangerColor, cautionColor, hxValue * 2.0);
                    }
                    
                    // Height-based intensity (brighter at top like Skyspace)
                    float heightGradient = smoothstep(0.0, 6.0, vPosition.y);
                    
                    // Breathing/heartbeat pulse
                    float pulse = 1.0 + heartbeat * 0.3;
                    
                    // Fresnel glow at edges
                    float fresnel = pow(1.0 - abs(dot(normalize(vNormal), vec3(0.0, -1.0, 0.0))), 1.5);
                    
                    // Gentle wave pattern
                    float wave = sin(vPosition.y * 2.0 + time * 0.5) * 0.1 + 0.9;
                    
                    float intensity = heightGradient * pulse * wave * 0.6;
                    float alpha = (0.15 + fresnel * 0.3) * intensity;
                    
                    gl_FragColor = vec4(color, alpha);
                }
            `,
            transparent: true,
            side: THREE.BackSide,
            depthWrite: false,
            blending: THREE.AdditiveBlending
        });
        
        this.lightDome = new THREE.Mesh(domeGeo, this.domeMaterial);
        this.lightDome.position.y = 0;
        this.add(this.lightDome);
        
        // Inner glow sphere for softer light
        const innerGlowGeo = new THREE.SphereGeometry(5, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2);
        const innerGlowMat = new THREE.MeshBasicMaterial({
            color: COLORS.safe,
            transparent: true,
            opacity: 0.05,
            side: THREE.BackSide,
            blending: THREE.AdditiveBlending
        });
        this.innerGlow = new THREE.Mesh(innerGlowGeo, innerGlowMat);
        this.add(this.innerGlow);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTIVE DECISION LANDSCAPE
    // ═══════════════════════════════════════════════════════════════════════
    
    createDecisionLandscape() {
        // 3D terrain representing h(x) - the safety function
        
        const size = 10;
        const segments = 80;
        const geometry = new THREE.PlaneGeometry(size, size, segments, segments);
        
        const positions = geometry.attributes.position.array;
        const colors = new Float32Array(positions.length);
        const uvs = geometry.attributes.uv.array;
        
        for (let i = 0; i < positions.length; i += 3) {
            const x = positions[i];
            const z = positions[i + 1];
            
            const hx = this.calculateHx(x, z);
            positions[i + 2] = hx * 2; // Scale height
            
            // Color gradient: green (safe) -> amber -> red (danger)
            this.setVertexColor(colors, i, hx);
        }
        
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geometry.computeVertexNormals();
        
        // Store reference for dynamic updates
        this.landscapeGeometry = geometry;
        this.landscapeColors = colors;
        
        const material = new THREE.MeshPhysicalMaterial({
            vertexColors: true,
            metalness: 0.4,
            roughness: 0.5,
            clearcoat: 0.3,
            clearcoatRoughness: 0.2,
            side: THREE.DoubleSide,
            transparent: true,
            opacity: 0.9,
            envMapIntensity: 0.5
        });
        
        this.landscape = new THREE.Mesh(geometry, material);
        this.landscape.rotation.x = -Math.PI / 2;
        this.landscape.position.y = 0.5;
        this.landscape.receiveShadow = true;
        this.landscape.userData.interactive = true;
        this.interactiveObjects.push(this.landscape);
        this.add(this.landscape);
        
        // Wireframe overlay for depth perception
        const wireframeMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            wireframe: true,
            transparent: true,
            opacity: 0.15
        });
        const wireframe = new THREE.Mesh(geometry.clone(), wireframeMat);
        wireframe.rotation.x = -Math.PI / 2;
        wireframe.position.y = 0.51;
        this.add(wireframe);
    }
    
    /**
     * Control Barrier Function h(x)
     * 
     * Based on kagami/core/safety/cbf/jax_optimal.py:LearnedBarrierFunction
     * 
     * Architecture: Linear baseline + risk aggregation
     *   h(x) = w_base · ||x|| + Σ w_i · risk_i(x)
     * 
     * Semantics:
     *   h(x) > 0: Safe (far from danger)
     *   h(x) = 0: On safety boundary
     *   h(x) < 0: Unsafe (violation!)
     * 
     * The guarantee: h(x) ≥ 0 ALWAYS (in deployment mode)
     */
    calculateHx(x, z) {
        // State vector (simplified 2D version for visualization)
        const state = { x, z };
        
        // === RISK FACTOR 1: Boundary proximity ===
        // Risk increases as we approach the edges
        const maxRadius = 4.5;
        const dist = Math.sqrt(x * x + z * z);
        const boundaryRisk = Math.max(0, (dist / maxRadius) - 0.3);
        
        // === RISK FACTOR 2: Obstacle regions ===
        // Define dangerous regions (obstacles)
        const obstacles = [
            { x: 2.5, z: 2.5, radius: 1.0 },   // Obstacle 1
            { x: -3.0, z: 1.5, radius: 0.8 },  // Obstacle 2
            { x: 1.0, z: -2.5, radius: 0.7 }   // Obstacle 3
        ];
        
        let obstacleRisk = 0;
        obstacles.forEach(obs => {
            const obsDistance = Math.sqrt((x - obs.x) ** 2 + (z - obs.z) ** 2);
            const penetration = Math.max(0, obs.radius - obsDistance);
            obstacleRisk += penetration / obs.radius;
        });
        
        // === RISK FACTOR 3: Velocity constraint (implicit) ===
        // Higher risk in narrow passages
        const passageRisk = Math.abs(Math.sin(x * 0.8) * Math.cos(z * 0.8)) * 0.1;
        
        // === LEARNED RISK WEIGHTS (from neural network) ===
        // These would be learned during training
        const w_boundary = 1.2;
        const w_obstacle = 2.0;
        const w_passage = 0.5;
        
        // === LINEAR BASELINE ===
        // Safe in center, decays outward
        const linearBaseline = 1.0 - dist * 0.15;
        
        // === AGGREGATE h(x) ===
        // h(x) = baseline - weighted_sum(risks)
        const totalRisk = w_boundary * boundaryRisk + 
                         w_obstacle * obstacleRisk + 
                         w_passage * passageRisk;
        
        const hx = linearBaseline - totalRisk;
        
        // h(x) can be negative (unsafe) - that's the point!
        // The CBF constraint ensures we never go there.
        return Math.max(-0.5, Math.min(1.0, hx));
    }
    
    /**
     * Compute Expected Free Energy G(π) at a point
     * Based on kagami/core/active_inference/jax_efe_cbf_optimizer.py
     * 
     * G(π) = epistemic_value + pragmatic_value + risk_value + catastrophe_value
     */
    calculateEFE(x, z) {
        const hx = this.calculateHx(x, z);
        
        // Epistemic value: Information gain (exploration bonus)
        // Higher in unexplored/uncertain areas
        const uncertainty = Math.exp(-((x * x + z * z) / 8));
        const epistemic = -uncertainty * 0.3; // Negative = good (minimize)
        
        // Pragmatic value: Goal achievement
        // Lower at the goal (center)
        const goalDist = Math.sqrt(x * x + z * z);
        const pragmatic = goalDist * 0.2;
        
        // Risk value: CBF violation penalty
        // λ * max(0, -h(x))
        const lambda = 10.0; // Penalty weight
        const risk = lambda * Math.max(0, -hx);
        
        // Catastrophe value: Severe consequence areas
        const catastrophe = hx < 0 ? 5.0 : 0;
        
        return {
            total: epistemic + pragmatic + risk + catastrophe,
            epistemic,
            pragmatic,
            risk,
            catastrophe,
            hx
        };
    }
    
    setVertexColor(colors, index, hx) {
        // Map h(x) value to color gradient
        let r, g, b;
        
        if (hx > 0.6) {
            // Safe zone: green
            const t = (hx - 0.6) / 0.4;
            r = 0.1 * (1 - t);
            g = 0.7 + 0.3 * t;
            b = 0.3 + 0.2 * t;
        } else if (hx > 0.3) {
            // Caution zone: amber
            const t = (hx - 0.3) / 0.3;
            r = 1.0 - 0.2 * t;
            g = 0.5 + 0.2 * t;
            b = 0.1 + 0.2 * t;
        } else {
            // Danger zone: red
            const t = hx / 0.3;
            r = 0.8 + 0.2 * (1 - t);
            g = 0.1 + 0.4 * t;
            b = 0.1;
        }
        
        colors[index] = r;
        colors[index + 1] = g;
        colors[index + 2] = b;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTIVE AGENT MARKER
    // ═══════════════════════════════════════════════════════════════════════
    
    createAgentMarker() {
        // Visual marker for the "agent" position that visitors can place
        
        const group = new THREE.Group();
        group.name = 'agent-marker';
        
        // Main sphere
        const sphereGeo = new THREE.SphereGeometry(0.2, 32, 32);
        const sphereMat = new THREE.MeshPhysicalMaterial({
            color: 0x67D4E4,
            emissive: 0x67D4E4,
            emissiveIntensity: 0.5,
            metalness: 0.8,
            roughness: 0.2,
            clearcoat: 1.0
        });
        const sphere = new THREE.Mesh(sphereGeo, sphereMat);
        group.add(sphere);
        
        // Glowing halo
        const haloGeo = new THREE.RingGeometry(0.25, 0.4, 32);
        const haloMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.5,
            side: THREE.DoubleSide,
            blending: THREE.AdditiveBlending
        });
        const halo = new THREE.Mesh(haloGeo, haloMat);
        halo.rotation.x = -Math.PI / 2;
        group.add(halo);
        
        // Vertical light beam
        const beamGeo = new THREE.CylinderGeometry(0.02, 0.1, 3, 8, 1, true);
        const beamMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.3,
            blending: THREE.AdditiveBlending
        });
        const beam = new THREE.Mesh(beamGeo, beamMat);
        beam.position.y = 1.5;
        group.add(beam);
        
        this.agentMarker = group;
        this.agentMarker.position.copy(this.agentPosition);
        this.add(this.agentMarker);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SAFE PATH VISUALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    createSafePaths() {
        // Glowing lines showing gradient descent toward safety
        
        this.pathLines = new THREE.Group();
        this.pathLines.name = 'safe-paths';
        
        // Will be populated when agent is placed
        this.updateSafePaths();
        this.add(this.pathLines);
    }
    
    updateSafePaths() {
        // Clear existing paths
        while (this.pathLines.children.length > 0) {
            const child = this.pathLines.children[0];
            if (child.geometry) child.geometry.dispose();
            if (child.material) child.material.dispose();
            this.pathLines.remove(child);
        }
        
        // Generate paths from agent position
        const startX = this.agentPosition.x;
        const startZ = this.agentPosition.z;
        
        // Create 8 paths in different directions
        const numPaths = 8;
        for (let i = 0; i < numPaths; i++) {
            const angle = (i / numPaths) * Math.PI * 2;
            const path = this.calculateGradientPath(
                startX + Math.cos(angle) * 0.5,
                startZ + Math.sin(angle) * 0.5,
                30
            );
            
            if (path.length > 2) {
                const curve = new THREE.CatmullRomCurve3(path);
                const tubeGeo = new THREE.TubeGeometry(curve, 32, 0.03, 8, false);
                
                // Color based on safety - using refined colony colors
                const endHx = this.calculateHx(path[path.length - 1].x, path[path.length - 1].z);
                const color = endHx > 0.5 ? 0x6FA370 : (endHx > 0.2 ? 0xE8940A : 0xE85A2F);
                
                const tubeMat = new THREE.MeshBasicMaterial({
                    color: color,
                    transparent: true,
                    opacity: 0.4,
                    blending: THREE.AdditiveBlending
                });
                
                const tube = new THREE.Mesh(tubeGeo, tubeMat);
                this.pathLines.add(tube);
            }
        }
    }
    
    calculateGradientPath(startX, startZ, steps) {
        const path = [];
        let x = startX;
        let z = startZ;
        const stepSize = 0.15;
        
        for (let i = 0; i < steps; i++) {
            const hx = this.calculateHx(x, z);
            const y = 0.5 + hx * 2 + 0.1; // Above landscape
            path.push(new THREE.Vector3(x, y, z));
            
            // Calculate gradient (toward higher h(x))
            const eps = 0.1;
            const dhdx = (this.calculateHx(x + eps, z) - this.calculateHx(x - eps, z)) / (2 * eps);
            const dhdz = (this.calculateHx(x, z + eps) - this.calculateHx(x, z - eps)) / (2 * eps);
            
            // Move in gradient direction
            const gradMag = Math.sqrt(dhdx * dhdx + dhdz * dhdz) + 0.001;
            x += (dhdx / gradMag) * stepSize;
            z += (dhdz / gradMag) * stepSize;
            
            // Stop if we've reached safety or edge
            if (hx > 0.9 || Math.abs(x) > 4.5 || Math.abs(z) > 4.5) break;
        }
        
        return path;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CONTOUR LINES (h(x) = constant)
    // ═══════════════════════════════════════════════════════════════════════
    
    createContourLines() {
        const contours = new THREE.Group();
        contours.name = 'contour-lines';
        
        const thresholds = [0.1, 0.3, 0.5, 0.7, 0.9];
        // Refined colony-based gradient (Spark red → Beacon amber → Grove green)
        const contourColors = [0xE85A2F, 0xE87830, 0xE8940A, 0x9CB55A, 0x6FA370];
        
        thresholds.forEach((threshold, idx) => {
            const points = this.generateContour(threshold);
            if (points.length > 2) {
                const curve = new THREE.CatmullRomCurve3(points, true);
                const curvePoints = curve.getPoints(100);
                const lineGeo = new THREE.BufferGeometry().setFromPoints(curvePoints);
                
                const lineMat = new THREE.LineBasicMaterial({
                    color: contourColors[idx],
                    transparent: true,
                    opacity: 0.5,
                    linewidth: 2
                });
                
                const line = new THREE.Line(lineGeo, lineMat);
                contours.add(line);
            }
        });
        
        this.contours = contours;
        this.add(contours);
        
        // === PROMINENT SAFETY BARRIER AT h(x) = 0 ===
        this.createSafetyBarrier();
    }
    
    /**
     * Create a visible, glowing barrier wall at h(x) = 0
     * This is THE CORE PRINCIPLE: the barrier is UNBREAKABLE
     */
    createSafetyBarrier() {
        const barrierGroup = new THREE.Group();
        barrierGroup.name = 'safety-barrier';
        
        // Generate barrier contour at h(x) = 0 (slightly positive for visibility)
        const barrierPoints = this.generateContour(0.0);
        
        if (barrierPoints.length > 3) {
            // Create glowing wall segments along the barrier
            const curve = new THREE.CatmullRomCurve3(barrierPoints, true);
            const curvePoints = curve.getPoints(200);
            
            // Main barrier tube - visible wall
            const tubeGeo = new THREE.TubeGeometry(curve, 200, 0.12, 16, true);
            const tubeMat = new THREE.MeshPhysicalMaterial({
                color: 0xE85A2F,
                emissive: 0xFF4422,
                emissiveIntensity: 0.8,
                metalness: 0.6,
                roughness: 0.3,
                clearcoat: 1.0,
                transparent: true,
                opacity: 0.9
            });
            
            const barrier = new THREE.Mesh(tubeGeo, tubeMat);
            barrierGroup.add(barrier);
            this.barrierMesh = barrier;
            
            // Outer glow (larger, more transparent)
            const glowGeo = new THREE.TubeGeometry(curve, 200, 0.25, 8, true);
            const glowMat = new THREE.MeshBasicMaterial({
                color: 0xFF3300,
                transparent: true,
                opacity: 0.25,
                blending: THREE.NormalBlending
            });
            const glow = new THREE.Mesh(glowGeo, glowMat);
            barrierGroup.add(glow);
            
            // Pulsing inner core
            const coreGeo = new THREE.TubeGeometry(curve, 200, 0.05, 8, true);
            const coreMat = new THREE.MeshBasicMaterial({
                color: 0xFFFFFF,
                transparent: true,
                opacity: 0.6
            });
            const core = new THREE.Mesh(coreGeo, coreMat);
            barrierGroup.add(core);
            this.barrierCore = core;
            
            // Add vertical barrier posts for visibility
            for (let i = 0; i < curvePoints.length; i += 20) {
                const p = curvePoints[i];
                const postGeo = new THREE.CylinderGeometry(0.03, 0.03, 1.5, 8);
                const postMat = new THREE.MeshPhysicalMaterial({
                    color: 0xE85A2F,
                    emissive: 0xE85A2F,
                    emissiveIntensity: 0.4,
                    metalness: 0.8,
                    roughness: 0.2
                });
                const post = new THREE.Mesh(postGeo, postMat);
                post.position.set(p.x, p.y + 0.75, p.z);
                barrierGroup.add(post);
            }
        }
        
        // Add "h(x) = 0" floating label at one point
        this.createBarrierLabel(barrierGroup);
        
        this.safetyBarrier = barrierGroup;
        this.add(barrierGroup);
    }
    
    createBarrierLabel(parent) {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 128;
        const ctx = canvas.getContext('2d');
        
        // Dark background with red accent
        ctx.fillStyle = '#1a0505';
        ctx.fillRect(0, 0, 512, 128);
        ctx.fillStyle = '#E85A2F';
        ctx.fillRect(0, 0, 8, 128);
        
        // Text
        ctx.fillStyle = '#FF6644';
        ctx.font = 'bold 48px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('h(x) = 0', 256, 50);
        
        ctx.fillStyle = '#CC8866';
        ctx.font = '24px "IBM Plex Mono", monospace';
        ctx.fillText('SAFETY BARRIER', 256, 95);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(2.0, 0.5);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.set(0, 2.5, -4);
        label.rotation.y = Math.PI / 6;
        label.userData.billboard = true;
        parent.add(label);
        this.barrierLabel = label;
    }
    
    generateContour(threshold) {
        // Simplified marching squares for contour generation
        const points = [];
        const steps = 60;
        
        // Sample around the center in a spiral
        for (let i = 0; i < steps; i++) {
            const t = i / steps;
            const radius = 1 + t * 3.5;
            const angle = t * Math.PI * 8;
            
            const x = Math.cos(angle) * radius;
            const z = Math.sin(angle) * radius;
            const hx = this.calculateHx(x, z);
            
            if (Math.abs(hx - threshold) < 0.08) {
                const y = 0.52 + hx * 2;
                points.push(new THREE.Vector3(x, y, z));
            }
        }
        
        return points;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DANGER FOG
    // ═══════════════════════════════════════════════════════════════════════
    
    createDangerFog() {
        // Volumetric fog that rises from dangerous zones
        
        const fogParticleCount = 500;
        const positions = new Float32Array(fogParticleCount * 3);
        const colors = new Float32Array(fogParticleCount * 3);
        const sizes = new Float32Array(fogParticleCount);
        
        for (let i = 0; i < fogParticleCount; i++) {
            // Position in outer (dangerous) areas
            const angle = Math.random() * Math.PI * 2;
            const radius = 3 + Math.random() * 2;
            
            positions[i * 3] = Math.cos(angle) * radius;
            positions[i * 3 + 1] = Math.random() * 1.5;
            positions[i * 3 + 2] = Math.sin(angle) * radius;
            
            // Red fog color
            colors[i * 3] = 1.0;
            colors[i * 3 + 1] = 0.2 + Math.random() * 0.2;
            colors[i * 3 + 2] = 0.1;
            
            sizes[i] = 0.3 + Math.random() * 0.3;
        }
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
        
        const material = new THREE.PointsMaterial({
            size: 0.4,
            vertexColors: true,
            transparent: true,
            opacity: 0.15,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        
        this.dangerFog = new THREE.Points(geometry, material);
        this.add(this.dangerFog);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // EFE FLOW PARTICLES
    // ═══════════════════════════════════════════════════════════════════════
    
    createEFEParticles() {
        const particleCount = 300;
        const geometry = new THREE.BufferGeometry();
        
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        const velocities = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            const theta = Math.random() * Math.PI * 2;
            const r = Math.random() * 4;
            
            positions[i * 3] = Math.cos(theta) * r;
            positions[i * 3 + 1] = Math.random() * 3 + 0.5;
            positions[i * 3 + 2] = Math.sin(theta) * r;
            
            // Gradient color: crystal blue to grove green
            const t = Math.random();
            colors[i * 3] = 0.4 * (1 - t) + 0.5 * t;
            colors[i * 3 + 1] = 0.83 * (1 - t) + 0.72 * t;
            colors[i * 3 + 2] = 0.89 * (1 - t) + 0.5 * t;
            
            velocities[i * 3] = 0;
            velocities[i * 3 + 1] = 0;
            velocities[i * 3 + 2] = 0;
        }
        
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        this.particleVelocities = velocities;
        
        const material = new THREE.PointsMaterial({
            size: 0.06,
            vertexColors: true,
            transparent: true,
            opacity: 0.7,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        
        this.particles = new THREE.Points(geometry, material);
        this.add(this.particles);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FORMULA HOLOGRAM
    // ═══════════════════════════════════════════════════════════════════════
    
    createFormulaHologram() {
        const group = new THREE.Group();
        group.name = 'formula-hologram';
        
        // Main formula canvas - larger for more detail
        const canvas = document.createElement('canvas');
        canvas.width = 1024;
        canvas.height = 320;
        const ctx = canvas.getContext('2d');
        
        this.formulaCanvas = canvas;
        this.formulaCtx = ctx;
        this.updateFormula();
        
        const texture = new THREE.CanvasTexture(canvas);
        this.formulaTexture = texture;
        
        const planeGeo = new THREE.PlaneGeometry(5, 1.5625);
        const planeMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide,
            blending: THREE.AdditiveBlending,
            depthWrite: false
        });
        
        const plane = new THREE.Mesh(planeGeo, planeMat);
        group.add(plane);
        
        // Holographic glow behind formula
        const glowGeo = new THREE.PlaneGeometry(5.3, 1.8);
        const glowMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.1,
            side: THREE.DoubleSide,
            blending: THREE.AdditiveBlending
        });
        const glow = new THREE.Mesh(glowGeo, glowMat);
        glow.position.z = -0.01;
        group.add(glow);
        
        this.formulaHologram = group;
        this.formulaHologram.position.set(0, 5, 0);
        this.add(this.formulaHologram);
        
        // === CBF-QP SIDE PANEL ===
        this.createCBFQPDisplay();
        
        // === EFE COMPONENTS PANEL ===
        this.createEFEComponentsDisplay();
    }
    
    createCBFQPDisplay() {
        // Side panel showing CBF-QP constraint (deployment mode)
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 384;
        const ctx = canvas.getContext('2d');
        
        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
        ctx.roundRect(10, 10, 492, 364, 10);
        ctx.fill();
        
        // Title
        ctx.fillStyle = '#FFD700';
        ctx.font = 'bold 24px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('CBF-QP (Deployment)', 256, 50);
        
        // QP formulation
        ctx.fillStyle = '#FFFFFF';
        ctx.font = '18px "IBM Plex Mono", monospace';
        ctx.fillText('min ||u − u_nom||²', 256, 100);
        
        ctx.fillStyle = '#5BC4D4';  // Crystal cyan (refined)
        ctx.font = '16px "IBM Plex Mono", monospace';
        ctx.fillText('subject to:', 256, 135);
        
        ctx.fillStyle = '#6FA370';  // Grove green (safety)
        ctx.font = '18px "IBM Plex Mono", monospace';
        ctx.fillText('L_f h + L_g h·u + α(h) ≥ 0', 256, 170);
        
        // Explanation
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Sans", sans-serif';
        ctx.fillText('L_f h: Lie derivative along drift', 256, 220);
        ctx.fillText('L_g h: Lie derivative along control', 256, 245);
        ctx.fillText('α(h): Class-K function (α·h)', 256, 270);
        
        // Guarantee box
        ctx.strokeStyle = '#6FA370';  // Grove green
        ctx.lineWidth = 2;
        ctx.roundRect(50, 295, 412, 55, 5);
        ctx.stroke();
        
        ctx.fillStyle = '#6FA370';  // Grove green
        ctx.font = 'bold 18px "IBM Plex Sans", sans-serif';
        ctx.fillText('Mathematical Guarantee:', 256, 320);
        ctx.font = 'bold 20px "IBM Plex Mono", monospace';
        ctx.fillText('h(x(t)) ≥ 0  ∀t ≥ 0', 256, 345);
        
        const texture = new THREE.CanvasTexture(canvas);
        const geo = new THREE.PlaneGeometry(2.5, 1.875);
        const mat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        const panel = new THREE.Mesh(geo, mat);
        panel.position.set(-4.5, 3.5, 0);
        panel.rotation.y = Math.PI / 6;
        this.add(panel);
    }
    
    createEFEComponentsDisplay() {
        // Side panel showing EFE component breakdown
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 384;
        this.efeCanvas = canvas;
        this.efeCtx = canvas.getContext('2d');
        
        this.updateEFEDisplay();
        
        const texture = new THREE.CanvasTexture(canvas);
        this.efeTexture = texture;
        
        const geo = new THREE.PlaneGeometry(2.5, 1.875);
        const mat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        this.efePanel = new THREE.Mesh(geo, mat);
        this.efePanel.position.set(4.5, 3.5, 0);
        this.efePanel.rotation.y = -Math.PI / 6;
        this.add(this.efePanel);
    }
    
    updateEFEDisplay() {
        if (!this.efeCtx) return;
        const ctx = this.efeCtx;
        
        ctx.clearRect(0, 0, 512, 384);
        
        // Calculate current EFE components
        const efe = this.calculateEFE(this.agentPosition.x, this.agentPosition.z);
        
        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
        ctx.roundRect(10, 10, 492, 364, 10);
        ctx.fill();
        
        // Title
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 24px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('EFE Components', 256, 50);
        
        // Component bars
        const components = [
            { name: 'Epistemic', value: efe.epistemic, color: '#9B7EBD', desc: 'Information gain' },
            { name: 'Pragmatic', value: efe.pragmatic, color: '#4ECDC4', desc: 'Goal distance' },
            { name: 'Risk λ·max(0,−h)', value: efe.risk, color: '#FF6B35', desc: 'CBF penalty' },
            { name: 'Catastrophe', value: efe.catastrophe, color: '#FF2222', desc: 'Severe violation' }
        ];
        
        let y = 90;
        components.forEach(comp => {
            // Label
            ctx.fillStyle = comp.color;
            ctx.font = 'bold 16px "IBM Plex Sans", sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(comp.name, 30, y);
            
            // Value
            ctx.textAlign = 'right';
            ctx.fillText(comp.value.toFixed(3), 480, y);
            
            // Bar
            const barWidth = Math.min(300, Math.abs(comp.value) * 100);
            ctx.fillStyle = comp.color;
            ctx.globalAlpha = 0.6;
            ctx.fillRect(30, y + 8, barWidth, 16);
            ctx.globalAlpha = 1.0;
            
            // Description
            ctx.fillStyle = '#666666';
            ctx.font = '12px "IBM Plex Sans", sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(comp.desc, 30, y + 38);
            
            y += 65;
        });
        
        // Total
        ctx.strokeStyle = '#67D4E4';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(30, y);
        ctx.lineTo(480, y);
        ctx.stroke();
        
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 20px "IBM Plex Mono", monospace';
        ctx.textAlign = 'left';
        ctx.fillText('G(π) =', 30, y + 30);
        ctx.textAlign = 'right';
        ctx.fillText(efe.total.toFixed(3), 480, y + 30);
        
        if (this.efeTexture) {
            this.efeTexture.needsUpdate = true;
        }
    }
    
    updateFormula() {
        const ctx = this.formulaCtx;
        ctx.clearRect(0, 0, 1024, 256);
        
        // Background glow
        const gradient = ctx.createRadialGradient(512, 128, 0, 512, 128, 512);
        gradient.addColorStop(0, 'rgba(103, 212, 228, 0.2)');
        gradient.addColorStop(1, 'rgba(103, 212, 228, 0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, 1024, 256);
        
        // === CONSTRAINED OPTIMIZATION FORMULA ===
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 32px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        // Main optimization problem
        ctx.fillText('π* = argmin G(π)  s.t.  h(x_π) ≥ 0', 512, 45);
        
        // EFE decomposition
        ctx.fillStyle = '#9E9994';
        ctx.font = '22px "IBM Plex Mono", monospace';
        ctx.fillText('G = epistemic + pragmatic + λ·max(0, −h) + catastrophe', 512, 85);
        
        // === CURRENT h(x) VALUE === (Colony-based status colors)
        const hxColor = this.currentHx > 0.3 ? '#6FA370' : (this.currentHx > 0 ? '#E8940A' : '#E85A2F');
        ctx.fillStyle = hxColor;
        ctx.font = 'bold 56px "IBM Plex Mono", monospace';
        ctx.fillText(`h(x) = ${this.currentHx.toFixed(3)}`, 512, 155);
        
        // === STATUS INDICATOR ===
        if (this.currentHx > 0) {
            ctx.fillStyle = '#6FA370';  // Grove green (safe)
            ctx.font = 'bold 28px "IBM Plex Mono", monospace';
            ctx.fillText('✓ SAFE: h(x) > 0', 512, 210);
        } else {
            ctx.fillStyle = '#E85A2F';  // Spark red (danger)
            ctx.font = 'bold 28px "IBM Plex Mono", monospace';
            ctx.fillText('⚠ VIOLATION: h(x) < 0', 512, 210);
        }
        
        // Constraint guarantee
        ctx.fillStyle = '#5BC4D4';  // Crystal cyan (refined)
        ctx.font = '20px "IBM Plex Sans", sans-serif';
        ctx.fillText('CBF Guarantee: h(x) ≥ 0 always (deployment mode)', 512, 242);
        
        if (this.formulaTexture) {
            this.formulaTexture.needsUpdate = true;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // OPTIMUM DISCOVERY REWARD
    // ═══════════════════════════════════════════════════════════════════════
    
    createOptimumReward() {
        // Hidden celebration at the global optimum (0, 0)
        
        const group = new THREE.Group();
        group.name = 'optimum-reward';
        group.visible = false;
        
        // Golden sphere
        const sphereGeo = new THREE.SphereGeometry(0.3, 32, 32);
        const sphereMat = new THREE.MeshPhysicalMaterial({
            color: 0xFFD700,
            emissive: 0xFFD700,
            emissiveIntensity: 1.0,
            metalness: 1.0,
            roughness: 0.1
        });
        const sphere = new THREE.Mesh(sphereGeo, sphereMat);
        group.add(sphere);
        
        // Celebration particles
        const celebrationGeo = new THREE.BufferGeometry();
        const celebCount = 100;
        const celebPositions = new Float32Array(celebCount * 3);
        const celebColors = new Float32Array(celebCount * 3);
        
        for (let i = 0; i < celebCount; i++) {
            celebPositions[i * 3] = (Math.random() - 0.5) * 3;
            celebPositions[i * 3 + 1] = Math.random() * 4;
            celebPositions[i * 3 + 2] = (Math.random() - 0.5) * 3;
            
            // Gold/white particles
            celebColors[i * 3] = 1.0;
            celebColors[i * 3 + 1] = 0.84 + Math.random() * 0.16;
            celebColors[i * 3 + 2] = Math.random() * 0.5;
        }
        
        celebrationGeo.setAttribute('position', new THREE.BufferAttribute(celebPositions, 3));
        celebrationGeo.setAttribute('color', new THREE.BufferAttribute(celebColors, 3));
        
        const celebMat = new THREE.PointsMaterial({
            size: 0.1,
            vertexColors: true,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending
        });
        
        const celebration = new THREE.Points(celebrationGeo, celebMat);
        group.add(celebration);
        
        this.optimumReward = group;
        this.optimumReward.position.set(0, 1.5, 0);
        this.add(this.optimumReward);
    }
    
    triggerOptimumCelebration() {
        if (this.discoveredOptimum) return;
        this.discoveredOptimum = true;
        
        console.log('🎉 OPTIMAL POINT DISCOVERED! h(x) maximized!');
        
        this.optimumReward.visible = true;
        
        // Animate celebration
        const startTime = this.time;
        this.celebrationStartTime = startTime;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PLAQUE
    // ═══════════════════════════════════════════════════════════════════════
    
    createPlaque() {
        if (PATENT) {
            const plaque = createPlaque(PATENT, { width: 3, height: 2 });
            plaque.position.set(0, 1.2, 5);
            plaque.rotation.x = -0.1;
            this.add(plaque);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    onClick(intersection) {
        // Place agent at clicked point on landscape
        const point = intersection?.point;
        if (point) {
            this.agentPosition.set(point.x, point.y + 0.3, point.z);
            this.agentMarker.position.copy(this.agentPosition);
            
            // Update h(x) at new position
            this.currentHx = this.calculateHx(point.x, point.z);
            this.updateFormula();
            this.updateSafePaths();
            
            // Check for optimum discovery
            const distFromOptimum = Math.sqrt(point.x * point.x + point.z * point.z);
            if (distFromOptimum < 0.5 && this.currentHx > 0.8) {
                this.triggerOptimumCelebration();
            }
        }
    }
    
    // Alias for backward compatibility
    handleClick(point) {
        this.onClick({ point });
    }
    
    setVisitorPosition(position) {
        // Called with visitor's camera position for body immersion effect
        this.visitorInfluence.set(position.x, 0, position.z);
        
        // Calculate h(x) at visitor position for embodied feedback
        const visitorHx = this.calculateHx(position.x, position.z);
        
        // Update dome color based on where visitor is standing
        if (this.domeMaterial) {
            // Blend between agent's h(x) and visitor's h(x)
            this.currentHx = this.currentHx * 0.7 + visitorHx * 0.3;
        }
        
        // Trigger warning if visitor approaches danger zone
        if (visitorHx < 0.2 && !this.visitorWarningActive) {
            this.triggerVisitorWarning();
        } else if (visitorHx >= 0.3) {
            this.clearVisitorWarning();
        }
    }
    
    triggerVisitorWarning() {
        this.visitorWarningActive = true;
        console.log('⚠️ Visitor approaching safety boundary!');
        
        // Intensify dome pulsing
        if (this.domeMaterial) {
            this.domeMaterial.uniforms.heartbeat.value = 1.0;
        }
    }
    
    clearVisitorWarning() {
        this.visitorWarningActive = false;
    }
    
    // Update landscape with visitor proximity effect
    updateLandscapeWithVisitor() {
        if (!this.landscapeGeometry || !this.visitorInfluence) return;
        
        const positions = this.landscapeGeometry.attributes.position.array;
        const colors = this.landscapeColors;
        const visitorX = this.visitorInfluence.x;
        const visitorZ = this.visitorInfluence.z;
        
        // Only update if visitor is reasonably close
        if (Math.abs(visitorX) > 6 && Math.abs(visitorZ) > 6) return;
        
        for (let i = 0; i < positions.length; i += 3) {
            const x = positions[i];
            const z = positions[i + 1];
            
            // Distance from visitor
            const distToVisitor = Math.sqrt((x - visitorX) ** 2 + (z - visitorZ) ** 2);
            
            // Base h(x) value
            let hx = this.calculateHx(x, z);
            
            // Visitor presence creates a slight "depression" in the landscape
            // representing their influence on the system state
            if (distToVisitor < 2.0) {
                const influence = Math.cos(distToVisitor / 2.0 * Math.PI * 0.5) * 0.15;
                hx -= influence;
            }
            
            // Add ripple effect emanating from visitor
            const ripplePhase = this.time * 3 - distToVisitor;
            const ripple = Math.sin(ripplePhase) * Math.exp(-distToVisitor * 0.5) * 0.05;
            
            positions[i + 2] = (hx + ripple) * 2;
            this.setVertexColor(colors, i, hx);
        }
        
        this.landscapeGeometry.attributes.position.needsUpdate = true;
        this.landscapeGeometry.attributes.color.needsUpdate = true;
        this.landscapeGeometry.computeVertexNormals();
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Update landscape with visitor presence effect
        if (this.visitorInfluence && (this.visitorInfluence.x !== 0 || this.visitorInfluence.z !== 0)) {
            // Throttle landscape updates for performance
            if (Math.floor(this.time * 10) % 2 === 0) {
                this.updateLandscapeWithVisitor();
            }
        }
        
        // Update light dome based on current h(x)
        if (this.domeMaterial) {
            this.domeMaterial.uniforms.time.value = this.time;
            this.domeMaterial.uniforms.hxValue.value = this.currentHx;
            
            // Heartbeat effect - faster when danger approaches
            const heartRate = this.currentHx > 0.5 ? 1.0 : (this.currentHx > 0.2 ? 2.0 : 4.0);
            this.heartbeatPhase += deltaTime * heartRate * Math.PI * 2;
            const heartbeat = Math.pow(Math.sin(this.heartbeatPhase) * 0.5 + 0.5, 3);
            
            // Intensify if visitor warning is active
            if (this.visitorWarningActive) {
                this.domeMaterial.uniforms.heartbeat.value = Math.min(1.0, heartbeat * 1.5);
            } else {
                this.domeMaterial.uniforms.heartbeat.value = heartbeat;
            }
        }
        
        // Animate inner glow color
        if (this.innerGlow) {
            const color = new THREE.Color();
            if (this.currentHx > 0.5) {
                color.lerpColors(COLORS.caution, COLORS.safe, (this.currentHx - 0.5) * 2);
            } else {
                color.lerpColors(COLORS.danger, COLORS.caution, this.currentHx * 2);
            }
            this.innerGlow.material.color.copy(color);
        }
        
        // Animate agent marker
        if (this.agentMarker) {
            this.agentMarker.children[0].rotation.y = this.time;
            this.agentMarker.children[1].rotation.z = this.time * 2; // Halo spin
            this.agentMarker.children[1].material.opacity = 0.3 + Math.sin(this.time * 3) * 0.2;
        }
        
        // Animate EFE particles
        this.animateParticles(deltaTime);
        
        // Animate danger fog
        this.animateDangerFog(deltaTime);
        
        // Update EFE components display periodically
        if (this.efeTexture && Math.floor(this.time * 2) !== Math.floor((this.time - deltaTime) * 2)) {
            this.updateEFEDisplay();
        }
        
        // Float formula hologram
        if (this.formulaHologram) {
            this.formulaHologram.position.y = 4.5 + Math.sin(this.time * 0.5) * 0.1;
            this.formulaHologram.rotation.y = Math.sin(this.time * 0.3) * 0.1;
        }
        
        // Animate optimum celebration
        if (this.discoveredOptimum && this.optimumReward.visible) {
            this.animateCelebration();
        }
        
        // Rotate contours slightly
        if (this.contours) {
            this.contours.rotation.y = Math.sin(this.time * 0.1) * 0.05;
            
            // Pulse contour lines based on h(x) proximity
            this.contours.children.forEach((line, idx) => {
                const threshold = [0.1, 0.3, 0.5, 0.7, 0.9][idx];
                const proximity = 1 - Math.abs(this.currentHx - threshold) * 2;
                const baseBrightness = 0.3;
                const pulseBrightness = Math.max(0, proximity) * 0.5 * (Math.sin(this.time * 3) * 0.5 + 0.5);
                line.material.opacity = baseBrightness + pulseBrightness;
            });
        }
        
        // Animate safety barrier (pulsing glow when agent approaches danger)
        if (this.barrierMesh && this.barrierCore) {
            // Barrier pulses faster and brighter when near danger
            const dangerFactor = Math.max(0, 1 - this.currentHx * 2);
            const pulseRate = 2 + dangerFactor * 4;
            const pulse = Math.sin(this.time * pulseRate) * 0.5 + 0.5;
            
            // Core brightness
            this.barrierCore.material.opacity = 0.4 + pulse * 0.4 + dangerFactor * 0.2;
            
            // Main barrier emissive intensity
            this.barrierMesh.material.emissiveIntensity = 0.6 + pulse * 0.4 + dangerFactor * 0.5;
            
            // Make barrier more visible when danger is imminent
            if (this.currentHx < 0.2) {
                this.barrierMesh.material.opacity = 0.95;
                this.barrierMesh.scale.setScalar(1 + pulse * 0.05);
            } else {
                this.barrierMesh.material.opacity = 0.85;
                this.barrierMesh.scale.setScalar(1);
            }
        }
        
        // Billboard the barrier label
        if (this.barrierLabel && this.barrierLabel.userData.billboard) {
            // Label faces camera (handled by main.js if passed camera)
        }
        
        // Pulse path lines
        if (this.pathLines && this.pathLines.children.length > 0) {
            const pulsePhase = this.time * 2;
            this.pathLines.children.forEach((tube, idx) => {
                const wave = Math.sin(pulsePhase + idx * 0.5) * 0.5 + 0.5;
                tube.material.opacity = 0.25 + wave * 0.35;
            });
        }
    }
    
    animateParticles(deltaTime) {
        if (!this.particles) return;
        
        const positions = this.particles.geometry.attributes.position.array;
        const velocities = this.particleVelocities;
        
        for (let i = 0; i < positions.length; i += 3) {
            const x = positions[i];
            const y = positions[i + 1];
            const z = positions[i + 2];
            
            // Gradient toward safe zone
            const dist = Math.sqrt(x * x + z * z);
            const gradX = -x / (dist + 0.5) * 0.03;
            const gradZ = -z / (dist + 0.5) * 0.03;
            
            // Add turbulence
            const noise = Math.sin(this.time + i) * 0.01;
            
            velocities[i] = velocities[i] * 0.95 + gradX + noise;
            velocities[i + 1] = velocities[i + 1] * 0.95 + (Math.random() - 0.5) * 0.02;
            velocities[i + 2] = velocities[i + 2] * 0.95 + gradZ + noise;
            
            positions[i] += velocities[i];
            positions[i + 1] += velocities[i + 1];
            positions[i + 2] += velocities[i + 2];
            
            // Reset particles
            if (dist < 0.5 || dist > 4.5 || y < 0.3 || y > 4) {
                const theta = Math.random() * Math.PI * 2;
                const r = 3 + Math.random() * 1.5;
                positions[i] = Math.cos(theta) * r;
                positions[i + 1] = Math.random() * 2 + 1;
                positions[i + 2] = Math.sin(theta) * r;
                velocities[i] = velocities[i + 1] = velocities[i + 2] = 0;
            }
        }
        
        this.particles.geometry.attributes.position.needsUpdate = true;
    }
    
    animateDangerFog(deltaTime) {
        if (!this.dangerFog) return;
        
        const positions = this.dangerFog.geometry.attributes.position.array;
        
        // Fog intensity based on overall safety
        const targetIntensity = 1 - this.currentHx;
        this.dangerFogIntensity += (targetIntensity - this.dangerFogIntensity) * deltaTime;
        this.dangerFog.material.opacity = 0.1 * this.dangerFogIntensity;
        
        for (let i = 0; i < positions.length; i += 3) {
            // Rise and drift
            positions[i + 1] += deltaTime * 0.5;
            positions[i] += Math.sin(this.time + i) * deltaTime * 0.2;
            positions[i + 2] += Math.cos(this.time + i * 0.7) * deltaTime * 0.2;
            
            // Reset at top
            if (positions[i + 1] > 2.5) {
                const angle = Math.random() * Math.PI * 2;
                const radius = 3 + Math.random() * 2;
                positions[i] = Math.cos(angle) * radius;
                positions[i + 1] = 0;
                positions[i + 2] = Math.sin(angle) * radius;
            }
        }
        
        this.dangerFog.geometry.attributes.position.needsUpdate = true;
    }
    
    animateCelebration() {
        if (!this.optimumReward) return;
        
        const timeSinceDiscovery = this.time - (this.celebrationStartTime || 0);
        
        // Spin and glow
        this.optimumReward.children[0].rotation.y = timeSinceDiscovery * 3;
        this.optimumReward.children[0].rotation.x = timeSinceDiscovery;
        
        // Expand celebration particles
        if (this.optimumReward.children[1]) {
            const positions = this.optimumReward.children[1].geometry.attributes.position.array;
            for (let i = 0; i < positions.length; i += 3) {
                positions[i + 1] += 0.02;
                positions[i] *= 1.002;
                positions[i + 2] *= 1.002;
            }
            this.optimumReward.children[1].geometry.attributes.position.needsUpdate = true;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CLEANUP
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        this.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                if (Array.isArray(obj.material)) {
                    obj.material.forEach(m => m.dispose());
                } else {
                    obj.material.dispose();
                }
            }
        });
    }
}

export function createEFECBFArtwork() {
    return new EFECBFArtwork();
}

export default EFECBFArtwork;
