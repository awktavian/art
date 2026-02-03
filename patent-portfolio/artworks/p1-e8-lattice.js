/**
 * P1-003: E8 Lattice Semantic Routing Artwork
 * ===========================================
 * 
 * An explorable 8-dimensional semantic space with 240 root vectors.
 * Type words to see them route through the lattice. Click nodes to
 * explore their 8D coordinates and connections.
 * 
 * Inspired by:
 * - James Turrell's Roden Crater celestial framing
 * - ARTECHOUSE's reactive systems
 * - The mathematical beauty of E8
 * 
 * Features:
 * - True E8 lattice with all 240 roots verified
 * - Interactive semantic search visualization
 * - Multi-hop routing with intermediate nodes
 * - 8D depth perception through size and fog
 * - Click nodes to see coordinates and neighbors
 * - Living crystal that breathes and rotates
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { PATENTS } from '../components/info-panel.js';

const PATENT = PATENTS.find(p => p.id === 'P1-003');

// Colony colors for semantic regions
const SEMANTIC_COLORS = {
    safety: 0x67D4E4,    // Crystal - safety/verification
    inference: 0x7EB77F, // Grove - reasoning/inference
    consensus: 0x9B7EBD, // Nexus - coordination
    crypto: 0xD4AF37,    // Forge - cryptography
    learning: 0xFF6B35,  // Spark - training/learning
    automation: 0x4ECDC4,// Flow - automation
    interface: 0xF59E0B  // Beacon - UI/interface
};

// ═══════════════════════════════════════════════════════════════════════════
// E8 LATTICE MATHEMATICS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Generate all 240 root vectors of the E8 lattice.
 * E8 has 240 minimal vectors of length √2.
 */
function generateE8Roots() {
    const roots = [];
    
    // Type 1: All permutations of (±1, ±1, 0, 0, 0, 0, 0, 0)
    // C(8,2) * 2^2 = 28 * 4 = 112 vectors
    for (let i = 0; i < 8; i++) {
        for (let j = i + 1; j < 8; j++) {
            for (let si = -1; si <= 1; si += 2) {
                for (let sj = -1; sj <= 1; sj += 2) {
                    const v = new Array(8).fill(0);
                    v[i] = si;
                    v[j] = sj;
                    roots.push(v);
                }
            }
        }
    }
    
    // Type 2: Half of (±1/2, ±1/2, ..., ±1/2) with even number of minuses
    // 2^8 / 2 = 128 vectors
    for (let bits = 0; bits < 256; bits++) {
        let negCount = 0;
        for (let i = 0; i < 8; i++) {
            if (bits & (1 << i)) negCount++;
        }
        if (negCount % 2 === 0) {
            const v = [];
            for (let i = 0; i < 8; i++) {
                v.push((bits & (1 << i)) ? -0.5 : 0.5);
            }
            roots.push(v);
        }
    }
    
    // Verify: should have exactly 240 roots
    console.assert(roots.length === 240, `E8 should have 240 roots, got ${roots.length}`);
    
    return roots;
}

/**
 * Project 8D vector to 3D using optimized projection.
 * Uses a rotation matrix derived from E8 symmetry.
 */
function project8Dto3D(v8, rotation = 0) {
    // Projection matrix optimized for visual clarity
    const cos = Math.cos(rotation);
    const sin = Math.sin(rotation);
    const cos2 = Math.cos(rotation * 0.7);
    const sin2 = Math.sin(rotation * 0.7);
    
    // Project to 3D with depth encoding
    const x = v8[0] * cos - v8[4] * sin + v8[1] * 0.3 + v8[5] * 0.2;
    const y = v8[1] * cos2 - v8[5] * sin2 + v8[2] * 0.4 + v8[6] * 0.3;
    const z = v8[2] * cos - v8[6] * sin + v8[3] * 0.5 + v8[7] * 0.4;
    
    return new THREE.Vector3(x, y, z);
}

/**
 * Calculate distance between two 8D vectors.
 */
function dist8D(a, b) {
    let sum = 0;
    for (let i = 0; i < 8; i++) {
        sum += (a[i] - b[i]) ** 2;
    }
    return Math.sqrt(sum);
}

/**
 * Find nearest neighbors in E8 lattice.
 * In E8, each root has exactly 56 nearest neighbors at distance √2.
 */
function findNeighbors(roots, index, maxDist = 1.42) {
    const neighbors = [];
    const root = roots[index];
    
    for (let i = 0; i < roots.length; i++) {
        if (i === index) continue;
        const d = dist8D(root, roots[i]);
        if (d <= maxDist) {
            neighbors.push({ index: i, distance: d });
        }
    }
    
    return neighbors.sort((a, b) => a.distance - b.distance);
}

// ═══════════════════════════════════════════════════════════════════════════
// E8 LATTICE ARTWORK
// ═══════════════════════════════════════════════════════════════════════════

export class E8LatticeArtwork extends THREE.Group {
    constructor() {
        super();
        this.name = 'artwork-e8-lattice';
        this.time = 0;
        
        // E8 data
        this.roots = generateE8Roots();
        this.nodes = [];
        this.connections = [];
        this.neighborMap = new Map();
        
        // Interaction state
        this.selectedNode = null;
        this.hoveredNode = null;
        this.searchQuery = '';
        this.activeRoutes = [];
        
        // Animation state
        this.rotationPhase = 0;
        this.breathPhase = 0;
        
        // Pre-compute neighbor relationships
        this.computeNeighborMap();
        
        this.create();
    }
    
    computeNeighborMap() {
        for (let i = 0; i < this.roots.length; i++) {
            const neighbors = findNeighbors(this.roots, i);
            this.neighborMap.set(i, neighbors.slice(0, 56)); // E8 has 56 nearest neighbors
        }
    }
    
    create() {
        // === CONTAINMENT STRUCTURE ===
        this.createCrystalShell();
        
        // === E8 LATTICE VISUALIZATION ===
        this.createLatticeNodes();
        this.createLatticeConnections();
        
        // === INTERACTIVE ELEMENTS ===
        this.createRoutingSystem();
        this.createSearchInterface();
        this.createInfoDisplay();
        
        // === ATMOSPHERIC ===
        this.createDepthFog();
        
        // === LABELS ===
        this.createDimensionLabels();
        this.createPlaque();
        
        // Mark as interactive
        this.userData.interactive = true;
        this.userData.artwork = PATENT;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CRYSTAL SHELL
    // ═══════════════════════════════════════════════════════════════════════
    
    createCrystalShell() {
        const group = new THREE.Group();
        group.name = 'crystal-shell';
        
        // Outer dodecahedron (E8 reference - 240 = 2 * 120, and dodecahedron has 120 symmetries)
        const outerGeo = new THREE.DodecahedronGeometry(4, 0);
        const outerMat = new THREE.MeshPhysicalMaterial({
            color: 0x67D4E4,
            metalness: 0.1,
            roughness: 0.1,
            transmission: 0.7,
            thickness: 0.5,
            clearcoat: 1.0,
            transparent: true,
            opacity: 0.3
        });
        this.outerShell = new THREE.Mesh(outerGeo, outerMat);
        this.outerShell.position.y = 3;
        group.add(this.outerShell);
        
        // Wireframe overlay
        const wireGeo = new THREE.DodecahedronGeometry(4.05, 0);
        const wireMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            wireframe: true,
            transparent: true,
            opacity: 0.4
        });
        const wire = new THREE.Mesh(wireGeo, wireMat);
        wire.position.y = 3;
        group.add(wire);
        
        // Inner glow
        const glowGeo = new THREE.IcosahedronGeometry(3.5, 2);
        const glowMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.03,
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeo, glowMat);
        glow.position.y = 3;
        group.add(glow);
        
        // Base pedestal
        const baseGeo = new THREE.CylinderGeometry(2, 2.5, 0.5, 32);
        const baseMat = new THREE.MeshPhysicalMaterial({
            color: 0x0A0A15,
            metalness: 0.9,
            roughness: 0.2,
            clearcoat: 0.5
        });
        const base = new THREE.Mesh(baseGeo, baseMat);
        base.position.y = 0.25;
        group.add(base);
        
        this.add(group);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // LATTICE NODES (240 roots)
    // ═══════════════════════════════════════════════════════════════════════
    
    createLatticeNodes() {
        const nodeGeo = new THREE.IcosahedronGeometry(0.06, 1);
        
        this.roots.forEach((root, i) => {
            // Assign semantic color based on 8D position
            const colorIndex = this.getSemanticRegion(root);
            const color = Object.values(SEMANTIC_COLORS)[colorIndex];
            
            const nodeMat = new THREE.MeshPhysicalMaterial({
                color: color,
                emissive: color,
                emissiveIntensity: 0.3,
                metalness: 0.5,
                roughness: 0.3
            });
            
            const node = new THREE.Mesh(nodeGeo, nodeMat);
            
            // Initial position (will be animated)
            const pos = project8Dto3D(root, 0);
            node.position.copy(pos);
            node.position.y += 3;
            
            // Store metadata for interaction
            node.userData = {
                index: i,
                root: root,
                type: 'e8-node',
                interactive: true,
                semanticRegion: colorIndex,
                coordinates8D: root.slice()
            };
            
            this.nodes.push(node);
            this.add(node);
        });
    }
    
    getSemanticRegion(root) {
        // Map 8D position to semantic region (0-6)
        // Using sum of first few dimensions
        const sum = root[0] + root[1] * 0.8 + root[2] * 0.6;
        const normalized = (sum + 2) / 4; // Roughly 0-1
        return Math.floor(normalized * 7) % 7;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // LATTICE CONNECTIONS
    // ═══════════════════════════════════════════════════════════════════════
    
    createLatticeConnections() {
        // Create connections based on E8 nearest-neighbor structure
        const connectedPairs = new Set();
        
        this.roots.forEach((root, i) => {
            const neighbors = this.neighborMap.get(i);
            
            // Only show a subset of connections for clarity (first 8 neighbors)
            neighbors.slice(0, 8).forEach(neighbor => {
                const j = neighbor.index;
                const pairKey = i < j ? `${i}-${j}` : `${j}-${i}`;
                
                if (!connectedPairs.has(pairKey)) {
                    connectedPairs.add(pairKey);
                    this.createConnection(i, j);
                }
            });
        });
    }
    
    createConnection(i, j) {
        const lineMat = new THREE.LineBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.15
        });
        
        const points = [
            this.nodes[i].position.clone(),
            this.nodes[j].position.clone()
        ];
        
        const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
        const line = new THREE.Line(lineGeo, lineMat);
        line.userData = { nodeA: i, nodeB: j };
        
        this.connections.push(line);
        this.add(line);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ROUTING SYSTEM
    // ═══════════════════════════════════════════════════════════════════════
    
    createRoutingSystem() {
        // Pool of route particles
        this.routeParticles = [];
        
        const particleGeo = new THREE.SphereGeometry(0.1, 8, 8);
        
        for (let i = 0; i < 30; i++) {
            const particleMat = new THREE.MeshBasicMaterial({
                color: 0xFFD700,
                transparent: true,
                opacity: 0
            });
            
            const particle = new THREE.Mesh(particleGeo, particleMat);
            particle.userData = {
                active: false,
                path: [],
                pathIndex: 0,
                progress: 0,
                speed: 0
            };
            
            this.routeParticles.push(particle);
            this.add(particle);
        }
    }
    
    triggerRoute(startNode, endNode) {
        // Find available particle
        const particle = this.routeParticles.find(p => !p.userData.active);
        if (!particle) return;
        
        // Calculate path through lattice (simplified - use intermediate hops)
        const path = this.findPath(startNode, endNode);
        
        particle.userData = {
            active: true,
            path: path,
            pathIndex: 0,
            progress: 0,
            speed: 0.3 + Math.random() * 0.2
        };
        
        particle.material.opacity = 1;
        particle.material.color.setHex(0xFFD700);
    }
    
    findPath(startIdx, endIdx) {
        // Simple pathfinding: use greedy approach through neighbors
        const path = [startIdx];
        let current = startIdx;
        const maxHops = 8;
        
        for (let hop = 0; hop < maxHops && current !== endIdx; hop++) {
            const neighbors = this.neighborMap.get(current);
            
            // Find neighbor closest to destination (in 8D)
            let bestNeighbor = null;
            let bestDist = Infinity;
            
            neighbors.forEach(n => {
                if (path.includes(n.index)) return;
                const dist = dist8D(this.roots[n.index], this.roots[endIdx]);
                if (dist < bestDist) {
                    bestDist = dist;
                    bestNeighbor = n.index;
                }
            });
            
            if (bestNeighbor !== null) {
                path.push(bestNeighbor);
                current = bestNeighbor;
            } else {
                break;
            }
        }
        
        // Add final destination if not reached
        if (current !== endIdx) {
            path.push(endIdx);
        }
        
        return path;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // SEARCH INTERFACE
    // ═══════════════════════════════════════════════════════════════════════
    
    createSearchInterface() {
        // Virtual search display (canvas texture)
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 128;
        this.searchCanvas = canvas;
        this.searchCtx = canvas.getContext('2d');
        
        this.updateSearchDisplay();
        
        const texture = new THREE.CanvasTexture(canvas);
        this.searchTexture = texture;
        
        const displayGeo = new THREE.PlaneGeometry(3, 0.75);
        const displayMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        this.searchDisplay = new THREE.Mesh(displayGeo, displayMat);
        this.searchDisplay.position.set(0, 6.5, 0);
        this.add(this.searchDisplay);
    }
    
    updateSearchDisplay() {
        const ctx = this.searchCtx;
        ctx.clearRect(0, 0, 512, 128);
        
        // Background
        ctx.fillStyle = 'rgba(0, 0, 0, 0.8)';
        ctx.roundRect(10, 10, 492, 108, 8);
        ctx.fill();
        
        // Search prompt
        ctx.fillStyle = '#9E9994';
        ctx.font = '20px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('SEMANTIC QUERY:', 30, 45);
        
        // Query text
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 28px "IBM Plex Mono", monospace';
        ctx.fillText(this.searchQuery || '▮ Type to search...', 30, 85);
        
        if (this.searchTexture) {
            this.searchTexture.needsUpdate = true;
        }
    }
    
    performSearch(query) {
        this.searchQuery = query;
        this.updateSearchDisplay();
        
        // Map query to semantic region and trigger route
        const queryHash = query.split('').reduce((a, c) => a + c.charCodeAt(0), 0);
        const startNode = queryHash % 240;
        const endNode = (queryHash * 7 + 123) % 240;
        
        this.triggerRoute(startNode, endNode);
        
        // Highlight destination node
        this.highlightNode(endNode);
    }
    
    highlightNode(index) {
        // Temporarily highlight a node
        const node = this.nodes[index];
        const originalEmissive = node.material.emissiveIntensity;
        
        node.material.emissiveIntensity = 1.5;
        node.scale.setScalar(2);
        
        setTimeout(() => {
            node.material.emissiveIntensity = originalEmissive;
            node.scale.setScalar(1);
        }, 2000);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INFO DISPLAY
    // ═══════════════════════════════════════════════════════════════════════
    
    createInfoDisplay() {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 256;
        this.infoCanvas = canvas;
        this.infoCtx = canvas.getContext('2d');
        
        this.updateInfoDisplay(null);
        
        const texture = new THREE.CanvasTexture(canvas);
        this.infoTexture = texture;
        
        const displayGeo = new THREE.PlaneGeometry(2, 1);
        const displayMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        
        this.infoDisplay = new THREE.Mesh(displayGeo, displayMat);
        this.infoDisplay.position.set(4, 3, 0);
        this.infoDisplay.rotation.y = -Math.PI / 4;
        this.add(this.infoDisplay);
    }
    
    updateInfoDisplay(nodeData) {
        const ctx = this.infoCtx;
        ctx.clearRect(0, 0, 512, 256);
        
        ctx.fillStyle = 'rgba(0, 0, 0, 0.85)';
        ctx.roundRect(10, 10, 492, 236, 8);
        ctx.fill();
        
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 20px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('E₈ NODE INFO', 256, 40);
        
        if (nodeData) {
            // Show 8D coordinates
            ctx.fillStyle = '#F5F0E8';
            ctx.font = '14px "IBM Plex Mono", monospace';
            ctx.textAlign = 'left';
            
            const coords = nodeData.coordinates8D;
            ctx.fillText(`Node #${nodeData.index}`, 30, 75);
            ctx.fillText(`[${coords.map(c => c.toFixed(1)).join(', ')}]`, 30, 100);
            
            ctx.fillText(`Neighbors: ${this.neighborMap.get(nodeData.index)?.length || 0}`, 30, 135);
            ctx.fillText(`Region: ${Object.keys(SEMANTIC_COLORS)[nodeData.semanticRegion]}`, 30, 160);
            
            // Show distance from origin
            const distFromOrigin = Math.sqrt(coords.reduce((a, c) => a + c * c, 0));
            ctx.fillText(`|v| = ${distFromOrigin.toFixed(3)}`, 30, 195);
        } else {
            ctx.fillStyle = '#9E9994';
            ctx.font = '16px "IBM Plex Sans", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('Click a node to see', 256, 100);
            ctx.fillText('its 8D coordinates', 256, 125);
        }
        
        if (this.infoTexture) {
            this.infoTexture.needsUpdate = true;
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DEPTH FOG
    // ═══════════════════════════════════════════════════════════════════════
    
    createDepthFog() {
        // Particles that create sense of depth in 8D space
        const particleCount = 300;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            const r = 2 + Math.random() * 2;
            
            positions[i * 3] = Math.sin(phi) * Math.cos(theta) * r;
            positions[i * 3 + 1] = Math.cos(phi) * r + 3;
            positions[i * 3 + 2] = Math.sin(phi) * Math.sin(theta) * r;
            
            colors[i * 3] = 0.4;
            colors[i * 3 + 1] = 0.83;
            colors[i * 3 + 2] = 0.89;
        }
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const material = new THREE.PointsMaterial({
            size: 0.03,
            vertexColors: true,
            transparent: true,
            opacity: 0.2,
            blending: THREE.AdditiveBlending
        });
        
        this.fogParticles = new THREE.Points(geometry, material);
        this.add(this.fogParticles);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DIMENSION LABELS
    // ═══════════════════════════════════════════════════════════════════════
    
    createDimensionLabels() {
        const canvas = document.createElement('canvas');
        canvas.width = 512;
        canvas.height = 128;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 64px "Orbitron", "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('E₈ · 240 ROOTS · 8D', 256, 64);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(4, 1);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.set(0, 7.5, 0);
        this.add(label);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // PLAQUE
    // ═══════════════════════════════════════════════════════════════════════
    
    createPlaque() {
        if (PATENT) {
            const plaque = createPlaque(PATENT, { width: 3, height: 2 });
            plaque.position.set(0, 1, 5);
            plaque.rotation.x = -0.1;
            this.add(plaque);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    handleClick(point, object) {
        if (object && object.userData && object.userData.type === 'e8-node') {
            this.selectedNode = object.userData.index;
            this.updateInfoDisplay(object.userData);
            
            // Highlight neighbors
            const neighbors = this.neighborMap.get(object.userData.index);
            neighbors?.slice(0, 8).forEach(n => {
                this.highlightNode(n.index);
            });
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        this.rotationPhase += deltaTime * 0.15;
        this.breathPhase += deltaTime * 0.5;
        
        // Breathing scale effect
        const breathScale = 1 + Math.sin(this.breathPhase) * 0.02;
        
        // Update node positions with rotation
        this.roots.forEach((root, i) => {
            const pos = project8Dto3D(root, this.rotationPhase);
            const node = this.nodes[i];
            
            node.position.copy(pos);
            node.position.multiplyScalar(breathScale);
            node.position.y += 3;
            
            // Pulse opacity based on "depth" in 8D
            const depth = root[3] + root[7];
            node.material.opacity = 0.6 + Math.sin(this.time * 2 + i * 0.1) * 0.2 + depth * 0.1;
            node.material.emissiveIntensity = 0.3 + Math.sin(this.time + i * 0.05) * 0.2;
        });
        
        // Update connection lines
        this.connections.forEach((line, i) => {
            const nodeA = this.nodes[line.userData.nodeA];
            const nodeB = this.nodes[line.userData.nodeB];
            
            const positions = line.geometry.attributes.position.array;
            positions[0] = nodeA.position.x;
            positions[1] = nodeA.position.y;
            positions[2] = nodeA.position.z;
            positions[3] = nodeB.position.x;
            positions[4] = nodeB.position.y;
            positions[5] = nodeB.position.z;
            line.geometry.attributes.position.needsUpdate = true;
            
            line.material.opacity = 0.1 + Math.sin(this.time * 0.5 + i * 0.1) * 0.05;
        });
        
        // Rotate shells
        if (this.outerShell) {
            this.outerShell.rotation.x = Math.sin(this.time * 0.2) * 0.1;
            this.outerShell.rotation.y = this.time * 0.05;
            this.outerShell.scale.setScalar(breathScale);
        }
        
        // Animate route particles
        this.animateRoutes(deltaTime);
        
        // Animate fog particles
        if (this.fogParticles) {
            this.fogParticles.rotation.y = this.time * 0.02;
        }
        
        // Float search display
        if (this.searchDisplay) {
            this.searchDisplay.position.y = 6.5 + Math.sin(this.time * 0.3) * 0.1;
        }
        
        // Periodic auto-routing for visual interest
        if (Math.random() < deltaTime * 0.3) {
            const start = Math.floor(Math.random() * 240);
            const end = Math.floor(Math.random() * 240);
            this.triggerRoute(start, end);
        }
    }
    
    animateRoutes(deltaTime) {
        // Track which nodes have active routing
        const activeNodes = new Set();
        const activeConnections = new Set();
        
        this.routeParticles.forEach(particle => {
            if (!particle.userData.active) return;
            
            const data = particle.userData;
            data.progress += deltaTime * data.speed;
            
            if (data.progress >= 1) {
                // Move to next segment
                data.pathIndex++;
                data.progress = 0;
                
                if (data.pathIndex >= data.path.length - 1) {
                    // Route complete
                    particle.userData.active = false;
                    particle.material.opacity = 0;
                    return;
                }
            }
            
            // Track active nodes for pulsing
            const currentIdx = data.path[data.pathIndex];
            const nextIdx = data.path[data.pathIndex + 1];
            activeNodes.add(currentIdx);
            activeNodes.add(nextIdx);
            activeConnections.add(`${Math.min(currentIdx, nextIdx)}-${Math.max(currentIdx, nextIdx)}`);
            
            // Interpolate between current and next node
            const currentNode = this.nodes[currentIdx];
            const nextNode = this.nodes[nextIdx];
            
            particle.position.lerpVectors(
                currentNode.position,
                nextNode.position,
                data.progress
            );
            
            // Fade based on progress through entire route
            const totalProgress = (data.pathIndex + data.progress) / (data.path.length - 1);
            particle.material.opacity = Math.sin(totalProgress * Math.PI);
        });
        
        // Pulse nodes that are part of active routes
        this.nodes.forEach((node, i) => {
            if (activeNodes.has(i)) {
                // Bright pulse when routing through
                node.material.emissiveIntensity = 1.0;
                node.scale.setScalar(1.3);
            } else {
                // Decay back to normal
                node.material.emissiveIntensity = Math.max(0.3, node.material.emissiveIntensity * 0.95);
                node.scale.lerp(new THREE.Vector3(1, 1, 1), 0.1);
            }
        });
        
        // Brighten connections on active routes
        this.connections.forEach((line) => {
            const key = `${Math.min(line.userData.nodeA, line.userData.nodeB)}-${Math.max(line.userData.nodeA, line.userData.nodeB)}`;
            if (activeConnections.has(key)) {
                line.material.opacity = 0.6;
                line.material.color.setHex(0x67D4E4);
            } else {
                line.material.opacity = Math.max(0.1, line.material.opacity * 0.95);
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

export function createE8LatticeArtwork() {
    return new E8LatticeArtwork();
}

export default E8LatticeArtwork;
