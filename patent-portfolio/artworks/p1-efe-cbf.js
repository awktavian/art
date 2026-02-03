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

// Color palette
const COLORS = {
    safe: new THREE.Color(0x00FF88),      // Bright green
    caution: new THREE.Color(0xFFAA00),   // Amber
    danger: new THREE.Color(0xFF2222),    // Red
    crystal: new THREE.Color(0x67D4E4),   // Crystal blue
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
    
    calculateHx(x, z) {
        // Control Barrier Function: creates a landscape with:
        // - Safe central zone (h(x) > 0)
        // - Dangerous edges (h(x) → 0)
        // - Interesting topology with local minima
        
        const dist = Math.sqrt(x * x + z * z);
        
        // Base barrier: safe in center, danger at edges
        const centerSafety = Math.max(0, 1.2 - dist * 0.25);
        
        // Add interesting features
        const wave = Math.sin(x * 1.5) * Math.cos(z * 1.5) * 0.15;
        const peak = Math.exp(-(dist * dist) / 8) * 0.4;
        
        // Local dip at (2, 2) to create exploration target
        const dipX = 2.5, dipZ = 2.5;
        const dipDist = Math.sqrt((x - dipX) ** 2 + (z - dipZ) ** 2);
        const dip = -Math.exp(-(dipDist * dipDist) / 0.5) * 0.3;
        
        // Global optimum at (0, 0)
        const optimumBoost = Math.exp(-(dist * dist) / 2) * 0.2;
        
        const hx = centerSafety + wave + peak + dip + optimumBoost;
        
        // Clamp to valid range [0, 1]
        return Math.max(0, Math.min(1, hx));
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
                
                // Color based on safety
                const endHx = this.calculateHx(path[path.length - 1].x, path[path.length - 1].z);
                const color = endHx > 0.5 ? 0x00FF88 : (endHx > 0.2 ? 0xFFAA00 : 0xFF4444);
                
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
        const contourColors = [0xFF2222, 0xFF8800, 0xFFCC00, 0x88FF00, 0x00FF88];
        
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
        
        // Main formula canvas
        const canvas = document.createElement('canvas');
        canvas.width = 1024;
        canvas.height = 256;
        const ctx = canvas.getContext('2d');
        
        this.formulaCanvas = canvas;
        this.formulaCtx = ctx;
        this.updateFormula();
        
        const texture = new THREE.CanvasTexture(canvas);
        this.formulaTexture = texture;
        
        const planeGeo = new THREE.PlaneGeometry(4, 1);
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
        const glowGeo = new THREE.PlaneGeometry(4.2, 1.2);
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
        this.formulaHologram.position.set(0, 4.5, 0);
        this.add(this.formulaHologram);
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
        
        // Formula text
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 48px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        
        // EFE = E[G] - λ·h(x)
        ctx.fillText('EFE = E[G] − λ·risk − cost', 512, 80);
        
        // Current h(x) value
        const hxColor = this.currentHx > 0.5 ? '#00FF88' : (this.currentHx > 0.2 ? '#FFAA00' : '#FF4444');
        ctx.fillStyle = hxColor;
        ctx.font = 'bold 64px "IBM Plex Mono", monospace';
        ctx.fillText(`h(x) = ${this.currentHx.toFixed(3)}`, 512, 170);
        
        // Constraint reminder
        ctx.fillStyle = this.currentHx > 0 ? '#00FF88' : '#FF4444';
        ctx.font = '32px "IBM Plex Mono", monospace';
        ctx.fillText('h(x) ≥ 0 ALWAYS', 512, 230);
        
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
    
    handleClick(point) {
        // Place agent at clicked point on landscape
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
    
    setVisitorPosition(position) {
        // Called with visitor's camera position for body immersion effect
        this.visitorInfluence.set(position.x, 0, position.z);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Update light dome based on current h(x)
        if (this.domeMaterial) {
            this.domeMaterial.uniforms.time.value = this.time;
            this.domeMaterial.uniforms.hxValue.value = this.currentHx;
            
            // Heartbeat effect - faster when danger approaches
            const heartRate = this.currentHx > 0.5 ? 1.0 : (this.currentHx > 0.2 ? 2.0 : 4.0);
            this.heartbeatPhase += deltaTime * heartRate * Math.PI * 2;
            const heartbeat = Math.pow(Math.sin(this.heartbeatPhase) * 0.5 + 0.5, 3);
            this.domeMaterial.uniforms.heartbeat.value = heartbeat;
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
