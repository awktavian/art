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

/**
 * Create a floating canvas-based text label for educational content.
 * Returns a THREE.Sprite with the label rendered at HiDPI resolution.
 */
function createEducationalLabel(text, options = {}) {
    const { fontSize = 32, color = '#E8E4D9', maxWidth = 512, bgColor = 'rgba(13,12,18,0.85)' } = options;
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = maxWidth * dpr;
    canvas.height = 128 * dpr;
    ctx.scale(dpr, dpr);
    
    // Background
    ctx.fillStyle = bgColor;
    ctx.roundRect?.(4, 4, maxWidth - 8, 120, 8);
    ctx.fill?.();
    
    // Text
    ctx.font = `${fontSize}px "IBM Plex Sans", sans-serif`;
    ctx.fillStyle = color;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    
    // Word wrap
    const words = text.split(' ');
    let line = '';
    let y = 40;
    for (const word of words) {
        const test = line + (line ? ' ' : '') + word;
        if (ctx.measureText(test).width > maxWidth - 40) {
            ctx.fillText(line, maxWidth / 2, y);
            line = word;
            y += fontSize + 4;
        } else {
            line = test;
        }
    }
    ctx.fillText(line, maxWidth / 2, y);
    
    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    const material = new THREE.SpriteMaterial({ map: texture, transparent: true, depthTest: false });
    const sprite = new THREE.Sprite(material);
    sprite.scale.set(2, 0.5, 1);
    return sprite;
}

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
        this.demoMode = false;
        this.demoTimer = 0;
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
        
        // Educational labels
        const titleLabel = createEducationalLabel('G2 Equivariant Neural Network', { fontSize: 22, maxWidth: 380 });
        titleLabel.position.set(0, 2.2, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        const infoLabel = createEducationalLabel('14-dim representation · Triple Dynkin edge · Lie algebra symmetry', { fontSize: 16, maxWidth: 420 });
        infoLabel.position.set(0, 0.5, 0);
        infoLabel.scale.set(2, 0.18, 1);
        this.add(infoLabel);
        
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
    
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
    }

    update(deltaTime) {
        this.time += deltaTime;
        if (this.demoMode) this.demoTimer += deltaTime;
        
        // Slow continuous rotation of the root system
        const rotSpeed = this.demoMode ? 0.05 : 0.15;
        
        this.nodes.forEach((node, i) => {
            const isLong = i >= 6;
            const baseAngle = ((i % 6) / 6) * Math.PI * 2 + (isLong ? Math.PI / 6 : 0);
            const baseRadius = isLong ? 1.4 : 0.8;
            
            if (this.demoMode) {
                // Weight transformation: spheres shift along Dynkin triple bond direction
                const wave = Math.sin(this.demoTimer * 2 + i * 0.4);
                const shiftDir = isLong ? 0.3 : -0.15; // long and short roots shift oppositely
                const dynkinShift = wave * shiftDir;
                
                // Spiral outward along bond direction (radial shift)
                const r = baseRadius + dynkinShift;
                const angleOffset = this.time * rotSpeed + wave * 0.1;
                node.position.x = Math.cos(baseAngle + angleOffset) * r;
                node.position.z = Math.sin(baseAngle + angleOffset) * r;
                node.position.y = 2 + Math.sin(this.demoTimer * 3 + i * 0.5) * 0.15;
                
                // Bright pulsing during transformation
                node.material.emissiveIntensity = 0.5 + Math.sin(this.demoTimer * 4 + i) * 0.3;
            } else {
                // Gentle rotation, subtle breathing
                const angleOffset = this.time * rotSpeed;
                node.position.x = Math.cos(baseAngle + angleOffset) * baseRadius;
                node.position.z = Math.sin(baseAngle + angleOffset) * baseRadius;
                node.position.y = 2;
                node.material.emissiveIntensity = 0.3 + Math.sin(this.time * 1.5 + i * 0.8) * 0.1;
            }
        });
        
        if (this.lattice) {
            this.lattice.rotation.y = this.time * 0.08;
            this.lattice.rotation.x = Math.sin(this.time * 0.15) * 0.08;
            if (this.demoMode) {
                // Lattice breathes with the weight transformation
                const breath = 1 + Math.sin(this.demoTimer * 2) * 0.1;
                this.lattice.scale.setScalar(breath);
            } else {
                this.lattice.scale.setScalar(1);
            }
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
        this.demoMode = false;
        this.demoTimer = 0;
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
        
        // Educational labels
        const titleLabel = createEducationalLabel('Multi-Tier Safety Hierarchy', { fontSize: 22, maxWidth: 380 });
        titleLabel.position.set(0, 2.2, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        const infoLabel = createEducationalLabel('h(x) ≥ 0 at every tier · Nested CBF barriers · Graduated response', { fontSize: 16, maxWidth: 440 });
        infoLabel.position.set(0, 0.5, 0);
        infoLabel.scale.set(2, 0.18, 1);
        this.add(infoLabel);
        
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
    
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
    }

    update(deltaTime) {
        this.time += deltaTime;
        if (this.demoMode) this.demoTimer += deltaTime;
        
        if (this.demoMode) {
            // STRESS TEST: barriers glow red, innermost pulses rapidly
            const stressPhase = Math.min(this.demoTimer / 2, 1); // ramp up over 2s
            
            this.barriers.forEach((barrier, i) => {
                // All barriers shift toward red during stress
                const r = stressPhase;
                barrier.material.color.setRGB(0.9 * r + (1 - r) * barrier.material.color.r, 
                    barrier.material.color.g * (1 - r * 0.7), 
                    barrier.material.color.b * (1 - r * 0.7));
                barrier.material.emissive?.setRGB(0.9 * r, 0.1 * (1 - r), 0.05 * (1 - r));
                barrier.material.emissiveIntensity = 0.3 + stressPhase * 0.4;
                
                // Innermost barrier (i=2) pulses rapidly, outer barriers pulse slower
                const pulseRate = i === 2 ? 12 : (i === 1 ? 6 : 3);
                const scale = 1 + Math.sin(this.demoTimer * pulseRate) * (0.03 + stressPhase * 0.08);
                barrier.scale.setScalar(scale);
                
                // Barriers wobble under stress
                barrier.rotation.y = this.time * 0.1 * (i + 1);
                barrier.rotation.x = Math.sin(this.demoTimer * (3 + i)) * stressPhase * 0.05;
            });
            
            // Agent flickers under stress
            if (this.agent) {
                this.agent.material.emissiveIntensity = 0.7 + Math.sin(this.demoTimer * 15) * 0.3 * stressPhase;
                this.agent.material.color.setHex(stressPhase > 0.5 ? 0xFF6B35 : 0x67D4E4);
            }
        } else {
            // Normal: layers pulse at different rates, gentle rotation
            this.barriers.forEach((barrier, i) => {
                // Reset colors on exit from demo
                const tierColors = [0xE85A2F, 0xE8940A, 0x6FA370];
                barrier.material.color.setHex(tierColors[i]);
                barrier.material.emissive?.setHex(0x000000);
                barrier.material.emissiveIntensity = 0;
                
                const rate = 0.8 + i * 0.4; // different rates per tier
                const scale = 1 + Math.sin(this.time * rate + i * 1.2) * 0.04;
                barrier.scale.setScalar(scale);
                barrier.rotation.y = this.time * 0.1 * (i + 1);
                barrier.rotation.x = 0;
            });
            
            if (this.agent) {
                this.agent.material.emissiveIntensity = 0.5 + Math.sin(this.time * 2) * 0.15;
                this.agent.material.color.setHex(0x67D4E4);
            }
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
        this.demoMode = false;
        this.demoTimer = 0;
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
        
        // Educational labels
        const titleLabel = createEducationalLabel('Cross-Hub CRDT Synchronization', { fontSize: 22, maxWidth: 400 });
        titleLabel.position.set(0, 2.2, 0);
        titleLabel.scale.set(1.6, 0.22, 1);
        this.add(titleLabel);
        
        const infoLabel = createEducationalLabel('Conflict-free replicated data types · Eventually consistent · Multi-hub', { fontSize: 16, maxWidth: 440 });
        infoLabel.position.set(0, 0.5, 0);
        infoLabel.scale.set(2, 0.18, 1);
        this.add(infoLabel);
        
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
    
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
    }

    update(deltaTime) {
        this.time += deltaTime;
        if (this.demoMode) this.demoTimer += deltaTime;
        
        if (this.demoMode) {
            // CONFLICT SCENARIO: two hubs detect conflict, then merge-resolve
            const conflictDuration = 3; // seconds of conflict
            const resolveDuration = 2; // seconds of resolution
            const cycleDuration = conflictDuration + resolveDuration;
            const cycleTime = this.demoTimer % cycleDuration;
            const conflicting = cycleTime < conflictDuration;
            
            // Pick two conflicting hubs
            const conflictA = 0;
            const conflictB = 2;
            
            this.hubs.forEach((hub, i) => {
                hub.rotation.y = this.time * 0.5 + i;
                
                if (i === conflictA || i === conflictB) {
                    if (conflicting) {
                        // Flash red during conflict
                        const flash = Math.sin(this.demoTimer * 10) * 0.5 + 0.5;
                        hub.material.color.setRGB(0.9, 0.15 * (1 - flash), 0.1 * (1 - flash));
                        hub.material.emissive.setRGB(0.9, 0.1, 0.05);
                        hub.material.emissiveIntensity = 0.4 + flash * 0.4;
                    } else {
                        // Resolve: transition red → green
                        const resolveT = (cycleTime - conflictDuration) / resolveDuration;
                        hub.material.color.setRGB(0.9 * (1 - resolveT), 0.6 * resolveT + 0.15, 0.1);
                        hub.material.emissive.setRGB(0.2 * (1 - resolveT), 0.7 * resolveT, 0.1 * resolveT);
                        hub.material.emissiveIntensity = 0.5;
                    }
                } else {
                    // Non-conflicting hubs: normal behavior
                    const hubColors = [0xFF6B35, 0xD4AF37, 0x4ECDC4, 0x9B7EBD, 0x7EB77F];
                    hub.material.color.setHex(hubColors[i]);
                    hub.material.emissive.setHex(hubColors[i]);
                    hub.material.emissiveIntensity = 0.3 + Math.sin(this.time * 2 + i) * 0.1;
                }
            });
            
            // Sync pulses rush between conflicting hubs during resolution
            this.syncPulses.forEach((pulse, pi) => {
                if (!conflicting && pi < 4) {
                    // Resolution pulses between conflict hubs (green)
                    pulse.material.color.setHex(0x4CFF4C);
                    pulse.material.emissive.setHex(0x4CFF4C);
                    pulse.userData.fromHub = pi % 2 === 0 ? conflictA : conflictB;
                    pulse.userData.toHub = pi % 2 === 0 ? conflictB : conflictA;
                } else {
                    pulse.material.color.setHex(0x6FA370);
                    pulse.material.emissive.setHex(0x6FA370);
                }
                
                pulse.userData.progress += deltaTime * pulse.userData.speed * (this.demoMode && !conflicting ? 2 : 1);
                if (pulse.userData.progress > 1) {
                    pulse.userData.progress = 0;
                    pulse.userData.fromHub = pulse.userData.toHub;
                    pulse.userData.toHub = Math.floor(Math.random() * 5);
                    if (pulse.userData.toHub === pulse.userData.fromHub) {
                        pulse.userData.toHub = (pulse.userData.toHub + 1) % 5;
                    }
                }
                
                const from = this.hubs[pulse.userData.fromHub].position;
                const to = this.hubs[pulse.userData.toHub].position;
                pulse.position.lerpVectors(from, to, pulse.userData.progress);
                pulse.visible = true;
            });
        } else {
            // Normal: gentle rotation, sync pulses travel between hubs
            const hubColors = [0xFF6B35, 0xD4AF37, 0x4ECDC4, 0x9B7EBD, 0x7EB77F];
            this.hubs.forEach((hub, i) => {
                hub.rotation.y = this.time * 0.5 + i;
                hub.material.color.setHex(hubColors[i]);
                hub.material.emissive.setHex(hubColors[i]);
                hub.material.emissiveIntensity = 0.3 + Math.sin(this.time * 1.5 + i * 0.9) * 0.15;
            });
            
            this.syncPulses.forEach(pulse => {
                pulse.material.color.setHex(0x6FA370);
                pulse.material.emissive.setHex(0x6FA370);
                pulse.userData.progress += deltaTime * pulse.userData.speed;
                
                if (pulse.userData.progress > 1) {
                    pulse.userData.progress = 0;
                    pulse.userData.fromHub = pulse.userData.toHub;
                    pulse.userData.toHub = Math.floor(Math.random() * 5);
                    if (pulse.userData.toHub === pulse.userData.fromHub) {
                        pulse.userData.toHub = (pulse.userData.toHub + 1) % 5;
                    }
                }
                
                const from = this.hubs[pulse.userData.fromHub].position;
                const to = this.hubs[pulse.userData.toHub].position;
                pulse.position.lerpVectors(from, to, pulse.userData.progress);
                pulse.visible = true;
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
        this.demoMode = false;
        this.demoTimer = 0;
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
        
        // Educational labels
        const titleLabel = createEducationalLabel('Catastrophe-Aware KAN', { fontSize: 24, maxWidth: 380 });
        titleLabel.position.set(0, 2.2, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        const infoLabel = createEducationalLabel('Kolmogorov-Arnold Networks · Thom catastrophe detection · Fold/cusp topology', { fontSize: 16, maxWidth: 460 });
        infoLabel.position.set(0, 0.5, 0);
        infoLabel.scale.set(2.2, 0.18, 1);
        this.add(infoLabel);
        
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
    
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
    }

    update(deltaTime) {
        this.time += deltaTime;
        if (this.demoMode) this.demoTimer += deltaTime;
        
        // KAN node animation
        this.splineNodes.forEach((node, i) => {
            if (this.demoMode) {
                // Nodes pulse in sequence like a wave propagating through the network
                const waveFront = (this.demoTimer * 4) % this.splineNodes.length;
                const dist = Math.abs(i - waveFront);
                node.material.emissiveIntensity = dist < 3 ? 0.6 + (1 - dist / 3) * 0.4 : 0.2;
            } else {
                node.material.emissiveIntensity = 0.3 + Math.sin(this.time * 1.5 + i * 0.3) * 0.1;
            }
        });
        
        // Catastrophe surface
        if (this.catastropheSurface) {
            if (this.demoMode) {
                // Animate the cusp catastrophe fold:
                // Smooth region transitions to discontinuous fold, cusp point highlighted
                const foldProgress = Math.min(this.demoTimer / 4, 1); // 4s to full fold
                const posAttr = this.catastropheSurface.geometry.getAttribute('position');
                const segments = 30;
                
                for (let j = 0; j <= segments; j++) {
                    for (let i = 0; i <= segments; i++) {
                        const idx = j * (segments + 1) + i;
                        const u = i / segments;
                        const v = j / segments;
                        const x = (u - 0.5) * 2;
                        const y = (v - 0.5) * 2;
                        
                        // Interpolate between smooth (z=0) and cusp (z = x³ - xy)
                        const cuspZ = x * x * x - x * y;
                        // Add fold intensification: as foldProgress increases, the fold sharpens
                        const foldZ = cuspZ * (1 + foldProgress * 2);
                        const z = foldZ * foldProgress;
                        
                        posAttr.setY(idx, z * 0.3 + 0.5);
                    }
                }
                posAttr.needsUpdate = true;
                this.catastropheSurface.geometry.computeVertexNormals();
                
                // Surface rotates slowly, becomes more opaque at cusp
                this.catastropheSurface.rotation.y = this.time * 0.1;
                this.catastropheSurface.material.opacity = 0.4 + foldProgress * 0.3;
                this.catastropheSurface.material.emissive?.setHex(foldProgress > 0.7 ? 0xFF3300 : 0xFF6B35);
                this.catastropheSurface.material.emissiveIntensity = foldProgress * 0.3;
            } else {
                // Normal: gentle undulation
                const posAttr = this.catastropheSurface.geometry.getAttribute('position');
                const segments = 30;
                
                for (let j = 0; j <= segments; j++) {
                    for (let i = 0; i <= segments; i++) {
                        const idx = j * (segments + 1) + i;
                        const u = i / segments;
                        const v = j / segments;
                        const x = (u - 0.5) * 2;
                        const y = (v - 0.5) * 2;
                        const cuspZ = x * x * x - x * y;
                        // Subtle time-based undulation
                        const wave = Math.sin(this.time * 0.8 + x * 2 + y * 2) * 0.1;
                        posAttr.setY(idx, (cuspZ + wave) * 0.3 + 0.5);
                    }
                }
                posAttr.needsUpdate = true;
                this.catastropheSurface.geometry.computeVertexNormals();
                
                this.catastropheSurface.rotation.y = this.time * 0.15;
                this.catastropheSurface.material.opacity = 0.4;
                this.catastropheSurface.material.emissiveIntensity = 0;
            }
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
        this.demoMode = false;
        this.demoTimer = 0;
        this.create();
    }
    
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
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
        
        // Educational labels
        const titleLabel = createEducationalLabel('Context-Bound Encryption', { fontSize: 24, maxWidth: 380 });
        titleLabel.position.set(0, 2.2, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        const infoLabel = createEducationalLabel('Encryption keys bound to context · AAD metadata · Purpose-limited decryption', { fontSize: 16, maxWidth: 460 });
        infoLabel.position.set(0, 0.5, 0);
        infoLabel.scale.set(2.2, 0.18, 1);
        this.add(infoLabel);
        
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
        if (this.demoMode) this.demoTimer += deltaTime;
        
        // Rotate key bits
        const demoPhase = this.demoMode ? Math.min(this.demoTimer / 3, 1) : -1;
        this.keyBits.forEach((bit, i) => {
            if (this.demoMode) {
                // Phase 1 (0-1s): key materializes — bits expand outward from center
                if (demoPhase < 0.33) {
                    const appear = Math.min(this.demoTimer / (0.03 * (i + 1)), 1);
                    const radius = 0.8 * appear;
                    bit.userData.angle += deltaTime * 2;
                    bit.position.x = Math.cos(bit.userData.angle) * radius;
                    bit.position.z = Math.sin(bit.userData.angle) * radius;
                    bit.scale.setScalar(appear);
                    bit.material.emissiveIntensity = 0.5 + appear * 0.5;
                // Phase 2 (1-2s): key binds to context — bits contract toward sphere
                } else if (demoPhase < 0.66) {
                    const bind = (demoPhase - 0.33) / 0.33;
                    const radius = 0.8 + bind * (1.2 - 0.8);
                    bit.userData.angle += deltaTime * (2 - bind * 1.5);
                    bit.position.x = Math.cos(bit.userData.angle) * radius;
                    bit.position.z = Math.sin(bit.userData.angle) * radius;
                    bit.material.emissiveIntensity = 1.0 - bind * 0.3;
                // Phase 3 (2-3s): lock engages — bits freeze and glow gold
                } else {
                    const lock = (demoPhase - 0.66) / 0.34;
                    bit.material.emissiveIntensity = 0.7 + Math.sin(lock * Math.PI) * 0.3;
                    bit.material.emissive.setHex(0xD4AF37);
                }
            } else {
                bit.userData.angle += deltaTime * 0.5;
                const angle = bit.userData.angle;
                bit.position.x = Math.cos(angle) * 0.8;
                bit.position.z = Math.sin(angle) * 0.8;
                bit.rotation.y = this.time + i;
                bit.scale.setScalar(1);
                bit.material.emissive.setHex(bit.userData.value ? 0x6FA370 : 0xE85A2F);
            }
        });
        
        // Pulse context sphere
        if (this.contextSphere) {
            if (this.demoMode && demoPhase >= 0.66) {
                // Lock engaged — sphere contracts and solidifies
                const lock = (demoPhase - 0.66) / 0.34;
                this.contextSphere.material.opacity = 0.2 + lock * 0.4;
                this.contextSphere.scale.setScalar(1 - lock * 0.15);
            } else {
                this.contextSphere.rotation.y = this.time * 0.1;
                this.contextSphere.material.opacity = 0.2;
                this.contextSphere.scale.setScalar(1);
            }
        }
        
        // Animate data stream
        if (this.dataStream) {
            const positions = this.dataStream.geometry.attributes.position.array;
            const speed = this.demoMode && demoPhase >= 0.66 ? 0 : (this.demoMode ? 0.2 : 0.5);
            for (let i = 0; i < positions.length / 3; i++) {
                positions[i * 3 + 1] += deltaTime * speed;
                if (positions[i * 3 + 1] > 2.8) {
                    positions[i * 3 + 1] = 0.8;
                }
            }
            this.dataStream.geometry.attributes.position.needsUpdate = true;
        }
        
        // Reset demo after full cycle
        if (this.demoMode && this.demoTimer > 3.5) {
            this.demoTimer = 0;
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
        this.demoMode = false;
        this.demoTimer = 0;
        this.create();
    }
    
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
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
        
        // Educational labels
        const titleLabel = createEducationalLabel('Earcon Orchestration Engine', { fontSize: 24, maxWidth: 380 });
        titleLabel.position.set(0, 2.2, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        const infoLabel = createEducationalLabel('Auditory icons · Context-aware sound design · Spatial audio routing', { fontSize: 16, maxWidth: 440 });
        infoLabel.position.set(0, 0.5, 0);
        infoLabel.scale.set(2.2, 0.18, 1);
        this.add(infoLabel);
        
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
        if (this.demoMode) this.demoTimer += deltaTime;
        
        // Demo: sequential earcon playback — musical phrase over 5 earcons
        const demoEarconIndex = this.demoMode ? Math.floor((this.demoTimer % 3) / 0.6) : -1;
        
        // Animate sound waves
        this.soundWaves.forEach((wave, i) => {
            if (wave.material.uniforms) {
                wave.material.uniforms.time.value = this.time + i * 0.3;
                // In demo, intensify the active speaker's wave
                if (this.demoMode && i < this.earcons.length) {
                    wave.material.uniforms.opacity.value = i === demoEarconIndex ? 0.7 : 0.1;
                } else {
                    wave.material.uniforms.opacity.value = 0.3;
                }
            }
        });
        
        // Pulse speaker cones
        this.speakers.forEach((speaker, i) => {
            if (this.demoMode) {
                // Sequential activation — speaker fires when its earcon plays
                const active = i < this.earcons.length && i === demoEarconIndex;
                speaker.cone.material.emissiveIntensity = active ? 1.0 : 0.05;
            } else {
                const pulse = Math.sin(this.time * 5 + i) * 0.5 + 0.5;
                speaker.cone.material.emissiveIntensity = 0.2 + pulse * 0.4;
            }
        });
        
        // Float earcons — in demo mode, active one scales up and bounces
        this.earcons.forEach((earcon, i) => {
            if (this.demoMode) {
                const active = i === demoEarconIndex;
                const bounce = active ? Math.abs(Math.sin(this.time * 12)) * 0.15 : 0;
                earcon.sprite.position.y = earcon.baseY + bounce;
                earcon.sprite.scale.setScalar(active ? 0.5 : 0.2);
                earcon.sprite.material.opacity = active ? 1.0 : 0.3;
            } else {
                earcon.sprite.position.y = earcon.baseY + Math.sin(this.time * 2 + earcon.phase) * 0.1;
                earcon.sprite.scale.setScalar(0.3);
                earcon.sprite.material.opacity = 0.8;
            }
        });
        
        // Pulse HRTF aura
        if (this.hrtfAura) {
            if (this.demoMode) {
                // Aura reacts to each earcon hit
                const hitPhase = (this.demoTimer % 0.6) / 0.6;
                const scale = 1 + (1 - hitPhase) * 0.3;
                this.hrtfAura.scale.setScalar(scale);
                this.hrtfAura.material.opacity = 0.15 + (1 - hitPhase) * 0.2;
            } else {
                const scale = 1 + Math.sin(this.time * 3) * 0.1;
                this.hrtfAura.scale.setScalar(scale);
                this.hrtfAura.material.opacity = 0.15;
            }
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
        this.demoMode = false;
        this.demoTimer = 0;
        this.ghostBids = [];
        this.create();
    }
    
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
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
        
        // Educational labels
        const titleLabel = createEducationalLabel('Unified Transaction EFE', { fontSize: 24, maxWidth: 380 });
        titleLabel.position.set(0, 2.2, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        const infoLabel = createEducationalLabel('Expected Free Energy bidding · Multi-objective optimization · Risk-aware', { fontSize: 16, maxWidth: 460 });
        infoLabel.position.set(0, 0.5, 0);
        infoLabel.scale.set(2.2, 0.18, 1);
        this.add(infoLabel);
        
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
        if (this.demoMode) this.demoTimer += deltaTime;
        
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
                const progress = (this.time * 2) % 1;
                const point = bid.curve.getPoint(progress);
                this.bidParticle.position.copy(point);
                this.bidParticle.visible = true;
            }
        });
        
        // Demo: show bid history trail — ghost spheres at past bid positions
        if (this.demoMode) {
            // Spawn a ghost every 0.4s up to 15 ghosts
            const ghostInterval = 0.4;
            const expectedGhosts = Math.min(Math.floor(this.demoTimer / ghostInterval), 15);
            
            while (this.ghostBids.length < expectedGhosts) {
                const bidIdx = this.ghostBids.length % this.bids.length;
                const progress = (this.ghostBids.length * 0.15) % 1;
                const point = this.bids[bidIdx].curve.getPoint(progress);
                
                const ghostGeo = new THREE.SphereGeometry(0.06, 8, 8);
                const ghostMat = new THREE.MeshBasicMaterial({
                    color: this.jobs[bidIdx] ? this.jobs[bidIdx].color : 0xFFFFFF,
                    transparent: true,
                    opacity: 0.6
                });
                const ghost = new THREE.Mesh(ghostGeo, ghostMat);
                ghost.position.copy(point);
                ghost.userData.spawnTime = this.demoTimer;
                this.ghostBids.push(ghost);
                this.add(ghost);
            }
            
            // Fade ghosts over time
            this.ghostBids.forEach(ghost => {
                const age = this.demoTimer - ghost.userData.spawnTime;
                ghost.material.opacity = Math.max(0.05, 0.6 - age * 0.08);
                ghost.scale.setScalar(1 + age * 0.05);
            });
            
            // Loop demo every 7s
            if (this.demoTimer > 7) {
                this.ghostBids.forEach(g => { this.remove(g); g.geometry.dispose(); g.material.dispose(); });
                this.ghostBids.length = 0;
                this.demoTimer = 0;
            }
        } else if (this.ghostBids.length > 0) {
            // Clean up ghosts when demo toggled off
            this.ghostBids.forEach(g => { this.remove(g); g.geometry.dispose(); g.material.dispose(); });
            this.ghostBids.length = 0;
        }
    }
    
    dispose() {
        this.ghostBids.forEach(g => { g.geometry.dispose(); g.material.dispose(); });
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
        this.demoMode = false;
        this.demoTimer = 0;
        this.create();
    }
    
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
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
        
        // Educational labels
        const titleLabel = createEducationalLabel('Music-Reactive Smart Lighting', { fontSize: 24, maxWidth: 380 });
        titleLabel.position.set(0, 2.2, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        const infoLabel = createEducationalLabel('Beat detection · Frequency-mapped colors · Tempo sync · Room zones', { fontSize: 16, maxWidth: 440 });
        infoLabel.position.set(0, 0.5, 0);
        infoLabel.scale.set(2.2, 0.18, 1);
        this.add(infoLabel);
        
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
        if (this.demoMode) this.demoTimer += deltaTime;
        
        // Intensity multiplier — demo mode cranks everything up
        const intensity = this.demoMode ? 2.5 : 1.0;
        const timeScale = this.demoMode ? 1.8 : 1.0;
        const t = this.time * timeScale;
        
        // Simulate music spectrum (would be real audio data in production)
        this.spectrumBars.forEach((bar, i) => {
            const bass = Math.abs(Math.sin(t * 4)) * (i < 8 ? 1 : 0.3);
            const mid = Math.abs(Math.sin(t * 6 + i * 0.3)) * (i >= 8 && i < 20 ? 0.8 : 0.2);
            const high = Math.abs(Math.sin(t * 12 + i * 0.1)) * (i >= 20 ? 0.6 : 0.1);
            
            const amplitude = (bass + mid + high + Math.random() * 0.1) * intensity;
            const height = 0.3 + amplitude * 1.2;
            
            bar.mesh.scale.y = height;
            bar.mesh.position.y = 2 + height / 2;
            bar.mesh.material.emissiveIntensity = Math.min(0.3 + amplitude * 0.5, 1.0);
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
            
            const opacityMul = this.demoMode ? 2.0 : 1.0;
            light.cone.material.opacity = Math.min((0.1 + bandEnergy * 0.15) * opacityMul, 0.8);
            light.cone.scale.y = (0.8 + bandEnergy * 0.4) * (this.demoMode ? 1.3 : 1.0);
        });
        
        // Update waveform
        if (this.waveGeometry) {
            const positions = this.waveGeometry.attributes.position.array;
            const waveAmp = this.demoMode ? 2.0 : 1.0;
            for (let i = 0; i < positions.length / 3; i++) {
                const x = i / 33;
                positions[i * 3 + 1] = 3.5 + 
                    Math.sin(t * 8 + x * 10) * 0.1 * waveAmp +
                    Math.sin(t * 12 + x * 20) * 0.05 * waveAmp;
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
        this.demoMode = false;
        this.demoTimer = 0;
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
        
        // Educational labels
        const titleLabel = createEducationalLabel('Weyl Equivariant Networks', { fontSize: 24, maxWidth: 380 });
        titleLabel.position.set(0, 2.2, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        const infoLabel = createEducationalLabel('Weyl group symmetry · Root system invariance · Reflection equivariance', { fontSize: 16, maxWidth: 440 });
        infoLabel.position.set(0, 0.5, 0);
        infoLabel.scale.set(2.2, 0.18, 1);
        this.add(infoLabel);
        
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
    
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
    }

    update(deltaTime) {
        this.time += deltaTime;
        if (this.demoMode) this.demoTimer += deltaTime;
        
        if (this.demoMode) {
            // REFLECTION DEMO: planes appear dramatically, roots mirror across them
            const reflectionCycle = this.demoTimer % 6; // 6s per full demo cycle
            const activeReflection = Math.floor(reflectionCycle / 2) % 3; // which plane is active
            const reflectionPhase = (reflectionCycle % 2) / 2; // 0→1 within each 2s segment
            
            // Root vectors: mirror across active reflection plane
            this.rootVectors.forEach((root, i) => {
                const baseRot = this.time * 0.1;
                
                if (reflectionPhase < 0.5) {
                    // Pre-reflection: roots drift to normal position
                    root.group.rotation.y = baseRot;
                } else {
                    // Post-reflection: snap to mirrored position
                    const mirrorAngle = this.reflectionPlanes[activeReflection]?.angle || 0;
                    root.group.rotation.y = baseRot + Math.PI - 2 * mirrorAngle;
                }
                
                // Pulse roots during active reflection
                root.group.traverse(obj => {
                    if (obj.material && obj.material.emissiveIntensity !== undefined) {
                        obj.material.emissiveIntensity = 0.4 + Math.sin(this.demoTimer * 6 + i) * 0.3;
                    }
                });
            });
            
            // Reflection planes: active one glows bright, others dim
            this.reflectionPlanes.forEach((plane, i) => {
                if (i === activeReflection) {
                    plane.mesh.material.opacity = 0.3 + Math.sin(this.demoTimer * 4) * 0.15;
                    plane.mesh.material.color.setHex(0xFFD700); // gold for active
                } else {
                    plane.mesh.material.opacity = 0.05;
                    plane.mesh.material.color.setHex(COLONY_COLORS.crystal);
                }
            });
            
            // Chamber wobbles during reflection
            if (this.chamber) {
                this.chamber.rotation.z = this.time * 0.15 + Math.sin(this.demoTimer * 3) * 0.1;
            }
            
            // Kernel shows equivariance: weights mirror symmetrically
            if (this.kernelGroup) {
                this.kernelGroup.rotation.y = this.time * 0.3;
                this.kernelGroup.children.forEach((cell, i) => {
                    const row = Math.floor(i / 3);
                    const col = i % 3;
                    const symmetricIdx = (2 - row) * 3 + (2 - col);
                    const baseWeight = Math.sin(this.demoTimer * 3 + symmetricIdx * 0.3) * 0.5 + 0.5;
                    cell.scale.y = 0.5 + baseWeight * 2;
                    cell.material.emissiveIntensity = 0.2 + baseWeight * 0.5;
                });
            }
        } else {
            // Normal: gentle rotation
            this.rootVectors.forEach(root => {
                root.group.rotation.y = this.time * 0.12;
            });
            
            this.reflectionPlanes.forEach((plane, i) => {
                plane.mesh.material.opacity = 0.12 + Math.sin(this.time * 1.2 + i * 0.8) * 0.06;
                plane.mesh.material.color.setHex(COLONY_COLORS.crystal);
            });
            
            if (this.chamber) {
                this.chamber.rotation.z = this.time * 0.2;
            }
            
            if (this.kernelGroup) {
                this.kernelGroup.rotation.y = this.time * 0.3;
                this.kernelGroup.children.forEach((cell, i) => {
                    const baseWeight = Math.sin(this.time * 1.5 + i * 0.3) * 0.5 + 0.5;
                    cell.scale.y = 0.5 + baseWeight * 2;
                    cell.material.emissiveIntensity = 0.1 + baseWeight * 0.2;
                });
            }
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
        this.orbits = [];
        this.reflectionPhase = 0;
        this.create();
    }
    create() {
        const color = COLONY_COLORS.crystal;
        
        // F4 has 52 dimensions: 4 Cartan generators + 48 root vectors
        // Visualize the 24 positive roots as a polytope (half of 48)
        // F4 root system projected to 3D
        const f4Roots = [];
        // 8 roots of type (±1, ±1, 0, 0) permutations — projected
        for (let i = 0; i < 4; i++) {
            for (let j = i + 1; j < 4; j++) {
                for (const s1 of [1, -1]) {
                    for (const s2 of [1, -1]) {
                        const v = [0, 0, 0, 0];
                        v[i] = s1; v[j] = s2;
                        f4Roots.push(new THREE.Vector3(v[0] + v[3] * 0.3, v[1] + v[2] * 0.3, v[2] - v[3] * 0.5));
                    }
                }
            }
        }
        // Normalize and scale to sculpture size
        const rootPoints = f4Roots.map(v => v.normalize().multiplyScalar(0.55));
        
        // Render root vertices as small glowing spheres
        const rootGeo = new THREE.SphereGeometry(0.035, 8, 8);
        rootPoints.forEach((pos, i) => {
            const hue = (i / rootPoints.length);
            const rootColor = new THREE.Color().setHSL(hue * 0.15 + 0.75, 0.7, 0.6);
            const sphere = new THREE.Mesh(rootGeo, new THREE.MeshPhysicalMaterial({
                color: rootColor, emissive: rootColor,
                emissiveIntensity: 0.3, transparent: true, opacity: 0.8
            }));
            sphere.position.copy(pos).add(new THREE.Vector3(0, 1.3, 0));
            this.add(sphere);
        });
        
        // Connect nearby roots with edges (Dynkin structure)
        const lineMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.2 });
        for (let i = 0; i < rootPoints.length; i++) {
            for (let j = i + 1; j < rootPoints.length; j++) {
                if (rootPoints[i].distanceTo(rootPoints[j]) < 0.7) {
                    const geo = new THREE.BufferGeometry().setFromPoints([
                        rootPoints[i].clone().add(new THREE.Vector3(0, 1.3, 0)),
                        rootPoints[j].clone().add(new THREE.Vector3(0, 1.3, 0))
                    ]);
                    this.add(new THREE.Line(geo, lineMat));
                }
            }
        }
        
        // 4 concentric cone shells representing the 4 simple roots
        for (let i = 0; i < 4; i++) {
            const coneGeo = new THREE.ConeGeometry(0.15 + i * 0.12, 0.15, 6 + i * 2);
            const coneMat = new THREE.MeshPhysicalMaterial({
                color, emissive: color, emissiveIntensity: 0.15,
                transparent: true, opacity: 0.25 - i * 0.04, side: THREE.DoubleSide, wireframe: true
            });
            const cone = new THREE.Mesh(coneGeo, coneMat);
            cone.position.set(0, 1.3, 0);
            this.cones.push(cone);
            this.add(cone);
        }
        
        // Orbit ring showing the Weyl group action
        const orbitGeo = new THREE.TorusGeometry(0.65, 0.01, 8, 64);
        for (let a = 0; a < 3; a++) {
            const orbit = new THREE.Mesh(orbitGeo, new THREE.MeshBasicMaterial({
                color, transparent: true, opacity: 0.2
            }));
            orbit.position.y = 1.3;
            orbit.rotation.x = a * Math.PI / 3;
            this.orbits.push(orbit);
            this.add(orbit);
        }
        
        // Labels
        const titleLabel = createEducationalLabel('F4 Exceptional Root System', { fontSize: 24, maxWidth: 380 });
        titleLabel.position.set(0, 2.1, 0);
        titleLabel.scale.set(1.5, 0.25, 1);
        this.add(titleLabel);
        
        const dimLabel = createEducationalLabel('52 dimensions · 48 roots · 1152-element Weyl group', { fontSize: 18, maxWidth: 420 });
        dimLabel.position.set(0, 0.55, 0);
        dimLabel.scale.set(1.8, 0.2, 1);
        this.add(dimLabel);
        
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
        
        // Slow rotation of root polytope
        this.cones.forEach((c, i) => {
            c.rotation.y = this.time * 0.15 + i * Math.PI / 4;
            c.rotation.x = Math.sin(this.time * 0.1 + i) * 0.3;
            c.material.emissiveIntensity = 0.15 + Math.sin(this.time * 1.5 + i) * 0.1;
        });
        this.orbits.forEach((o, i) => {
            o.rotation.y = this.time * 0.08 + i * Math.PI / 3;
        });
        
        // Weyl reflection animation — periodic reflection pulses
        this.reflectionPhase = (this.time % 12) / 12; // 12s cycle
        const reflectionActive = this.reflectionPhase > 0.7 && this.reflectionPhase < 0.9;
        
        if (reflectionActive) {
            // Pulse all root spheres with reflection effect
            this.traverse(obj => {
                if (obj.isMesh && obj.geometry?.type === 'SphereGeometry' && obj.material?.emissive) {
                    const localPhase = Math.sin(this.time * 8 + obj.position.x * 10);
                    obj.material.emissiveIntensity = 0.5 + localPhase * 0.3;
                    // Briefly mirror positions (reflection visualization)
                    const reflectAxis = Math.floor(this.time / 12) % 3;
                    if (reflectAxis === 0) obj.position.x *= 1 + localPhase * 0.01;
                    else if (reflectAxis === 1) obj.position.z *= 1 + localPhase * 0.01;
                }
            });
        }
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
        this.barrierMeshes = [];
        this.threatParticles = [];
        this.guardShield = null;
        this.cbfCurve = null;
        this.demoMode = false;
        this.demoTimer = 0;
        this.create();
    }
    create() {
        // === GUARDIAN SENTINEL (WildGuard classifier) ===
        // Tall armored figure — the content filter that classifies threats
        const guardGroup = new THREE.Group();
        guardGroup.position.set(-0.4, 0, 0);
        
        // Torso
        const torsoGeo = new THREE.CylinderGeometry(0.12, 0.16, 0.6, 8);
        const guardMat = new THREE.MeshPhysicalMaterial({
            color: 0xE85A2F, emissive: 0xE85A2F, emissiveIntensity: 0.35, metalness: 0.7, roughness: 0.3
        });
        const torso = new THREE.Mesh(torsoGeo, guardMat);
        torso.position.y = 1.3;
        guardGroup.add(torso);
        
        // Head/visor
        const headGeo = new THREE.OctahedronGeometry(0.1, 1);
        const head = new THREE.Mesh(headGeo, new THREE.MeshPhysicalMaterial({
            color: 0xFF6B3D, emissive: 0xFF6B3D, emissiveIntensity: 0.5
        }));
        head.position.y = 1.7;
        guardGroup.add(head);
        
        // Shield — a hemisphere representing the safety barrier
        const shieldGeo = new THREE.SphereGeometry(0.3, 16, 16, 0, Math.PI);
        this.guardShield = new THREE.Mesh(shieldGeo, new THREE.MeshPhysicalMaterial({
            color: 0xE85A2F, emissive: 0xE85A2F, emissiveIntensity: 0.15,
            transparent: true, opacity: 0.35, side: THREE.DoubleSide
        }));
        this.guardShield.position.set(0.15, 1.3, 0);
        this.guardShield.rotation.y = -Math.PI / 2;
        guardGroup.add(this.guardShield);
        this.add(guardGroup);
        
        // === CBF MATHEMATICIAN ===
        // Shows h(x) ≥ 0 constraint as a 3D surface
        const cbfGroup = new THREE.Group();
        cbfGroup.position.set(0.4, 0, 0);
        
        // Generate CBF surface: h(x,y) = 1 - x² - y² (barrier function)
        const gridSize = 20;
        const positions = [];
        const colors = [];
        for (let i = 0; i < gridSize; i++) {
            for (let j = 0; j < gridSize; j++) {
                const x = (i / (gridSize - 1) - 0.5) * 1.2;
                const z = (j / (gridSize - 1) - 0.5) * 1.2;
                const h = 0.5 * (1 - x * x * 4 - z * z * 4);
                positions.push(x, 1.2 + h * 0.4, z);
                
                // Green where h(x) > 0 (safe), red where h(x) < 0 (unsafe)
                const safe = h > 0;
                colors.push(safe ? 0.2 : 0.9, safe ? 0.7 : 0.15, safe ? 0.25 : 0.1);
            }
        }
        
        const cbfPointsGeo = new THREE.BufferGeometry();
        cbfPointsGeo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        cbfPointsGeo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        const cbfPoints = new THREE.Points(cbfPointsGeo, new THREE.PointsMaterial({
            size: 0.03, vertexColors: true, transparent: true, opacity: 0.85
        }));
        cbfGroup.add(cbfPoints);
        this.cbfCurve = cbfPoints;
        
        // Zero-level set ring: h(x) = 0 boundary
        const zeroRingGeo = new THREE.TorusGeometry(0.3, 0.008, 8, 48);
        const zeroRing = new THREE.Mesh(zeroRingGeo, new THREE.MeshBasicMaterial({
            color: 0xFFD700, transparent: true, opacity: 0.7
        }));
        zeroRing.rotation.x = Math.PI / 2;
        zeroRing.position.y = 1.2;
        cbfGroup.add(zeroRing);
        this.add(cbfGroup);
        
        // === PIPELINE connecting guard → CBF ===
        const pipePoints = [
            new THREE.Vector3(-0.1, 1.5, 0),
            new THREE.Vector3(0.15, 1.55, 0),
            new THREE.Vector3(0.25, 1.4, 0)
        ];
        const pipeCurve = new THREE.QuadraticBezierCurve3(...pipePoints);
        const pipeGeo = new THREE.TubeGeometry(pipeCurve, 16, 0.015, 8, false);
        this.add(new THREE.Mesh(pipeGeo, new THREE.MeshBasicMaterial({
            color: 0x67D4E4, transparent: true, opacity: 0.5
        })));
        
        // === Threat particles (red dots that get blocked) ===
        const threatGeo = new THREE.SphereGeometry(0.02, 6, 6);
        for (let i = 0; i < 8; i++) {
            const threat = new THREE.Mesh(threatGeo, new THREE.MeshBasicMaterial({
                color: 0xFF2222, transparent: true, opacity: 0.7
            }));
            threat.position.set(-0.8 - Math.random() * 0.3, 1.0 + Math.random() * 0.6, (Math.random() - 0.5) * 0.4);
            threat.userData.speed = 0.2 + Math.random() * 0.3;
            threat.userData.startX = threat.position.x;
            this.threatParticles.push(threat);
            this.add(threat);
        }
        
        // Labels
        const guardLabel = createEducationalLabel('WildGuard Classifier', { fontSize: 22, maxWidth: 280 });
        guardLabel.position.set(-0.4, 2.0, 0);
        guardLabel.scale.set(1.2, 0.2, 1);
        this.add(guardLabel);
        
        const cbfLabel = createEducationalLabel('h(x) ≥ 0 — Safety Barrier', { fontSize: 22, maxWidth: 320 });
        cbfLabel.position.set(0.4, 2.0, 0);
        cbfLabel.scale.set(1.3, 0.2, 1);
        this.add(cbfLabel);
        
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
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
    }

    update(deltaTime) {
        this.time += deltaTime;
        if (this.demoMode) this.demoTimer += deltaTime;
        
        if (this.demoMode) {
            // INTENSIFIED THREAT: more aggressive particles, shield strains
            const intensity = Math.min(this.demoTimer / 3, 1); // ramp over 3s
            
            // Shield pulses faster and strains under load
            if (this.guardShield) {
                const pulseRate = 3 + intensity * 8; // 3→11 Hz
                this.guardShield.material.opacity = 0.3 + Math.sin(this.time * pulseRate) * 0.2;
                this.guardShield.material.emissiveIntensity = 0.2 + intensity * 0.4 + Math.sin(this.time * pulseRate) * 0.15;
                // Shield flickers between orange and red under stress
                const stress = Math.sin(this.demoTimer * 6) * 0.5 + 0.5;
                this.guardShield.material.color.setRGB(0.9, 0.35 * (1 - stress * intensity), 0.1);
            }
            
            // Threats move faster and spawn closer
            this.threatParticles.forEach((t, i) => {
                const speedMult = 1 + intensity * 2; // up to 3x speed
                t.position.x += t.userData.speed * deltaTime * speedMult;
                
                if (t.position.x > -0.25) {
                    // Reset closer to shield during intensity
                    t.position.x = t.userData.startX + intensity * 0.3;
                    t.material.opacity = 1.0;
                    // Grow threat particles
                    const scale = 1 + intensity * 0.8;
                    t.scale.setScalar(scale);
                } else {
                    t.material.opacity = 0.6 + Math.sin(this.time * 6 + i) * 0.3;
                }
            });
            
            // CBF surface: h(x) value drops toward 0 under stress
            if (this.cbfCurve) {
                this.cbfCurve.rotation.y = Math.sin(this.time * 0.5) * 0.3;
                // Shift points downward to show h(x) approaching boundary
                const posAttr = this.cbfCurve.geometry.getAttribute('position');
                const gridSize = 20;
                for (let i = 0; i < gridSize; i++) {
                    for (let j = 0; j < gridSize; j++) {
                        const idx = i * gridSize + j;
                        const x = (i / (gridSize - 1) - 0.5) * 1.2;
                        const z = (j / (gridSize - 1) - 0.5) * 1.2;
                        const h = 0.5 * (1 - x * x * 4 - z * z * 4);
                        // Compress safe region as intensity rises
                        const compressed = h * (1 - intensity * 0.6);
                        posAttr.setY(idx, 1.2 + compressed * 0.4);
                    }
                }
                posAttr.needsUpdate = true;
            }
        } else {
            // Normal mode
            if (this.guardShield) {
                this.guardShield.material.opacity = 0.25 + Math.sin(this.time * 2) * 0.08;
                this.guardShield.material.emissiveIntensity = 0.15 + Math.sin(this.time * 1.5) * 0.08;
                this.guardShield.material.color.setHex(0xE85A2F);
            }
            
            this.threatParticles.forEach((t) => {
                t.position.x += t.userData.speed * deltaTime;
                t.scale.setScalar(1);
                if (t.position.x > -0.25) {
                    t.position.x = t.userData.startX;
                    t.material.opacity = 1.0;
                } else {
                    t.material.opacity = 0.5 + Math.sin(this.time * 3) * 0.15;
                }
            });
            
            if (this.cbfCurve) {
                this.cbfCurve.rotation.y = Math.sin(this.time * 0.3) * 0.15;
                // Restore original positions
                const posAttr = this.cbfCurve.geometry.getAttribute('position');
                const gridSize = 20;
                for (let i = 0; i < gridSize; i++) {
                    for (let j = 0; j < gridSize; j++) {
                        const idx = i * gridSize + j;
                        const x = (i / (gridSize - 1) - 0.5) * 1.2;
                        const z = (j / (gridSize - 1) - 0.5) * 1.2;
                        const h = 0.5 * (1 - x * x * 4 - z * z * 4);
                        posAttr.setY(idx, 1.2 + h * 0.4);
                    }
                }
                posAttr.needsUpdate = true;
            }
        }
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
        this.leftCluster = [];
        this.rightCluster = [];
        this.bridges = [];
        this.partitionPlane = null;
        this.healParticles = [];
        this.demoMode = false;
        this.demoTimer = 0;
        this.create();
    }
    create() {
        const nc = COLONY_COLORS.nexus;
        const nodeGeo = new THREE.SphereGeometry(0.08, 12, 12);
        
        // === Left cluster (3 nodes — the partition survivors) ===
        const leftPositions = [
            new THREE.Vector3(-0.5, 1.5, 0),
            new THREE.Vector3(-0.65, 1.2, 0.15),
            new THREE.Vector3(-0.4, 1.1, -0.15)
        ];
        leftPositions.forEach((pos, i) => {
            const node = new THREE.Mesh(nodeGeo, new THREE.MeshPhysicalMaterial({
                color: 0x4ECDC4, emissive: 0x4ECDC4, emissiveIntensity: 0.4
            }));
            node.position.copy(pos);
            this.leftCluster.push(node);
            this.add(node);
        });
        
        // Left internal connections
        const leftLineMat = new THREE.LineBasicMaterial({ color: 0x4ECDC4, transparent: true, opacity: 0.4 });
        for (let i = 0; i < leftPositions.length; i++) {
            for (let j = i + 1; j < leftPositions.length; j++) {
                const geo = new THREE.BufferGeometry().setFromPoints([leftPositions[i], leftPositions[j]]);
                this.add(new THREE.Line(geo, leftLineMat));
            }
        }
        
        // === Right cluster (3 nodes — the isolated partition) ===
        const rightPositions = [
            new THREE.Vector3(0.5, 1.5, 0),
            new THREE.Vector3(0.65, 1.2, -0.15),
            new THREE.Vector3(0.4, 1.1, 0.15)
        ];
        rightPositions.forEach((pos) => {
            const node = new THREE.Mesh(nodeGeo, new THREE.MeshPhysicalMaterial({
                color: 0xE8940A, emissive: 0xE8940A, emissiveIntensity: 0.4
            }));
            node.position.copy(pos);
            this.rightCluster.push(node);
            this.add(node);
        });
        
        // Right internal connections
        const rightLineMat = new THREE.LineBasicMaterial({ color: 0xE8940A, transparent: true, opacity: 0.4 });
        for (let i = 0; i < rightPositions.length; i++) {
            for (let j = i + 1; j < rightPositions.length; j++) {
                const geo = new THREE.BufferGeometry().setFromPoints([rightPositions[i], rightPositions[j]]);
                this.add(new THREE.Line(geo, rightLineMat));
            }
        }
        
        // === Partition plane — a translucent vertical divider ===
        const planeGeo = new THREE.PlaneGeometry(0.02, 0.8);
        this.partitionPlane = new THREE.Mesh(planeGeo, new THREE.MeshBasicMaterial({
            color: 0xFF4444, transparent: true, opacity: 0.4, side: THREE.DoubleSide
        }));
        this.partitionPlane.position.set(0, 1.3, 0);
        this.add(this.partitionPlane);
        
        // Partition line visual (jagged)
        const partPoints = [];
        for (let y = 0.8; y <= 1.8; y += 0.05) {
            partPoints.push(new THREE.Vector3(Math.sin(y * 20) * 0.03, y, 0));
        }
        const partGeo = new THREE.BufferGeometry().setFromPoints(partPoints);
        this.add(new THREE.Line(partGeo, new THREE.LineBasicMaterial({
            color: 0xFF4444, transparent: true, opacity: 0.6
        })));
        
        // === Bridge connections (cross-partition) — these heal/break ===
        for (let i = 0; i < 3; i++) {
            const bridgeGeo = new THREE.BufferGeometry().setFromPoints([
                leftPositions[i], rightPositions[i]
            ]);
            const bridge = new THREE.Line(bridgeGeo, new THREE.LineBasicMaterial({
                color: nc, transparent: true, opacity: 0.0 // starts broken
            }));
            this.bridges.push(bridge);
            this.add(bridge);
        }
        
        // === Heal particles (green, travel across partition when reconverging) ===
        const healGeo = new THREE.SphereGeometry(0.015, 4, 4);
        for (let i = 0; i < 4; i++) {
            const hp = new THREE.Mesh(healGeo, new THREE.MeshBasicMaterial({
                color: 0x4CFF4C, transparent: true, opacity: 0
            }));
            hp.position.set(-0.3, 1.3, 0);
            hp.userData.progress = -1; // inactive
            this.healParticles.push(hp);
            this.add(hp);
        }
        
        // Labels
        const titleLabel = createEducationalLabel('CALM: Partition Tolerance', { fontSize: 22, maxWidth: 360 });
        titleLabel.position.set(0, 2.0, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        const leftLabel = createEducationalLabel('Partition A', { fontSize: 18, maxWidth: 180 });
        leftLabel.position.set(-0.5, 0.75, 0);
        leftLabel.scale.set(0.7, 0.14, 1);
        this.add(leftLabel);
        
        const rightLabel = createEducationalLabel('Partition B', { fontSize: 18, maxWidth: 180 });
        rightLabel.position.set(0.5, 0.75, 0);
        rightLabel.scale.set(0.7, 0.14, 1);
        this.add(rightLabel);
        
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
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
    }

    update(deltaTime) {
        this.time += deltaTime;
        if (this.demoMode) this.demoTimer += deltaTime;
        
        if (this.demoMode) {
            // INTERACTIVE PARTITION DEMO:
            // Phase 1 (0-3s): partition plane shifts, message queue builds up
            // Phase 2 (3-5s): queue overwhelms, nodes flash warnings
            // Phase 3 (5-8s): healing cascade — bridges reconnect, queue drains
            const cycleDuration = 8;
            const cycleTime = this.demoTimer % cycleDuration;
            
            const isBuildup = cycleTime < 3;
            const isOverwhelm = cycleTime >= 3 && cycleTime < 5;
            const isHealing = cycleTime >= 5;
            
            // Partition plane shifts and widens during buildup
            if (this.partitionPlane) {
                if (isBuildup) {
                    const shift = Math.sin(this.demoTimer * 2) * 0.1;
                    this.partitionPlane.position.x = shift;
                    this.partitionPlane.material.opacity = 0.5 + Math.sin(this.demoTimer * 5) * 0.15;
                    this.partitionPlane.scale.x = 1 + cycleTime * 0.5; // widens
                } else if (isOverwhelm) {
                    // Partition flashes urgently
                    this.partitionPlane.material.opacity = 0.6 + Math.sin(this.demoTimer * 12) * 0.3;
                    this.partitionPlane.material.color.setHex(0xFF0000);
                } else {
                    // Healing: partition fades and shrinks
                    const healT = (cycleTime - 5) / 3;
                    this.partitionPlane.material.opacity = 0.6 * (1 - healT);
                    this.partitionPlane.scale.x = Math.max(0.1, (1 - healT) * 2);
                    this.partitionPlane.position.x = 0;
                    this.partitionPlane.material.color.setHex(healT > 0.5 ? 0x44FF44 : 0xFF4444);
                }
            }
            
            // Left cluster: isolated, increasing stress
            this.leftCluster.forEach((n, i) => {
                if (isBuildup || isOverwhelm) {
                    // Nodes jitter and pulse fast (message queue pressure)
                    const jitter = isOverwhelm ? 0.02 : 0.005;
                    n.position.x += (Math.random() - 0.5) * jitter;
                    n.material.emissiveIntensity = isOverwhelm 
                        ? 0.6 + Math.sin(this.demoTimer * 10 + i) * 0.3
                        : 0.4 + Math.sin(this.demoTimer * 4 + i) * 0.15;
                } else {
                    // Healing: calm down
                    n.material.emissiveIntensity = 0.6;
                }
            });
            
            this.rightCluster.forEach((n, i) => {
                if (isBuildup || isOverwhelm) {
                    const jitter = isOverwhelm ? 0.02 : 0.005;
                    n.position.x += (Math.random() - 0.5) * jitter;
                    n.material.emissiveIntensity = isOverwhelm
                        ? 0.6 + Math.sin(this.demoTimer * 10 + i + 3) * 0.3
                        : 0.4 + Math.sin(this.demoTimer * 4 + i + 2) * 0.15;
                } else {
                    n.material.emissiveIntensity = 0.6;
                }
            });
            
            // Bridges: reconnect during healing phase
            this.bridges.forEach((b, i) => {
                if (isHealing) {
                    const healT = (cycleTime - 5) / 3;
                    const bridgeDelay = i * 0.3;
                    b.material.opacity = Math.max(0, Math.min(0.6, (healT - bridgeDelay) * 2));
                    b.material.color.setHex(0x4CFF4C); // green bridges
                } else {
                    b.material.opacity = 0;
                    b.material.color.setHex(COLONY_COLORS.nexus);
                }
            });
            
            // Heal particles: burst during healing
            if (isHealing) {
                this.healParticles.forEach((hp, i) => {
                    const healT = cycleTime - 5;
                    if (hp.userData.progress < 0 && healT > i * 0.4) {
                        hp.userData.progress = 0;
                    }
                    if (hp.userData.progress >= 0) {
                        hp.userData.progress += deltaTime * 0.8; // faster healing
                        const t = hp.userData.progress;
                        hp.position.x = -0.3 + t * 0.6;
                        hp.material.opacity = t < 0.1 ? t * 10 : (t > 0.9 ? (1 - t) * 10 : 0.9);
                        if (t > 1) hp.userData.progress = -1;
                    }
                });
            } else {
                this.healParticles.forEach(hp => {
                    hp.userData.progress = -1;
                    hp.material.opacity = 0;
                });
            }
        } else {
            // Normal mode: 6-second partition/heal cycle
            const cycle = this.time % 6;
            const partitioned = cycle < 3;
            
            this.leftCluster.forEach((n, i) => {
                n.material.emissiveIntensity = partitioned ? 0.3 + Math.sin(this.time * 2 + i) * 0.1 : 0.5;
            });
            this.rightCluster.forEach((n, i) => {
                n.material.emissiveIntensity = partitioned ? 0.3 + Math.sin(this.time * 2 + i + 2) * 0.1 : 0.5;
            });
            
            if (this.partitionPlane) {
                this.partitionPlane.position.x = 0;
                this.partitionPlane.scale.x = 1;
                this.partitionPlane.material.color.setHex(0xFF4444);
                this.partitionPlane.material.opacity = partitioned ? 0.4 + Math.sin(this.time * 3) * 0.08 : Math.max(0, (3 - (cycle - 3)) / 3 * 0.3);
            }
            
            this.bridges.forEach((b) => {
                b.material.opacity = partitioned ? 0 : Math.min(1, (cycle - 3) / 2) * 0.5;
                b.material.color.setHex(COLONY_COLORS.nexus);
            });
            
            if (!partitioned) {
                this.healParticles.forEach((hp, i) => {
                    if (hp.userData.progress < 0 && (cycle - 3) > i * 0.3) {
                        hp.userData.progress = 0;
                    }
                    if (hp.userData.progress >= 0) {
                        hp.userData.progress += deltaTime * 0.5;
                        const t = hp.userData.progress;
                        hp.position.x = -0.3 + t * 0.6;
                        hp.material.opacity = t < 0.1 ? t * 10 : (t > 0.9 ? (1 - t) * 10 : 0.7);
                        if (t > 1) hp.userData.progress = -1;
                    }
                });
            } else {
                this.healParticles.forEach(hp => {
                    hp.userData.progress = -1;
                    hp.material.opacity = 0;
                });
            }
        }
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
        this.activePhase = 0;
        this.create();
    }
    create() {
        const color = COLONY_COLORS.grove;
        const phaseNames = [
            'Perception', 'Motor', 'Language', 'Reasoning',
            'Planning', 'Social', 'Safety', 'Memory',
            'Creativity', 'Transfer', 'Multi-Agent', 'Meta-Learning',
            'Curriculum', 'Mastery'
        ];
        
        // Create 14-phase spiral staircase
        for (let i = 0; i < 14; i++) {
            const angle = (i / 14) * Math.PI * 3; // 1.5 full rotations
            const radius = 0.4 + i * 0.03;
            const height = 0.3 + i * 0.1;
            
            const stepGeo = new THREE.BoxGeometry(0.2, 0.08, 0.35);
            const brightness = i / 14;
            const stepColor = new THREE.Color(color).lerp(new THREE.Color(0xffffff), brightness * 0.3);
            const step = new THREE.Mesh(stepGeo, new THREE.MeshPhysicalMaterial({
                color: stepColor,
                emissive: stepColor,
                emissiveIntensity: 0.15 + brightness * 0.2,
                metalness: 0.3,
                roughness: 0.5
            }));
            step.position.set(
                Math.cos(angle) * radius,
                height,
                Math.sin(angle) * radius
            );
            step.rotation.y = -angle + Math.PI / 2;
            step.userData.phaseName = phaseNames[i];
            this.steps.push(step);
            this.add(step);
            
            // Phase number label
            const label = createEducationalLabel(`${i + 1}. ${phaseNames[i]}`, { fontSize: 22, maxWidth: 256 });
            label.position.copy(step.position);
            label.position.y += 0.15;
            label.visible = true; // Always visible with alpha fade
            label.userData.isLabel = true;
            step.userData.label = label;
            this.add(label);
        }
        
        // Central axis
        const axisGeo = new THREE.CylinderGeometry(0.02, 0.02, 1.8, 8);
        const axis = new THREE.Mesh(axisGeo, new THREE.MeshPhysicalMaterial({
            color: COLONY_COLORS.grove, emissive: COLONY_COLORS.grove, emissiveIntensity: 0.3, transparent: true, opacity: 0.5
        }));
        axis.position.y = 1.1;
        this.add(axis);
        
        // Progress indicator (glowing sphere climbs the staircase)
        const indicatorGeo = new THREE.SphereGeometry(0.06, 16, 16);
        this.indicator = new THREE.Mesh(indicatorGeo, new THREE.MeshPhysicalMaterial({
            color: 0xffffff, emissive: COLONY_COLORS.grove, emissiveIntensity: 0.8
        }));
        this.add(this.indicator);
        
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
        
        // Animate active phase cycling (5-second per phase)
        this.activePhase = Math.floor(this.time / 5) % 14;
        
        this.steps.forEach((s, i) => {
            const isActive = i === this.activePhase;
            const isPast = i < this.activePhase;
            s.material.emissiveIntensity = isActive ? 0.7 : isPast ? 0.35 : 0.12;
            s.scale.y = isActive ? 1.5 : 1;
            
            // Labels always visible with alpha fade based on active state
            if (s.userData.label) {
                s.userData.label.visible = true;
                if (s.userData.label.material) {
                    s.userData.label.material.opacity = isActive ? 1.0 : isPast ? 0.5 : 0.25;
                }
            }
        });
        
        // Move indicator along the staircase
        if (this.indicator && this.steps[this.activePhase]) {
            const target = this.steps[this.activePhase].position;
            this.indicator.position.lerp(target, 0.05);
            this.indicator.position.y = target.y + 0.12;
            this.indicator.material.emissiveIntensity = 0.6 + Math.sin(this.time * 4) * 0.3;
        }
        
        // Graduation ceremony at phase 14 completion
        if (this.activePhase === 13) {
            this.steps.forEach(s => {
                s.material.emissiveIntensity = 0.5 + Math.sin(this.time * 3) * 0.2;
            });
            if (this.indicator) {
                this.indicator.scale.setScalar(1 + Math.sin(this.time * 5) * 0.3);
            }
        }
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
        this.searchParticles = [];
        this.searchPhase = 0;
        this.create();
    }
    create() {
        const methods = [
            { name: 'MCTS', color: 0x9B7EBD, offset: -0.5 },
            { name: 'CFR', color: 0x4ECDC4, offset: 0 },
            { name: 'EFE', color: 0xE8940A, offset: 0.5 }
        ];
        
        const nodeGeo = new THREE.SphereGeometry(0.06, 12, 12);
        
        methods.forEach((method, t) => {
            const rootMat = new THREE.MeshPhysicalMaterial({
                color: method.color, emissive: method.color, emissiveIntensity: 0.5
            });
            const root = new THREE.Mesh(new THREE.SphereGeometry(0.1, 16, 16), rootMat);
            root.position.set(method.offset, 1.7, 0);
            this.trees.push(root);
            this.add(root);
            
            // Label
            const label = createEducationalLabel(method.name, { fontSize: 28, maxWidth: 192 });
            label.position.set(method.offset, 1.95, 0);
            label.scale.set(0.8, 0.2, 1);
            this.add(label);
            
            // Build 3-level tree (branching factor 3)
            const levels = [
                [root.position.clone()]
            ];
            for (let depth = 0; depth < 3; depth++) {
                const parentLevel = levels[depth];
                const childLevel = [];
                parentLevel.forEach((parentPos, pi) => {
                    const branches = depth === 0 ? 3 : 2;
                    for (let b = 0; b < branches; b++) {
                        const angle = ((b - (branches - 1) / 2) / branches) * 1.2 + t * 0.3;
                        const childPos = new THREE.Vector3(
                            parentPos.x + Math.sin(angle) * (0.25 - depth * 0.05),
                            parentPos.y - 0.25,
                            parentPos.z + Math.cos(angle) * 0.1
                        );
                        childLevel.push(childPos);
                        
                        const node = new THREE.Mesh(nodeGeo, new THREE.MeshPhysicalMaterial({
                            color: method.color, emissive: method.color,
                            emissiveIntensity: 0.15, transparent: true, opacity: 0.7 - depth * 0.15
                        }));
                        node.position.copy(childPos);
                        this.add(node);
                        
                        // Edge
                        const edgeGeo = new THREE.BufferGeometry().setFromPoints([parentPos, childPos]);
                        this.add(new THREE.Line(edgeGeo, new THREE.LineBasicMaterial({
                            color: method.color, transparent: true, opacity: 0.3
                        })));
                    }
                });
                levels.push(childLevel);
            }
        });
        
        // Merge zone label (where trees intersect)
        const mergeLabel = createEducationalLabel('Unified Search: MCTS × CFR × EFE', { fontSize: 22, maxWidth: 420 });
        mergeLabel.position.set(0, 0.5, 0);
        mergeLabel.scale.set(2, 0.3, 1);
        this.add(mergeLabel);
        
        // Search particle
        const spGeo = new THREE.SphereGeometry(0.04, 8, 8);
        this.searchParticle = new THREE.Mesh(spGeo, new THREE.MeshBasicMaterial({
            color: 0xFFFFFF, transparent: true, opacity: 0.8
        }));
        this.searchParticle.position.set(0, 1.7, 0);
        this.add(this.searchParticle);
        
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
        
        // Cycle: 0=MCTS(2s), 1=CFR(2s), 2=EFE(2s), 3=unify(2s) → 8s total
        this.searchPhase = Math.floor((this.time % 8) / 2);
        const phaseProgress = ((this.time % 8) / 2) - this.searchPhase; // 0→1 within each 2s phase
        
        const methodColors = [0x9B7EBD, 0x4ECDC4, 0xE8940A];
        
        this.trees.forEach((r, i) => {
            const isActiveMethod = (this.searchPhase < 3 && i === this.searchPhase);
            const isUnify = this.searchPhase === 3;
            
            // Root glow — active method glows brighter
            r.material.emissiveIntensity = isActiveMethod ? 0.8 + Math.sin(this.time * 6) * 0.15
                                         : isUnify ? 0.6 + Math.sin(this.time * 4 + i) * 0.1
                                         : 0.25;
            r.scale.setScalar(isActiveMethod ? 1.15 + Math.sin(this.time * 5) * 0.05 : 1);
        });
        
        // Glow tree edges for active method
        let childIdx = 0;
        this.traverse(obj => {
            if (obj.isLine && obj.material && !obj.userData?.isPedestal) {
                const lineColor = obj.material.color;
                const matchesMCTS = lineColor && Math.abs(lineColor.r - 0.608) < 0.1;
                const matchesCFR = lineColor && Math.abs(lineColor.g - 0.804) < 0.1 && lineColor.r < 0.4;
                const matchesEFE = lineColor && lineColor.r > 0.8 && lineColor.g < 0.6;
                
                let isActiveLine = false;
                if (this.searchPhase === 0 && matchesMCTS) isActiveLine = true;
                if (this.searchPhase === 1 && matchesCFR) isActiveLine = true;
                if (this.searchPhase === 2 && matchesEFE) isActiveLine = true;
                if (this.searchPhase === 3) isActiveLine = true;
                
                obj.material.opacity = isActiveLine ? 0.6 + Math.sin(this.time * 3 + childIdx) * 0.2 : 0.15;
                childIdx++;
            }
        });
        
        // During unification, find deepest leaves and color them gold
        if (this.searchPhase === 3) {
            let leafCount = 0;
            this.traverse(obj => {
                if (obj.isMesh && obj.geometry?.type === 'SphereGeometry' && obj !== this.searchParticle) {
                    // Deepest nodes are lowest y
                    if (obj.position.y < 0.9 && obj.position.y > 0.5) {
                        const goldPulse = 0.4 + Math.sin(this.time * 5 + leafCount) * 0.3;
                        obj.material.emissive.setHex(0xFFD700);
                        obj.material.emissiveIntensity = goldPulse;
                        leafCount++;
                    }
                }
            });
        } else {
            // Reset deep leaf colors to their tree color during non-unify phases
            this.traverse(obj => {
                if (obj.isMesh && obj.geometry?.type === 'SphereGeometry' && obj !== this.searchParticle
                    && obj.position.y < 0.9 && obj.position.y > 0.5) {
                    obj.material.emissive.copy(obj.material.color);
                    obj.material.emissiveIntensity = 0.15;
                }
            });
        }
        
        // Animate search particle descending through active tree
        if (this.searchParticle && this.searchPhase < 3) {
            const activeRoot = this.trees[this.searchPhase];
            const startY = activeRoot.position.y;
            const endY = startY - 0.75;
            const particleY = startY - phaseProgress * (startY - endY);
            const sway = Math.sin(phaseProgress * Math.PI * 3) * 0.15;
            this.searchParticle.position.set(activeRoot.position.x + sway, particleY, 0.05);
            this.searchParticle.material.color.setHex(methodColors[this.searchPhase]);
            this.searchParticle.material.opacity = 0.9;
            this.searchParticle.visible = true;
        } else if (this.searchParticle) {
            // Unify phase — particle orbits at merge zone
            const orbitAngle = this.time * 4;
            this.searchParticle.position.set(Math.cos(orbitAngle) * 0.2, 0.7, Math.sin(orbitAngle) * 0.2);
            this.searchParticle.material.color.setHex(0xFFD700);
            this.searchParticle.material.opacity = 0.6 + Math.sin(this.time * 8) * 0.3;
            this.searchParticle.visible = true;
        }
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
        this.waveform = null;
        this.freqBands = [];
        this.windowType = 0;
        this.create();
    }
    create() {
        const color = COLONY_COLORS.flow;
        
        // === Circular spectrum analyzer (32 bars in a ring) ===
        const numBars = 32;
        for (let i = 0; i < numBars; i++) {
            const angle = (i / numBars) * Math.PI * 2;
            const barGeo = new THREE.BoxGeometry(0.04, 0.3, 0.04);
            const hue = i / numBars;
            const barColor = new THREE.Color().setHSL(hue * 0.3 + 0.5, 0.8, 0.55);
            const bar = new THREE.Mesh(barGeo, new THREE.MeshPhysicalMaterial({
                color: barColor, emissive: barColor, emissiveIntensity: 0.3
            }));
            const radius = 0.55;
            bar.position.set(Math.cos(angle) * radius, 1.3, Math.sin(angle) * radius);
            bar.lookAt(new THREE.Vector3(0, 1.3, 0));
            bar.userData.angle = angle;
            bar.userData.baseRadius = radius;
            this.bars.push(bar);
            this.add(bar);
        }
        
        // === Central waveform oscilloscope ===
        const wavePoints = [];
        for (let i = 0; i < 64; i++) {
            const t = (i / 63 - 0.5) * 1.4;
            wavePoints.push(new THREE.Vector3(t, 1.3, 0));
        }
        const waveGeo = new THREE.BufferGeometry().setFromPoints(wavePoints);
        this.waveform = new THREE.Line(waveGeo, new THREE.LineBasicMaterial({
            color, transparent: true, opacity: 0.6
        }));
        this.add(this.waveform);
        
        // === Frequency band labels ===
        const bands = ['Bass', 'Mid', 'Treble', 'Ultra'];
        bands.forEach((band, i) => {
            const angle = (i / bands.length) * Math.PI * 2 - Math.PI / 4;
            const label = createEducationalLabel(band, { fontSize: 20, maxWidth: 128 });
            label.position.set(Math.cos(angle) * 0.85, 1.3, Math.sin(angle) * 0.85);
            label.scale.set(0.5, 0.12, 1);
            this.freqBands.push(label);
            this.add(label);
        });
        
        // Central hub
        const hubGeo = new THREE.SphereGeometry(0.08, 16, 16);
        const hub = new THREE.Mesh(hubGeo, new THREE.MeshPhysicalMaterial({
            color, emissive: color, emissiveIntensity: 0.5
        }));
        hub.position.y = 1.3;
        this.add(hub);
        
        // === Time→Frequency transformation panel ===
        this.fftCanvas = document.createElement('canvas');
        this.fftCanvas.width = 512;
        this.fftCanvas.height = 256;
        this.fftTexture = new THREE.CanvasTexture(this.fftCanvas);
        const fftPlane = new THREE.Mesh(
            new THREE.PlaneGeometry(1.8, 0.9),
            new THREE.MeshBasicMaterial({ map: this.fftTexture, transparent: true, side: THREE.DoubleSide })
        );
        fftPlane.position.set(0, 0.6, 0.5);
        fftPlane.rotation.x = -0.3;
        this.add(fftPlane);
        
        this.windowType = 0; // 0=Rectangular, 1=Hann, 2=Hamming
        this.windowNames = ['Rectangular', 'Hann', 'Hamming'];
        
        // Title
        const title = createEducationalLabel('Spectrum Analysis Engine', { fontSize: 22, maxWidth: 360 });
        title.position.set(0, 2.0, 0);
        title.scale.set(1.5, 0.22, 1);
        this.add(title);
        
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
        
        // Animate spectrum bars — simulate FFT output with layered sine waves
        this.bars.forEach((b, i) => {
            const freq1 = Math.sin(this.time * 3 + i * 0.3) * 0.5;
            const freq2 = Math.sin(this.time * 5.7 + i * 0.7) * 0.3;
            const freq3 = Math.sin(this.time * 1.3 + i * 1.1) * 0.2;
            const h = 0.15 + Math.abs(freq1 + freq2 + freq3);
            b.scale.y = h * 3;
            b.material.emissiveIntensity = 0.2 + h * 0.5;
        });
        
        // Animate waveform
        if (this.waveform) {
            const pos = this.waveform.geometry.attributes.position;
            for (let i = 0; i < pos.count; i++) {
                const x = pos.getX(i);
                const wave = Math.sin(x * 8 + this.time * 4) * 0.08
                           + Math.sin(x * 12 - this.time * 6) * 0.04;
                pos.setY(i, 1.3 + wave);
            }
            pos.needsUpdate = true;
        }
        
        // Update FFT transformation display
        if (this.fftCanvas && Math.floor(this.time * 4) % 2 === 0) {
            const fctx = this.fftCanvas.getContext('2d');
            const w = 512, h = 256;
            fctx.fillStyle = 'rgba(10, 10, 15, 0.95)';
            fctx.fillRect(0, 0, w, h);
            
            // Time domain (top half)
            fctx.strokeStyle = '#4ECDC4';
            fctx.lineWidth = 2;
            fctx.beginPath();
            for (let i = 0; i < w; i++) {
                const x = i / w * 8 * Math.PI;
                const windowFn = this.windowType === 1 ? 0.5 * (1 - Math.cos(2 * Math.PI * i / w)) :
                                 this.windowType === 2 ? 0.54 - 0.46 * Math.cos(2 * Math.PI * i / w) : 1;
                const y = (Math.sin(x + this.time * 4) * 0.3 + Math.sin(x * 3 + this.time * 6) * 0.15) * windowFn;
                const py = 60 - y * 80;
                if (i === 0) fctx.moveTo(i, py); else fctx.lineTo(i, py);
            }
            fctx.stroke();
            
            fctx.fillStyle = '#4ECDC4';
            fctx.font = '14px "IBM Plex Mono", monospace';
            fctx.fillText('Time Domain', 10, 15);
            fctx.fillText('Window: ' + this.windowNames[this.windowType], 350, 15);
            
            // Arrow
            fctx.fillStyle = '#9E9994';
            fctx.font = '20px "IBM Plex Mono", monospace';
            fctx.textAlign = 'center';
            fctx.fillText('FFT →', w / 2, h / 2 + 5);
            fctx.textAlign = 'left';
            
            // Frequency domain (bottom half)
            fctx.strokeStyle = '#F59E0B';
            fctx.fillStyle = '#F59E0B';
            const numBins = 32;
            const barW = (w - 20) / numBins;
            for (let i = 0; i < numBins; i++) {
                const mag = Math.abs(Math.sin(this.time * 3 + i * 0.3)) * 0.5 + 
                           Math.abs(Math.sin(this.time * 5.7 + i * 0.7)) * 0.3;
                const barH = mag * 80;
                fctx.fillRect(10 + i * barW, h - 20 - barH, barW - 2, barH);
            }
            fctx.fillStyle = '#F59E0B';
            fctx.font = '14px "IBM Plex Mono", monospace';
            fctx.fillText('Frequency Domain', 10, h - 5);
            
            this.fftTexture.needsUpdate = true;
        }
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
        this.agentCore = null;
        this.bidArrows = [];
        this.marketNodes = [];
        this.profitTrail = [];
        this.demoMode = false;
        this.demoTimer = 0;
        this.create();
    }
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
    }
    create() {
        const bc = COLONY_COLORS.beacon;
        
        // === Central autonomous agent — faceted diamond ===
        const agentGeo = new THREE.OctahedronGeometry(0.2, 1);
        this.agentCore = new THREE.Mesh(agentGeo, new THREE.MeshPhysicalMaterial({
            color: bc, emissive: bc, emissiveIntensity: 0.6, metalness: 0.8, roughness: 0.15
        }));
        this.agentCore.position.y = 1.5;
        this.add(this.agentCore);
        
        // Agent "eye" — inner glow
        const eyeGeo = new THREE.SphereGeometry(0.06, 12, 12);
        const eye = new THREE.Mesh(eyeGeo, new THREE.MeshBasicMaterial({ color: 0xFFFFFF }));
        eye.position.y = 1.5;
        this.add(eye);
        
        // === Marketplace ring — 8 client nodes arranged in a circle ===
        const marketRadius = 0.7;
        const clientColors = [0x4ECDC4, 0x9B7EBD, 0xE8940A, 0x6FA370, 0xE85A2F, 0x67D4E4, 0xFFD700, 0xFF6B8A];
        for (let i = 0; i < 8; i++) {
            const angle = (i / 8) * Math.PI * 2;
            const clientGeo = new THREE.BoxGeometry(0.1, 0.1, 0.1);
            const client = new THREE.Mesh(clientGeo, new THREE.MeshPhysicalMaterial({
                color: clientColors[i], emissive: clientColors[i], emissiveIntensity: 0.2
            }));
            client.position.set(
                Math.cos(angle) * marketRadius,
                0.9 + Math.sin(angle * 2) * 0.1,
                Math.sin(angle) * marketRadius
            );
            client.userData.angle = angle;
            this.marketNodes.push(client);
            this.add(client);
            
            // Bid line from agent to client
            const lineGeo = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(0, 1.5, 0),
                client.position.clone()
            ]);
            const line = new THREE.Line(lineGeo, new THREE.LineBasicMaterial({
                color: clientColors[i], transparent: true, opacity: 0.15
            }));
            line.userData.targetIdx = i;
            this.bidArrows.push(line);
            this.add(line);
        }
        
        // Market floor ring
        const ringGeo = new THREE.TorusGeometry(marketRadius, 0.01, 8, 48);
        const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({
            color: bc, transparent: true, opacity: 0.25
        }));
        ring.rotation.x = Math.PI / 2;
        ring.position.y = 0.9;
        this.add(ring);
        
        // === Profit trail (rising particles) ===
        const trailGeo = new THREE.SphereGeometry(0.015, 6, 6);
        for (let i = 0; i < 12; i++) {
            const p = new THREE.Mesh(trailGeo, new THREE.MeshBasicMaterial({
                color: 0x4CFF4C, transparent: true, opacity: 0.5
            }));
            p.position.set((Math.random() - 0.5) * 0.3, 1.6 + Math.random() * 0.5, (Math.random() - 0.5) * 0.3);
            p.userData.baseY = p.position.y;
            p.userData.speed = 0.1 + Math.random() * 0.2;
            this.profitTrail.push(p);
            this.add(p);
        }
        
        // Labels
        const titleLabel = createEducationalLabel('Autonomous Economic Agent', { fontSize: 22, maxWidth: 380 });
        titleLabel.position.set(0, 2.1, 0);
        titleLabel.scale.set(1.6, 0.22, 1);
        this.add(titleLabel);
        
        const mechLabel = createEducationalLabel('EFE-Guided Bidding · Multi-Market · Profit Optimization', { fontSize: 16, maxWidth: 420 });
        mechLabel.position.set(0, 0.5, 0);
        mechLabel.scale.set(2, 0.18, 1);
        this.add(mechLabel);
        
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
        if (this.demoMode) this.demoTimer += deltaTime;
        
        // Demo: highlight one market node, show bid→outcome, profit trail rises
        const demoTarget = this.demoMode ? Math.floor(this.demoTimer / 2) % 8 : -1;
        const demoCyclePhase = this.demoMode ? (this.demoTimer % 2) / 2 : 0; // 0→1 over 2s per node
        
        // Agent rotates and pulses
        if (this.agentCore) {
            this.agentCore.rotation.y += deltaTime * (this.demoMode ? 1.5 : 0.8);
            this.agentCore.rotation.x = Math.sin(this.time * 0.5) * 0.2;
            if (this.demoMode && demoCyclePhase > 0.8) {
                // Flash on "outcome" phase
                this.agentCore.material.emissiveIntensity = 0.8 + Math.sin(this.time * 10) * 0.2;
            } else {
                this.agentCore.material.emissiveIntensity = 0.5 + Math.sin(this.time * 2) * 0.2;
            }
        }
        
        // Animate bid lines
        const activeBid = this.demoMode ? demoTarget : Math.floor(this.time * 1.5) % 8;
        this.bidArrows.forEach((line, i) => {
            if (this.demoMode && i === demoTarget) {
                // Demo: bid line pulses brightly during approach, flashes on outcome
                line.material.opacity = demoCyclePhase < 0.6 ? 0.3 + demoCyclePhase * 0.5 : 0.8;
            } else {
                line.material.opacity = i === activeBid ? 0.6 : 0.1;
            }
        });
        this.marketNodes.forEach((node, i) => {
            if (this.demoMode && i === demoTarget) {
                // Targeted node glows, scales up on outcome
                node.material.emissiveIntensity = 0.4 + demoCyclePhase * 0.6;
                node.scale.setScalar(1.0 + demoCyclePhase * 0.5);
            } else {
                node.material.emissiveIntensity = i === activeBid ? 0.7 : 0.15;
                node.scale.setScalar(i === activeBid ? 1.3 : 1.0);
            }
        });
        
        // Profit particles rise and reset — in demo, surge upward on outcome phase
        const profitSpeed = this.demoMode && demoCyclePhase > 0.7 ? 3.0 : 1.0;
        this.profitTrail.forEach(p => {
            p.position.y += p.userData.speed * deltaTime * profitSpeed;
            if (p.position.y > 2.2) {
                p.position.y = p.userData.baseY;
            }
            if (this.demoMode && demoCyclePhase > 0.7) {
                p.material.opacity = 0.7;
                p.material.color.setHex(0x4CFF4C);
            } else {
                p.material.opacity = 0.3 + Math.sin(this.time * 3 + p.position.x * 10) * 0.2;
            }
        });
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
        this.hub = null;
        this.messageParticles = [];
        this.ringLayers = [];
        this.demoMode = false;
        this.demoTimer = 0;
        this.create();
    }
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
    }
    create() {
        const color = COLONY_COLORS.forge;
        
        // === Central E8 hub — icosahedron (closest regular solid to the E8 projection) ===
        const hubGeo = new THREE.IcosahedronGeometry(0.18, 1);
        this.hub = new THREE.Mesh(hubGeo, new THREE.MeshPhysicalMaterial({
            color, emissive: color, emissiveIntensity: 0.6, metalness: 0.6, roughness: 0.2
        }));
        this.hub.position.y = 1.35;
        this.add(this.hub);
        
        // Wireframe overlay
        const wireHub = new THREE.Mesh(
            new THREE.IcosahedronGeometry(0.2, 1),
            new THREE.MeshBasicMaterial({ color, wireframe: true, transparent: true, opacity: 0.3 })
        );
        wireHub.position.y = 1.35;
        this.add(wireHub);
        
        // === 248-channel representation ===
        // Show 3 concentric rings of channels (8 + 16 + 24 = 48, representing the layered routing)
        const layerSizes = [8, 16, 24];
        const layerRadii = [0.35, 0.55, 0.75];
        const layerColors = [0xE8940A, 0x9B7EBD, 0x4ECDC4];
        
        layerSizes.forEach((count, layer) => {
            const ringGeo = new THREE.TorusGeometry(layerRadii[layer], 0.005, 8, 64);
            const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({
                color: layerColors[layer], transparent: true, opacity: 0.2
            }));
            ring.rotation.x = Math.PI / 2;
            ring.position.y = 1.35;
            this.ringLayers.push(ring);
            this.add(ring);
            
            for (let i = 0; i < count; i++) {
                const angle = (i / count) * Math.PI * 2;
                const nodeGeo = new THREE.SphereGeometry(0.02, 6, 6);
                const node = new THREE.Mesh(nodeGeo, new THREE.MeshPhysicalMaterial({
                    color: layerColors[layer], emissive: layerColors[layer], emissiveIntensity: 0.3
                }));
                node.position.set(
                    Math.cos(angle) * layerRadii[layer],
                    1.35,
                    Math.sin(angle) * layerRadii[layer]
                );
                node.userData.angle = angle;
                node.userData.layer = layer;
                this.channels.push(node);
                this.add(node);
            }
        });
        
        // === Message particles — travel from hub to nodes ===
        const particleGeo = new THREE.SphereGeometry(0.015, 4, 4);
        for (let i = 0; i < 6; i++) {
            const p = new THREE.Mesh(particleGeo, new THREE.MeshBasicMaterial({
                color: 0xFFFFFF, transparent: true, opacity: 0.8
            }));
            p.position.set(0, 1.35, 0);
            p.userData.targetAngle = Math.random() * Math.PI * 2;
            p.userData.targetRadius = layerRadii[Math.floor(Math.random() * 3)];
            p.userData.progress = Math.random();
            p.userData.speed = 0.5 + Math.random() * 0.5;
            this.messageParticles.push(p);
            this.add(p);
        }
        
        // Labels
        const titleLabel = createEducationalLabel('E8 Unified Event Bus', { fontSize: 24, maxWidth: 360 });
        titleLabel.position.set(0, 2.05, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        const dimLabel = createEducationalLabel('248 channels · 3 routing layers · Lattice-based dispatch', { fontSize: 16, maxWidth: 420 });
        dimLabel.position.set(0, 0.5, 0);
        dimLabel.scale.set(2, 0.18, 1);
        this.add(dimLabel);
        
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
        if (this.demoMode) this.demoTimer += deltaTime;
        
        // Demo: dispatch a visible event from hub through ring layers
        const demoCycle = this.demoMode ? (this.demoTimer % 4) / 4 : -1; // 4s per dispatch
        // Target a specific channel in each layer sequentially
        const demoLayer = this.demoMode ? Math.min(Math.floor(demoCycle * 4), 2) : -1;
        const demoAngle = this.demoMode ? (Math.floor(this.demoTimer / 4) % 8) * (Math.PI / 4) : 0;
        
        // Hub rotation and pulse
        if (this.hub) {
            this.hub.rotation.y += deltaTime * 0.3;
            this.hub.rotation.x = Math.sin(this.time * 0.4) * 0.15;
            if (this.demoMode && demoCycle < 0.15) {
                // Hub flashes on dispatch
                this.hub.material.emissiveIntensity = 1.0;
            } else {
                this.hub.material.emissiveIntensity = 0.5 + Math.sin(this.time * 2) * 0.2;
            }
        }
        
        // Channel nodes pulse in waves — in demo, target channel lights up
        const layerRadii = [0.35, 0.55, 0.75];
        this.channels.forEach((ch) => {
            if (this.demoMode) {
                const isTargetLayer = ch.userData.layer <= demoLayer;
                const angleDist = Math.abs(((ch.userData.angle - demoAngle + Math.PI) % (Math.PI * 2)) - Math.PI);
                const isNearTarget = angleDist < 0.5;
                if (isTargetLayer && isNearTarget) {
                    ch.material.emissiveIntensity = 0.8;
                    ch.scale.setScalar(1.8);
                } else {
                    ch.material.emissiveIntensity = 0.1;
                    ch.scale.setScalar(1.0);
                }
            } else {
                ch.material.emissiveIntensity = 0.2 + Math.sin(this.time * 3 + ch.userData.angle + ch.userData.layer) * 0.2;
                ch.scale.setScalar(1.0);
            }
        });
        
        // Ring layers gently rotate — in demo, active layer highlights
        this.ringLayers.forEach((ring, i) => {
            ring.rotation.z = this.time * (0.1 + i * 0.05) * (i % 2 === 0 ? 1 : -1);
            if (this.demoMode) {
                ring.material.opacity = i <= demoLayer ? 0.5 : 0.1;
            } else {
                ring.material.opacity = 0.2;
            }
        });
        
        // Message particles — in demo, all converge on the target angle/layer
        this.messageParticles.forEach((p, i) => {
            if (this.demoMode) {
                // All particles follow the demo dispatch path
                const targetRadius = layerRadii[Math.min(i % 3, demoLayer >= 0 ? demoLayer : 0)];
                p.userData.progress += deltaTime * 0.8;
                if (p.userData.progress > 1) p.userData.progress = 0;
                const t = p.userData.progress;
                const r = t * targetRadius;
                p.position.set(
                    Math.cos(demoAngle + i * 0.1) * r,
                    1.35,
                    Math.sin(demoAngle + i * 0.1) * r
                );
                p.material.opacity = 0.9;
                p.material.color.setHex(0xFFFF00);
            } else {
                p.userData.progress += p.userData.speed * deltaTime;
                if (p.userData.progress > 1) {
                    p.userData.progress = 0;
                    p.userData.targetAngle = Math.random() * Math.PI * 2;
                    p.userData.targetRadius = [0.35, 0.55, 0.75][Math.floor(Math.random() * 3)];
                }
                const t = p.userData.progress;
                const r = t * p.userData.targetRadius;
                p.position.set(
                    Math.cos(p.userData.targetAngle) * r,
                    1.35,
                    Math.sin(p.userData.targetAngle) * r
                );
                p.material.opacity = t < 0.1 ? t * 10 : (t > 0.9 ? (1 - t) * 10 : 0.8);
                p.material.color.setHex(0xFFFFFF);
            }
        });
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
        this.verdictCenter = null;
        this.scoreBeams = [];
        this.convergenceRing = null;
        this.demoMode = false;
        this.demoTimer = 0;
        this.failJudge = -1;
        this.create();
    }
    onClick() {
        this.demoMode = !this.demoMode;
        this.demoTimer = 0;
        this.failJudge = this.demoMode ? Math.floor(Math.random() * 6) : -1;
    }
    create() {
        const color = COLONY_COLORS.forge;
        const dimensions = ['Correctness', 'Safety', 'Privacy', 'Craft', 'Performance', 'Alignment'];
        const dimColors = [0x4CFF4C, 0xE85A2F, 0x9B7EBD, 0xE8940A, 0x4ECDC4, 0x67D4E4];
        
        // === 6 Judge Chambers arranged in hexagon ===
        for (let i = 0; i < 6; i++) {
            const angle = (i / 6) * Math.PI * 2;
            const x = Math.cos(angle) * 0.65;
            const z = Math.sin(angle) * 0.65;
            
            // Judge chamber — a small podium with glowing top
            const baseGeo = new THREE.BoxGeometry(0.18, 0.3, 0.15);
            const judge = new THREE.Mesh(baseGeo, new THREE.MeshPhysicalMaterial({
                color: dimColors[i], emissive: dimColors[i], emissiveIntensity: 0.25,
                metalness: 0.5, roughness: 0.3
            }));
            judge.position.set(x, 1.1, z);
            judge.rotation.y = -angle;
            
            // Gavel/indicator on top
            const gavelGeo = new THREE.SphereGeometry(0.05, 8, 8);
            const gavel = new THREE.Mesh(gavelGeo, new THREE.MeshPhysicalMaterial({
                color: dimColors[i], emissive: dimColors[i], emissiveIntensity: 0.5
            }));
            gavel.position.y = 0.22;
            judge.add(gavel);
            
            this.judges.push(judge);
            this.add(judge);
            
            // Dimension label
            const label = createEducationalLabel(dimensions[i], { fontSize: 18, maxWidth: 192 });
            label.position.set(x, 1.5, z);
            label.scale.set(0.7, 0.14, 1);
            this.add(label);
            
            // Score beam from judge to center
            const beamGeo = new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(x, 1.1, z),
                new THREE.Vector3(0, 1.3, 0)
            ]);
            const beam = new THREE.Line(beamGeo, new THREE.LineBasicMaterial({
                color: dimColors[i], transparent: true, opacity: 0.15
            }));
            this.scoreBeams.push(beam);
            this.add(beam);
        }
        
        // === Central verdict aggregator ===
        const verdictGeo = new THREE.DodecahedronGeometry(0.12, 0);
        this.verdictCenter = new THREE.Mesh(verdictGeo, new THREE.MeshPhysicalMaterial({
            color: 0x6FA370, emissive: 0x6FA370, emissiveIntensity: 0.5,
            metalness: 0.7, roughness: 0.2
        }));
        this.verdictCenter.position.y = 1.3;
        this.add(this.verdictCenter);
        
        // Convergence ring — the ≥90/100 threshold
        const convGeo = new THREE.TorusGeometry(0.65, 0.008, 8, 48);
        this.convergenceRing = new THREE.Mesh(convGeo, new THREE.MeshBasicMaterial({
            color: 0x6FA370, transparent: true, opacity: 0.3
        }));
        this.convergenceRing.rotation.x = Math.PI / 2;
        this.convergenceRing.position.y = 1.1;
        this.add(this.convergenceRing);
        
        // Title
        const titleLabel = createEducationalLabel('Ralph: 6-Judge Parallel Audit', { fontSize: 22, maxWidth: 380 });
        titleLabel.position.set(0, 1.9, 0);
        titleLabel.scale.set(1.5, 0.22, 1);
        this.add(titleLabel);
        
        // Threshold label
        const threshLabel = createEducationalLabel('All dimensions ≥ 90/100 or reject', { fontSize: 16, maxWidth: 340 });
        threshLabel.position.set(0, 0.5, 0);
        threshLabel.scale.set(1.5, 0.15, 1);
        this.add(threshLabel);
        
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
        if (this.demoMode) this.demoTimer += deltaTime;
        
        // Demo: "fail" scenario — one judge turns red, others converge to override
        // Phase 0-2s: normal evaluation, phase 2-3s: fail judge goes red, 
        // phase 3-5s: others converge brighter to override, phase 5-6s: verdict passes anyway
        const demoPhase = this.demoMode ? Math.min(this.demoTimer / 6, 1) : -1;
        
        // Judges evaluate in parallel — staggered pulse
        const auditCycle = (this.time % 4) / 4;
        this.judges.forEach((j, i) => {
            if (this.demoMode) {
                const isFail = i === this.failJudge;
                
                if (demoPhase < 0.33) {
                    // Phase 1: normal evaluation wave
                    const wave = Math.sin(this.demoTimer * 3 + i * 0.5) * 0.5 + 0.5;
                    j.material.emissiveIntensity = 0.3 + wave * 0.3;
                } else if (demoPhase < 0.5) {
                    // Phase 2: fail judge turns red
                    if (isFail) {
                        j.material.color.setHex(0xFF2222);
                        j.material.emissive.setHex(0xFF2222);
                        j.material.emissiveIntensity = 0.8;
                        if (j.children[0]) {
                            j.children[0].material.color.setHex(0xFF0000);
                            j.children[0].material.emissive.setHex(0xFF0000);
                            j.children[0].material.emissiveIntensity = 1.0;
                        }
                    } else {
                        j.material.emissiveIntensity = 0.3;
                    }
                } else if (demoPhase < 0.83) {
                    // Phase 3: other judges converge — glow brighter to override
                    if (isFail) {
                        j.material.emissiveIntensity = 0.6 + Math.sin(this.time * 8) * 0.2;
                    } else {
                        const converge = (demoPhase - 0.5) / 0.33;
                        j.material.emissiveIntensity = 0.4 + converge * 0.5;
                        if (j.children[0]) {
                            j.children[0].material.emissiveIntensity = 0.5 + converge * 0.5;
                        }
                    }
                } else {
                    // Phase 4: verdict — all judges settle, fail judge dims
                    if (isFail) {
                        j.material.emissiveIntensity = 0.2;
                    } else {
                        j.material.emissiveIntensity = 0.7;
                    }
                }
            } else {
                // Restore original colors
                const dimColors = [0x4CFF4C, 0xE85A2F, 0x9B7EBD, 0xE8940A, 0x4ECDC4, 0x67D4E4];
                j.material.color.setHex(dimColors[i]);
                j.material.emissive.setHex(dimColors[i]);
                if (j.children[0]) {
                    j.children[0].material.color.setHex(dimColors[i]);
                    j.children[0].material.emissive.setHex(dimColors[i]);
                }
                
                const judgePhase = ((auditCycle * 6 - i + 6) % 6) / 6;
                const evaluating = judgePhase > 0 && judgePhase < 0.3;
                j.material.emissiveIntensity = evaluating ? 0.6 : 0.2 + Math.sin(this.time + i) * 0.05;
                if (j.children[0]) {
                    j.children[0].material.emissiveIntensity = evaluating ? 1.0 : 0.3;
                }
            }
        });
        
        // Score beams brighten when active
        this.scoreBeams.forEach((beam, i) => {
            if (this.demoMode) {
                const isFail = i === this.failJudge;
                if (demoPhase > 0.5 && demoPhase < 0.83) {
                    // During convergence, all non-fail beams glow
                    beam.material.opacity = isFail ? 0.1 : 0.6;
                    if (!isFail) beam.material.color.setHex(0x6FA370);
                    if (isFail) beam.material.color.setHex(0xFF2222);
                } else if (demoPhase >= 0.83) {
                    beam.material.opacity = 0.4;
                    beam.material.color.setHex(0x6FA370);
                } else {
                    beam.material.opacity = 0.15;
                }
            } else {
                const judgePhase = (((this.time % 4) / 4 * 6 - i + 6) % 6) / 6;
                beam.material.opacity = judgePhase > 0.2 && judgePhase < 0.35 ? 0.5 : 0.1;
            }
        });
        
        // Verdict center
        if (this.verdictCenter) {
            this.verdictCenter.rotation.y += deltaTime * 0.5;
            if (this.demoMode) {
                if (demoPhase >= 0.83) {
                    // Verdict passes — green flash
                    this.verdictCenter.material.emissiveIntensity = 0.9;
                    this.verdictCenter.material.color.set(0x4CFF4C);
                    this.verdictCenter.material.emissive.set(0x4CFF4C);
                } else if (demoPhase > 0.33) {
                    // Under stress — amber
                    this.verdictCenter.material.emissiveIntensity = 0.4 + Math.sin(this.time * 4) * 0.2;
                    this.verdictCenter.material.color.set(0xF59E0B);
                    this.verdictCenter.material.emissive.set(0xF59E0B);
                } else {
                    this.verdictCenter.material.emissiveIntensity = 0.3;
                    this.verdictCenter.material.color.set(0x6FA370);
                    this.verdictCenter.material.emissive.set(0x6FA370);
                }
            } else {
                const allDone = auditCycle > 0.85;
                this.verdictCenter.material.emissiveIntensity = allDone ? 0.8 : 0.3 + Math.sin(this.time * 2) * 0.1;
                this.verdictCenter.material.color.set(allDone ? 0x4CFF4C : 0x6FA370);
                this.verdictCenter.material.emissive.set(allDone ? 0x4CFF4C : 0x6FA370);
            }
        }
        
        // Convergence ring
        if (this.convergenceRing) {
            if (this.demoMode) {
                this.convergenceRing.material.opacity = demoPhase >= 0.83 ? 0.7 : 0.1;
            } else {
                this.convergenceRing.material.opacity = auditCycle > 0.85 ? 0.5 : 0.15;
            }
        }
        
        // Loop demo
        if (this.demoMode && this.demoTimer > 7) {
            this.demoTimer = 0;
            this.failJudge = Math.floor(Math.random() * 6);
        }
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
