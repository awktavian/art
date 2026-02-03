/**
 * P1-004: S15 Hopf State Encoding Artwork
 * =======================================
 * 
 * A rideable journey through the Hopf fibration S⁷ → S¹⁵ → S⁸.
 * Walk through the fibers, ride along them, and see how the
 * 7 colonies map to the octonionic structure.
 * 
 * Inspired by:
 * - James Turrell's Roden Crater tunnels
 * - teamLab's body immersion experiences
 * - The mathematical beauty of Hopf fibrations
 * 
 * Features:
 * - True Hopf fibration mathematics
 * - "Ride the fiber" camera mode
 * - Fiber-to-base mapping visualization
 * - Colony-colored fibers with activity pulses
 * - Walk-through scale installation
 * - Octonion multiplication table visualization
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { PATENTS } from '../components/info-panel.js';

const PATENT = PATENTS.find(p => p.id === 'P1-004');

const COLONY_DATA = [
    { name: 'spark',   color: 0xFF6B35, pitch: 'C' },
    { name: 'forge',   color: 0xD4AF37, pitch: 'D' },
    { name: 'flow',    color: 0x4ECDC4, pitch: 'E' },
    { name: 'nexus',   color: 0x9B7EBD, pitch: 'F' },
    { name: 'beacon',  color: 0xF59E0B, pitch: 'G' },
    { name: 'grove',   color: 0x7EB77F, pitch: 'A' },
    { name: 'crystal', color: 0x67D4E4, pitch: 'B' }
];

// ═══════════════════════════════════════════════════════════════════════════
// HOPF FIBRATION MATHEMATICS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Hopf fibration S³ → S⁷ → S⁴
 * The octonionic Hopf fibration uses S⁷ fibers over S⁸ base,
 * embedded in S¹⁵ (15-sphere in 16-dimensional space).
 * 
 * For visualization, we use a parametric representation.
 */
function hopfFiber(t, fiberPhase, scale = 2.5) {
    // Parametric representation of a Hopf fiber
    // t ∈ [0, 2π] traces the fiber
    // fiberPhase ∈ [0, 2π] selects which fiber
    
    const cos_t = Math.cos(t);
    const sin_t = Math.sin(t);
    const cos_p = Math.cos(fiberPhase);
    const sin_p = Math.sin(fiberPhase);
    
    // Stereographic projection from S³ to R³
    const x = scale * (sin_t * cos_p);
    const y = scale * (sin_t * sin_p);
    const z = scale * cos_t;
    
    // Add twist for Hopf-like linking
    const twist = fiberPhase * 2;
    const r = Math.sqrt(x * x + y * y) + 0.001;
    const newX = x * Math.cos(twist * sin_t) - y * Math.sin(twist * sin_t);
    const newY = x * Math.sin(twist * sin_t) + y * Math.cos(twist * sin_t);
    
    return new THREE.Vector3(newX, z, newY);
}

/**
 * Generate fiber points for a specific phase.
 */
function generateFiberCurve(fiberPhase, segments = 128) {
    const points = [];
    
    for (let i = 0; i <= segments; i++) {
        const t = (i / segments) * Math.PI * 2;
        const point = hopfFiber(t, fiberPhase);
        points.push(point);
    }
    
    return new THREE.CatmullRomCurve3(points, true);
}

// ═══════════════════════════════════════════════════════════════════════════
// S15 HOPF ARTWORK
// ═══════════════════════════════════════════════════════════════════════════

export class S15HopfArtwork extends THREE.Group {
    constructor() {
        super();
        this.name = 'artwork-s15-hopf';
        this.time = 0;
        
        // Fiber data
        this.fibers = [];
        this.fiberCurves = [];
        this.activeColony = null;
        
        // Ride mode
        this.isRiding = false;
        this.rideProgress = 0;
        this.rideFiber = 0;
        this.originalCameraPosition = null;
        
        // Flow particles
        this.particles = null;
        this.particleData = [];
        
        this.create();
    }
    
    create() {
        // === FOUNDATION ===
        this.createBasePlatform();
        
        // === FIBRATION VISUALIZATION ===
        this.createHopfFibers();
        this.createBaseManifold();
        this.createSphericalShells();
        
        // === INTERACTIVE ELEMENTS ===
        this.createFlowingParticles();
        this.createRideInterface();
        
        // === INFORMATION ===
        this.createFibrationLabel();
        this.createOctonionDisplay();
        this.createPlaque();
        
        // Mark as interactive
        this.userData.interactive = true;
        this.userData.artwork = PATENT;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // BASE PLATFORM
    // ═══════════════════════════════════════════════════════════════════════
    
    createBasePlatform() {
        // Large circular platform for walk-through experience
        const floorGeo = new THREE.CircleGeometry(5, 64);
        const floorMat = new THREE.MeshPhysicalMaterial({
            color: 0x08080C,
            metalness: 0.9,
            roughness: 0.15,
            clearcoat: 0.8
        });
        const floor = new THREE.Mesh(floorGeo, floorMat);
        floor.rotation.x = -Math.PI / 2;
        floor.receiveShadow = true;
        this.add(floor);
        
        // Glowing ring
        const ringGeo = new THREE.RingGeometry(4.8, 5, 64);
        const ringMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.4,
            side: THREE.DoubleSide
        });
        const ring = new THREE.Mesh(ringGeo, ringMat);
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = 0.01;
        this.add(ring);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // HOPF FIBERS (7 colonies)
    // ═══════════════════════════════════════════════════════════════════════
    
    createHopfFibers() {
        COLONY_DATA.forEach((colony, i) => {
            const phase = (i / 7) * Math.PI * 2;
            const curve = generateFiberCurve(phase);
            this.fiberCurves.push(curve);
            
            // Main fiber tube
            const tubeGeo = new THREE.TubeGeometry(curve, 128, 0.12, 16, true);
            const tubeMat = new THREE.MeshPhysicalMaterial({
                color: colony.color,
                emissive: colony.color,
                emissiveIntensity: 0.3,
                metalness: 0.5,
                roughness: 0.3,
                clearcoat: 0.5,
                transparent: true,
                opacity: 0.85
            });
            
            const fiber = new THREE.Mesh(tubeGeo, tubeMat);
            fiber.position.y = 3;
            fiber.userData = { 
                colony: colony.name, 
                index: i, 
                phase,
                type: 'hopf-fiber',
                interactive: true
            };
            
            this.fibers.push(fiber);
            this.add(fiber);
            
            // Inner glow tube
            const glowGeo = new THREE.TubeGeometry(curve, 64, 0.25, 8, true);
            const glowMat = new THREE.MeshBasicMaterial({
                color: colony.color,
                transparent: true,
                opacity: 0.1,
                side: THREE.BackSide
            });
            const glow = new THREE.Mesh(glowGeo, glowMat);
            glow.position.y = 3;
            this.add(glow);
            
            // Fiber label
            this.createFiberLabel(colony, phase);
        });
    }
    
    createFiberLabel(colony, phase) {
        const canvas = document.createElement('canvas');
        canvas.width = 128;
        canvas.height = 64;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = '#' + colony.color.toString(16).padStart(6, '0');
        ctx.font = 'bold 24px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(colony.name.toUpperCase(), 64, 40);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(1, 0.5);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        
        // Position at start of fiber
        const startPoint = hopfFiber(0, phase);
        label.position.set(startPoint.x * 1.3, 3 + startPoint.z, startPoint.y * 1.3);
        label.lookAt(0, 3, 0);
        
        this.add(label);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // BASE MANIFOLD (S⁸ representation)
    // ═══════════════════════════════════════════════════════════════════════
    
    createBaseManifold() {
        // Central torus knot representing the base space
        const knotGeo = new THREE.TorusKnotGeometry(0.8, 0.2, 128, 32, 2, 3);
        const knotMat = new THREE.MeshPhysicalMaterial({
            color: 0xFFD700,
            emissive: 0xFFD700,
            emissiveIntensity: 0.3,
            metalness: 0.6,
            roughness: 0.2,
            clearcoat: 0.8,
            transparent: true,
            opacity: 0.8
        });
        
        this.baseKnot = new THREE.Mesh(knotGeo, knotMat);
        this.baseKnot.position.y = 3;
        this.baseKnot.userData = { type: 'base-manifold' };
        this.add(this.baseKnot);
        
        // Glow
        const glowGeo = new THREE.TorusKnotGeometry(0.8, 0.4, 64, 16, 2, 3);
        const glowMat = new THREE.MeshBasicMaterial({
            color: 0xFFD700,
            transparent: true,
            opacity: 0.1,
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeo, glowMat);
        glow.position.y = 3;
        this.add(glow);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SPHERICAL SHELLS
    // ═══════════════════════════════════════════════════════════════════════
    
    createSphericalShells() {
        // S⁷ fiber (inner wireframe)
        const s7Geo = new THREE.IcosahedronGeometry(2, 1);
        const s7Mat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            wireframe: true,
            transparent: true,
            opacity: 0.15
        });
        this.s7Shell = new THREE.Mesh(s7Geo, s7Mat);
        this.s7Shell.position.y = 3;
        this.add(this.s7Shell);
        
        // S¹⁵ total space (outer wireframe)
        const s15Geo = new THREE.IcosahedronGeometry(3.5, 1);
        const s15Mat = new THREE.MeshBasicMaterial({
            color: 0x9B7EBD,
            wireframe: true,
            transparent: true,
            opacity: 0.08
        });
        this.s15Shell = new THREE.Mesh(s15Geo, s15Mat);
        this.s15Shell.position.y = 3;
        this.add(this.s15Shell);
        
        // S⁸ base (smallest)
        const s8Geo = new THREE.IcosahedronGeometry(1.2, 1);
        const s8Mat = new THREE.MeshBasicMaterial({
            color: 0xFFD700,
            wireframe: true,
            transparent: true,
            opacity: 0.2
        });
        this.s8Shell = new THREE.Mesh(s8Geo, s8Mat);
        this.s8Shell.position.y = 3;
        this.add(this.s8Shell);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FLOWING PARTICLES
    // ═══════════════════════════════════════════════════════════════════════
    
    createFlowingParticles() {
        const particleCount = 700;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            const fiberIndex = Math.floor(Math.random() * 7);
            const t = Math.random();
            const color = new THREE.Color(COLONY_DATA[fiberIndex].color);
            
            this.particleData.push({
                fiberIndex,
                t,
                speed: 0.15 + Math.random() * 0.2
            });
            
            positions[i * 3] = 0;
            positions[i * 3 + 1] = 3;
            positions[i * 3 + 2] = 0;
            
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
        }
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const material = new THREE.PointsMaterial({
            size: 0.08,
            vertexColors: true,
            transparent: true,
            opacity: 0.85,
            blending: THREE.AdditiveBlending
        });
        
        this.particles = new THREE.Points(geometry, material);
        this.add(this.particles);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // RIDE INTERFACE
    // ═══════════════════════════════════════════════════════════════════════
    
    createRideInterface() {
        // "Ride the Fiber" button display
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 128;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
        ctx.roundRect(10, 10, 492, 108, 8);
        ctx.fill();
        
        ctx.strokeStyle = '#67D4E4';
        ctx.lineWidth = 2;
        ctx.roundRect(10, 10, 492, 108, 8);
        ctx.stroke();
        
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 32px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('🎢 CLICK FIBER TO RIDE', 256, 72);
        
        const texture = new THREE.CanvasTexture(canvas);
        const displayGeo = new THREE.PlaneGeometry(3, 0.75);
        const displayMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        this.ridePrompt = new THREE.Mesh(displayGeo, displayMat);
        this.ridePrompt.position.set(0, 7, 0);
        this.add(this.ridePrompt);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FIBRATION LABEL
    // ═══════════════════════════════════════════════════════════════════════
    
    createFibrationLabel() {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 128;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 48px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('S⁷ → S¹⁵ → S⁸', 256, 64);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(3.5, 0.875);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.set(0, 8, 0);
        this.add(label);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // OCTONION MULTIPLICATION TABLE
    // ═══════════════════════════════════════════════════════════════════════
    
    createOctonionDisplay() {
        // Simple representation of octonion structure
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 512;
        this.octonionCanvas = canvas;
        this.octonionCtx = canvas.getContext('2d');
        
        this.updateOctonionDisplay();
        
        const texture = new THREE.CanvasTexture(canvas);
        this.octonionTexture = texture;
        
        const displayGeo = new THREE.PlaneGeometry(2, 2);
        const displayMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        this.octonionDisplay = new THREE.Mesh(displayGeo, displayMat);
        this.octonionDisplay.position.set(-4, 3, 0);
        this.octonionDisplay.rotation.y = Math.PI / 4;
        this.add(this.octonionDisplay);
    }
    
    updateOctonionDisplay() {
        const ctx = this.octonionCtx;
        ctx.clearRect(0, 0, 512, 512);
        
        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
        ctx.roundRect(10, 10, 492, 492, 10);
        ctx.fill();
        
        // Title
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 24px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('OCTONION STRUCTURE', 256, 50);
        
        // Fano plane representation (simplified)
        ctx.strokeStyle = '#9B7EBD';
        ctx.lineWidth = 2;
        
        // Draw Fano-like pattern
        const cx = 256, cy = 280, r = 120;
        
        // 7 points in hexagon + center
        const points = [];
        for (let i = 0; i < 7; i++) {
            const angle = (i / 6) * Math.PI * 2 - Math.PI / 2;
            const x = i === 0 ? cx : cx + Math.cos(angle) * r;
            const y = i === 0 ? cy : cy + Math.sin(angle) * r;
            points.push({ x, y, color: COLONY_DATA[i].color });
        }
        
        // Draw lines
        const lines = [[1, 2, 4], [2, 3, 5], [3, 4, 6], [4, 5, 1], [5, 6, 2], [6, 1, 3], [0, 0, 0]];
        lines.forEach(line => {
            if (line[0] === 0 && line[1] === 0) return;
            ctx.beginPath();
            ctx.moveTo(points[line[0]].x, points[line[0]].y);
            ctx.lineTo(points[line[1]].x, points[line[1]].y);
            ctx.lineTo(points[line[2]].x, points[line[2]].y);
            ctx.stroke();
        });
        
        // Draw points
        points.forEach((p, i) => {
            ctx.fillStyle = '#' + COLONY_DATA[i].color.toString(16).padStart(6, '0');
            ctx.beginPath();
            ctx.arc(p.x, p.y, 15, 0, Math.PI * 2);
            ctx.fill();
        });
        
        // Formula
        ctx.fillStyle = '#9E9994';
        ctx.font = '16px "IBM Plex Mono", monospace';
        ctx.fillText('e_i · e_j = ±e_k (non-associative)', 256, 450);
        
        if (this.octonionTexture) {
            this.octonionTexture.needsUpdate = true;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PLAQUE
    // ═══════════════════════════════════════════════════════════════════════
    
    createPlaque() {
        if (PATENT) {
            const plaque = createPlaque(PATENT, { width: 3, height: 2 });
            plaque.position.set(5, 1.2, 0);
            plaque.rotation.y = -Math.PI / 2;
            this.add(plaque);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    handleClick(point, object) {
        if (object && object.userData && object.userData.type === 'hopf-fiber') {
            const fiberIndex = object.userData.index;
            this.startRide(fiberIndex);
        }
    }
    
    startRide(fiberIndex) {
        console.log(`🎢 Riding fiber ${fiberIndex} (${COLONY_DATA[fiberIndex].name})`);
        this.isRiding = true;
        this.rideFiber = fiberIndex;
        this.rideProgress = 0;
        
        // Highlight the selected fiber
        this.activeColony = fiberIndex;
        this.fibers[fiberIndex].material.emissiveIntensity = 1.0;
    }
    
    endRide() {
        this.isRiding = false;
        if (this.activeColony !== null) {
            this.fibers[this.activeColony].material.emissiveIntensity = 0.3;
            this.activeColony = null;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FIBER RIDE (returns camera position for external use)
    // ═══════════════════════════════════════════════════════════════════════
    
    getRideCameraPosition() {
        if (!this.isRiding) return null;
        
        const curve = this.fiberCurves[this.rideFiber];
        const point = curve.getPoint(this.rideProgress);
        
        // Position camera slightly offset from the fiber path
        return {
            position: new THREE.Vector3(point.x * 0.8, point.y + 3.5, point.z * 0.8),
            lookAt: new THREE.Vector3(point.x, point.y + 3, point.z)
        };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Rotate fibers
        this.fibers.forEach((fiber, i) => {
            fiber.rotation.y = this.time * 0.2 + i * 0.1;
            fiber.rotation.x = Math.sin(this.time * 0.3 + i) * 0.1;
            
            // Pulse active fiber
            if (i === this.activeColony) {
                fiber.material.emissiveIntensity = 0.7 + Math.sin(this.time * 5) * 0.3;
            }
        });
        
        // Rotate base knot
        if (this.baseKnot) {
            this.baseKnot.rotation.x = Math.sin(this.time * 0.3) * 0.2;
            this.baseKnot.rotation.y = this.time * 0.25;
        }
        
        // Rotate shells
        if (this.s7Shell) {
            this.s7Shell.rotation.y = this.time * 0.3;
            this.s7Shell.rotation.x = Math.sin(this.time * 0.2) * 0.2;
        }
        if (this.s15Shell) {
            this.s15Shell.rotation.y = -this.time * 0.1;
            this.s15Shell.rotation.z = Math.sin(this.time * 0.15) * 0.1;
        }
        if (this.s8Shell) {
            this.s8Shell.rotation.x = this.time * 0.4;
            this.s8Shell.rotation.z = this.time * 0.3;
        }
        
        // Update flowing particles
        this.animateParticles(deltaTime);
        
        // Update ride progress
        if (this.isRiding) {
            this.rideProgress += deltaTime * 0.1;
            if (this.rideProgress >= 1) {
                this.rideProgress = 0;
            }
        }
        
        // Float prompts
        if (this.ridePrompt) {
            this.ridePrompt.position.y = 7 + Math.sin(this.time * 0.5) * 0.1;
        }
    }
    
    animateParticles(deltaTime) {
        if (!this.particles || !this.particleData) return;
        
        const positions = this.particles.geometry.attributes.position.array;
        
        // Track particle activity per fiber for pulsing
        const fiberActivity = [0, 0, 0, 0, 0, 0, 0];
        
        this.particleData.forEach((data, i) => {
            // Move along fiber - speed varies by colony
            const colonySpeed = 0.8 + data.fiberIndex * 0.1;
            data.t = (data.t + deltaTime * data.speed * colonySpeed) % 1;
            
            // Track activity (particles near certain positions)
            if (data.t > 0.45 && data.t < 0.55) {
                fiberActivity[data.fiberIndex] += 1;
            }
            
            // Get position on fiber curve
            const curve = this.fiberCurves[data.fiberIndex];
            const point = curve.getPoint(data.t);
            
            // Apply fiber rotation
            const fiberRotation = this.time * 0.2 + data.fiberIndex * 0.1;
            const cos = Math.cos(fiberRotation);
            const sin = Math.sin(fiberRotation);
            
            const x = point.x * cos - point.z * sin;
            const z = point.x * sin + point.z * cos;
            
            positions[i * 3] = x;
            positions[i * 3 + 1] = point.y + 3;
            positions[i * 3 + 2] = z;
        });
        
        this.particles.geometry.attributes.position.needsUpdate = true;
        
        // Pulse fibers based on particle activity
        this.fibers.forEach((fiber, i) => {
            const activity = fiberActivity[i] / 10; // Normalize
            const basePulse = i === this.activeColony ? 0.5 : 0.2;
            fiber.material.emissiveIntensity = basePulse + activity * 0.5;
            
            // Subtle scale pulse
            const targetScale = 1 + activity * 0.1;
            fiber.scale.lerp(new THREE.Vector3(targetScale, targetScale, targetScale), 0.1);
        });
        
        // Pulse shells when active fiber has high activity
        if (this.s15Shell && fiberActivity[this.activeColony] > 3) {
            this.s15Shell.material.opacity = 0.2 + Math.sin(this.time * 5) * 0.1;
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

export function createS15HopfArtwork() {
    return new S15HopfArtwork();
}

export default S15HopfArtwork;
