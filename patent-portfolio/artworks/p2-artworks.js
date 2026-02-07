/**
 * P2 Custom Artworks
 * ==================
 * 
 * Distinct visualizations for P2 (Priority 2) patents.
 * Each artwork has its own unique visual language tied to the patent's innovation.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { PATENTS } from '../components/info-panel.js';

// ═══════════════════════════════════════════════════════════════════════════
// SHARED UTILITIES
// ═══════════════════════════════════════════════════════════════════════════

function getPatent(id) {
    return PATENTS.find(p => p.id === id);
}

// Colony colors
const COLONY_COLORS = {
    spark:   0xFF6B35,
    forge:   0xD4AF37,
    flow:    0x4ECDC4,
    nexus:   0x9B7EBD,
    beacon:  0xF59E0B,
    grove:   0x7EB77F,
    crystal: 0x67D4E4
};

// ═══════════════════════════════════════════════════════════════════════════
// P2-A4: G2 EQUIVARIANT NEURAL LAYERS
// Visualizes the G2 Lie group symmetry
// ═══════════════════════════════════════════════════════════════════════════

export class G2EquivariantArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-A4');
        this.name = 'artwork-p2-a4';
        this.time = 0;
        this.nodes = [];
        this.edges = [];
        this.create();
    }
    
    create() {
        // G2 has a 14-dimensional representation
        // Its Dynkin diagram is ○=≡○ (with triple edge)
        
        // Create rotating G2 root system visualization
        this.createRootSystem();
        this.createWeightLattice();
        this.createDynkinDiagram();
        this.createPedestal();
        
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2.5, height: 1.5 });
            plaque.position.set(2, 0.5, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P2-A4', interactive: true };
    }
    
    createRootSystem() {
        // G2 has 12 roots arranged in a hexagonal pattern
        const rootGeo = new THREE.SphereGeometry(0.08, 16, 16);
        const rootMat = new THREE.MeshPhysicalMaterial({
            color: COLONY_COLORS.spark,
            emissive: COLONY_COLORS.spark,
            emissiveIntensity: 0.3,
            metalness: 0.5,
            roughness: 0.3
        });
        
        // Short roots (6)
        for (let i = 0; i < 6; i++) {
            const angle = (i / 6) * Math.PI * 2;
            const node = new THREE.Mesh(rootGeo, rootMat.clone());
            node.position.set(
                Math.cos(angle) * 0.8,
                2,
                Math.sin(angle) * 0.8
            );
            this.nodes.push(node);
            this.add(node);
        }
        
        // Long roots (6) - at √3 times the distance
        const longRootMat = rootMat.clone();
        longRootMat.color.setHex(0xFFD700);
        
        for (let i = 0; i < 6; i++) {
            const angle = (i / 6) * Math.PI * 2 + Math.PI / 6;
            const node = new THREE.Mesh(rootGeo, longRootMat);
            node.position.set(
                Math.cos(angle) * 1.4,
                2,
                Math.sin(angle) * 1.4
            );
            this.nodes.push(node);
            this.add(node);
        }
        
        // Connect roots with edges
        this.createEdges();
    }
    
    createEdges() {
        const edgeMat = new THREE.LineBasicMaterial({
            color: 0xF5F0E8,
            transparent: true,
            opacity: 0.3
        });
        
        // Connect adjacent roots
        for (let i = 0; i < 6; i++) {
            const next = (i + 1) % 6;
            
            // Short to short
            const points1 = [
                this.nodes[i].position.clone(),
                this.nodes[next].position.clone()
            ];
            const geo1 = new THREE.BufferGeometry().setFromPoints(points1);
            const line1 = new THREE.Line(geo1, edgeMat);
            this.edges.push(line1);
            this.add(line1);
            
            // Long to long
            const points2 = [
                this.nodes[i + 6].position.clone(),
                this.nodes[next + 6].position.clone()
            ];
            const geo2 = new THREE.BufferGeometry().setFromPoints(points2);
            const line2 = new THREE.Line(geo2, edgeMat);
            this.edges.push(line2);
            this.add(line2);
        }
    }
    
    createWeightLattice() {
        // Transparent container showing the weight lattice
        const latticeGeo = new THREE.DodecahedronGeometry(1.8, 0);
        const latticeMat = new THREE.MeshBasicMaterial({
            color: COLONY_COLORS.spark,
            wireframe: true,
            transparent: true,
            opacity: 0.15
        });
        
        this.lattice = new THREE.Mesh(latticeGeo, latticeMat);
        this.lattice.position.y = 2;
        this.add(this.lattice);
    }
    
    createDynkinDiagram() {
        // G2 Dynkin diagram: ○=≡○
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 64;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        
        ctx.fillStyle = 'rgba(0,0,0,0.8)';
        ctx.fillRect(0, 0, 256, 64);
        
        // Draw circles
        ctx.strokeStyle = '#FF6B35';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(64, 32, 15, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(192, 32, 15, 0, Math.PI * 2);
        ctx.stroke();
        
        // Draw triple edge
        ctx.beginPath();
        for (let i = -1; i <= 1; i++) {
            ctx.moveTo(79, 32 + i * 5);
            ctx.lineTo(177, 32 + i * 5);
        }
        ctx.stroke();
        
        // Arrow
        ctx.beginPath();
        ctx.moveTo(140, 25);
        ctx.lineTo(150, 32);
        ctx.lineTo(140, 39);
        ctx.stroke();
        
        const texture = new THREE.CanvasTexture(canvas);
        const geo = new THREE.PlaneGeometry(1.5, 0.375);
        const mat = new THREE.MeshBasicMaterial({ map: texture, transparent: true, side: THREE.DoubleSide });
        const diagram = new THREE.Mesh(geo, mat);
        diagram.position.set(0, 3.5, 0);
        this.add(diagram);
    }
    
    createPedestal() {
        const pedestalGeo = new THREE.CylinderGeometry(1, 1.2, 0.3, 32);
        const pedestalMat = new THREE.MeshPhysicalMaterial({
            color: 0x1D1C22,
            metalness: 0.9,
            roughness: 0.1
        });
        const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
        pedestal.position.y = 0.15;
        pedestal.userData.isPedestal = true;
        this.add(pedestal);
    }
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Rotate the root system
        this.nodes.forEach((node, i) => {
            node.rotation.y = this.time * 0.3;
            node.material.emissiveIntensity = 0.3 + Math.sin(this.time * 2 + i) * 0.2;
        });
        
        if (this.lattice) {
            this.lattice.rotation.y = this.time * 0.1;
            this.lattice.rotation.x = Math.sin(this.time * 0.2) * 0.1;
        }
    }
    
    dispose() {
        this.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-B2: 3-TIER CBF SAFETY HIERARCHY
// Nested safety barriers visualization
// ═══════════════════════════════════════════════════════════════════════════

export class SafetyHierarchyArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-B2');
        this.name = 'artwork-p2-b2';
        this.time = 0;
        this.barriers = [];
        this.create();
    }
    
    create() {
        // 3 nested barriers representing safety tiers
        this.createBarriers();
        this.createSafetyIndicators();
        this.createCenterAgent();
        this.createPedestal();
        
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2.5, height: 1.5 });
            plaque.position.set(2.5, 0.5, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P2-B2', interactive: true };
    }
    
    createBarriers() {
        // Film-quality colors: Spark (danger) → Beacon (caution) → Grove (safe)
        const tierColors = [0xE85A2F, 0xE8940A, 0x6FA370];
        const tierSizes = [2.0, 1.4, 0.8];
        
        tierColors.forEach((color, i) => {
            // Barrier sphere
            const barrierGeo = new THREE.SphereGeometry(tierSizes[i], 32, 32);
            const barrierMat = new THREE.MeshPhysicalMaterial({
                color: color,
                transparent: true,
                opacity: 0.15 + i * 0.1,
                side: THREE.DoubleSide,
                metalness: 0.1,
                roughness: 0.9
            });
            
            const barrier = new THREE.Mesh(barrierGeo, barrierMat);
            barrier.position.y = 1.5;
            this.barriers.push(barrier);
            this.add(barrier);
            
            // Wireframe
            const wireGeo = new THREE.SphereGeometry(tierSizes[i] + 0.02, 16, 16);
            const wireMat = new THREE.MeshBasicMaterial({
                color: color,
                wireframe: true,
                transparent: true,
                opacity: 0.3
            });
            const wire = new THREE.Mesh(wireGeo, wireMat);
            wire.position.y = 1.5;
            this.add(wire);
        });
    }
    
    createSafetyIndicators() {
        // Labels for each tier
        const tiers = ['h₁(x) Behavioral', 'h₂(x) Operational', 'h₃(x) Catastrophic'];
        
        tiers.forEach((label, i) => {
            const canvas = document.createElement('canvas');
            canvas.width = 256;
            canvas.height = 48;
            const ctx = canvas.getContext('2d', { willReadFrequently: true });
            
            // Colony-based status colors: Grove (safe) → Beacon (caution) → Spark (danger)
            const colors = ['#6FA370', '#E8940A', '#E85A2F'];
            ctx.fillStyle = colors[i];
            ctx.font = '18px "IBM Plex Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(label, 128, 32);
            
            const texture = new THREE.CanvasTexture(canvas);
            const geo = new THREE.PlaneGeometry(1.5, 0.28);
            const mat = new THREE.MeshBasicMaterial({ map: texture, transparent: true, side: THREE.DoubleSide });
            const labelMesh = new THREE.Mesh(geo, mat);
            labelMesh.position.set(-1.8, 2.5 - i * 0.5, 0);
            labelMesh.rotation.y = Math.PI / 6;
            this.add(labelMesh);
        });
    }
    
    createCenterAgent() {
        // Agent at the center (protected by barriers)
        const agentGeo = new THREE.SphereGeometry(0.15, 32, 32);
        const agentMat = new THREE.MeshPhysicalMaterial({
            color: 0x67D4E4,
            emissive: 0x67D4E4,
            emissiveIntensity: 0.5,
            metalness: 0.5,
            roughness: 0.3
        });
        
        this.agent = new THREE.Mesh(agentGeo, agentMat);
        this.agent.position.y = 1.5;
        this.add(this.agent);
    }
    
    createPedestal() {
        const pedestalGeo = new THREE.CylinderGeometry(1.2, 1.4, 0.3, 32);
        const pedestalMat = new THREE.MeshPhysicalMaterial({
            color: 0x1D1C22,
            metalness: 0.9,
            roughness: 0.1
        });
        const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
        pedestal.position.y = 0.15;
        pedestal.userData.isPedestal = true;
        this.add(pedestal);
    }
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Pulse barriers
        this.barriers.forEach((barrier, i) => {
            const scale = 1 + Math.sin(this.time * (1 + i * 0.3)) * 0.05;
            barrier.scale.setScalar(scale);
            barrier.rotation.y = this.time * 0.1 * (i + 1);
        });
        
        // Pulse agent
        if (this.agent) {
            this.agent.material.emissiveIntensity = 0.5 + Math.sin(this.time * 3) * 0.2;
        }
    }
    
    dispose() {
        this.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-C2: CROSS-HUB CRDT SYSTEM
// Distributed state synchronization
// ═══════════════════════════════════════════════════════════════════════════

export class CrossHubCRDTArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-C2');
        this.name = 'artwork-p2-c2';
        this.time = 0;
        this.hubs = [];
        this.syncPulses = [];
        this.create();
    }
    
    create() {
        this.createHubs();
        this.createConnections();
        this.createSyncPulses();
        this.createPedestal();
        
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2.5, height: 1.5 });
            plaque.position.set(2.5, 0.5, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P2-C2', interactive: true };
    }
    
    createHubs() {
        // 5 hubs in a pentagon arrangement
        const hubGeo = new THREE.IcosahedronGeometry(0.25, 1);
        const hubColors = [0xFF6B35, 0xD4AF37, 0x4ECDC4, 0x9B7EBD, 0x7EB77F];
        
        for (let i = 0; i < 5; i++) {
            const angle = (i / 5) * Math.PI * 2 - Math.PI / 2;
            const hubMat = new THREE.MeshPhysicalMaterial({
                color: hubColors[i],
                emissive: hubColors[i],
                emissiveIntensity: 0.3,
                metalness: 0.5,
                roughness: 0.3
            });
            
            const hub = new THREE.Mesh(hubGeo, hubMat);
            hub.position.set(
                Math.cos(angle) * 1.2,
                1.5,
                Math.sin(angle) * 1.2
            );
            hub.userData = { index: i };
            this.hubs.push(hub);
            this.add(hub);
            
            // Hub label
            const labelGeo = new THREE.PlaneGeometry(0.4, 0.15);
            const canvas = document.createElement('canvas');
            canvas.width = 128;
            canvas.height = 48;
            const ctx = canvas.getContext('2d', { willReadFrequently: true });
            ctx.fillStyle = '#FFFFFF';
            ctx.font = 'bold 24px "IBM Plex Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(`Hub ${i + 1}`, 64, 32);
            
            const labelMat = new THREE.MeshBasicMaterial({
                map: new THREE.CanvasTexture(canvas),
                transparent: true,
                side: THREE.DoubleSide
            });
            const label = new THREE.Mesh(labelGeo, labelMat);
            label.position.copy(hub.position);
            label.position.y += 0.5;
            this.add(label);
        }
    }
    
    createConnections() {
        const lineMat = new THREE.LineBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.3
        });
        
        // Connect each hub to all others (full mesh)
        for (let i = 0; i < 5; i++) {
            for (let j = i + 1; j < 5; j++) {
                const points = [
                    this.hubs[i].position.clone(),
                    this.hubs[j].position.clone()
                ];
                const geo = new THREE.BufferGeometry().setFromPoints(points);
                const line = new THREE.Line(geo, lineMat);
                this.add(line);
            }
        }
    }
    
    createSyncPulses() {
        // Particles that travel between hubs representing sync - FILM QUALITY
        const pulseGeo = new THREE.SphereGeometry(0.05, 12, 12);
        const pulseMat = new THREE.MeshPhysicalMaterial({
            color: 0x6FA370,  // Grove green
            emissive: 0x6FA370,
            emissiveIntensity: 0.6,
            transparent: true,
            opacity: 0.9,
            metalness: 0.2,
            roughness: 0.3
        });
        
        // Create 10 pulses
        for (let i = 0; i < 10; i++) {
            const pulse = new THREE.Mesh(pulseGeo, pulseMat.clone());
            pulse.visible = false;
            pulse.userData = {
                fromHub: Math.floor(Math.random() * 5),
                toHub: Math.floor(Math.random() * 5),
                progress: Math.random(),
                speed: 0.3 + Math.random() * 0.3
            };
            this.syncPulses.push(pulse);
            this.add(pulse);
        }
    }
    
    createPedestal() {
        const pedestalGeo = new THREE.CylinderGeometry(1.5, 1.7, 0.3, 32);
        const pedestalMat = new THREE.MeshPhysicalMaterial({
            color: 0x1D1C22,
            metalness: 0.9,
            roughness: 0.1
        });
        const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
        pedestal.position.y = 0.15;
        pedestal.userData.isPedestal = true;
        this.add(pedestal);
    }
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Rotate hubs
        this.hubs.forEach((hub, i) => {
            hub.rotation.y = this.time * 0.5 + i;
            hub.material.emissiveIntensity = 0.3 + Math.sin(this.time * 2 + i) * 0.2;
        });
        
        // Animate sync pulses
        this.syncPulses.forEach(pulse => {
            pulse.userData.progress += deltaTime * pulse.userData.speed;
            
            if (pulse.userData.progress > 1) {
                // Reset with new route
                pulse.userData.progress = 0;
                pulse.userData.fromHub = pulse.userData.toHub;
                pulse.userData.toHub = Math.floor(Math.random() * 5);
                if (pulse.userData.toHub === pulse.userData.fromHub) {
                    pulse.userData.toHub = (pulse.userData.toHub + 1) % 5;
                }
            }
            
            // Position along path
            const from = this.hubs[pulse.userData.fromHub].position;
            const to = this.hubs[pulse.userData.toHub].position;
            pulse.position.lerpVectors(from, to, pulse.userData.progress);
            pulse.visible = true;
        });
    }
    
    dispose() {
        this.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-D2: CATASTROPHE KAN LAYERS
// Kolmogorov-Arnold Network visualization
// ═══════════════════════════════════════════════════════════════════════════

export class CatastropheKANArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-D2');
        this.name = 'artwork-p2-d2';
        this.time = 0;
        this.splineNodes = [];
        this.create();
    }
    
    create() {
        this.createKANLayers();
        this.createCatastropheSurface();
        this.createPedestal();
        
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2.5, height: 1.5 });
            plaque.position.set(2.5, 0.5, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P2-D2', interactive: true };
    }
    
    createKANLayers() {
        // KAN uses learnable spline functions instead of fixed activations
        // Visualize as flowing curves through the network
        
        const layers = [4, 8, 8, 4]; // Network architecture
        const layerSpacing = 0.8;
        
        layers.forEach((nodeCount, layerIdx) => {
            const y = 1.5 + layerIdx * layerSpacing;
            
            for (let i = 0; i < nodeCount; i++) {
                const angle = (i / nodeCount) * Math.PI * 2;
                const radius = 0.5 + layerIdx * 0.2;
                
                const nodeGeo = new THREE.SphereGeometry(0.06, 16, 16);
                const nodeMat = new THREE.MeshPhysicalMaterial({
                    color: 0x9B7EBD,
                    emissive: 0x9B7EBD,
                    emissiveIntensity: 0.3
                });
                
                const node = new THREE.Mesh(nodeGeo, nodeMat);
                node.position.set(
                    Math.cos(angle) * radius,
                    y,
                    Math.sin(angle) * radius
                );
                this.splineNodes.push(node);
                this.add(node);
            }
            
            // Connect to previous layer with spline curves
            if (layerIdx > 0) {
                // Calculate start indices correctly
                const prevStart = layers.slice(0, layerIdx - 1).reduce((a, b) => a + b, 0);
                const currStart = layers.slice(0, layerIdx).reduce((a, b) => a + b, 0);
                
                for (let i = 0; i < Math.min(5, layers[layerIdx - 1]); i++) {
                    for (let j = 0; j < Math.min(3, nodeCount); j++) {
                        const from = this.splineNodes[prevStart + i];
                        const to = this.splineNodes[currStart + j];
                        
                        // Safety check
                        if (!from || !to) continue;
                        
                        // Create spline curve
                        const midY = (from.position.y + to.position.y) / 2;
                        const midOffset = new THREE.Vector3(
                            (Math.random() - 0.5) * 0.3,
                            0,
                            (Math.random() - 0.5) * 0.3
                        );
                        
                        const curve = new THREE.QuadraticBezierCurve3(
                            from.position,
                            new THREE.Vector3(
                                (from.position.x + to.position.x) / 2 + midOffset.x,
                                midY,
                                (from.position.z + to.position.z) / 2 + midOffset.z
                            ),
                            to.position
                        );
                        
                        const points = curve.getPoints(20);
                        const geo = new THREE.BufferGeometry().setFromPoints(points);
                        const mat = new THREE.LineBasicMaterial({
                            color: 0x4ECDC4,
                            transparent: true,
                            opacity: 0.3
                        });
                        const line = new THREE.Line(geo, mat);
                        this.add(line);
                    }
                }
            }
        });
    }
    
    createCatastropheSurface() {
        // Cusp catastrophe surface (fold)
        // Using BufferGeometry since ParametricGeometry is deprecated
        const segments = 30;
        const geo = new THREE.BufferGeometry();
        const vertices = [];
        const indices = [];
        const normals = [];
        const uvs = [];
        
        for (let j = 0; j <= segments; j++) {
            for (let i = 0; i <= segments; i++) {
                const u = i / segments;
                const v = j / segments;
                const x = (u - 0.5) * 2;
                const y = (v - 0.5) * 2;
                // Cusp catastrophe: z = x³ - xy
                const z = x * x * x - x * y;
                vertices.push(x * 0.5, z * 0.3 + 0.5, y * 0.5);
                normals.push(0, 1, 0);  // Simplified normals
                uvs.push(u, v);
            }
        }
        
        for (let j = 0; j < segments; j++) {
            for (let i = 0; i < segments; i++) {
                const a = i + (segments + 1) * j;
                const b = i + (segments + 1) * (j + 1);
                const c = (i + 1) + (segments + 1) * (j + 1);
                const d = (i + 1) + (segments + 1) * j;
                indices.push(a, b, d, b, c, d);
            }
        }
        
        geo.setIndex(indices);
        geo.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
        geo.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
        geo.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
        geo.computeVertexNormals();
        
        const mat = new THREE.MeshPhysicalMaterial({
            color: 0xFF6B35,
            transparent: true,
            opacity: 0.4,
            side: THREE.DoubleSide,
            metalness: 0.3,
            roughness: 0.7
        });
        
        this.catastropheSurface = new THREE.Mesh(geo, mat);
        this.catastropheSurface.position.set(-1.5, 2, 0);
        this.add(this.catastropheSurface);
    }
    
    createPedestal() {
        const pedestalGeo = new THREE.CylinderGeometry(1.3, 1.5, 0.3, 32);
        const pedestalMat = new THREE.MeshPhysicalMaterial({
            color: 0x1D1C22,
            metalness: 0.9,
            roughness: 0.1
        });
        const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
        pedestal.position.y = 0.15;
        pedestal.userData.isPedestal = true;
        this.add(pedestal);
    }
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Pulse nodes
        this.splineNodes.forEach((node, i) => {
            node.material.emissiveIntensity = 0.3 + Math.sin(this.time * 3 + i * 0.2) * 0.2;
        });
        
        // Rotate catastrophe surface
        if (this.catastropheSurface) {
            this.catastropheSurface.rotation.y = this.time * 0.2;
        }
    }
    
    dispose() {
        this.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-E2: CONTEXT-BOUND ENCRYPTION
// Encryption context visualization
// ═══════════════════════════════════════════════════════════════════════════

export class ContextBoundEncryptionArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-E2');
        this.name = 'artwork-p2-e2';
        this.time = 0;
        this.keyBits = [];
        this.create();
    }
    
    create() {
        this.createContextSphere();
        this.createEncryptionKey();
        this.createDataStream();
        this.createPedestal();
        
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2.5, height: 1.5 });
            plaque.position.set(2.5, 0.5, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P2-E2', interactive: true };
    }
    
    createContextSphere() {
        // Sphere representing valid encryption context
        const geo = new THREE.SphereGeometry(1.2, 32, 32);
        const mat = new THREE.MeshPhysicalMaterial({
            color: 0xD4AF37,
            transparent: true,
            opacity: 0.2,
            side: THREE.DoubleSide,
            metalness: 0.3,
            roughness: 0.7
        });
        
        this.contextSphere = new THREE.Mesh(geo, mat);
        this.contextSphere.position.y = 1.8;
        this.add(this.contextSphere);
        
        // Context boundary wireframe
        const wireGeo = new THREE.SphereGeometry(1.22, 16, 16);
        const wireMat = new THREE.MeshBasicMaterial({
            color: 0xD4AF37,
            wireframe: true,
            transparent: true,
            opacity: 0.4
        });
        const wire = new THREE.Mesh(wireGeo, wireMat);
        wire.position.y = 1.8;
        this.add(wire);
    }
    
    createEncryptionKey() {
        // Key represented as rotating bits
        const bitGeo = new THREE.BoxGeometry(0.1, 0.1, 0.1);
        
        for (let i = 0; i < 32; i++) {
            const angle = (i / 32) * Math.PI * 2;
            const radius = 0.8;
            const isOne = Math.random() > 0.5;
            
            // Film-quality: Grove green (1) vs Spark red (0)
            const bitMat = new THREE.MeshPhysicalMaterial({
                color: isOne ? 0x6FA370 : 0xE85A2F,
                emissive: isOne ? 0x6FA370 : 0xE85A2F,
                emissiveIntensity: 0.5
            });
            
            const bit = new THREE.Mesh(bitGeo, bitMat);
            bit.position.set(
                Math.cos(angle) * radius,
                1.8,
                Math.sin(angle) * radius
            );
            bit.userData = { value: isOne, angle };
            this.keyBits.push(bit);
            this.add(bit);
        }
    }
    
    createDataStream() {
        // Particles flowing through the encryption
        const particleCount = 50;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        for (let i = 0; i < particleCount; i++) {
            positions[i * 3] = (Math.random() - 0.5) * 0.5;
            positions[i * 3 + 1] = Math.random() * 2 + 0.8;
            positions[i * 3 + 2] = (Math.random() - 0.5) * 0.5;
            
            colors[i * 3] = 0.4;
            colors[i * 3 + 1] = 0.83;
            colors[i * 3 + 2] = 0.89;
        }
        
        const geo = new THREE.BufferGeometry();
        geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const mat = new THREE.PointsMaterial({
            size: 0.05,
            vertexColors: true,
            transparent: true,
            opacity: 0.7,
            blending: THREE.AdditiveBlending
        });
        
        this.dataStream = new THREE.Points(geo, mat);
        this.add(this.dataStream);
    }
    
    createPedestal() {
        const pedestalGeo = new THREE.CylinderGeometry(1.3, 1.5, 0.3, 32);
        const pedestalMat = new THREE.MeshPhysicalMaterial({
            color: 0x1D1C22,
            metalness: 0.9,
            roughness: 0.1
        });
        const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
        pedestal.position.y = 0.15;
        pedestal.userData.isPedestal = true;
        this.add(pedestal);
    }
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Rotate key bits
        this.keyBits.forEach((bit, i) => {
            bit.userData.angle += deltaTime * 0.5;
            const angle = bit.userData.angle;
            bit.position.x = Math.cos(angle) * 0.8;
            bit.position.z = Math.sin(angle) * 0.8;
            bit.rotation.y = this.time + i;
        });
        
        // Pulse context sphere
        if (this.contextSphere) {
            this.contextSphere.rotation.y = this.time * 0.1;
        }
        
        // Animate data stream
        if (this.dataStream) {
            const positions = this.dataStream.geometry.attributes.position.array;
            for (let i = 0; i < positions.length / 3; i++) {
                positions[i * 3 + 1] += deltaTime * 0.5;
                if (positions[i * 3 + 1] > 2.8) {
                    positions[i * 3 + 1] = 0.8;
                }
            }
            this.dataStream.geometry.attributes.position.needsUpdate = true;
        }
    }
    
    dispose() {
        this.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-G1: EARCON ORCHESTRATION ENGINE
// Spatial audio cues for ambient intelligence
// ═══════════════════════════════════════════════════════════════════════════

export class EarconOrchestrationArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-G1') || { id: 'P2-G1', name: 'Earcon Orchestration Engine' };
        this.name = 'artwork-p2-g1';
        this.time = 0;
        this.soundWaves = [];
        this.speakers = [];
        this.earcons = [];
        this.create();
    }
    
    create() {
        // Create spatial audio sculpture
        this.createSpeakerArray();
        this.createSoundWaves();
        this.createEarconDisplay();
        this.createListenerHead();
        this.createPedestal();
        
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2.5, height: 1.5 });
            plaque.position.set(2.2, 0.5, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P2-G1', interactive: true };
    }
    
    createSpeakerArray() {
        // 7.1 surround sound layout with speakers
        const speakerPositions = [
            { angle: 0, y: 2.5, label: 'C' },          // Center
            { angle: -30, y: 2.5, label: 'L' },        // Left
            { angle: 30, y: 2.5, label: 'R' },         // Right
            { angle: -110, y: 2.5, label: 'LS' },      // Left Surround
            { angle: 110, y: 2.5, label: 'RS' },       // Right Surround
            { angle: -150, y: 2.5, label: 'LB' },      // Left Back
            { angle: 150, y: 2.5, label: 'RB' },       // Right Back
        ];
        
        const speakerGeo = new THREE.BoxGeometry(0.15, 0.25, 0.1);
        const speakerMat = new THREE.MeshPhysicalMaterial({
            color: 0x333333,
            metalness: 0.8,
            roughness: 0.3
        });
        
        const coneMat = new THREE.MeshPhysicalMaterial({
            color: COLONY_COLORS.grove,
            emissive: COLONY_COLORS.grove,
            emissiveIntensity: 0.2,
            metalness: 0.3,
            roughness: 0.5
        });
        
        speakerPositions.forEach((pos, i) => {
            const rad = THREE.MathUtils.degToRad(pos.angle);
            const speaker = new THREE.Group();
            
            // Speaker body
            const body = new THREE.Mesh(speakerGeo, speakerMat);
            speaker.add(body);
            
            // Speaker cone
            const coneGeo = new THREE.CircleGeometry(0.06, 16);
            const cone = new THREE.Mesh(coneGeo, coneMat.clone());
            cone.position.z = 0.051;
            speaker.add(cone);
            
            // Position in circle
            speaker.position.set(
                Math.sin(rad) * 1.5,
                pos.y,
                Math.cos(rad) * 1.5
            );
            speaker.lookAt(0, pos.y, 0);
            
            this.speakers.push({ mesh: speaker, cone, angle: pos.angle });
            this.add(speaker);
        });
        
        // Subwoofer
        const subGeo = new THREE.BoxGeometry(0.4, 0.5, 0.35);
        const sub = new THREE.Mesh(subGeo, speakerMat);
        sub.position.set(-1.2, 0.25, 0.8);
        this.add(sub);
    }
    
    createSoundWaves() {
        // Expanding ring waves from each speaker
        const waveMat = new THREE.ShaderMaterial({
            uniforms: {
                time: { value: 0 },
                color: { value: new THREE.Color(COLONY_COLORS.grove) },
                opacity: { value: 0.3 }
            },
            vertexShader: `
                varying vec2 vUv;
                void main() {
                    vUv = uv;
                    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
                }
            `,
            fragmentShader: `
                uniform float time;
                uniform vec3 color;
                uniform float opacity;
                varying vec2 vUv;
                
                void main() {
                    vec2 center = vec2(0.5);
                    float dist = distance(vUv, center) * 2.0;
                    
                    // Multiple expanding rings
                    float wave1 = sin((dist - time * 0.5) * 20.0) * 0.5 + 0.5;
                    float wave2 = sin((dist - time * 0.7) * 15.0) * 0.5 + 0.5;
                    
                    // Fade at edges
                    float edge = 1.0 - smoothstep(0.8, 1.0, dist);
                    
                    float wave = (wave1 + wave2) * 0.5 * edge;
                    
                    gl_FragColor = vec4(color, wave * opacity);
                }
            `,
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false
        });
        
        // Create wave planes for each speaker
        this.speakers.forEach((speaker, i) => {
            const waveGeo = new THREE.PlaneGeometry(1.5, 1.5);
            const wave = new THREE.Mesh(waveGeo, waveMat.clone());
            wave.position.copy(speaker.mesh.position);
            wave.position.z -= 0.3;
            wave.lookAt(0, speaker.mesh.position.y, 0);
            
            this.soundWaves.push(wave);
            this.add(wave);
        });
    }
    
    createEarconDisplay() {
        // Floating earcon symbols (notification sounds)
        const earconTypes = [
            { symbol: '🔔', label: 'Alert', color: 0xFF6B35 },
            { symbol: '✓', label: 'Success', color: 0x7EB77F },
            { symbol: '⚠', label: 'Warning', color: 0xF59E0B },
            { symbol: '♪', label: 'Ambience', color: 0x67D4E4 },
            { symbol: '🎵', label: 'Music', color: 0x9B7EBD }
        ];
        
        const canvas = document.createElement('canvas');
        canvas.width = 128;
        canvas.height = 128;
        const ctx = canvas.getContext('2d', { willReadFrequently: true });
        
        earconTypes.forEach((earcon, i) => {
            // Create sprite for each earcon type - use a fresh canvas for each
            const earconCanvas = document.createElement('canvas');
            earconCanvas.width = 128;
            earconCanvas.height = 128;
            const earconCtx = earconCanvas.getContext('2d', { willReadFrequently: true });
            
            earconCtx.fillStyle = '#' + earcon.color.toString(16).padStart(6, '0');
            earconCtx.font = '64px Arial';
            earconCtx.textAlign = 'center';
            earconCtx.textBaseline = 'middle';
            earconCtx.fillText(earcon.symbol, 64, 64);
            
            const texture = new THREE.CanvasTexture(earconCanvas);
            texture.needsUpdate = true;
            
            const spriteMat = new THREE.SpriteMaterial({
                map: texture,
                transparent: true,
                opacity: 0.8,
                color: earcon.color
            });
            
            const sprite = new THREE.Sprite(spriteMat);
            const angle = (i / earconTypes.length) * Math.PI * 2;
            sprite.position.set(
                Math.cos(angle) * 0.6,
                3.5,
                Math.sin(angle) * 0.6
            );
            sprite.scale.setScalar(0.3);
            
            this.earcons.push({ sprite, baseY: 3.5, phase: i * 0.5 });
            this.add(sprite);
        });
    }
    
    createListenerHead() {
        // Abstract listener head in center
        const headGeo = new THREE.SphereGeometry(0.25, 32, 32);
        const headMat = new THREE.MeshPhysicalMaterial({
            color: 0xFFDBB5,
            metalness: 0,
            roughness: 0.5
        });
        const head = new THREE.Mesh(headGeo, headMat);
        head.position.set(0, 2.5, 0);
        this.add(head);
        
        // Ears
        const earGeo = new THREE.SphereGeometry(0.08, 16, 16);
        const leftEar = new THREE.Mesh(earGeo, headMat);
        leftEar.position.set(-0.25, 2.5, 0);
        this.add(leftEar);
        
        const rightEar = new THREE.Mesh(earGeo, headMat);
        rightEar.position.set(0.25, 2.5, 0);
        this.add(rightEar);
        
        // HRTF visualization - glowing aura around head - FILM QUALITY
        const hrtfGeo = new THREE.SphereGeometry(0.4, 32, 32);
        const hrtfMat = new THREE.MeshPhysicalMaterial({
            color: COLONY_COLORS.grove,
            emissive: COLONY_COLORS.grove,
            emissiveIntensity: 0.3,
            transparent: true,
            opacity: 0.15,
            metalness: 0,
            roughness: 0.8,
            side: THREE.BackSide
        });
        this.hrtfAura = new THREE.Mesh(hrtfGeo, hrtfMat);
        this.hrtfAura.position.copy(head.position);
        this.add(this.hrtfAura);
    }
    
    createPedestal() {
        const pedestalGeo = new THREE.CylinderGeometry(0.8, 1.0, 0.1, 32);
        const pedestalMat = new THREE.MeshStandardMaterial({
            color: 0x222222,
            metalness: 0.7,
            roughness: 0.3
        });
        const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
        pedestal.position.y = 0.05;
        this.add(pedestal);
    }
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Animate sound waves
        this.soundWaves.forEach((wave, i) => {
            if (wave.material.uniforms) {
                wave.material.uniforms.time.value = this.time + i * 0.3;
            }
        });
        
        // Pulse speaker cones
        this.speakers.forEach((speaker, i) => {
            const pulse = Math.sin(this.time * 5 + i) * 0.5 + 0.5;
            speaker.cone.material.emissiveIntensity = 0.2 + pulse * 0.4;
        });
        
        // Float earcons
        this.earcons.forEach(earcon => {
            earcon.sprite.position.y = earcon.baseY + Math.sin(this.time * 2 + earcon.phase) * 0.1;
        });
        
        // Pulse HRTF aura
        if (this.hrtfAura) {
            const scale = 1 + Math.sin(this.time * 3) * 0.1;
            this.hrtfAura.scale.setScalar(scale);
        }
    }
    
    dispose() {
        this.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-H2: FREELANCER BIDDING AGENT
// Autonomous job market participation
// ═══════════════════════════════════════════════════════════════════════════

export class FreelancerBiddingArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-H2') || { id: 'P2-H2', name: 'Freelancer Bidding Agent' };
        this.name = 'artwork-p2-h2';
        this.time = 0;
        this.jobs = [];
        this.bids = [];
        this.agent = null;
        this.create();
    }
    
    create() {
        // Create market visualization
        this.createMarketBoard();
        this.createAgent();
        this.createJobCards();
        this.createBidTrails();
        this.createPedestal();
        
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2.5, height: 1.5 });
            plaque.position.set(2.2, 0.5, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P2-H2', interactive: true };
    }
    
    createMarketBoard() {
        // Large market display board
        const boardGeo = new THREE.PlaneGeometry(3, 2);
        const boardMat = new THREE.MeshPhysicalMaterial({
            color: 0x0A1628,
            emissive: 0x0A1628,
            emissiveIntensity: 0.1,
            metalness: 0.3,
            roughness: 0.8,
            transparent: true,
            opacity: 0.9
        });
        this.board = new THREE.Mesh(boardGeo, boardMat);
        this.board.position.set(0, 2.5, -1.5);
        this.add(this.board);
        
        // Board frame
        const frameGeo = new THREE.BoxGeometry(3.1, 2.1, 0.1);
        const frameMat = new THREE.MeshStandardMaterial({
            color: COLONY_COLORS.beacon,
            metalness: 0.7,
            roughness: 0.3
        });
        const frame = new THREE.Mesh(frameGeo, frameMat);
        frame.position.copy(this.board.position);
        frame.position.z -= 0.05;
        this.add(frame);
        
        // Grid lines on board
        const gridMat = new THREE.LineBasicMaterial({ 
            color: COLONY_COLORS.beacon, 
            transparent: true, 
            opacity: 0.3 
        });
        
        for (let i = 0; i < 5; i++) {
            const x = -1.3 + i * 0.65;
            const points = [
                new THREE.Vector3(x, 1.6, -1.49),
                new THREE.Vector3(x, 3.4, -1.49)
            ];
            const geo = new THREE.BufferGeometry().setFromPoints(points);
            const line = new THREE.Line(geo, gridMat);
            this.add(line);
        }
    }
    
    createAgent() {
        // AI agent representation
        const agentGeo = new THREE.OctahedronGeometry(0.25, 0);
        const agentMat = new THREE.MeshPhysicalMaterial({
            color: COLONY_COLORS.beacon,
            emissive: COLONY_COLORS.beacon,
            emissiveIntensity: 0.5,
            metalness: 0.5,
            roughness: 0.2,
            clearcoat: 1.0
        });
        this.agent = new THREE.Mesh(agentGeo, agentMat);
        this.agent.position.set(0, 2, 0.5);
        this.add(this.agent);
        
        // Agent glow
        const glowGeo = new THREE.SphereGeometry(0.4, 16, 16);
        const glowMat = new THREE.MeshBasicMaterial({
            color: COLONY_COLORS.beacon,
            transparent: true,
            opacity: 0.15,
            side: THREE.BackSide
        });
        this.agentGlow = new THREE.Mesh(glowGeo, glowMat);
        this.agentGlow.position.copy(this.agent.position);
        this.add(this.agentGlow);
    }
    
    createJobCards() {
        // Floating job posting cards
        const jobTypes = [
            { type: 'Web Dev', budget: '$500', color: 0x4ECDC4 },
            { type: 'ML Model', budget: '$2000', color: 0x9B7EBD },
            { type: 'UI Design', budget: '$800', color: 0xFF6B35 },
            { type: 'API Dev', budget: '$1200', color: 0x7EB77F },
            { type: 'Data Eng', budget: '$1500', color: 0xD4AF37 }
        ];
        
        jobTypes.forEach((job, i) => {
            const cardGeo = new THREE.PlaneGeometry(0.6, 0.4);
            const cardMat = new THREE.MeshPhysicalMaterial({
                color: job.color,
                emissive: job.color,
                emissiveIntensity: 0.2,
                metalness: 0.2,
                roughness: 0.5,
                transparent: true,
                opacity: 0.9,
                side: THREE.DoubleSide
            });
            const card = new THREE.Mesh(cardGeo, cardMat);
            
            // Position around the board
            const angle = (i / jobTypes.length) * Math.PI - Math.PI / 2;
            card.position.set(
                Math.sin(angle) * 1.8,
                2.5 + Math.cos(angle) * 0.5,
                -1.3
            );
            card.rotation.y = Math.sin(angle) * 0.2;
            
            this.jobs.push({ 
                mesh: card, 
                basePos: card.position.clone(),
                phase: i * 0.7,
                color: job.color
            });
            this.add(card);
        });
    }
    
    createBidTrails() {
        // Lines connecting agent to jobs (bid connections)
        this.jobs.forEach((job, i) => {
            const curve = new THREE.CatmullRomCurve3([
                this.agent.position.clone(),
                new THREE.Vector3(
                    (this.agent.position.x + job.basePos.x) / 2,
                    this.agent.position.y + 0.3,
                    (this.agent.position.z + job.basePos.z) / 2
                ),
                job.basePos.clone()
            ]);
            
            const points = curve.getPoints(20);
            const geo = new THREE.BufferGeometry().setFromPoints(points);
            const mat = new THREE.LineBasicMaterial({
                color: job.color,
                transparent: true,
                opacity: 0.3
            });
            const line = new THREE.Line(geo, mat);
            
            this.bids.push({ line, curve, active: false, progress: 0 });
            this.add(line);
        });
        
        // Bid particle that travels along connections
        const bidGeo = new THREE.SphereGeometry(0.05, 8, 8);
        const bidMat = new THREE.MeshBasicMaterial({
            color: COLONY_COLORS.beacon
        });
        this.bidParticle = new THREE.Mesh(bidGeo, bidMat);
        this.bidParticle.visible = false;
        this.add(this.bidParticle);
    }
    
    createPedestal() {
        const pedestalGeo = new THREE.CylinderGeometry(0.5, 0.6, 0.1, 32);
        const pedestalMat = new THREE.MeshStandardMaterial({
            color: 0x222222,
            metalness: 0.7,
            roughness: 0.3
        });
        const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
        pedestal.position.y = 0.05;
        this.add(pedestal);
    }
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Rotate agent
        if (this.agent) {
            this.agent.rotation.y += deltaTime * 0.5;
            this.agent.rotation.x = Math.sin(this.time * 2) * 0.1;
        }
        
        // Pulse agent glow
        if (this.agentGlow) {
            const scale = 1 + Math.sin(this.time * 3) * 0.1;
            this.agentGlow.scale.setScalar(scale);
        }
        
        // Animate job cards
        this.jobs.forEach(job => {
            job.mesh.position.y = job.basePos.y + Math.sin(this.time * 1.5 + job.phase) * 0.1;
        });
        
        // Animate bid connections (one at a time)
        const activeBidIndex = Math.floor(this.time * 0.5) % this.bids.length;
        this.bids.forEach((bid, i) => {
            bid.line.material.opacity = i === activeBidIndex ? 0.6 : 0.2;
            
            if (i === activeBidIndex) {
                // Animate particle along this bid
                const progress = (this.time * 2) % 1;
                const point = bid.curve.getPoint(progress);
                this.bidParticle.position.copy(point);
                this.bidParticle.visible = true;
            }
        });
    }
    
    dispose() {
        this.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-F2: MUSIC-REACTIVE LIGHTING
// Real-time spectrum analysis for ambient lighting
// ═══════════════════════════════════════════════════════════════════════════

export class MusicReactiveLightingArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-F2') || { id: 'P2-F2', name: 'Music-Reactive Lighting' };
        this.name = 'artwork-p2-f2';
        this.time = 0;
        this.spectrumBars = [];
        this.lights = [];
        this.create();
    }
    
    create() {
        // Create music visualization sculpture
        this.createSpectrumAnalyzer();
        this.createReactiveLights();
        this.createWaveform();
        this.createPedestal();
        
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2.5, height: 1.5 });
            plaque.position.set(2.2, 0.5, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P2-F2', interactive: true };
    }
    
    createSpectrumAnalyzer() {
        // FFT-style frequency bars
        const numBars = 32;
        const barMat = new THREE.MeshPhysicalMaterial({
            color: COLONY_COLORS.flow,
            emissive: COLONY_COLORS.flow,
            emissiveIntensity: 0.3,
            metalness: 0.5,
            roughness: 0.3,
            transparent: true,
            opacity: 0.9
        });
        
        for (let i = 0; i < numBars; i++) {
            const barGeo = new THREE.BoxGeometry(0.08, 0.5, 0.08);
            const bar = new THREE.Mesh(barGeo, barMat.clone());
            
            const angle = (i / numBars) * Math.PI * 2;
            const radius = 0.8;
            bar.position.set(
                Math.cos(angle) * radius,
                2,
                Math.sin(angle) * radius
            );
            
            // Color gradient from low to high frequencies
            const hue = 0.5 + (i / numBars) * 0.3; // cyan to purple
            bar.material.color.setHSL(hue, 0.8, 0.5);
            bar.material.emissive.setHSL(hue, 0.8, 0.3);
            
            this.spectrumBars.push({ 
                mesh: bar, 
                baseHeight: 0.5,
                frequency: i / numBars,
                phase: i * 0.2
            });
            this.add(bar);
        }
    }
    
    createReactiveLights() {
        // Room corner lights that react to spectrum
        const lightPositions = [
            { x: -1.2, z: -1.2 },
            { x: 1.2, z: -1.2 },
            { x: -1.2, z: 1.2 },
            { x: 1.2, z: 1.2 }
        ];
        
        const colors = [0xFF6B35, 0x4ECDC4, 0x9B7EBD, 0xF59E0B];
        
        lightPositions.forEach((pos, i) => {
            // Light fixture
            const fixtureGeo = new THREE.CylinderGeometry(0.1, 0.15, 0.3, 16);
            const fixtureMat = new THREE.MeshStandardMaterial({
                color: 0x333333,
                metalness: 0.8,
                roughness: 0.3
            });
            const fixture = new THREE.Mesh(fixtureGeo, fixtureMat);
            fixture.position.set(pos.x, 3, pos.z);
            this.add(fixture);
            
            // Light cone (visible beam)
            const coneGeo = new THREE.ConeGeometry(0.5, 2, 16, 1, true);
            const coneMat = new THREE.MeshBasicMaterial({
                color: colors[i],
                transparent: true,
                opacity: 0.15,
                side: THREE.DoubleSide
            });
            const cone = new THREE.Mesh(coneGeo, coneMat);
            cone.rotation.x = Math.PI;
            cone.position.set(pos.x, 2, pos.z);
            
            this.lights.push({ 
                cone, 
                color: colors[i],
                frequencyBand: i / 4 // Each light responds to different freq band
            });
            this.add(cone);
        });
    }
    
    createWaveform() {
        // Oscilloscope-style waveform
        const wavePoints = [];
        for (let i = 0; i < 100; i++) {
            wavePoints.push(new THREE.Vector3(
                -1.5 + i * 0.03,
                3.5,
                0
            ));
        }
        
        this.waveGeometry = new THREE.BufferGeometry().setFromPoints(wavePoints);
        const waveMat = new THREE.LineBasicMaterial({
            color: COLONY_COLORS.flow,
            transparent: true,
            opacity: 0.8
        });
        this.waveform = new THREE.Line(this.waveGeometry, waveMat);
        this.add(this.waveform);
    }
    
    createPedestal() {
        const pedestalGeo = new THREE.CylinderGeometry(1.0, 1.2, 0.1, 32);
        const pedestalMat = new THREE.MeshStandardMaterial({
            color: 0x222222,
            metalness: 0.7,
            roughness: 0.3
        });
        const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
        pedestal.position.y = 0.05;
        this.add(pedestal);
    }
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Simulate music spectrum (would be real audio data in production)
        this.spectrumBars.forEach((bar, i) => {
            // Simulated beat pattern
            const bass = Math.abs(Math.sin(this.time * 4)) * (i < 8 ? 1 : 0.3);
            const mid = Math.abs(Math.sin(this.time * 6 + i * 0.3)) * (i >= 8 && i < 20 ? 0.8 : 0.2);
            const high = Math.abs(Math.sin(this.time * 12 + i * 0.1)) * (i >= 20 ? 0.6 : 0.1);
            
            const amplitude = bass + mid + high + Math.random() * 0.1;
            const height = 0.3 + amplitude * 1.2;
            
            bar.mesh.scale.y = height;
            bar.mesh.position.y = 2 + height / 2;
            bar.mesh.material.emissiveIntensity = 0.3 + amplitude * 0.5;
        });
        
        // React lights to spectrum bands
        this.lights.forEach((light, i) => {
            const bandStart = Math.floor(i * 8);
            const bandEnd = bandStart + 8;
            
            let bandEnergy = 0;
            for (let j = bandStart; j < bandEnd && j < this.spectrumBars.length; j++) {
                bandEnergy += this.spectrumBars[j].mesh.scale.y;
            }
            bandEnergy /= 8;
            
            light.cone.material.opacity = 0.1 + bandEnergy * 0.15;
            light.cone.scale.y = 0.8 + bandEnergy * 0.4;
        });
        
        // Update waveform
        if (this.waveGeometry) {
            const positions = this.waveGeometry.attributes.position.array;
            for (let i = 0; i < positions.length / 3; i++) {
                const x = i / 33;
                positions[i * 3 + 1] = 3.5 + 
                    Math.sin(this.time * 8 + x * 10) * 0.1 +
                    Math.sin(this.time * 12 + x * 20) * 0.05;
            }
            this.waveGeometry.attributes.position.needsUpdate = true;
        }
    }
    
    dispose() {
        this.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-A5: WEYL EQUIVARIANT CONVOLUTION
// Root system symmetry preservation in CNNs
// ═══════════════════════════════════════════════════════════════════════════

export class WeylEquivariantArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-A5') || { id: 'P2-A5', name: 'Weyl Equivariant Convolution' };
        this.name = 'artwork-p2-a5';
        this.time = 0;
        this.rootVectors = [];
        this.reflectionPlanes = [];
        this.create();
    }
    
    create() {
        // Create Weyl group visualization
        this.createWeylChamber();
        this.createRootVectors();
        this.createReflectionPlanes();
        this.createKernel();
        this.createPedestal();
        
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2.5, height: 1.5 });
            plaque.position.set(2.2, 0.5, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P2-A5', interactive: true };
    }
    
    createWeylChamber() {
        // Fundamental domain / Weyl chamber (wedge shape)
        const shape = new THREE.Shape();
        shape.moveTo(0, 0);
        shape.lineTo(1.5, 0);
        shape.lineTo(0.75, 1.3);
        shape.lineTo(0, 0);
        
        const extrudeSettings = { depth: 0.05, bevelEnabled: false };
        const chamberGeo = new THREE.ExtrudeGeometry(shape, extrudeSettings);
        const chamberMat = new THREE.MeshPhysicalMaterial({
            color: COLONY_COLORS.spark,
            emissive: COLONY_COLORS.spark,
            emissiveIntensity: 0.1,
            metalness: 0.3,
            roughness: 0.5,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        });
        this.chamber = new THREE.Mesh(chamberGeo, chamberMat);
        this.chamber.rotation.x = -Math.PI / 2;
        this.chamber.position.set(-0.75, 2, 0);
        this.add(this.chamber);
    }
    
    createRootVectors() {
        // A2 root system (hexagonal pattern)
        const rootAngles = [0, 60, 120, 180, 240, 300];
        const arrowMat = new THREE.MeshPhysicalMaterial({
            color: COLONY_COLORS.spark,
            emissive: COLONY_COLORS.spark,
            emissiveIntensity: 0.4,
            metalness: 0.5,
            roughness: 0.3
        });
        
        rootAngles.forEach((angle, i) => {
            const rad = THREE.MathUtils.degToRad(angle);
            const length = 0.8;
            
            // Arrow shaft
            const shaftGeo = new THREE.CylinderGeometry(0.03, 0.03, length, 8);
            const shaft = new THREE.Mesh(shaftGeo, arrowMat.clone());
            shaft.rotation.z = rad - Math.PI / 2;
            shaft.position.set(
                Math.cos(rad) * length / 2,
                2.5,
                Math.sin(rad) * length / 2
            );
            
            // Arrow head
            const headGeo = new THREE.ConeGeometry(0.08, 0.15, 8);
            const head = new THREE.Mesh(headGeo, arrowMat);
            head.rotation.z = rad - Math.PI / 2;
            head.position.set(
                Math.cos(rad) * (length + 0.075),
                2.5,
                Math.sin(rad) * (length + 0.075)
            );
            
            const arrow = new THREE.Group();
            arrow.add(shaft);
            arrow.add(head);
            
            this.rootVectors.push({ 
                group: arrow,
                angle: rad,
                phase: i * 0.5
            });
            this.add(arrow);
        });
    }
    
    createReflectionPlanes() {
        // Hyperplanes perpendicular to roots
        const planeAngles = [30, 90, 150];
        const planeMat = new THREE.MeshBasicMaterial({
            color: COLONY_COLORS.crystal,
            transparent: true,
            opacity: 0.2,
            side: THREE.DoubleSide
        });
        
        planeAngles.forEach((angle, i) => {
            const rad = THREE.MathUtils.degToRad(angle);
            const planeGeo = new THREE.PlaneGeometry(2, 1.5);
            const plane = new THREE.Mesh(planeGeo, planeMat.clone());
            
            plane.rotation.y = rad;
            plane.position.y = 2.5;
            
            this.reflectionPlanes.push({ mesh: plane, angle: rad });
            this.add(plane);
        });
    }
    
    createKernel() {
        // Convolution kernel visualization (equivariant filter)
        const kernelSize = 3;
        const kernelMat = new THREE.MeshPhysicalMaterial({
            color: 0xF5F0E8,
            emissive: COLONY_COLORS.spark,
            emissiveIntensity: 0.2,
            metalness: 0.4,
            roughness: 0.5,
            transparent: true,
            opacity: 0.8
        });
        
        this.kernelGroup = new THREE.Group();
        
        for (let i = 0; i < kernelSize; i++) {
            for (let j = 0; j < kernelSize; j++) {
                const cellGeo = new THREE.BoxGeometry(0.2, 0.05, 0.2);
                const cell = new THREE.Mesh(cellGeo, kernelMat.clone());
                cell.position.set(
                    (i - 1) * 0.25,
                    0,
                    (j - 1) * 0.25
                );
                
                // Random initial "weight"
                const weight = Math.random();
                cell.scale.y = 0.5 + weight * 2;
                cell.userData.weight = weight;
                
                this.kernelGroup.add(cell);
            }
        }
        
        this.kernelGroup.position.set(0, 3.5, 0);
        this.add(this.kernelGroup);
    }
    
    createPedestal() {
        const pedestalGeo = new THREE.CylinderGeometry(0.8, 1.0, 0.1, 32);
        const pedestalMat = new THREE.MeshStandardMaterial({
            color: 0x222222,
            metalness: 0.7,
            roughness: 0.3
        });
        const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
        pedestal.position.y = 0.05;
        this.add(pedestal);
    }
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Slowly rotate root system
        this.rootVectors.forEach(root => {
            root.group.rotation.y = this.time * 0.2;
        });
        
        // Pulse reflection planes
        this.reflectionPlanes.forEach((plane, i) => {
            plane.mesh.material.opacity = 0.15 + Math.sin(this.time * 2 + i) * 0.1;
        });
        
        // Rotate Weyl chamber
        if (this.chamber) {
            this.chamber.rotation.z = this.time * 0.3;
        }
        
        // Animate kernel weights (showing equivariance)
        if (this.kernelGroup) {
            this.kernelGroup.rotation.y = this.time * 0.5;
            
            this.kernelGroup.children.forEach((cell, i) => {
                const row = Math.floor(i / 3);
                const col = i % 3;
                
                // Symmetrical weight animation
                const symmetricIdx = (2 - row) * 3 + (2 - col);
                const baseWeight = Math.sin(this.time * 2 + i * 0.3) * 0.5 + 0.5;
                
                cell.scale.y = 0.5 + baseWeight * 2;
                cell.material.emissiveIntensity = 0.1 + baseWeight * 0.3;
            });
        }
    }
    
    dispose() {
        this.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-I1: FIGMA-TO-CODE PIPELINE
// Direct Figma design to implementation
// ═══════════════════════════════════════════════════════════════════════════

export class FigmaToCodeArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-I1') || { id: 'P2-I1', name: 'Figma-to-Code Pipeline' };
        this.name = 'artwork-p2-i1';
        this.time = 0;
        this.uiElements = [];
        this.codeLines = [];
        this.pipeline = null;
        this.create();
    }
    
    create() {
        // Create design-to-code transformation visualization
        this.createFigmaCanvas();
        this.createPipeline();
        this.createCodeOutput();
        this.createPedestal();
        
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2.5, height: 1.5 });
            plaque.position.set(2.2, 0.5, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P2-I1', interactive: true };
    }
    
    createFigmaCanvas() {
        // Figma-style design canvas on left
        const canvasGeo = new THREE.PlaneGeometry(1.5, 2);
        const canvasMat = new THREE.MeshPhysicalMaterial({
            color: 0x2C2C2C,
            metalness: 0.1,
            roughness: 0.8,
            side: THREE.DoubleSide
        });
        this.figmaCanvas = new THREE.Mesh(canvasGeo, canvasMat);
        this.figmaCanvas.position.set(-1.2, 2.5, 0);
        this.figmaCanvas.rotation.y = Math.PI / 6;
        this.add(this.figmaCanvas);
        
        // Frame
        const frameGeo = new THREE.BoxGeometry(1.6, 2.1, 0.05);
        const frameMat = new THREE.MeshStandardMaterial({
            color: 0x9B7EBD,
            metalness: 0.6,
            roughness: 0.4
        });
        const frame = new THREE.Mesh(frameGeo, frameMat);
        frame.position.copy(this.figmaCanvas.position);
        frame.position.z -= 0.03;
        frame.rotation.y = Math.PI / 6;
        this.add(frame);
        
        // UI Components on canvas
        const componentColors = [0xFF6B35, 0x4ECDC4, 0xF59E0B, 0x7EB77F, 0x67D4E4];
        const componentPositions = [
            { x: 0, y: 0.6, w: 1.2, h: 0.3 },   // Header
            { x: -0.3, y: 0.1, w: 0.5, h: 0.8 }, // Sidebar
            { x: 0.3, y: 0, w: 0.7, h: 1.0 },    // Main content
            { x: 0.3, y: -0.7, w: 0.4, h: 0.2 }, // Button
            { x: -0.3, y: -0.7, w: 0.4, h: 0.15 } // Input
        ];
        
        componentPositions.forEach((comp, i) => {
            const compGeo = new THREE.PlaneGeometry(comp.w, comp.h);
            const compMat = new THREE.MeshBasicMaterial({
                color: componentColors[i],
                transparent: true,
                opacity: 0.8
            });
            const compMesh = new THREE.Mesh(compGeo, compMat);
            
            // Position relative to canvas
            compMesh.position.copy(this.figmaCanvas.position);
            compMesh.position.x += comp.x * Math.cos(Math.PI / 6);
            compMesh.position.y += comp.y;
            compMesh.position.z += comp.x * Math.sin(Math.PI / 6) + 0.01;
            compMesh.rotation.y = Math.PI / 6;
            
            this.uiElements.push({ mesh: compMesh, color: componentColors[i], phase: i * 0.3 });
            this.add(compMesh);
        });
    }
    
    createPipeline() {
        // Transformation arrows/stream
        const pipelinePoints = [];
        for (let i = 0; i <= 20; i++) {
            const t = i / 20;
            pipelinePoints.push(new THREE.Vector3(
                -0.5 + t * 2.2,
                2.5 + Math.sin(t * Math.PI) * 0.3,
                0
            ));
        }
        
        const pipelineCurve = new THREE.CatmullRomCurve3(pipelinePoints);
        const pipelineGeo = new THREE.TubeGeometry(pipelineCurve, 30, 0.05, 8, false);
        const pipelineMat = new THREE.MeshPhysicalMaterial({
            color: 0x9B7EBD,
            emissive: 0x9B7EBD,
            emissiveIntensity: 0.3,
            metalness: 0.5,
            roughness: 0.3,
            transparent: true,
            opacity: 0.7
        });
        this.pipeline = new THREE.Mesh(pipelineGeo, pipelineMat);
        this.add(this.pipeline);
        
        // Data packets flowing through pipeline - FILM QUALITY PBR
        const packetGeo = new THREE.SphereGeometry(0.08, 16, 16);
        const packetMat = new THREE.MeshPhysicalMaterial({ 
            color: 0xF5F0E8,
            emissive: 0xF5F0E8,
            emissiveIntensity: 0.3,
            metalness: 0.2,
            roughness: 0.3
        });
        this.packets = [];
        
        for (let i = 0; i < 5; i++) {
            const packet = new THREE.Mesh(packetGeo, packetMat.clone());
            packet.material.color.setHex([0xFF6B35, 0x4ECDC4, 0xF59E0B, 0x7EB77F, 0x67D4E4][i]);
            this.packets.push({ mesh: packet, offset: i * 0.2, curve: pipelineCurve });
            this.add(packet);
        }
    }
    
    createCodeOutput() {
        // Code editor style output on right
        const codeGeo = new THREE.PlaneGeometry(1.5, 2);
        const codeMat = new THREE.MeshPhysicalMaterial({
            color: 0x1E1E1E,
            metalness: 0.1,
            roughness: 0.9,
            side: THREE.DoubleSide
        });
        this.codeCanvas = new THREE.Mesh(codeGeo, codeMat);
        this.codeCanvas.position.set(1.2, 2.5, 0);
        this.codeCanvas.rotation.y = -Math.PI / 6;
        this.add(this.codeCanvas);
        
        // Frame
        const frameGeo = new THREE.BoxGeometry(1.6, 2.1, 0.05);
        const frameMat = new THREE.MeshStandardMaterial({
            color: 0x4ECDC4,
            metalness: 0.6,
            roughness: 0.4
        });
        const frame = new THREE.Mesh(frameGeo, frameMat);
        frame.position.copy(this.codeCanvas.position);
        frame.position.z -= 0.03;
        frame.rotation.y = -Math.PI / 6;
        this.add(frame);
        
        // Code lines (simulated)
        const lineColors = [0x569CD6, 0xCE9178, 0x4EC9B0, 0xDCDCAA, 0x9CDCFE];
        
        for (let i = 0; i < 12; i++) {
            const lineWidth = 0.3 + Math.random() * 0.8;
            const lineGeo = new THREE.PlaneGeometry(lineWidth, 0.05);
            const lineMat = new THREE.MeshBasicMaterial({
                color: lineColors[i % lineColors.length],
                transparent: true,
                opacity: 0.8
            });
            const line = new THREE.Mesh(lineGeo, lineMat);
            
            line.position.copy(this.codeCanvas.position);
            const xOffset = -0.5 + (lineWidth / 2) + (i % 3) * 0.1;
            line.position.x += xOffset * Math.cos(-Math.PI / 6);
            line.position.y += 0.8 - i * 0.13;
            line.position.z += xOffset * Math.sin(-Math.PI / 6) + 0.01;
            line.rotation.y = -Math.PI / 6;
            
            this.codeLines.push({ mesh: line, delay: i * 0.2 });
            this.add(line);
        }
    }
    
    createPedestal() {
        const pedestalGeo = new THREE.BoxGeometry(3, 0.1, 1.5);
        const pedestalMat = new THREE.MeshStandardMaterial({
            color: 0x222222,
            metalness: 0.7,
            roughness: 0.3
        });
        const pedestal = new THREE.Mesh(pedestalGeo, pedestalMat);
        pedestal.position.y = 0.05;
        this.add(pedestal);
    }
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Pulse UI elements
        this.uiElements.forEach(elem => {
            const pulse = Math.sin(this.time * 2 + elem.phase) * 0.1 + 0.9;
            elem.mesh.material.opacity = 0.7 + pulse * 0.2;
        });
        
        // Animate packets through pipeline
        this.packets.forEach(packet => {
            const t = ((this.time * 0.3 + packet.offset) % 1);
            const point = packet.curve.getPoint(t);
            packet.mesh.position.copy(point);
        });
        
        // Reveal code lines progressively
        this.codeLines.forEach(line => {
            const reveal = Math.max(0, Math.min(1, (this.time - line.delay) / 0.3));
            line.mesh.scale.x = reveal;
            line.mesh.material.opacity = reveal * 0.8;
        });
        
        // Reset code animation periodically
        if (this.time > 5) {
            this.time = 0;
        }
    }
    
    dispose() {
        this.traverse(obj => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-A6: JORDAN ALGEBRA BELIEF PROPAGATION (F4)
// Self-dual cone optimization landscape
// ═══════════════════════════════════════════════════════════════════════════

export class JordanF4Artwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-A6');
        this.name = 'artwork-p2-a6';
        this.time = 0;
        this.cones = [];
        this.create();
    }
    create() {
        const color = COLONY_COLORS.crystal;
        for (let i = 0; i < 3; i++) {
            const coneGeo = new THREE.ConeGeometry(0.4 - i * 0.1, 0.8, 8);
            const coneMat = new THREE.MeshPhysicalMaterial({
                color,
                emissive: color,
                emissiveIntensity: 0.2,
                transparent: true,
                opacity: 0.5 - i * 0.1,
                side: THREE.DoubleSide
            });
            const cone = new THREE.Mesh(coneGeo, coneMat);
            cone.position.set(0, 1.2 + i * 0.4, 0);
            cone.rotation.x = Math.PI / 2;
            this.cones.push(cone);
            this.add(cone);
        }
        this._addPlaqueAndPedestal();
        this.userData = { patentId: 'P2-A6', interactive: true };
    }
    _addPlaqueAndPedestal() {
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2, height: 1.2 });
            plaque.position.set(1.8, 0.6, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        const pedestalGeo = new THREE.CylinderGeometry(1, 1.2, 0.2, 32);
        const pedestal = new THREE.Mesh(pedestalGeo, new THREE.MeshPhysicalMaterial({ color: 0x1D1C22, metalness: 0.9, roughness: 0.1 }));
        pedestal.position.y = 0.1;
        pedestal.userData.isPedestal = true;
        this.add(pedestal);
    }
    update(deltaTime) {
        this.time += deltaTime;
        this.cones.forEach((c, i) => {
            c.rotation.z = this.time * 0.2 + i * 0.3;
            c.material.emissiveIntensity = 0.2 + Math.sin(this.time * 2 + i) * 0.15;
        });
    }
    dispose() { this.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-B3: WILDGUARD + CBF PIPELINE
// Guardian sentinel + mathematician
// ═══════════════════════════════════════════════════════════════════════════

export class WildGuardCBFArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-B3');
        this.name = 'artwork-p2-b3';
        this.time = 0;
        this.create();
    }
    create() {
        const guardGeo = new THREE.CylinderGeometry(0.15, 0.2, 1, 8);
        const guardMat = new THREE.MeshPhysicalMaterial({ color: 0xE85A2F, emissive: 0xE85A2F, emissiveIntensity: 0.3 });
        const guard = new THREE.Mesh(guardGeo, guardMat);
        guard.position.set(-0.5, 1.2, 0);
        this.add(guard);
        const mathGeo = new THREE.OctahedronGeometry(0.25, 0);
        const mathMat = new THREE.MeshPhysicalMaterial({ color: 0x6FA370, emissive: 0x6FA370, emissiveIntensity: 0.3 });
        const math = new THREE.Mesh(mathGeo, mathMat);
        math.position.set(0.5, 1.2, 0);
        this.add(math);
        const pipeGeo = new THREE.CylinderGeometry(0.03, 0.03, 1.2, 8);
        const pipe = new THREE.Mesh(pipeGeo, new THREE.MeshBasicMaterial({ color: 0x67D4E4, transparent: true, opacity: 0.5 }));
        pipe.rotation.z = Math.PI / 2;
        pipe.position.y = 1.5;
        this.add(pipe);
        this._addPlaqueAndPedestal();
        this.userData = { patentId: 'P2-B3', interactive: true };
    }
    _addPlaqueAndPedestal() {
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2, height: 1.2 });
            plaque.position.set(1.8, 0.6, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        const pedestalGeo = new THREE.CylinderGeometry(1, 1.2, 0.2, 32);
        const _ped = new THREE.Mesh(pedestalGeo, new THREE.MeshPhysicalMaterial({ color: 0x1D1C22, metalness: 0.9, roughness: 0.1 }));
        _ped.position.y = 0.1;
        _ped.userData.isPedestal = true;
        this.add(_ped);
    }
    update(deltaTime) {
        this.time += deltaTime;
        this.children.filter(c => c.material?.emissiveIntensity !== undefined).forEach((c, i) => {
            c.material.emissiveIntensity = 0.3 + Math.sin(this.time * 2 + i) * 0.2;
        });
    }
    dispose() { this.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-C3: CALM PARTITION TOLERANCE
// Network splitting and reconverging
// ═══════════════════════════════════════════════════════════════════════════

export class CALMPartitionArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-C3');
        this.name = 'artwork-p2-c3';
        this.time = 0;
        this.nodes = [];
        this.create();
    }
    create() {
        const lineMat = new THREE.LineBasicMaterial({ color: COLONY_COLORS.nexus, transparent: true, opacity: 0.5 });
        for (let i = 0; i < 6; i++) {
            const angle = (i / 6) * Math.PI * 2;
            const nodeGeo = new THREE.SphereGeometry(0.12, 16, 16);
            const node = new THREE.Mesh(nodeGeo, new THREE.MeshPhysicalMaterial({
                color: COLONY_COLORS.nexus,
                emissive: COLONY_COLORS.nexus,
                emissiveIntensity: 0.3
            }));
            node.position.set(Math.cos(angle) * 0.9, 1.5, Math.sin(angle) * 0.9);
            this.nodes.push(node);
            this.add(node);
        }
        for (let i = 0; i < 6; i++) {
            const j = (i + 1) % 6;
            const geo = new THREE.BufferGeometry().setFromPoints([this.nodes[i].position.clone(), this.nodes[j].position.clone()]);
            this.add(new THREE.Line(geo, lineMat));
        }
        this._addPlaqueAndPedestal();
        this.userData = { patentId: 'P2-C3', interactive: true };
    }
    _addPlaqueAndPedestal() {
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2, height: 1.2 });
            plaque.position.set(1.8, 0.6, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        const _ped = new THREE.Mesh(new THREE.CylinderGeometry(1, 1.2, 0.2, 32), new THREE.MeshPhysicalMaterial({ color: 0x1D1C22, metalness: 0.9, roughness: 0.1 }));
        _ped.position.y = 0.1;
        _ped.userData.isPedestal = true;
        this.add(_ped);
    }
    update(deltaTime) {
        this.time += deltaTime;
        this.nodes.forEach((n, i) => {
            n.material.emissiveIntensity = 0.3 + Math.sin(this.time * 2 + i) * 0.2;
            n.scale.setScalar(1 + Math.sin(this.time * 3 + i * 0.5) * 0.05);
        });
    }
    dispose() { this.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-D3: 14-PHASE TRAINING CURRICULUM
// Staircase of learning stages
// ═══════════════════════════════════════════════════════════════════════════

export class Curriculum14PhaseArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-D3');
        this.name = 'artwork-p2-d3';
        this.time = 0;
        this.steps = [];
        this.create();
    }
    create() {
        const color = COLONY_COLORS.grove;
        for (let i = 0; i < 7; i++) {
            const stepGeo = new THREE.BoxGeometry(0.25, 0.15, 0.4);
            const step = new THREE.Mesh(stepGeo, new THREE.MeshPhysicalMaterial({
                color,
                emissive: color,
                emissiveIntensity: 0.2 + i * 0.03
            }));
            step.position.set(0, 0.2 + i * 0.2, -0.2 + i * 0.05);
            this.steps.push(step);
            this.add(step);
        }
        this._addPlaqueAndPedestal();
        this.userData = { patentId: 'P2-D3', interactive: true };
    }
    _addPlaqueAndPedestal() {
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2, height: 1.2 });
            plaque.position.set(1.8, 0.6, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        const _ped = new THREE.Mesh(new THREE.CylinderGeometry(1, 1.2, 0.2, 32), new THREE.MeshPhysicalMaterial({ color: 0x1D1C22, metalness: 0.9, roughness: 0.1 }));
        _ped.position.y = 0.1;
        _ped.userData.isPedestal = true;
        this.add(_ped);
    }
    update(deltaTime) {
        this.time += deltaTime;
        this.steps.forEach((s, i) => {
            s.material.emissiveIntensity = 0.2 + i * 0.03 + Math.sin(this.time + i * 0.5) * 0.1;
        });
    }
    dispose() { this.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-D4: UNIFIED SEARCH (MCTS+CFR+EFE)
// Three intertwined search trees
// ═══════════════════════════════════════════════════════════════════════════

export class UnifiedSearchArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-D4');
        this.name = 'artwork-p2-d4';
        this.time = 0;
        this.trees = [];
        this.create();
    }
    create() {
        const colors = [0x9B7EBD, 0x4ECDC4, 0xE8940A];
        for (let t = 0; t < 3; t++) {
            const rootGeo = new THREE.SphereGeometry(0.1, 16, 16);
            const root = new THREE.Mesh(rootGeo, new THREE.MeshPhysicalMaterial({
                color: colors[t],
                emissive: colors[t],
                emissiveIntensity: 0.4
            }));
            root.position.set((t - 1) * 0.4, 1.6, 0);
            this.trees.push(root);
            this.add(root);
            for (let i = 0; i < 4; i++) {
                const angle = (i / 4) * Math.PI * 2 + t * 0.5;
                const node = new THREE.Mesh(rootGeo, new THREE.MeshPhysicalMaterial({
                    color: colors[t],
                    emissive: colors[t],
                    emissiveIntensity: 0.2,
                    transparent: true,
                    opacity: 0.8
                }));
                node.position.set(
                    (t - 1) * 0.4 + Math.cos(angle) * 0.35,
                    1.2 - i * 0.15,
                    Math.sin(angle) * 0.35
                );
                this.add(node);
                const geo = new THREE.BufferGeometry().setFromPoints([root.position.clone(), node.position.clone()]);
                this.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color: colors[t], transparent: true, opacity: 0.4 })));
            }
        }
        this._addPlaqueAndPedestal();
        this.userData = { patentId: 'P2-D4', interactive: true };
    }
    _addPlaqueAndPedestal() {
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2, height: 1.2 });
            plaque.position.set(1.8, 0.6, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        const _ped = new THREE.Mesh(new THREE.CylinderGeometry(1, 1.2, 0.2, 32), new THREE.MeshPhysicalMaterial({ color: 0x1D1C22, metalness: 0.9, roughness: 0.1 }));
        _ped.position.y = 0.1;
        _ped.userData.isPedestal = true;
        this.add(_ped);
    }
    update(deltaTime) {
        this.time += deltaTime;
        this.trees.forEach((r, i) => {
            r.material.emissiveIntensity = 0.4 + Math.sin(this.time * 2 + i) * 0.2;
        });
    }
    dispose() { this.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-F1: SPECTRUM ENGINE
// Audio spectrum analysis / reactive lighting
// ═══════════════════════════════════════════════════════════════════════════

export class SpectrumEngineArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-F1');
        this.name = 'artwork-p2-f1';
        this.time = 0;
        this.bars = [];
        this.create();
    }
    create() {
        const color = COLONY_COLORS.flow;
        for (let i = 0; i < 16; i++) {
            const barGeo = new THREE.BoxGeometry(0.08, 0.4, 0.08);
            const bar = new THREE.Mesh(barGeo, new THREE.MeshPhysicalMaterial({
                color,
                emissive: color,
                emissiveIntensity: 0.3
            }));
            bar.position.set(-0.6 + i * 0.08, 1.2, 0);
            this.bars.push(bar);
            this.add(bar);
        }
        this._addPlaqueAndPedestal();
        this.userData = { patentId: 'P2-F1', interactive: true };
    }
    _addPlaqueAndPedestal() {
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2, height: 1.2 });
            plaque.position.set(1.8, 0.6, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        const _ped = new THREE.Mesh(new THREE.CylinderGeometry(1, 1.2, 0.2, 32), new THREE.MeshPhysicalMaterial({ color: 0x1D1C22, metalness: 0.9, roughness: 0.1 }));
        _ped.position.y = 0.1;
        _ped.userData.isPedestal = true;
        this.add(_ped);
    }
    update(deltaTime) {
        this.time += deltaTime;
        this.bars.forEach((b, i) => {
            const h = 0.3 + Math.abs(Math.sin(this.time * 4 + i * 0.4)) * 0.5;
            b.scale.y = h;
            b.position.y = 0.9 + h * 0.5;
            b.material.emissiveIntensity = 0.3 + Math.sin(this.time * 3 + i) * 0.2;
        });
    }
    dispose() { this.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-H1: AUTONOMOUS ECONOMIC AGENT
// Bidding marketplace animation
// ═══════════════════════════════════════════════════════════════════════════

export class AutonomousEconomicAgentArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-H1');
        this.name = 'artwork-p2-h1';
        this.time = 0;
        this.create();
    }
    create() {
        const agentGeo = new THREE.OctahedronGeometry(0.3, 0);
        const agent = new THREE.Mesh(agentGeo, new THREE.MeshPhysicalMaterial({
            color: COLONY_COLORS.beacon,
            emissive: COLONY_COLORS.beacon,
            emissiveIntensity: 0.5
        }));
        agent.position.y = 1.5;
        this.add(agent);
        const marketGeo = new THREE.RingGeometry(0.6, 1, 32);
        const market = new THREE.Mesh(marketGeo, new THREE.MeshBasicMaterial({
            color: COLONY_COLORS.beacon,
            transparent: true,
            opacity: 0.3,
            side: THREE.DoubleSide
        }));
        market.rotation.x = -Math.PI / 2;
        market.position.y = 0.3;
        this.add(market);
        this._addPlaqueAndPedestal();
        this.userData = { patentId: 'P2-H1', interactive: true };
    }
    _addPlaqueAndPedestal() {
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2, height: 1.2 });
            plaque.position.set(1.8, 0.6, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        const _ped = new THREE.Mesh(new THREE.CylinderGeometry(1, 1.2, 0.2, 32), new THREE.MeshPhysicalMaterial({ color: 0x1D1C22, metalness: 0.9, roughness: 0.1 }));
        _ped.position.y = 0.1;
        _ped.userData.isPedestal = true;
        this.add(_ped);
    }
    update(deltaTime) {
        this.time += deltaTime;
        this.children.filter(c => c.material?.emissiveIntensity !== undefined).forEach(c => {
            c.material.emissiveIntensity = 0.5 + Math.sin(this.time * 2) * 0.2;
        });
        const agentMesh = this.children.find(c => c.type === 'Mesh' && c.geometry?.type === 'OctahedronGeometry');
        if (agentMesh) agentMesh.rotation.y += deltaTime * 0.5;
    }
    dispose() { this.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-I1: E8 UNIFIED EVENT BUS
// 248-channel routing visualization
// ═══════════════════════════════════════════════════════════════════════════

export class E8EventBusArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-I1');
        this.name = 'artwork-p2-i1';
        this.time = 0;
        this.channels = [];
        this.create();
    }
    create() {
        const color = COLONY_COLORS.forge;
        const hubGeo = new THREE.SphereGeometry(0.2, 32, 32);
        const hub = new THREE.Mesh(hubGeo, new THREE.MeshPhysicalMaterial({
            color,
            emissive: color,
            emissiveIntensity: 0.5
        }));
        hub.position.y = 1.5;
        this.add(hub);
        for (let i = 0; i < 12; i++) {
            const angle = (i / 12) * Math.PI * 2;
            const channelGeo = new THREE.CylinderGeometry(0.02, 0.02, 0.6, 8);
            const channel = new THREE.Mesh(channelGeo, new THREE.MeshBasicMaterial({
                color,
                transparent: true,
                opacity: 0.5
            }));
            channel.position.set(Math.cos(angle) * 0.5, 1.2, Math.sin(angle) * 0.5);
            channel.rotation.z = -angle;
            this.channels.push(channel);
            this.add(channel);
        }
        this._addPlaqueAndPedestal();
        this.userData = { patentId: 'P2-I1', interactive: true };
    }
    _addPlaqueAndPedestal() {
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2, height: 1.2 });
            plaque.position.set(1.8, 0.6, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        const _ped = new THREE.Mesh(new THREE.CylinderGeometry(1, 1.2, 0.2, 32), new THREE.MeshPhysicalMaterial({ color: 0x1D1C22, metalness: 0.9, roughness: 0.1 }));
        _ped.position.y = 0.1;
        _ped.userData.isPedestal = true;
        this.add(_ped);
    }
    update(deltaTime) {
        this.time += deltaTime;
        this.channels.forEach((c, i) => {
            c.material.opacity = 0.3 + Math.sin(this.time * 2 + i * 0.5) * 0.3;
        });
        const hubMesh = this.children.find(c => c.geometry?.type === 'SphereGeometry');
        if (hubMesh?.material?.emissiveIntensity !== undefined) {
            hubMesh.material.emissiveIntensity = 0.5 + Math.sin(this.time * 3) * 0.2;
        }
    }
    dispose() { this.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
}

// ═══════════════════════════════════════════════════════════════════════════
// P2-I2: RALPH PARALLEL AUDIT
// Six parallel judge chambers
// ═══════════════════════════════════════════════════════════════════════════

export class RalphParallelAuditArtwork extends THREE.Group {
    constructor() {
        super();
        this.patent = getPatent('P2-I2');
        this.name = 'artwork-p2-i2';
        this.time = 0;
        this.judges = [];
        this.create();
    }
    create() {
        const color = COLONY_COLORS.forge;
        for (let i = 0; i < 6; i++) {
            const angle = (i / 6) * Math.PI * 2;
            const judgeGeo = new THREE.BoxGeometry(0.2, 0.35, 0.15);
            const judge = new THREE.Mesh(judgeGeo, new THREE.MeshPhysicalMaterial({
                color,
                emissive: color,
                emissiveIntensity: 0.2
            }));
            judge.position.set(Math.cos(angle) * 0.7, 1.2, Math.sin(angle) * 0.7);
            judge.rotation.y = -angle;
            this.judges.push(judge);
            this.add(judge);
        }
        const centerGeo = new THREE.SphereGeometry(0.15, 16, 16);
        const center = new THREE.Mesh(centerGeo, new THREE.MeshPhysicalMaterial({
            color: 0x6FA370,
            emissive: 0x6FA370,
            emissiveIntensity: 0.4
        }));
        center.position.y = 1.5;
        this.add(center);
        this._addPlaqueAndPedestal();
        this.userData = { patentId: 'P2-I2', interactive: true };
    }
    _addPlaqueAndPedestal() {
        if (this.patent) {
            const plaque = createPlaque(this.patent, { width: 2, height: 1.2 });
            plaque.position.set(1.8, 0.6, 0);
            plaque.rotation.y = -Math.PI / 4;
            this.add(plaque);
        }
        const _ped = new THREE.Mesh(new THREE.CylinderGeometry(1, 1.2, 0.2, 32), new THREE.MeshPhysicalMaterial({ color: 0x1D1C22, metalness: 0.9, roughness: 0.1 }));
        _ped.position.y = 0.1;
        _ped.userData.isPedestal = true;
        this.add(_ped);
    }
    update(deltaTime) {
        this.time += deltaTime;
        this.judges.forEach((j, i) => {
            j.material.emissiveIntensity = 0.2 + Math.sin(this.time * 2 + i) * 0.15;
        });
    }
    dispose() { this.traverse(o => { if (o.geometry) o.geometry.dispose(); if (o.material) o.material.dispose(); }); }
}

// ═══════════════════════════════════════════════════════════════════════════
// FACTORY FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

export function createP2Artwork(patentId) {
    switch (patentId) {
        case 'P2-A4': return new G2EquivariantArtwork();
        case 'P2-A5': return new WeylEquivariantArtwork();
        case 'P2-A6': return new JordanF4Artwork();
        case 'P2-B2': return new SafetyHierarchyArtwork();
        case 'P2-B3': return new WildGuardCBFArtwork();
        case 'P2-C2': return new CrossHubCRDTArtwork();
        case 'P2-C3': return new CALMPartitionArtwork();
        case 'P2-D2': return new CatastropheKANArtwork();
        case 'P2-D3': return new Curriculum14PhaseArtwork();
        case 'P2-D4': return new UnifiedSearchArtwork();
        case 'P2-E2': return new ContextBoundEncryptionArtwork();
        case 'P2-F1': return new SpectrumEngineArtwork();
        case 'P2-F2': return new MusicReactiveLightingArtwork();
        case 'P2-G1': return new EarconOrchestrationArtwork();
        case 'P2-H1': return new AutonomousEconomicAgentArtwork();
        case 'P2-H2': return new FreelancerBiddingArtwork();
        case 'P2-I1': return new E8EventBusArtwork();
        case 'P2-I2': return new RalphParallelAuditArtwork();
        default: return null;
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════════════════

export default {
    G2EquivariantArtwork,
    SafetyHierarchyArtwork,
    CrossHubCRDTArtwork,
    CatastropheKANArtwork,
    ContextBoundEncryptionArtwork,
    EarconOrchestrationArtwork,
    FreelancerBiddingArtwork,
    MusicReactiveLightingArtwork,
    WeylEquivariantArtwork,
    FigmaToCodeArtwork,
    JordanF4Artwork,
    WildGuardCBFArtwork,
    CALMPartitionArtwork,
    Curriculum14PhaseArtwork,
    UnifiedSearchArtwork,
    SpectrumEngineArtwork,
    AutonomousEconomicAgentArtwork,
    E8EventBusArtwork,
    RalphParallelAuditArtwork,
    createP2Artwork
};
