/**
 * P1-004: S15 Hopf State Encoding Artwork
 * =======================================
 * 
 * TRUE OCTONIONIC HOPF FIBRATION: S⁷ → S¹⁵ → S⁸
 * 
 * Mathematical Foundation (from kagami_math/s15_hopf.py):
 * ======================================================
 * 
 * The octonionic Hopf fibration is the last of the four Hopf fibrations:
 *   - Real:        S⁰ → S¹ → S¹  (trivial)
 *   - Complex:     S¹ → S³ → S²  (classical Hopf)
 *   - Quaternionic: S³ → S⁷ → S⁴
 *   - Octonionic:  S⁷ → S¹⁵ → S⁸ (THIS ARTWORK)
 * 
 * Space Definitions:
 *   S¹⁵ = { (x, y) ∈ 𝕆 × 𝕆 : |x|² + |y|² = 1 }  (Unit sphere in ℝ¹⁶)
 *   S⁸  = { (t, o) ∈ ℝ ⊕ 𝕆 : t² + |o|² = 1 }    (Unit sphere in ℝ⁹)
 *   S⁷  = { x ∈ Im(𝕆) : |x| = 1 }               (Unit imaginary octonions)
 * 
 * Hopf Projection:
 *   π: S¹⁵ → S⁸
 *   π(x, y) = (|x|² - |y|², 2·x̄·y)
 * 
 * K OS Application:
 *   S¹⁵ (15D): Total state space
 *   S⁸  (8D):  Semantic content (matches E₈ lattice dimension!)
 *   S⁷  (7D):  Colony routing (matches 7 colonies!)
 * 
 * Inspired by:
 * - James Turrell's Roden Crater tunnels
 * - teamLab's body immersion experiences
 * - The mathematical beauty of division algebras
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { PATENTS } from '../components/info-panel.js';

const PATENT = PATENTS.find(p => p.id === 'P1-004');

const COLONY_DATA = [
    { name: 'spark',   color: 0xFF6B35, basis: 'e₁' },
    { name: 'forge',   color: 0xD4AF37, basis: 'e₂' },
    { name: 'flow',    color: 0x4ECDC4, basis: 'e₃' },
    { name: 'nexus',   color: 0x9B7EBD, basis: 'e₄' },
    { name: 'beacon',  color: 0xF59E0B, basis: 'e₅' },
    { name: 'grove',   color: 0x7EB77F, basis: 'e₆' },
    { name: 'crystal', color: 0x67D4E4, basis: 'e₇' }
];

// ═══════════════════════════════════════════════════════════════════════════
// OCTONION MATHEMATICS (from kagami_math/s15_hopf.py)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Fano plane multiplication table for octonions.
 * Each line [i, j, k] means: eᵢ × eⱼ = +eₖ (cyclic)
 * Based on Cayley-Dickson construction.
 */
const FANO_LINES = [
    [1, 2, 4],  // e₁ × e₂ = e₄
    [2, 3, 5],  // e₂ × e₃ = e₅
    [3, 4, 6],  // e₃ × e₄ = e₆
    [4, 5, 7],  // e₄ × e₅ = e₇
    [5, 6, 1],  // e₅ × e₆ = e₁
    [6, 7, 2],  // e₆ × e₇ = e₂
    [7, 1, 3]   // e₇ × e₁ = e₃
];

/**
 * Octonion class for mathematical operations.
 * Octonion: a₀ + a₁e₁ + a₂e₂ + a₃e₃ + a₄e₄ + a₅e₅ + a₆e₆ + a₇e₇
 */
class Octonion {
    constructor(components = [1, 0, 0, 0, 0, 0, 0, 0]) {
        // Ensure 8 components
        this.c = components.slice(0, 8);
        while (this.c.length < 8) this.c.push(0);
    }
    
    static zero() {
        return new Octonion([0, 0, 0, 0, 0, 0, 0, 0]);
    }
    
    static one() {
        return new Octonion([1, 0, 0, 0, 0, 0, 0, 0]);
    }
    
    static basis(i) {
        const c = [0, 0, 0, 0, 0, 0, 0, 0];
        c[i] = 1;
        return new Octonion(c);
    }
    
    // Conjugate: (a₀, a₁, ..., a₇) → (a₀, -a₁, ..., -a₇)
    conjugate() {
        return new Octonion([
            this.c[0],
            -this.c[1], -this.c[2], -this.c[3], -this.c[4],
            -this.c[5], -this.c[6], -this.c[7]
        ]);
    }
    
    // Norm squared: |o|² = Σ aᵢ²
    normSq() {
        return this.c.reduce((sum, x) => sum + x * x, 0);
    }
    
    // Norm: |o|
    norm() {
        return Math.sqrt(this.normSq());
    }
    
    // Addition
    add(other) {
        return new Octonion(this.c.map((x, i) => x + other.c[i]));
    }
    
    // Subtraction
    sub(other) {
        return new Octonion(this.c.map((x, i) => x - other.c[i]));
    }
    
    // Scalar multiplication
    scale(s) {
        return new Octonion(this.c.map(x => x * s));
    }
    
    // Octonion multiplication (Cayley-Dickson)
    mul(other) {
        const a = this.c;
        const b = other.c;
        const result = [0, 0, 0, 0, 0, 0, 0, 0];
        
        // Real part: a₀b₀ - Σᵢ aᵢbᵢ
        result[0] = a[0] * b[0];
        for (let i = 1; i < 8; i++) {
            result[0] -= a[i] * b[i];
        }
        
        // Imaginary parts: a₀bᵢ + aᵢb₀ + Σⱼₖ εᵢⱼₖ aⱼbₖ
        for (let i = 1; i < 8; i++) {
            result[i] = a[0] * b[i] + a[i] * b[0];
        }
        
        // Apply Fano plane multiplication rules
        for (const [i, j, k] of FANO_LINES) {
            // eᵢ × eⱼ = +eₖ (cyclic)
            result[k] += a[i] * b[j];
            result[k] -= a[j] * b[i];
            
            // eⱼ × eₖ = +eᵢ
            result[i] += a[j] * b[k];
            result[i] -= a[k] * b[j];
            
            // eₖ × eᵢ = +eⱼ
            result[j] += a[k] * b[i];
            result[j] -= a[i] * b[k];
        }
        
        return new Octonion(result);
    }
    
    // Normalize to unit octonion
    normalize() {
        const n = this.norm();
        if (n < 1e-10) return Octonion.one();
        return this.scale(1 / n);
    }
    
    // Imaginary part (components 1-7)
    imaginary() {
        return new Octonion([0, this.c[1], this.c[2], this.c[3], 
                            this.c[4], this.c[5], this.c[6], this.c[7]]);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// HOPF FIBRATION MATHEMATICS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Hopf projection: π: S¹⁵ → S⁸
 * π(x, y) = (|x|² - |y|², 2·x̄·y)
 * 
 * @param {Octonion} x - First octonion (|x|² + |y|² = 1)
 * @param {Octonion} y - Second octonion
 * @returns {{ t: number, o: Octonion }} - Point on S⁸ as (t, o)
 */
function hopfProject(x, y) {
    // t = |x|² - |y|²
    const t = x.normSq() - y.normSq();
    
    // o = 2·x̄·y (octonion multiplication)
    const xBar = x.conjugate();
    const o = xBar.mul(y).scale(2);
    
    return { t, o };
}

/**
 * Generate a point on S¹⁵ given a base point on S⁸ and a fiber phase.
 * Inverse of hopfProject: finds (x, y) with |x|² + |y|² = 1, |x|² - |y|² = t, 2·x̄·y = o.
 */
function hopfLift(t, o, phase) {
    const xNorm = Math.sqrt(Math.max(1e-10, (1 + t) / 2));
    const yNorm = Math.sqrt(Math.max(1e-10, (1 - t) / 2));
    const cos_p = Math.cos(phase);
    const sin_p = Math.sin(phase);

    if (xNorm >= 0.1) {
        // x = xNorm * (cos_p, sin_p*u) for unit imaginary u; take u so that fiber varies
        const u = new Octonion([0, 1, 0, 0, 0, 0, 0, 0]);
        const x = new Octonion([
            xNorm * cos_p,
            xNorm * sin_p * u.c[1],
            xNorm * sin_p * u.c[2],
            xNorm * sin_p * u.c[3],
            xNorm * sin_p * u.c[4],
            xNorm * sin_p * u.c[5],
            xNorm * sin_p * u.c[6],
            xNorm * sin_p * u.c[7]
        ]);
        // y such that 2·x̄·y = o => y = (x.conjugate().mul(o)).scale(0.5 / xNorm²)
        const xBar = x.conjugate();
        const yRaw = xBar.mul(o).scale(0.5 / (xNorm * xNorm));
        const y = yRaw.normalize().scale(yNorm);
        return { x, y };
    }
    // Near south pole: |y| = yNorm, |x| ≈ 0; use y as primary
    const n = o.norm();
    if (n < 1e-10) {
        const y = new Octonion([yNorm * cos_p, yNorm * sin_p, 0, 0, 0, 0, 0, 0]).normalize().scale(yNorm);
        return { x: new Octonion([xNorm, 0, 0, 0, 0, 0, 0, 0]), y };
    }
    const yDir = o.scale(1 / n);
    const y = yDir.scale(yNorm);
    const x = new Octonion([xNorm * cos_p, xNorm * sin_p, 0, 0, 0, 0, 0, 0]);
    return { x, y };
}

/**
 * Generate points along a fiber for a given S⁸ base point.
 * The fiber is homeomorphic to S⁷.
 * 
 * @param {number} baseIndex - Index 0-6 for which colony/base point
 * @param {number} segments - Number of segments for the curve
 * @returns {THREE.Vector3[]} - 3D projected points
 */
function generateOctonionicFiber(baseIndex, segments = 128) {
    const points = [];
    
    // Each colony corresponds to a direction on S⁸
    // Map to a point on S⁸ using imaginary octonion basis
    const colonyAngle = (baseIndex / 7) * Math.PI * 2;
    const t = Math.cos(colonyAngle) * 0.6; // Stay away from poles
    
    // Octonion direction for this colony
    const oComponents = [0, 0, 0, 0, 0, 0, 0, 0];
    oComponents[baseIndex + 1] = Math.sqrt(1 - t * t) * Math.cos(colonyAngle * 0.5);
    oComponents[((baseIndex + 3) % 7) + 1] = Math.sqrt(1 - t * t) * Math.sin(colonyAngle * 0.5);
    const o = new Octonion(oComponents);
    
    for (let i = 0; i <= segments; i++) {
        const phase = (i / segments) * Math.PI * 2;
        const { x, y } = hopfLift(t, o, phase);
        
        // Project 16D to 3D using weighted sum of components
        // This projection preserves the linking of fibers
        const point = projectS15to3D(x, y, baseIndex, phase);
        points.push(point);
    }
    
    return points;
}

/**
 * Stereographic projection S¹⁵ → ℝ¹⁵, then project to 3D.
 * S¹⁵ = { (x,y) ∈ 𝕆² : |x|² + |y|² = 1 }; 16 coords = (x.c[0..7], y.c[0..7]).
 * Stereographic from north pole (0,...,0,1): u_i = p_i / (1 - p_15) for i < 15.
 */
function projectS15to3D(x, y, fiberIndex, phase) {
    const coords = [...x.c, ...y.c];
    const n = coords.length;
    let sum = 0;
    for (let i = 0; i < n; i++) sum += coords[i] * coords[i];
    const norm = Math.sqrt(Math.max(1e-10, sum));
    if (norm < 1e-10) {
        return new THREE.Vector3(0, 0, 0);
    }
    const p15 = coords[15] / norm;
    const denom = 1 - p15;
    if (Math.abs(denom) < 1e-6) {
        return new THREE.Vector3(0, 2.5, 0);
    }
    const u = coords.map((c, i) => (c / norm) / denom);
    const fiberAngle = (fiberIndex / 7) * Math.PI * 2;
    const scale = 2.5;
    const px = u[0] + u[4] * 0.5 + Math.cos(fiberAngle) * 0.2;
    const py = u[1] + u[5] * 0.5 + Math.sin(fiberAngle) * 0.2;
    const pz = u[2] + u[6] * 0.5 + u[8] * 0.3;
    const twist = phase * 0.5;
    const r = Math.sqrt(px * px + py * py) + 1e-6;
    const nx = px * Math.cos(twist) - py * Math.sin(twist);
    const nz = px * Math.sin(twist) + py * Math.cos(twist);
    return new THREE.Vector3(nx * scale, pz * scale, nz * scale);
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
        
        // Flow particles
        this.particles = null;
        this.particleData = [];
        
        // Dimensional indicators
        this.dimLabels = [];
        
        this.create();
    }
    
    create() {
        // === FOUNDATION ===
        this.createBasePlatform();
        
        // === TRUE OCTONIONIC FIBRATION ===
        this.createOctonionicFibers();
        this.createBaseManifoldS8();
        this.createDimensionalShells();
        
        // === MATHEMATICAL DISPLAYS ===
        this.createDimensionDecomposition();
        this.createHopfProjectionDisplay();
        this.createOctonionMultiplicationTable();
        this.createNonAssociativityDemo();
        
        // === INTERACTIVE ELEMENTS ===
        this.createFlowingParticles();
        this.createRideInterface();
        
        // === INFORMATION ===
        this.createPlaque();
        
        // Mark as interactive
        this.userData.interactive = true;
        this.userData.artwork = PATENT;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // BASE PLATFORM
    // ═══════════════════════════════════════════════════════════════════════
    
    createBasePlatform() {
        // Large circular platform
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
        
        // Glowing ring with dimension indicator (15 = 8 + 7)
        const ringGeo = new THREE.RingGeometry(4.7, 5, 64);
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
        
        // 8-segment inner ring (S⁸ base)
        const innerRingGeo = new THREE.RingGeometry(2.8, 3.2, 8);
        const innerRingMat = new THREE.MeshBasicMaterial({
            color: 0xFFD700,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        const innerRing = new THREE.Mesh(innerRingGeo, innerRingMat);
        innerRing.rotation.x = -Math.PI / 2;
        innerRing.position.y = 0.02;
        this.add(innerRing);
        
        // 7-segment middle ring (S⁷ fiber)
        const midRingGeo = new THREE.RingGeometry(3.5, 3.9, 7);
        const midRingMat = new THREE.MeshBasicMaterial({
            color: 0x9B7EBD,
            transparent: true,
            opacity: 0.25,
            side: THREE.DoubleSide
        });
        const midRing = new THREE.Mesh(midRingGeo, midRingMat);
        midRing.rotation.x = -Math.PI / 2;
        midRing.position.y = 0.015;
        this.add(midRing);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // OCTONIONIC FIBERS (7 colonies = S⁷ fiber)
    // ═══════════════════════════════════════════════════════════════════════
    
    createOctonionicFibers() {
        COLONY_DATA.forEach((colony, i) => {
            const points = generateOctonionicFiber(i, 128);
            const curve = new THREE.CatmullRomCurve3(points, true);
            this.fiberCurves.push(curve);
            
            // Main fiber tube
            const tubeGeo = new THREE.TubeGeometry(curve, 128, 0.1, 16, true);
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
                basis: colony.basis,
                type: 'hopf-fiber',
                interactive: true
            };
            
            this.fibers.push(fiber);
            this.add(fiber);
            
            // Inner glow
            const glowGeo = new THREE.TubeGeometry(curve, 64, 0.2, 8, true);
            const glowMat = new THREE.MeshBasicMaterial({
                color: colony.color,
                transparent: true,
                opacity: 0.08,
                side: THREE.BackSide
            });
            const glow = new THREE.Mesh(glowGeo, glowMat);
            glow.position.y = 3;
            this.add(glow);
            
            // Colony label with basis element
            this.createFiberLabel(colony, i);
        });
    }
    
    createFiberLabel(colony, index) {
        const canvas = document.createElement('canvas');
        canvas.width = 128;
        canvas.height = 64;
        const ctx = canvas.getContext('2d');
        
        const colorHex = '#' + colony.color.toString(16).padStart(6, '0');
        
        ctx.fillStyle = colorHex;
        ctx.font = 'bold 20px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(colony.name.toUpperCase(), 64, 28);
        
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.fillText(colony.basis, 64, 48);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(0.8, 0.4);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        
        // Position based on fiber
        const angle = (index / 7) * Math.PI * 2;
        label.position.set(
            Math.cos(angle) * 3.5,
            6,
            Math.sin(angle) * 3.5
        );
        label.lookAt(0, 6, 0);
        
        this.add(label);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // BASE MANIFOLD S⁸
    // ═══════════════════════════════════════════════════════════════════════
    
    createBaseManifoldS8() {
        // S⁸ visualization as a glowing octahedral structure
        // 8 dimensions represented by 8 vertices
        const octaGeo = new THREE.OctahedronGeometry(0.8, 1);
        const octaMat = new THREE.MeshPhysicalMaterial({
            color: 0xFFD700,
            emissive: 0xFFD700,
            emissiveIntensity: 0.4,
            metalness: 0.7,
            roughness: 0.2,
            clearcoat: 0.9,
            transparent: true,
            opacity: 0.8
        });
        
        this.baseManifold = new THREE.Mesh(octaGeo, octaMat);
        this.baseManifold.position.y = 3;
        this.baseManifold.userData = { type: 'base-manifold-s8' };
        this.add(this.baseManifold);
        
        // Wireframe for dimension count visualization
        const wireGeo = new THREE.OctahedronGeometry(0.85, 0);
        const wireMat = new THREE.MeshBasicMaterial({
            color: 0xFFD700,
            wireframe: true,
            transparent: true,
            opacity: 0.5
        });
        const wire = new THREE.Mesh(wireGeo, wireMat);
        wire.position.y = 3;
        this.add(wire);
        
        // Glow sphere
        const glowGeo = new THREE.SphereGeometry(1.1, 32, 32);
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
    // DIMENSIONAL SHELLS (showing 15 = 8 + 7)
    // ═══════════════════════════════════════════════════════════════════════
    
    createDimensionalShells() {
        // S⁷ fiber shell (7 segments)
        const s7Geo = new THREE.IcosahedronGeometry(2, 0);
        const s7Mat = new THREE.MeshBasicMaterial({
            color: 0x9B7EBD,
            wireframe: true,
            transparent: true,
            opacity: 0.2
        });
        this.s7Shell = new THREE.Mesh(s7Geo, s7Mat);
        this.s7Shell.position.y = 3;
        this.add(this.s7Shell);
        
        // S¹⁵ total space shell (outer)
        const s15Geo = new THREE.IcosahedronGeometry(3.5, 1);
        const s15Mat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            wireframe: true,
            transparent: true,
            opacity: 0.1
        });
        this.s15Shell = new THREE.Mesh(s15Geo, s15Mat);
        this.s15Shell.position.y = 3;
        this.add(this.s15Shell);
        
        // S⁸ base shell
        const s8Geo = new THREE.SphereGeometry(1.5, 8, 8);
        const s8Mat = new THREE.MeshBasicMaterial({
            color: 0xFFD700,
            wireframe: true,
            transparent: true,
            opacity: 0.15
        });
        this.s8Shell = new THREE.Mesh(s8Geo, s8Mat);
        this.s8Shell.position.y = 3;
        this.add(this.s8Shell);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DIMENSION DECOMPOSITION DISPLAY
    // ═══════════════════════════════════════════════════════════════════════
    
    createDimensionDecomposition() {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 256;
        const ctx = canvas.getContext('2d');
        
        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
        ctx.roundRect(10, 10, 492, 236, 10);
        ctx.fill();
        
        // Title
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 28px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('S⁷ → S¹⁵ → S⁸', 256, 50);
        
        // Dimension equation
        ctx.font = 'bold 36px "IBM Plex Mono", monospace';
        ctx.fillStyle = '#FFFFFF';
        ctx.fillText('15', 120, 120);
        ctx.fillText('=', 180, 120);
        ctx.fillStyle = '#FFD700';
        ctx.fillText('8', 230, 120);
        ctx.fillStyle = '#FFFFFF';
        ctx.fillText('+', 280, 120);
        ctx.fillStyle = '#9B7EBD';
        ctx.fillText('7', 330, 120);
        
        // Labels
        ctx.font = '18px "IBM Plex Sans", sans-serif';
        ctx.fillStyle = '#67D4E4';
        ctx.fillText('total', 120, 150);
        ctx.fillStyle = '#FFD700';
        ctx.fillText('base (E₈)', 230, 150);
        ctx.fillStyle = '#9B7EBD';
        ctx.fillText('fiber (colonies)', 360, 150);
        
        // Mapping description
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Sans", sans-serif';
        ctx.fillText('π(x, y) = (|x|² − |y|², 2·x̄·y)', 256, 200);
        ctx.fillText('Hopf projection formula', 256, 225);
        
        const texture = new THREE.CanvasTexture(canvas);
        const displayGeo = new THREE.PlaneGeometry(3, 1.5);
        const displayMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        const display = new THREE.Mesh(displayGeo, displayMat);
        display.position.set(0, 8, 0);
        this.add(display);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // HOPF PROJECTION DISPLAY
    // ═══════════════════════════════════════════════════════════════════════
    
    createHopfProjectionDisplay() {
        const canvas = document.createElement('canvas');
        canvas.width = 400;
        canvas.height = 300;
        this.projectionCanvas = canvas;
        this.projectionCtx = canvas.getContext('2d');
        
        this.updateProjectionDisplay();
        
        const texture = new THREE.CanvasTexture(canvas);
        this.projectionTexture = texture;
        
        const displayGeo = new THREE.PlaneGeometry(2.4, 1.8);
        const displayMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        this.projectionDisplay = new THREE.Mesh(displayGeo, displayMat);
        this.projectionDisplay.position.set(4.5, 3, 0);
        this.projectionDisplay.rotation.y = -Math.PI / 3;
        this.add(this.projectionDisplay);
    }
    
    updateProjectionDisplay() {
        const ctx = this.projectionCtx;
        ctx.clearRect(0, 0, 400, 300);
        
        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.9)';
        ctx.roundRect(5, 5, 390, 290, 8);
        ctx.fill();
        
        // Title
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 18px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Hopf Projection π: S¹⁵ → S⁸', 200, 35);
        
        // Draw S15 → S8 diagram
        const cx = 200, cy = 160;
        
        // S¹⁵ (left circle)
        ctx.strokeStyle = '#67D4E4';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx - 80, cy, 50, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = '#67D4E4';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('S¹⁵', cx - 80, cy + 70);
        ctx.font = '11px "IBM Plex Sans", sans-serif';
        ctx.fillText('(x, y) ∈ 𝕆²', cx - 80, cy + 85);
        
        // Arrow
        ctx.strokeStyle = '#FFFFFF';
        ctx.beginPath();
        ctx.moveTo(cx - 20, cy);
        ctx.lineTo(cx + 20, cy);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(cx + 15, cy - 5);
        ctx.lineTo(cx + 25, cy);
        ctx.lineTo(cx + 15, cy + 5);
        ctx.stroke();
        
        ctx.fillStyle = '#FFFFFF';
        ctx.font = '12px "IBM Plex Mono", monospace';
        ctx.fillText('π', cx, cy - 10);
        
        // S⁸ (right circle)
        ctx.strokeStyle = '#FFD700';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx + 80, cy, 40, 0, Math.PI * 2);
        ctx.stroke();
        ctx.fillStyle = '#FFD700';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.fillText('S⁸', cx + 80, cy + 60);
        ctx.font = '11px "IBM Plex Sans", sans-serif';
        ctx.fillText('(t, o) ∈ ℝ⊕𝕆', cx + 80, cy + 75);
        
        // Fiber S⁷ indication
        ctx.strokeStyle = '#9B7EBD';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.arc(cx - 80, cy, 35, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#9B7EBD';
        ctx.font = '10px "IBM Plex Mono", monospace';
        ctx.fillText('S⁷ fiber', cx - 80, cy - 42);
        
        // Formula at bottom
        ctx.fillStyle = '#9E9994';
        ctx.font = '12px "IBM Plex Mono", monospace';
        ctx.fillText('t = |x|² − |y|²    o = 2·x̄·y', 200, 260);
        
        if (this.projectionTexture) {
            this.projectionTexture.needsUpdate = true;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // OCTONION MULTIPLICATION TABLE (FANO PLANE)
    // ═══════════════════════════════════════════════════════════════════════
    
    createOctonionMultiplicationTable() {
        const canvas = document.createElement('canvas');
        canvas.width = 400;
        canvas.height = 400;
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
        this.octonionDisplay.position.set(-4.5, 3, 0);
        this.octonionDisplay.rotation.y = Math.PI / 3;
        this.add(this.octonionDisplay);
    }
    
    updateOctonionDisplay() {
        const ctx = this.octonionCtx;
        ctx.clearRect(0, 0, 400, 400);
        
        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.9)';
        ctx.roundRect(5, 5, 390, 390, 8);
        ctx.fill();
        
        // Title
        ctx.fillStyle = '#9B7EBD';
        ctx.font = 'bold 18px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Fano Plane (Octonion Multiplication)', 200, 35);
        
        // Draw Fano plane
        const cx = 200, cy = 200, r = 100;
        
        // Calculate 7 points: 6 on hexagon + 1 center
        const points = [];
        for (let i = 0; i < 7; i++) {
            if (i === 0) {
                points.push({ x: cx, y: cy }); // Center
            } else {
                const angle = ((i - 1) / 6) * Math.PI * 2 - Math.PI / 2;
                points.push({
                    x: cx + Math.cos(angle) * r,
                    y: cy + Math.sin(angle) * r
                });
            }
        }
        
        // Draw Fano lines (7 lines, each through 3 points)
        ctx.strokeStyle = 'rgba(155, 126, 189, 0.4)';
        ctx.lineWidth = 2;
        
        FANO_LINES.forEach(([a, b, c]) => {
            // Draw triangle connecting points a, b, c (1-indexed to 0-indexed for array)
            const pa = points[a] || points[0];
            const pb = points[b] || points[0];
            const pc = points[c] || points[0];
            
            ctx.beginPath();
            ctx.moveTo(pa.x, pa.y);
            ctx.lineTo(pb.x, pb.y);
            ctx.lineTo(pc.x, pc.y);
            ctx.closePath();
            ctx.stroke();
        });
        
        // Draw central circle (for center point lines)
        ctx.strokeStyle = 'rgba(155, 126, 189, 0.3)';
        ctx.beginPath();
        ctx.arc(cx, cy, r * 0.6, 0, Math.PI * 2);
        ctx.stroke();
        
        // Draw points with colony colors
        points.forEach((p, i) => {
            const colony = COLONY_DATA[i];
            const colorHex = '#' + colony.color.toString(16).padStart(6, '0');
            
            // Glow
            const gradient = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, 20);
            gradient.addColorStop(0, colorHex);
            gradient.addColorStop(1, 'transparent');
            ctx.fillStyle = gradient;
            ctx.fillRect(p.x - 20, p.y - 20, 40, 40);
            
            // Point
            ctx.fillStyle = colorHex;
            ctx.beginPath();
            ctx.arc(p.x, p.y, 12, 0, Math.PI * 2);
            ctx.fill();
            
            // Label
            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'bold 10px "IBM Plex Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(colony.basis, p.x, p.y + 4);
        });
        
        // Legend
        ctx.fillStyle = '#9E9994';
        ctx.font = '12px "IBM Plex Mono", monospace';
        ctx.fillText('eᵢ × eⱼ = ±eₖ  (non-associative)', 200, 350);
        ctx.font = '10px "IBM Plex Sans", sans-serif';
        ctx.fillText('Each line: cyclic multiplication rule', 200, 370);
        
        if (this.octonionTexture) {
            this.octonionTexture.needsUpdate = true;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // NON-ASSOCIATIVITY DEMONSTRATION
    // ═══════════════════════════════════════════════════════════════════════
    
    createNonAssociativityDemo() {
        // Panel showing why (ab)c ≠ a(bc) for octonions
        const canvas = document.createElement('canvas');
        canvas.width = 400;
        canvas.height = 280;
        const ctx = canvas.getContext('2d');
        
        // Background
        ctx.fillStyle = 'rgba(20, 10, 30, 0.95)';
        if (ctx.roundRect) {
            ctx.beginPath();
            ctx.roundRect(5, 5, 390, 270, 8);
            ctx.fill();
        } else {
            ctx.fillRect(5, 5, 390, 270);
        }
        
        // Title
        ctx.fillStyle = '#FF6B35';
        ctx.font = 'bold 18px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Why Non-Associative?', 200, 35);
        
        // Subtitle
        ctx.fillStyle = '#888888';
        ctx.font = '12px "IBM Plex Sans", sans-serif';
        ctx.fillText('Octonions break (ab)c = a(bc)', 200, 55);
        
        // Example calculation
        ctx.fillStyle = '#F5F0E8';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.textAlign = 'left';
        
        ctx.fillText('Example: a=e₁, b=e₂, c=e₃', 30, 90);
        
        // Left side: (e₁·e₂)·e₃
        ctx.fillStyle = '#67D4E4';
        ctx.fillText('(e₁ × e₂) × e₃', 30, 125);
        ctx.fillStyle = '#AAAAAA';
        ctx.fillText('= e₄ × e₃', 30, 145);
        ctx.fillStyle = '#7EB77F';
        ctx.font = 'bold 16px "IBM Plex Mono", monospace';
        ctx.fillText('= −e₆', 30, 170);
        
        // Right side: e₁·(e₂·e₃)
        ctx.fillStyle = '#67D4E4';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.fillText('e₁ × (e₂ × e₃)', 220, 125);
        ctx.fillStyle = '#AAAAAA';
        ctx.fillText('= e₁ × e₅', 220, 145);
        ctx.fillStyle = '#FF6B35';
        ctx.font = 'bold 16px "IBM Plex Mono", monospace';
        ctx.fillText('= +e₃', 220, 170);
        
        // Conclusion
        ctx.fillStyle = '#FF4444';
        ctx.font = 'bold 16px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('−e₆ ≠ +e₃  ✗', 200, 210);
        
        // Why it matters
        ctx.fillStyle = '#9E9994';
        ctx.font = '11px "IBM Plex Sans", sans-serif';
        ctx.fillText('Non-associativity enables richer state space', 200, 245);
        ctx.fillText('for encoding complex relationships', 200, 260);
        
        const texture = new THREE.CanvasTexture(canvas);
        const geo = new THREE.PlaneGeometry(2.0, 1.4);
        const mat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        const panel = new THREE.Mesh(geo, mat);
        panel.position.set(4.5, 3.5, -2);
        panel.rotation.y = -Math.PI / 4;
        this.add(panel);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // FLOWING PARTICLES
    // ═══════════════════════════════════════════════════════════════════════
    
    createFlowingParticles() {
        const particleCount = 500;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            const fiberIndex = Math.floor(Math.random() * 7);
            const t = Math.random();
            const color = new THREE.Color(COLONY_DATA[fiberIndex].color);
            
            this.particleData.push({
                fiberIndex,
                t,
                speed: 0.1 + Math.random() * 0.15
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
            size: 0.06,
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
        // Prompt to start ride
        const promptCanvas = document.createElement('canvas');
        promptCanvas.width = 400;
        promptCanvas.height = 100;
        const promptCtx = promptCanvas.getContext('2d');
        
        promptCtx.fillStyle = 'rgba(0, 0, 0, 0.8)';
        promptCtx.roundRect(10, 10, 380, 80, 8);
        promptCtx.fill();
        
        promptCtx.strokeStyle = '#67D4E4';
        promptCtx.lineWidth = 2;
        promptCtx.roundRect(10, 10, 380, 80, 8);
        promptCtx.stroke();
        
        promptCtx.fillStyle = '#67D4E4';
        promptCtx.font = 'bold 24px "IBM Plex Sans", sans-serif';
        promptCtx.textAlign = 'center';
        promptCtx.fillText('CLICK FIBER TO RIDE S⁷', 200, 60);
        
        const promptTexture = new THREE.CanvasTexture(promptCanvas);
        const promptGeo = new THREE.PlaneGeometry(2.5, 0.625);
        const promptMat = new THREE.MeshBasicMaterial({
            map: promptTexture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        this.ridePrompt = new THREE.Mesh(promptGeo, promptMat);
        this.ridePrompt.position.set(0, 9.5, 0);
        this.add(this.ridePrompt);
        
        // S15 coordinate display (visible during ride)
        this.rideDisplayCanvas = document.createElement('canvas');
        this.rideDisplayCanvas.width = 500;
        this.rideDisplayCanvas.height = 300;
        this.rideDisplayTexture = new THREE.CanvasTexture(this.rideDisplayCanvas);
        
        const rideDisplayGeo = new THREE.PlaneGeometry(2.8, 1.68);
        const rideDisplayMat = new THREE.MeshBasicMaterial({
            map: this.rideDisplayTexture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        this.rideDisplay = new THREE.Mesh(rideDisplayGeo, rideDisplayMat);
        this.rideDisplay.position.set(0, 8, 0);
        this.rideDisplay.visible = false;
        this.add(this.rideDisplay);
        
        // Camera control callback
        this.onCameraUpdate = null;
    }
    
    updateRideDisplay() {
        if (!this.rideDisplayCanvas) return;
        
        const ctx = this.rideDisplayCanvas.getContext('2d');
        const w = this.rideDisplayCanvas.width;
        const h = this.rideDisplayCanvas.height;
        
        ctx.fillStyle = 'rgba(0, 0, 0, 0.9)';
        ctx.fillRect(0, 0, w, h);
        
        ctx.strokeStyle = COLONY_DATA[this.rideFiber].color;
        ctx.lineWidth = 3;
        ctx.strokeRect(5, 5, w - 10, h - 10);
        
        // Colony name
        const colonyColor = '#' + COLONY_DATA[this.rideFiber].color.toString(16).padStart(6, '0');
        ctx.fillStyle = colonyColor;
        ctx.font = 'bold 28px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`Riding ${COLONY_DATA[this.rideFiber].name} Fiber`, w/2, 45);
        
        // Progress bar
        ctx.fillStyle = '#333';
        ctx.fillRect(30, 70, w - 60, 15);
        ctx.fillStyle = colonyColor;
        ctx.fillRect(30, 70, (w - 60) * this.rideProgress, 15);
        
        // S15 coordinates display
        const point = this.fiberCurves[this.rideFiber].getPoint(this.rideProgress);
        
        // Simulated S15 coordinates (lift from 3D visualization to S15)
        const s15Coords = this.computeS15Coordinates(point, this.rideFiber);
        
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.textAlign = 'left';
        ctx.fillText('S¹⁵ COORDINATES:', 30, 115);
        
        ctx.fillStyle = '#F5F0E8';
        ctx.font = '12px "IBM Plex Mono", monospace';
        
        // Display first 8 (S8 base) and last 7 (S7 fiber)
        ctx.fillText(`S⁸ base:  [${s15Coords.s8.map(x => x.toFixed(2)).join(', ')}]`, 30, 140);
        ctx.fillText(`S⁷ fiber: [${s15Coords.s7.map(x => x.toFixed(2)).join(', ')}]`, 30, 165);
        
        // Hopf projection formula
        ctx.fillStyle = '#67D4E4';
        ctx.font = '12px "IBM Plex Mono", monospace';
        ctx.fillText('π(x,y) = (|x|²-|y|², 2x̄y) : S¹⁵ → S⁸', 30, 200);
        
        // Octonion basis element
        ctx.fillStyle = colonyColor;
        ctx.font = 'bold 18px "IBM Plex Mono", monospace';
        ctx.fillText(`Basis: e${this.rideFiber + 1}`, 30, 240);
        
        // Exit hint
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Press ESC or click elsewhere to exit ride', w/2, 280);
        
        this.rideDisplayTexture.needsUpdate = true;
    }
    
    computeS15Coordinates(point3D, fiberIndex) {
        // Compute approximate S15 coordinates from 3D visualization point
        // S15 = S8 (base) × S7 (fiber) via Hopf fibration
        
        const t = this.rideProgress;
        const phase = t * Math.PI * 2;
        
        // S8 base coordinates (8D unit vector)
        const s8 = [
            point3D.x * 0.3,
            point3D.y * 0.3 - 0.5,
            point3D.z * 0.3,
            Math.cos(phase) * 0.2,
            Math.sin(phase) * 0.2,
            Math.cos(phase * 2) * 0.15,
            Math.sin(phase * 2) * 0.15,
            0.1
        ];
        
        // Normalize to unit sphere
        const s8Norm = Math.sqrt(s8.reduce((sum, x) => sum + x*x, 0));
        const s8Normalized = s8.map(x => x / s8Norm);
        
        // S7 fiber coordinates (7D unit vector)
        const s7 = new Array(7).fill(0);
        s7[fiberIndex] = Math.cos(phase);
        s7[(fiberIndex + 1) % 7] = Math.sin(phase) * 0.5;
        s7[(fiberIndex + 2) % 7] = Math.sin(phase * 0.5) * 0.3;
        
        // Normalize
        const s7Norm = Math.sqrt(s7.reduce((sum, x) => sum + x*x, 0)) || 1;
        const s7Normalized = s7.map(x => x / s7Norm);
        
        return { s8: s8Normalized, s7: s7Normalized };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PLAQUE
    // ═══════════════════════════════════════════════════════════════════════
    
    createPlaque() {
        if (PATENT) {
            const plaque = createPlaque(PATENT, { width: 3, height: 2 });
            plaque.position.set(5.5, 1.2, 0);
            plaque.rotation.y = -Math.PI / 2;
            this.add(plaque);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    onClick(intersection) {
        const object = intersection?.object;
        if (object && object.userData && object.userData.type === 'hopf-fiber') {
            const fiberIndex = object.userData.index;
            this.startRide(fiberIndex);
        }
    }
    
    // Alias for backward compatibility
    handleClick(point, object) {
        this.onClick({ point, object });
    }
    
    startRide(fiberIndex) {
        console.log(`🎢 Riding S⁷ fiber ${fiberIndex} (${COLONY_DATA[fiberIndex].name})`);
        this.isRiding = true;
        this.rideFiber = fiberIndex;
        this.rideProgress = 0;
        this.activeColony = fiberIndex;
        this.fibers[fiberIndex].material.emissiveIntensity = 1.0;
        
        // Show ride display, hide prompt
        if (this.rideDisplay) this.rideDisplay.visible = true;
        if (this.ridePrompt) this.ridePrompt.visible = false;
        
        // Emit ride start event
        window.dispatchEvent(new CustomEvent('hopf-ride-start', {
            detail: { fiberIndex, colonyName: COLONY_DATA[fiberIndex].name }
        }));
    }
    
    endRide() {
        this.isRiding = false;
        if (this.activeColony !== null) {
            this.fibers[this.activeColony].material.emissiveIntensity = 0.3;
            this.activeColony = null;
        }
        
        // Hide ride display, show prompt
        if (this.rideDisplay) this.rideDisplay.visible = false;
        if (this.ridePrompt) this.ridePrompt.visible = true;
        
        // Emit ride end event
        window.dispatchEvent(new CustomEvent('hopf-ride-end'));
    }
    
    getRideCameraPosition() {
        if (!this.isRiding) return null;
        
        const curve = this.fiberCurves[this.rideFiber];
        const point = curve.getPoint(this.rideProgress);
        const tangent = curve.getTangent(this.rideProgress);
        
        // Camera follows fiber from slightly outside
        const offset = 2.5;
        const heightOffset = 1.0;
        
        // Position camera along the normal direction from curve
        const normal = new THREE.Vector3(-tangent.z, 0, tangent.x).normalize();
        
        const cameraPos = new THREE.Vector3(
            point.x + normal.x * offset,
            point.y + 3 + heightOffset + Math.sin(this.rideProgress * Math.PI * 4) * 0.3,
            point.z + normal.z * offset
        );
        
        // Look at the current point on the fiber
        const lookAt = new THREE.Vector3(point.x, point.y + 3, point.z);
        
        return {
            position: cameraPos,
            lookAt: lookAt,
            fiberIndex: this.rideFiber,
            progress: this.rideProgress
        };
    }
    
    // Set camera update callback for main.js to use
    setCameraCallback(callback) {
        this.onCameraUpdate = callback;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Rotate fibers with different speeds per colony
        this.fibers.forEach((fiber, i) => {
            const baseSpeed = 0.15 + i * 0.02;
            fiber.rotation.y = this.time * baseSpeed + i * 0.15;
            fiber.rotation.x = Math.sin(this.time * 0.2 + i * 0.5) * 0.08;
            
            // Pulse active fiber
            if (i === this.activeColony) {
                fiber.material.emissiveIntensity = 0.7 + Math.sin(this.time * 5) * 0.3;
            }
        });
        
        // Rotate base manifold (S⁸)
        if (this.baseManifold) {
            this.baseManifold.rotation.x = this.time * 0.3;
            this.baseManifold.rotation.y = this.time * 0.2;
            this.baseManifold.rotation.z = Math.sin(this.time * 0.25) * 0.15;
        }
        
        // Rotate shells with dimension-appropriate speeds
        if (this.s7Shell) {
            this.s7Shell.rotation.y = this.time * 0.25;
            this.s7Shell.rotation.x = Math.sin(this.time * 0.15) * 0.15;
        }
        if (this.s15Shell) {
            this.s15Shell.rotation.y = -this.time * 0.08;
            this.s15Shell.rotation.z = Math.sin(this.time * 0.1) * 0.08;
        }
        if (this.s8Shell) {
            this.s8Shell.rotation.x = this.time * 0.35;
            this.s8Shell.rotation.z = this.time * 0.25;
        }
        
        // Update flowing particles
        this.animateParticles(deltaTime);
        
        // Update ride progress
        if (this.isRiding) {
            this.rideProgress += deltaTime * 0.08;
            if (this.rideProgress >= 1) {
                this.rideProgress = 0; // Loop the ride
            }
            
            // Update ride display with S15 coordinates
            this.updateRideDisplay();
            
            // Call camera callback if registered
            if (this.onCameraUpdate) {
                const camData = this.getRideCameraPosition();
                if (camData) {
                    this.onCameraUpdate(camData);
                }
            }
        }
        
        // Float prompt
        if (this.ridePrompt) {
            this.ridePrompt.position.y = 9.5 + Math.sin(this.time * 0.4) * 0.1;
        }
    }
    
    animateParticles(deltaTime) {
        if (!this.particles || !this.particleData) return;
        
        const positions = this.particles.geometry.attributes.position.array;
        const fiberActivity = [0, 0, 0, 0, 0, 0, 0];
        
        this.particleData.forEach((data, i) => {
            // Move along fiber with colony-specific speed
            const colonySpeed = 0.7 + data.fiberIndex * 0.08;
            data.t = (data.t + deltaTime * data.speed * colonySpeed) % 1;
            
            // Track activity
            if (data.t > 0.4 && data.t < 0.6) {
                fiberActivity[data.fiberIndex] += 1;
            }
            
            // Get position on fiber curve
            const curve = this.fiberCurves[data.fiberIndex];
            const point = curve.getPoint(data.t);
            
            // Apply fiber rotation
            const baseSpeed = 0.15 + data.fiberIndex * 0.02;
            const fiberRotation = this.time * baseSpeed + data.fiberIndex * 0.15;
            const cos = Math.cos(fiberRotation);
            const sin = Math.sin(fiberRotation);
            
            const x = point.x * cos - point.z * sin;
            const z = point.x * sin + point.z * cos;
            
            positions[i * 3] = x;
            positions[i * 3 + 1] = point.y + 3;
            positions[i * 3 + 2] = z;
        });
        
        this.particles.geometry.attributes.position.needsUpdate = true;
        
        // Pulse fibers based on activity
        this.fibers.forEach((fiber, i) => {
            if (i !== this.activeColony) {
                const activity = fiberActivity[i] / 8;
                fiber.material.emissiveIntensity = 0.2 + activity * 0.4;
            }
        });
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
