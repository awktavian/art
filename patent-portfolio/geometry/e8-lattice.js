/**
 * E8 Lattice Visualization
 * =========================
 * 
 * 240 roots of the E8 lattice visualized as instanced particles.
 * E8 achieves optimal sphere packing in 8 dimensions (Viazovska, 2016).
 * Used for semantic routing in Kagami.
 * 
 * E8 = D8 ∪ (D8 + ½·1⃗)
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import {
    COLONY_ORDER,
    COLONY_COLORS,
    getColonyColor as getColonyColorBase,
    DURATION_S
} from '../../lib/design-tokens.js';

// Helper to get colony color as THREE.Color
function getColonyColor(index) {
    return getColonyColorBase(THREE, index);
}

// ═══════════════════════════════════════════════════════════════════════════
// E8 ROOT SYSTEM GENERATION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Generate the 240 roots of E8 lattice
 * E8 roots have the form:
 * - 112 roots: all permutations of (±1, ±1, 0, 0, 0, 0, 0, 0)
 * - 128 roots: (±½, ±½, ±½, ±½, ±½, ±½, ±½, ±½) with even number of minus signs
 */
function generateE8Roots() {
    const roots = [];
    
    // Type 1: Permutations of (±1, ±1, 0, 0, 0, 0, 0, 0) - 112 roots
    for (let i = 0; i < 8; i++) {
        for (let j = i + 1; j < 8; j++) {
            for (const si of [-1, 1]) {
                for (const sj of [-1, 1]) {
                    const root = [0, 0, 0, 0, 0, 0, 0, 0];
                    root[i] = si;
                    root[j] = sj;
                    roots.push(root);
                }
            }
        }
    }
    
    // Type 2: Half-integer coordinates with even number of minus signs - 128 roots
    for (let mask = 0; mask < 256; mask++) {
        // Count number of 1 bits (minus signs)
        let count = 0;
        for (let i = 0; i < 8; i++) {
            if (mask & (1 << i)) count++;
        }
        
        // Only even number of minus signs
        if (count % 2 === 0) {
            const root = [];
            for (let i = 0; i < 8; i++) {
                root.push((mask & (1 << i)) ? -0.5 : 0.5);
            }
            roots.push(root);
        }
    }
    
    return roots;
}

/**
 * Project 8D E8 root to 3D using stereographic-like projection
 */
function projectE8To3D(root8D) {
    // Use first 3 coordinates plus a projection of the remaining 5
    const x = root8D[0] + root8D[3] * 0.3 + root8D[6] * 0.1;
    const y = root8D[1] + root8D[4] * 0.3 + root8D[7] * 0.1;
    const z = root8D[2] + root8D[5] * 0.3;
    
    return new THREE.Vector3(x, y, z);
}

/**
 * Assign colony to E8 root based on position
 */
function assignColony(root8D, index) {
    // Partition 240 roots into 7 colonies (~34 each)
    // Use a hash of the root's position
    const hash = Math.abs(
        root8D[0] * 7 + root8D[1] * 13 + root8D[2] * 17 + 
        root8D[3] * 23 + root8D[4] * 29 + root8D[5] * 31 +
        root8D[6] * 37 + root8D[7] * 41
    );
    return Math.floor(hash * 7) % 7;
}

// ═══════════════════════════════════════════════════════════════════════════
// E8 LATTICE CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class E8Lattice extends THREE.Group {
    constructor(options = {}) {
        super();
        
        this.options = {
            scale: options.scale || 5,
            particleSize: options.particleSize || 0.08,
            rotationSpeed: options.rotationSpeed || 0.02,
            pulseSpeed: options.pulseSpeed || 1.0,
            showConnections: options.showConnections !== false,
            connectionOpacity: options.connectionOpacity || 0.15,
            ...options
        };
        
        // Generate E8 roots
        this.roots8D = generateE8Roots();
        this.roots3D = this.roots8D.map(r => projectE8To3D(r));
        this.colonyAssignments = this.roots8D.map((r, i) => assignColony(r, i));
        
        // Animation state
        this.time = 0;
        this.rotationMatrix = new THREE.Matrix4();
        
        // Build geometry
        this.createParticles();
        
        if (this.options.showConnections) {
            this.createConnections();
        }
        
        this.name = 'E8Lattice';
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PARTICLE CREATION (Instanced)
    // ═══════════════════════════════════════════════════════════════════════
    
    createParticles() {
        const { scale, particleSize } = this.options;
        const count = 240;
        
        // Icosahedron geometry for particles
        const geometry = new THREE.IcosahedronGeometry(particleSize, 1);
        
        // Material with vertex colors
        const material = new THREE.MeshPhysicalMaterial({
            metalness: 0.3,
            roughness: 0.4,
            clearcoat: 0.5,
            transparent: true,
            opacity: 0.85
        });
        
        // Create instanced mesh
        this.particles = new THREE.InstancedMesh(geometry, material, count);
        this.particles.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
        
        // Initialize instance colors
        const colors = new Float32Array(count * 3);
        const color = new THREE.Color();
        
        // Store data for animation
        this.particleData = [];
        
        for (let i = 0; i < count; i++) {
            const root3D = this.roots3D[i];
            const colony = this.colonyAssignments[i];
            
            // Set color based on colony
            color.copy(getColonyColor(colony));
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
            
            // Store animation data
            this.particleData.push({
                basePosition: root3D.clone().multiplyScalar(scale),
                colony: colony,
                phase: (i * 0.618) % 1 * Math.PI * 2, // Golden ratio distribution
                scale: 1.0
            });
        }
        
        // Apply colors
        this.particles.instanceColor = new THREE.InstancedBufferAttribute(colors, 3);
        
        // Initial matrix setup
        this.updateParticleMatrices();
        
        this.add(this.particles);
    }
    
    updateParticleMatrices() {
        const matrix = new THREE.Matrix4();
        const position = new THREE.Vector3();
        const quaternion = new THREE.Quaternion();
        const scale = new THREE.Vector3();
        
        for (let i = 0; i < 240; i++) {
            const data = this.particleData[i];
            
            position.copy(data.basePosition);
            
            // Apply 8D rotation projection (animate through different 3D slices)
            position.applyMatrix4(this.rotationMatrix);
            
            quaternion.setFromAxisAngle(new THREE.Vector3(0, 1, 0), this.time + data.phase);
            scale.setScalar(data.scale);
            
            matrix.compose(position, quaternion, scale);
            this.particles.setMatrixAt(i, matrix);
        }
        
        this.particles.instanceMatrix.needsUpdate = true;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CONNECTION LINES
    // ═══════════════════════════════════════════════════════════════════════
    
    createConnections() {
        const { scale, connectionOpacity } = this.options;
        
        // Create sparse connections (neighbors in E8)
        const connectionGeometry = new THREE.BufferGeometry();
        const positions = [];
        const colors = [];
        
        // Connect nearby particles (simplified - just show structure)
        for (let i = 0; i < 240; i += 3) {
            const p1 = this.roots3D[i].clone().multiplyScalar(scale);
            const p2 = this.roots3D[(i + 15) % 240].clone().multiplyScalar(scale);
            
            const c1 = getColonyColor(this.colonyAssignments[i]);
            const c2 = getColonyColor(this.colonyAssignments[(i + 15) % 240]);
            
            positions.push(p1.x, p1.y, p1.z);
            positions.push(p2.x, p2.y, p2.z);
            
            colors.push(c1.r, c1.g, c1.b);
            colors.push(c2.r, c2.g, c2.b);
        }
        
        connectionGeometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        connectionGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        
        const connectionMaterial = new THREE.LineBasicMaterial({
            vertexColors: true,
            transparent: true,
            opacity: connectionOpacity,
            blending: THREE.AdditiveBlending
        });
        
        this.connections = new THREE.LineSegments(connectionGeometry, connectionMaterial);
        this.add(this.connections);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION UPDATE
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime * this.options.pulseSpeed;
        
        // Update 8D rotation (creates the illusion of rotating through higher dimensions)
        const angle = this.time * this.options.rotationSpeed;
        
        // Rotation in the 3-7 plane (one of the extra dimensions)
        this.rotationMatrix.identity();
        const c = Math.cos(angle * 0.3);
        const s = Math.sin(angle * 0.3);
        
        // Simple rotation effect
        this.rotationMatrix.makeRotationY(angle);
        
        // Pulse animation for particles
        for (let i = 0; i < 240; i++) {
            const data = this.particleData[i];
            const pulse = Math.sin(this.time * 2 + data.phase) * 0.15 + 1.0;
            data.scale = pulse;
        }
        
        // Update matrices
        this.updateParticleMatrices();
        
        // Rotate the entire group slightly
        this.rotation.y = Math.sin(this.time * 0.1) * 0.05;
        this.rotation.x = Math.sin(this.time * 0.07) * 0.03;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    /**
     * Highlight particles of a specific colony
     */
    highlightColony(colonyIndex, highlight = true) {
        const colors = this.particles.instanceColor.array;
        const highlightFactor = highlight ? 1.5 : 1.0;
        
        for (let i = 0; i < 240; i++) {
            if (this.colonyAssignments[i] === colonyIndex) {
                const color = getColonyColor(colonyIndex);
                colors[i * 3] = Math.min(1, color.r * highlightFactor);
                colors[i * 3 + 1] = Math.min(1, color.g * highlightFactor);
                colors[i * 3 + 2] = Math.min(1, color.b * highlightFactor);
                
                this.particleData[i].scale = highlight ? 1.5 : 1.0;
            }
        }
        
        this.particles.instanceColor.needsUpdate = true;
    }
    
    /**
     * Set visibility by colony
     */
    setColonyVisibility(colonyIndex, visible) {
        for (let i = 0; i < 240; i++) {
            if (this.colonyAssignments[i] === colonyIndex) {
                this.particleData[i].scale = visible ? 1.0 : 0.0;
            }
        }
    }
    
    /**
     * Get statistics
     */
    getStats() {
        const colonyCounts = new Array(7).fill(0);
        for (const colony of this.colonyAssignments) {
            colonyCounts[colony]++;
        }
        
        return {
            totalRoots: 240,
            colonyCounts,
            avgPerColony: 240 / 7
        };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DISPOSAL
    // ═══════════════════════════════════════════════════════════════════════
    
    dispose() {
        if (this.particles) {
            this.particles.geometry.dispose();
            this.particles.material.dispose();
        }
        
        if (this.connections) {
            this.connections.geometry.dispose();
            this.connections.material.dispose();
        }
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FACTORY FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

export function createE8Lattice(options = {}) {
    return new E8Lattice(options);
}

export default E8Lattice;
