/**
 * P1-005: OrganismRSSM Architecture Artwork
 * =========================================
 * 
 * A "world tree" - the RSSM architecture visualized as
 * a living organism with 7 colony branches.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { PATENTS } from '../components/info-panel.js';

const PATENT = PATENTS.find(p => p.id === 'P1-005');

const COLONY_DATA = [
    { name: 'Spark', color: 0xFF6B35 },
    { name: 'Forge', color: 0xD4AF37 },
    { name: 'Flow', color: 0x4ECDC4 },
    { name: 'Nexus', color: 0x9B7EBD },
    { name: 'Beacon', color: 0xF59E0B },
    { name: 'Grove', color: 0x7EB77F },
    { name: 'Crystal', color: 0x67D4E4 }
];

export class OrganismRSSMArtwork extends THREE.Group {
    constructor() {
        super();
        this.name = 'artwork-organism-rssm';
        this.time = 0;
        
        this.branches = [];
        this.neurons = [];
        this.synapses = [];
        
        this.create();
    }
    
    create() {
        // Root system (bottom)
        this.createRootSystem();
        
        // Central trunk (RSSM core)
        this.createTrunk();
        
        // 7 colony branches
        this.createBranches();
        
        // Neural activity particles
        this.createNeuralActivity();
        
        // State indicators
        this.createStateIndicators();
        
        // Plaque
        if (PATENT) {
            const plaque = createPlaque(PATENT, { width: 2.5, height: 1.5 });
            plaque.position.set(4, 1.5, 0);
            plaque.rotation.y = -Math.PI / 2;
            this.add(plaque);
        }
    }
    
    createRootSystem() {
        // Ground plane with "neural network" pattern
        const groundGeo = new THREE.CircleGeometry(4, 64);
        const groundMat = new THREE.MeshStandardMaterial({
            color: 0x0A1210,
            metalness: 0.3,
            roughness: 0.8
        });
        const ground = new THREE.Mesh(groundGeo, groundMat);
        ground.rotation.x = -Math.PI / 2;
        ground.receiveShadow = true;
        this.add(ground);
        
        // Root tendrils spreading outward
        for (let i = 0; i < 12; i++) {
            const angle = (i / 12) * Math.PI * 2;
            const rootCurve = new THREE.CatmullRomCurve3([
                new THREE.Vector3(0, 0, 0),
                new THREE.Vector3(Math.cos(angle) * 1.5, -0.3, Math.sin(angle) * 1.5),
                new THREE.Vector3(Math.cos(angle) * 3, -0.1, Math.sin(angle) * 3),
                new THREE.Vector3(Math.cos(angle) * 3.8, 0.1, Math.sin(angle) * 3.8)
            ]);
            
            const rootGeo = new THREE.TubeGeometry(rootCurve, 32, 0.08 - i * 0.004, 8, false);
            const rootMat = new THREE.MeshPhysicalMaterial({
                color: 0x2A4A3A,
                metalness: 0.2,
                roughness: 0.7
            });
            const root = new THREE.Mesh(rootGeo, rootMat);
            this.add(root);
        }
    }
    
    createTrunk() {
        // Central RSSM core - organic trunk
        const trunkCurve = new THREE.CatmullRomCurve3([
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(0.1, 0.5, 0.05),
            new THREE.Vector3(-0.05, 1, 0.1),
            new THREE.Vector3(0.08, 1.5, -0.05),
            new THREE.Vector3(0, 2, 0),
            new THREE.Vector3(-0.1, 2.5, 0.05),
            new THREE.Vector3(0, 3, 0)
        ]);
        
        // Varying radius along trunk
        const radiusFunc = (t) => {
            return 0.3 * (1 - t * 0.5) + 0.1;
        };
        
        // Custom tube with varying radius
        const points = trunkCurve.getPoints(50);
        const trunkGeo = new THREE.TubeGeometry(trunkCurve, 50, 0.25, 12, false);
        const trunkMat = new THREE.MeshPhysicalMaterial({
            color: 0x3D5A4A,
            metalness: 0.2,
            roughness: 0.6,
            clearcoat: 0.3
        });
        this.trunk = new THREE.Mesh(trunkGeo, trunkMat);
        this.add(this.trunk);
        
        // Glowing core inside trunk (RSSM state)
        const coreGeo = new THREE.CylinderGeometry(0.15, 0.15, 2.5, 32);
        const coreMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.3
        });
        const core = new THREE.Mesh(coreGeo, coreMat);
        core.position.y = 1.5;
        this.add(core);
        
        // RSSM label
        this.createTrunkLabel();
    }
    
    createTrunkLabel() {
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 128;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = 'transparent';
        ctx.fillRect(0, 0, 256, 128);
        
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 32px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('RSSM', 128, 50);
        ctx.font = '20px "IBM Plex Mono", monospace';
        ctx.fillText('World Model', 128, 85);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(1.5, 0.75);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.set(0, 1.5, 0.5);
        this.add(label);
    }
    
    createBranches() {
        // 7 branches, one for each colony
        COLONY_DATA.forEach((colony, i) => {
            const angle = (i / 7) * Math.PI * 2;
            const branchStart = new THREE.Vector3(0, 2.5 + i * 0.1, 0);
            
            // Main branch
            const branchEnd = new THREE.Vector3(
                Math.cos(angle) * 2.5,
                3.5 + Math.sin(i * 0.5) * 0.5,
                Math.sin(angle) * 2.5
            );
            
            const branchCurve = new THREE.QuadraticBezierCurve3(
                branchStart,
                new THREE.Vector3(
                    Math.cos(angle) * 1,
                    3 + i * 0.05,
                    Math.sin(angle) * 1
                ),
                branchEnd
            );
            
            const branchGeo = new THREE.TubeGeometry(branchCurve, 32, 0.1 - i * 0.005, 8, false);
            const branchMat = new THREE.MeshPhysicalMaterial({
                color: 0x4A6A5A,
                metalness: 0.2,
                roughness: 0.6
            });
            const branch = new THREE.Mesh(branchGeo, branchMat);
            this.add(branch);
            
            // Colony node at end of branch
            const nodeGeo = new THREE.IcosahedronGeometry(0.25, 2);
            const nodeMat = new THREE.MeshPhysicalMaterial({
                color: colony.color,
                emissive: colony.color,
                emissiveIntensity: 0.4,
                metalness: 0.3,
                roughness: 0.4,
                clearcoat: 0.6
            });
            const node = new THREE.Mesh(nodeGeo, nodeMat);
            node.position.copy(branchEnd);
            node.userData = { colony: colony.name, index: i };
            this.add(node);
            this.branches.push({ branch, node, endPos: branchEnd });
            
            // Colony glow
            const glowGeo = new THREE.IcosahedronGeometry(0.35, 1);
            const glowMat = new THREE.MeshBasicMaterial({
                color: colony.color,
                transparent: true,
                opacity: 0.15,
                side: THREE.BackSide
            });
            const glow = new THREE.Mesh(glowGeo, glowMat);
            glow.position.copy(branchEnd);
            this.add(glow);
            
            // Sub-branches (leaves/neurons)
            this.createSubBranches(branchEnd, colony.color, i);
            
            // Colony label
            this.createColonyLabel(colony.name, branchEnd, colony.color);
        });
    }
    
    createSubBranches(origin, color, index) {
        // Small sub-branches (neurons)
        for (let j = 0; j < 5; j++) {
            const angle = (j / 5) * Math.PI * 2 + index;
            const length = 0.3 + Math.random() * 0.3;
            
            const endPos = new THREE.Vector3(
                origin.x + Math.cos(angle) * length,
                origin.y + Math.random() * 0.3,
                origin.z + Math.sin(angle) * length
            );
            
            const subCurve = new THREE.LineCurve3(origin, endPos);
            const subGeo = new THREE.TubeGeometry(subCurve, 8, 0.02, 4, false);
            const subMat = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.5
            });
            const sub = new THREE.Mesh(subGeo, subMat);
            this.add(sub);
            
            // Small neuron at end
            const neuronGeo = new THREE.SphereGeometry(0.05, 8, 8);
            const neuronMat = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.8
            });
            const neuron = new THREE.Mesh(neuronGeo, neuronMat);
            neuron.position.copy(endPos);
            this.add(neuron);
            this.neurons.push(neuron);
        }
    }
    
    createColonyLabel(name, position, color) {
        const canvas = document.createElement('canvas');
        canvas.width = 128;
        canvas.height = 48;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = 'transparent';
        ctx.fillRect(0, 0, 128, 48);
        
        ctx.fillStyle = '#' + color.toString(16).padStart(6, '0');
        ctx.font = 'bold 18px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(name, 64, 28);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(0.8, 0.3);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.set(position.x, position.y + 0.5, position.z);
        label.lookAt(0, position.y + 0.5, 0);
        label.rotation.y += Math.PI;
        this.add(label);
    }
    
    createNeuralActivity() {
        // Particles flowing up the tree (state updates)
        const particleCount = 100;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        this.particleVelocities = new Float32Array(particleCount);
        
        for (let i = 0; i < particleCount; i++) {
            // Start at random positions along the tree
            const height = Math.random() * 3;
            const angle = Math.random() * Math.PI * 2;
            const radius = Math.random() * 0.5;
            
            positions[i * 3] = Math.cos(angle) * radius;
            positions[i * 3 + 1] = height;
            positions[i * 3 + 2] = Math.sin(angle) * radius;
            
            // Greenish-cyan colors
            colors[i * 3] = 0.4;
            colors[i * 3 + 1] = 0.8 + Math.random() * 0.2;
            colors[i * 3 + 2] = 0.7 + Math.random() * 0.3;
            
            this.particleVelocities[i] = 0.3 + Math.random() * 0.3;
        }
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const material = new THREE.PointsMaterial({
            size: 0.05,
            vertexColors: true,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending
        });
        
        this.activityParticles = new THREE.Points(geometry, material);
        this.add(this.activityParticles);
    }
    
    createStateIndicators() {
        // Hidden state visualization (rings around trunk)
        for (let i = 0; i < 5; i++) {
            const ringGeo = new THREE.TorusGeometry(0.35 + i * 0.02, 0.02, 8, 32);
            const ringMat = new THREE.MeshBasicMaterial({
                color: 0x67D4E4,
                transparent: true,
                opacity: 0.3 - i * 0.05
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = Math.PI / 2;
            ring.position.y = 1.0 + i * 0.4;
            this.add(ring);
            this.synapses.push(ring);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Gentle sway of branches
        this.branches.forEach((b, i) => {
            const sway = Math.sin(this.time * 0.5 + i * 0.5) * 0.05;
            b.node.position.x = b.endPos.x + sway;
            b.node.position.z = b.endPos.z + Math.sin(this.time * 0.7 + i) * 0.03;
            
            // Pulse glow
            b.node.material.emissiveIntensity = 0.3 + Math.sin(this.time * 2 + i) * 0.2;
        });
        
        // Animate neurons
        this.neurons.forEach((neuron, i) => {
            const pulse = Math.sin(this.time * 3 + i * 0.3);
            neuron.scale.setScalar(1 + pulse * 0.2);
            neuron.material.opacity = 0.6 + pulse * 0.2;
        });
        
        // Update activity particles (flow upward)
        if (this.activityParticles) {
            const positions = this.activityParticles.geometry.attributes.position.array;
            
            for (let i = 0; i < this.particleVelocities.length; i++) {
                // Move upward
                positions[i * 3 + 1] += deltaTime * this.particleVelocities[i];
                
                // Reset if too high
                if (positions[i * 3 + 1] > 4) {
                    positions[i * 3 + 1] = 0;
                    const angle = Math.random() * Math.PI * 2;
                    const radius = Math.random() * 0.3;
                    positions[i * 3] = Math.cos(angle) * radius;
                    positions[i * 3 + 2] = Math.sin(angle) * radius;
                }
                
                // Spread outward as they rise
                const height = positions[i * 3 + 1];
                if (height > 2.5) {
                    const spread = (height - 2.5) * 0.3;
                    const angle = Math.atan2(positions[i * 3 + 2], positions[i * 3]);
                    positions[i * 3] += Math.cos(angle) * deltaTime * spread;
                    positions[i * 3 + 2] += Math.sin(angle) * deltaTime * spread;
                }
            }
            
            this.activityParticles.geometry.attributes.position.needsUpdate = true;
        }
        
        // Pulse state rings in sequence
        this.synapses.forEach((ring, i) => {
            const sequentialPhase = (this.time * 0.5 - i * 0.15) % 1;
            const pulse = sequentialPhase > 0.8 ? Math.sin((sequentialPhase - 0.8) * Math.PI * 5) : 0;
            ring.scale.setScalar(1 + pulse * 0.2);
            ring.material.opacity = 0.15 + pulse * 0.25;
        });
        
        // Track particle density near branches for reactions
        if (this.activityParticles) {
            const positions = this.activityParticles.geometry.attributes.position.array;
            
            // Count particles near each branch
            const branchActivity = this.branches.map(() => 0);
            
            for (let i = 0; i < positions.length / 3; i++) {
                const px = positions[i * 3];
                const py = positions[i * 3 + 1];
                const pz = positions[i * 3 + 2];
                
                // Check distance to each branch endpoint
                this.branches.forEach((b, bi) => {
                    const dx = px - b.endPos.x;
                    const dy = py - b.endPos.y;
                    const dz = pz - b.endPos.z;
                    const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
                    if (dist < 1) branchActivity[bi]++;
                });
            }
            
            // Branches react to particle flow
            this.branches.forEach((b, i) => {
                const activity = branchActivity[i] / 5;
                const sway = Math.sin(this.time * 0.5 + i * 0.5) * 0.05;
                const activityWiggle = activity * Math.sin(this.time * 8 + i) * 0.03;
                
                b.node.position.x = b.endPos.x + sway + activityWiggle;
                b.node.position.z = b.endPos.z + Math.sin(this.time * 0.7 + i) * 0.03;
                
                // Brighter when particles nearby
                b.node.material.emissiveIntensity = 0.3 + activity * 0.4 + Math.sin(this.time * 2 + i) * 0.1;
            });
        }
        
        // Neurons sparkle when "active" (random sparkling)
        this.neurons.forEach((neuron, i) => {
            const baseScale = 1 + Math.sin(this.time * 3 + i * 0.3) * 0.1;
            
            // Random sparkle
            const sparkle = Math.random() < 0.02 ? 0.4 : 0;
            neuron.scale.setScalar(baseScale + sparkle);
            neuron.material.opacity = 0.5 + Math.sin(this.time * 3 + i * 0.3) * 0.15 + sparkle;
        });
        
        // Trunk core pulses with overall activity
        if (this.trunk && this.trunk.userData.core) {
            const totalActivity = this.branches.reduce((sum, b, i) => {
                return sum + (b.node.material.emissiveIntensity - 0.3);
            }, 0);
            const corePulse = totalActivity / this.branches.length;
            this.trunk.userData.core.material.emissiveIntensity = 0.3 + corePulse * 2;
        }
    }
    
    dispose() {
        this.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

export function createOrganismRSSMArtwork() {
    return new OrganismRSSMArtwork();
}

export default OrganismRSSMArtwork;
