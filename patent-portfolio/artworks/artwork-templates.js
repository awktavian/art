/**
 * Artwork Templates
 * =================
 * 
 * Reusable visualization templates for P2 and P3 patents.
 * Each category has its own distinct visual language.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { getCanvasFont, setupHiDPICanvas } from '../lib/typography.js';

// ═══════════════════════════════════════════════════════════════════════════
// COLONY COLORS
// ═══════════════════════════════════════════════════════════════════════════

const COLONY_COLORS = {
    spark:   0xFF6B35,
    forge:   0xD4AF37,
    flow:    0x4ECDC4,
    nexus:   0x9B7EBD,
    beacon:  0xF59E0B,
    grove:   0x7EB77F,
    crystal: 0x67D4E4
};

const CATEGORY_VISUALS = {
    // Math - Geometric structures
    A: { type: 'geometry', shapes: ['icosahedron', 'octahedron', 'tetrahedron'] },
    // Safety - Barrier/shield aesthetics
    B: { type: 'barrier', color: 0x7EB77F },
    // Consensus - Network nodes
    C: { type: 'network', nodes: 7 },
    // World Models - Organic/tree structures
    D: { type: 'organic', branches: 5 },
    // Crypto - Crystal/key forms
    E: { type: 'crystal', facets: 8 },
    // Smart Home - Ambient/cozy
    F: { type: 'ambient', warmth: true },
    // Voice - Sound waves
    G: { type: 'waves', frequency: 3 },
    // Economic - Flow/charts
    H: { type: 'flow', streams: 5 },
    // Platform - Architecture/grid
    I: { type: 'grid', layers: 3 },
    // Reasoning - Decision tree
    J: { type: 'tree', depth: 4 },
    // Visual - Abstract art
    K: { type: 'abstract', particles: true }
};

// ═══════════════════════════════════════════════════════════════════════════
// BASE ARTWORK CLASS
// ═══════════════════════════════════════════════════════════════════════════

export class TemplateArtwork extends THREE.Group {
    constructor(patent) {
        super();
        this.patent = patent;
        this.time = 0;
        this.name = `artwork-${patent.id}`;
        this.userData = { patentId: patent.id, interactive: true };
        
        this.create();
    }
    
    create() {
        const category = CATEGORY_VISUALS[this.patent.category];
        const colony = this.patent.colony;
        const color = COLONY_COLORS[colony] || 0x67D4E4;
        
        // Create pedestal
        this.createPedestal(color);
        
        // Create category-specific visualization
        switch (category?.type) {
            case 'geometry':
                this.createGeometryVisualization(color);
                break;
            case 'barrier':
                this.createBarrierVisualization(color);
                break;
            case 'network':
                this.createNetworkVisualization(color, category.nodes);
                break;
            case 'organic':
                this.createOrganicVisualization(color);
                break;
            case 'crystal':
                this.createCrystalVisualization(color);
                break;
            case 'ambient':
                this.createAmbientVisualization(color);
                break;
            case 'waves':
                this.createWaveVisualization(color);
                break;
            case 'flow':
                this.createFlowVisualization(color);
                break;
            case 'grid':
                this.createGridVisualization(color);
                break;
            case 'tree':
                this.createTreeVisualization(color);
                break;
            case 'abstract':
                this.createAbstractVisualization(color);
                break;
            default:
                this.createDefaultVisualization(color);
        }
        
        // Add plaque
        const plaque = createPlaque(this.patent, { 
            width: 1.8, 
            height: 1.0,
            showDescription: true 
        });
        plaque.position.set(0, 0.7, 1.8);
        plaque.rotation.x = -0.2;
        this.add(plaque);
    }
    
    createPedestal(color) {
        const geo = new THREE.CylinderGeometry(1, 1.2, 0.2, 32);
        const mat = new THREE.MeshPhysicalMaterial({
            color: 0x0A0A15,
            metalness: 0.8,
            roughness: 0.2
        });
        const pedestal = new THREE.Mesh(geo, mat);
        pedestal.position.y = 0.1;
        pedestal.userData.isPedestal = true;
        this.add(pedestal);
        
        // Glowing rim
        const rimGeo = new THREE.TorusGeometry(1.1, 0.03, 16, 64);
        const rimMat = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.6
        });
        const rim = new THREE.Mesh(rimGeo, rimMat);
        rim.rotation.x = Math.PI / 2;
        rim.position.y = 0.21;
        this.add(rim);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CATEGORY-SPECIFIC VISUALIZATIONS
    // ═══════════════════════════════════════════════════════════════════════
    
    createGeometryVisualization(color) {
        // Nested geometric shapes
        const shapes = ['IcosahedronGeometry', 'OctahedronGeometry', 'TetrahedronGeometry'];
        
        shapes.forEach((shapeName, i) => {
            const size = 0.5 - i * 0.12;
            const geo = new THREE[shapeName](size, 0);
            const mat = new THREE.MeshPhysicalMaterial({
                color: color,
                metalness: 0.3,
                roughness: 0.4,
                transparent: true,
                opacity: 0.6 + i * 0.1,
                wireframe: i % 2 === 1
            });
            const mesh = new THREE.Mesh(geo, mat);
            mesh.position.y = 1.2;
            mesh.userData.rotationOffset = i * 0.5;
            this.add(mesh);
            this.shapes = this.shapes || [];
            this.shapes.push(mesh);
        });
    }
    
    createBarrierVisualization(color) {
        // Nested barrier domes
        for (let i = 0; i < 3; i++) {
            const radius = 0.8 - i * 0.2;
            const geo = new THREE.SphereGeometry(radius, 32, 16, 0, Math.PI * 2, 0, Math.PI / 2);
            const mat = new THREE.MeshPhysicalMaterial({
                color: i === 0 ? 0x7EB77F : color,
                metalness: 0,
                roughness: 0.3,
                transparent: true,
                opacity: 0.3 - i * 0.05,
                side: THREE.DoubleSide
            });
            const dome = new THREE.Mesh(geo, mat);
            dome.position.y = 0.22;
            this.add(dome);
        }
        
        // h(x) text
        this.createFloatingText('h(x) ≥ 0', color);
    }
    
    createNetworkVisualization(color, nodeCount = 7) {
        // Network of connected nodes
        const nodes = [];
        
        for (let i = 0; i < nodeCount; i++) {
            const angle = (i / nodeCount) * Math.PI * 2;
            const radius = 0.6;
            
            const nodeGeo = new THREE.SphereGeometry(0.1, 16, 16);
            const nodeMat = new THREE.MeshPhysicalMaterial({
                color: color,
                emissive: color,
                emissiveIntensity: 0.3,
                metalness: 0.3,
                roughness: 0.4
            });
            const node = new THREE.Mesh(nodeGeo, nodeMat);
            node.position.set(
                Math.cos(angle) * radius,
                1.2 + Math.sin(i * 0.5) * 0.1,
                Math.sin(angle) * radius
            );
            nodes.push(node);
            this.add(node);
        }
        
        // Connect nodes
        const lineMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.4 });
        for (let i = 0; i < nodes.length; i++) {
            for (let j = i + 1; j < nodes.length; j++) {
                if (Math.random() < 0.4) {
                    const points = [nodes[i].position.clone(), nodes[j].position.clone()];
                    const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
                    const line = new THREE.Line(lineGeo, lineMat);
                    this.add(line);
                }
            }
        }
        
        this.networkNodes = nodes;
    }
    
    createOrganicVisualization(color) {
        // Tree-like organic structure
        const trunkGeo = new THREE.CylinderGeometry(0.08, 0.12, 1, 8);
        const trunkMat = new THREE.MeshPhysicalMaterial({
            color: 0x3D5A4A,
            metalness: 0.1,
            roughness: 0.8
        });
        const trunk = new THREE.Mesh(trunkGeo, trunkMat);
        trunk.position.y = 0.7;
        this.add(trunk);
        
        // Branches
        for (let i = 0; i < 5; i++) {
            const angle = (i / 5) * Math.PI * 2;
            const branchGeo = new THREE.CylinderGeometry(0.02, 0.04, 0.4, 6);
            const branch = new THREE.Mesh(branchGeo, trunkMat);
            branch.position.set(
                Math.cos(angle) * 0.15,
                1.0 + i * 0.1,
                Math.sin(angle) * 0.15
            );
            branch.rotation.z = Math.PI / 4 * (Math.cos(angle) > 0 ? 1 : -1);
            this.add(branch);
            
            // Leaf/node
            const leafGeo = new THREE.IcosahedronGeometry(0.08, 0);
            const leafMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.8 });
            const leaf = new THREE.Mesh(leafGeo, leafMat);
            leaf.position.set(
                Math.cos(angle) * 0.4,
                1.1 + i * 0.1,
                Math.sin(angle) * 0.4
            );
            this.add(leaf);
        }
    }
    
    createCrystalVisualization(color) {
        // Crystal formation
        const crystalGeo = new THREE.OctahedronGeometry(0.5, 0);
        const crystalMat = new THREE.MeshPhysicalMaterial({
            color: color,
            metalness: 0.1,
            roughness: 0,
            transmission: 0.7,
            thickness: 0.5,
            iridescence: 0.8,
            transparent: true,
            opacity: 0.9
        });
        this.crystal = new THREE.Mesh(crystalGeo, crystalMat);
        this.crystal.position.y = 1.2;
        this.add(this.crystal);
        
        // Surrounding smaller crystals
        for (let i = 0; i < 6; i++) {
            const angle = (i / 6) * Math.PI * 2;
            const smallGeo = new THREE.OctahedronGeometry(0.15, 0);
            const small = new THREE.Mesh(smallGeo, crystalMat.clone());
            small.position.set(
                Math.cos(angle) * 0.6,
                0.9 + Math.random() * 0.3,
                Math.sin(angle) * 0.6
            );
            small.rotation.set(Math.random(), Math.random(), Math.random());
            this.add(small);
        }
    }
    
    createAmbientVisualization(color) {
        // Warm ambient glow orb
        const orbGeo = new THREE.SphereGeometry(0.4, 32, 32);
        const orbMat = new THREE.MeshPhysicalMaterial({
            color: color,
            emissive: color,
            emissiveIntensity: 0.5,
            metalness: 0,
            roughness: 0.5,
            transparent: true,
            opacity: 0.8
        });
        this.orb = new THREE.Mesh(orbGeo, orbMat);
        this.orb.position.y = 1.2;
        this.add(this.orb);
        
        // Glow shell
        const glowGeo = new THREE.SphereGeometry(0.6, 16, 16);
        const glowMat = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.1,
            side: THREE.BackSide
        });
        const glow = new THREE.Mesh(glowGeo, glowMat);
        glow.position.y = 1.2;
        this.add(glow);
    }
    
    createWaveVisualization(color) {
        // Sound wave rings
        this.waveRings = [];
        
        for (let i = 0; i < 5; i++) {
            const ringGeo = new THREE.TorusGeometry(0.3 + i * 0.15, 0.02, 16, 64);
            const ringMat = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.6 - i * 0.1
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.position.y = 1.2;
            ring.userData.baseRadius = 0.3 + i * 0.15;
            ring.userData.phase = i * 0.5;
            this.waveRings.push(ring);
            this.add(ring);
        }
    }
    
    createFlowVisualization(color) {
        // Flow streams
        const streamCount = 5;
        this.flowParticles = [];
        
        for (let s = 0; s < streamCount; s++) {
            const angle = (s / streamCount) * Math.PI * 2;
            
            for (let i = 0; i < 10; i++) {
                const particleGeo = new THREE.SphereGeometry(0.03, 8, 8);
                const particleMat = new THREE.MeshBasicMaterial({
                    color: color,
                    transparent: true,
                    opacity: 0.8
                });
                const particle = new THREE.Mesh(particleGeo, particleMat);
                particle.userData = { stream: s, index: i, angle };
                this.flowParticles.push(particle);
                this.add(particle);
            }
        }
    }
    
    createGridVisualization(color) {
        // Layered grid structure
        for (let layer = 0; layer < 3; layer++) {
            const gridSize = 0.8 - layer * 0.2;
            const gridHelper = new THREE.GridHelper(gridSize, 4, color, color);
            gridHelper.position.y = 0.6 + layer * 0.4;
            gridHelper.material.transparent = true;
            gridHelper.material.opacity = 0.4;
            this.add(gridHelper);
        }
        
        // Center pillar
        const pillarGeo = new THREE.BoxGeometry(0.1, 1, 0.1);
        const pillarMat = new THREE.MeshPhysicalMaterial({
            color: color,
            emissive: color,
            emissiveIntensity: 0.3,
            metalness: 0.5,
            roughness: 0.3
        });
        const pillar = new THREE.Mesh(pillarGeo, pillarMat);
        pillar.position.y = 0.7;
        this.add(pillar);
    }
    
    createTreeVisualization(color) {
        // Decision tree structure
        const createNode = (x, y, z, level) => {
            const nodeGeo = new THREE.SphereGeometry(0.08 - level * 0.015, 16, 16);
            const nodeMat = new THREE.MeshPhysicalMaterial({
                color: color,
                emissive: color,
                emissiveIntensity: 0.2,
                metalness: 0.3,
                roughness: 0.4
            });
            const node = new THREE.Mesh(nodeGeo, nodeMat);
            node.position.set(x, y, z);
            return node;
        };
        
        // Root
        const root = createNode(0, 1.5, 0, 0);
        this.add(root);
        
        // Branches
        const lineMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 });
        
        const addBranch = (parent, level, direction) => {
            if (level > 3) return;
            
            const spread = 0.3 - level * 0.05;
            const drop = 0.25;
            
            const childPos = new THREE.Vector3(
                parent.position.x + direction * spread,
                parent.position.y - drop,
                parent.position.z + (Math.random() - 0.5) * 0.1
            );
            
            const child = createNode(childPos.x, childPos.y, childPos.z, level);
            this.add(child);
            
            // Connect
            const points = [parent.position.clone(), childPos];
            const lineGeo = new THREE.BufferGeometry().setFromPoints(points);
            const line = new THREE.Line(lineGeo, lineMat);
            this.add(line);
            
            // Recurse
            addBranch(child, level + 1, -1);
            addBranch(child, level + 1, 1);
        };
        
        addBranch(root, 1, -1);
        addBranch(root, 1, 1);
    }
    
    createAbstractVisualization(color) {
        // Abstract particle cloud
        const particleCount = 100;
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        const colorObj = new THREE.Color(color);
        
        for (let i = 0; i < particleCount; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.acos(2 * Math.random() - 1);
            const r = 0.3 + Math.random() * 0.4;
            
            positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = r * Math.cos(phi) + 1.2;
            positions[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta);
            
            colors[i * 3] = colorObj.r * (0.8 + Math.random() * 0.2);
            colors[i * 3 + 1] = colorObj.g * (0.8 + Math.random() * 0.2);
            colors[i * 3 + 2] = colorObj.b * (0.8 + Math.random() * 0.2);
        }
        
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const material = new THREE.PointsMaterial({
            size: 0.04,
            vertexColors: true,
            transparent: true,
            opacity: 0.8,
            blending: THREE.AdditiveBlending
        });
        
        this.particleCloud = new THREE.Points(geometry, material);
        this.add(this.particleCloud);
    }
    
    createDefaultVisualization(color) {
        // Default: Simple rotating cube
        const cubeGeo = new THREE.BoxGeometry(0.5, 0.5, 0.5);
        const cubeMat = new THREE.MeshPhysicalMaterial({
            color: color,
            metalness: 0.5,
            roughness: 0.3,
            clearcoat: 0.5
        });
        this.cube = new THREE.Mesh(cubeGeo, cubeMat);
        this.cube.position.y = 1.2;
        this.add(this.cube);
    }
    
    createFloatingText(text, color) {
        // Higher resolution canvas for crisp text (512x128 @ 2x DPI)
        const canvas = document.createElement('canvas');
        const ctx = setupHiDPICanvas(canvas, 256, 64, 2);
        
        // Clear with transparency
        ctx.clearRect(0, 0, 256, 64);
        
        // Text with glow effect
        const colorHex = '#' + color.toString(16).padStart(6, '0');
        ctx.shadowColor = colorHex;
        ctx.shadowBlur = 8;
        ctx.fillStyle = colorHex;
        ctx.font = getCanvasFont(32, 'mono');
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, 128, 32);
        
        const texture = new THREE.CanvasTexture(canvas);
        texture.anisotropy = 8;
        
        const geo = new THREE.PlaneGeometry(1.2, 0.3);
        const mat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide,
            depthWrite: false
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.y = 1.8;
        mesh.userData.isBillboard = true;  // Flag for billboard behavior
        mesh.userData.floatingLabel = true;
        this.add(mesh);
        
        // Store reference for billboard update
        if (!this.billboards) this.billboards = [];
        this.billboards.push(mesh);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime, camera = null) {
        this.time += deltaTime;
        
        // Billboard behavior - make floating text face camera
        if (camera && this.billboards) {
            this.billboards.forEach(billboard => {
                billboard.lookAt(camera.position);
            });
        }
        
        // Animate shapes
        if (this.shapes) {
            this.shapes.forEach((shape, i) => {
                shape.rotation.x = this.time * 0.5 + shape.userData.rotationOffset;
                shape.rotation.y = this.time * 0.3 + shape.userData.rotationOffset * 0.5;
            });
        }
        
        // Animate crystal
        if (this.crystal) {
            this.crystal.rotation.y = this.time * 0.3;
            this.crystal.position.y = 1.2 + Math.sin(this.time * 2) * 0.05;
        }
        
        // Animate orb
        if (this.orb) {
            const pulse = Math.sin(this.time * 2) * 0.5 + 0.5;
            this.orb.material.emissiveIntensity = 0.3 + pulse * 0.3;
        }
        
        // Animate wave rings
        if (this.waveRings) {
            this.waveRings.forEach((ring, i) => {
                const scale = 1 + Math.sin(this.time * 3 + ring.userData.phase) * 0.2;
                ring.scale.setScalar(scale);
                ring.material.opacity = 0.6 - Math.abs(Math.sin(this.time * 3 + ring.userData.phase)) * 0.3;
            });
        }
        
        // Animate flow particles
        if (this.flowParticles) {
            this.flowParticles.forEach(particle => {
                const t = (this.time * 0.5 + particle.userData.index * 0.1) % 1;
                const angle = particle.userData.angle;
                const radius = 0.3 + t * 0.4;
                
                particle.position.set(
                    Math.cos(angle) * radius,
                    0.5 + t * 1.2,
                    Math.sin(angle) * radius
                );
                particle.material.opacity = 1 - t;
            });
        }
        
        // Animate network nodes
        if (this.networkNodes) {
            this.networkNodes.forEach((node, i) => {
                node.position.y = 1.2 + Math.sin(this.time * 2 + i * 0.5) * 0.05;
            });
        }
        
        // Animate particle cloud
        if (this.particleCloud) {
            this.particleCloud.rotation.y = this.time * 0.2;
        }
        
        // Animate cube
        if (this.cube) {
            this.cube.rotation.x = this.time * 0.5;
            this.cube.rotation.y = this.time * 0.3;
        }
    }
    
    dispose() {
        this.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// FACTORY FUNCTION
// ═══════════════════════════════════════════════════════════════════════════

export function createTemplateArtwork(patent) {
    return new TemplateArtwork(patent);
}

export default TemplateArtwork;
