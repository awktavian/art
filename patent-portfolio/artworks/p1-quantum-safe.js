/**
 * P1-006: Hybrid Quantum-Safe Cryptography Artwork
 * ================================================
 * 
 * A split sculpture showing classical key (brass) merging
 * with quantum key (iridescent). Live encryption demo.
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { PATENTS } from '../components/info-panel.js';

const PATENT = PATENTS.find(p => p.id === 'P1-006');

export class QuantumSafeArtwork extends THREE.Group {
    constructor() {
        super();
        this.name = 'artwork-quantum-safe';
        this.time = 0;
        
        this.classicalKey = null;
        this.quantumKey = null;
        this.mergePoint = null;
        this.encryptionDemo = null;
        
        this.create();
    }
    
    create() {
        // Base platform (vault door aesthetic)
        this.createVaultBase();
        
        // Classical key (left side - brass)
        this.createClassicalKey();
        
        // Quantum key (right side - iridescent)
        this.createQuantumKey();
        
        // Merge point (center)
        this.createMergePoint();
        
        // Data stream visualization
        this.createDataStream();
        
        // Live encryption display
        this.createEncryptionDisplay();
        
        // Plaque
        if (PATENT) {
            const plaque = createPlaque(PATENT, { width: 2.5, height: 1.5 });
            plaque.position.set(0, 0.8, 4);
            plaque.rotation.x = -0.2;
            this.add(plaque);
        }
    }
    
    createVaultBase() {
        // Circular vault door platform
        const baseGeo = new THREE.CylinderGeometry(3, 3.2, 0.4, 64);
        const baseMat = new THREE.MeshPhysicalMaterial({
            color: 0x1A1820,
            metalness: 0.9,
            roughness: 0.3,
            clearcoat: 0.5
        });
        const base = new THREE.Mesh(baseGeo, baseMat);
        base.position.y = 0.2;
        this.add(base);
        
        // Vault door rings
        for (let i = 0; i < 3; i++) {
            const ringGeo = new THREE.TorusGeometry(2 + i * 0.4, 0.05, 16, 64);
            const ringMat = new THREE.MeshBasicMaterial({
                color: 0xD4AF37, // Forge gold
                transparent: true,
                opacity: 0.5 - i * 0.1
            });
            const ring = new THREE.Mesh(ringGeo, ringMat);
            ring.rotation.x = Math.PI / 2;
            ring.position.y = 0.42;
            this.add(ring);
        }
        
        // Lock mechanism details
        this.createLockDetails();
    }
    
    createLockDetails() {
        // Decorative bolts around edge
        for (let i = 0; i < 12; i++) {
            const angle = (i / 12) * Math.PI * 2;
            const boltGeo = new THREE.CylinderGeometry(0.08, 0.08, 0.15, 16);
            const boltMat = new THREE.MeshStandardMaterial({
                color: 0xD4AF37,
                metalness: 0.8,
                roughness: 0.4
            });
            const bolt = new THREE.Mesh(boltGeo, boltMat);
            bolt.position.set(
                Math.cos(angle) * 2.9,
                0.35,
                Math.sin(angle) * 2.9
            );
            this.add(bolt);
        }
    }
    
    createClassicalKey() {
        // Traditional key shape (brass colored)
        const keyGroup = new THREE.Group();
        
        // Shaft
        const shaftGeo = new THREE.CylinderGeometry(0.1, 0.1, 2, 16);
        const shaftMat = new THREE.MeshPhysicalMaterial({
            color: 0xD4AF37,
            metalness: 0.9,
            roughness: 0.2,
            clearcoat: 0.8
        });
        const shaft = new THREE.Mesh(shaftGeo, shaftMat);
        shaft.rotation.z = Math.PI / 2;
        keyGroup.add(shaft);
        
        // Bow (handle)
        const bowGeo = new THREE.TorusGeometry(0.3, 0.1, 16, 32);
        const bow = new THREE.Mesh(bowGeo, shaftMat);
        bow.position.x = -1;
        keyGroup.add(bow);
        
        // Bits (teeth)
        for (let i = 0; i < 4; i++) {
            const bitGeo = new THREE.BoxGeometry(0.15, 0.1 + i * 0.05, 0.1);
            const bit = new THREE.Mesh(bitGeo, shaftMat);
            bit.position.set(0.5 + i * 0.2, -0.1 - i * 0.025, 0);
            keyGroup.add(bit);
        }
        
        // Label
        this.createKeyLabel(keyGroup, 'AES-256', 0xD4AF37, -0.5);
        
        this.classicalKey = keyGroup;
        keyGroup.position.set(-1.5, 2, 0);
        keyGroup.rotation.y = Math.PI / 4;
        this.add(keyGroup);
    }
    
    createQuantumKey() {
        // Quantum key (iridescent, crystalline)
        const keyGroup = new THREE.Group();
        
        // Main crystal shape
        const crystalGeo = new THREE.OctahedronGeometry(0.5, 0);
        const crystalMat = new THREE.MeshPhysicalMaterial({
            color: 0x67D4E4,
            metalness: 0.1,
            roughness: 0,
            transmission: 0.8,
            thickness: 1.0,
            iridescence: 1.0,
            iridescenceIOR: 1.3,
            transparent: true,
            opacity: 0.9
        });
        const crystal = new THREE.Mesh(crystalGeo, crystalMat);
        keyGroup.add(crystal);
        
        // Orbiting qubits
        for (let i = 0; i < 6; i++) {
            const qubitGeo = new THREE.SphereGeometry(0.08, 16, 16);
            const qubitMat = new THREE.MeshBasicMaterial({
                color: 0x67D4E4,
                transparent: true,
                opacity: 0.8
            });
            const qubit = new THREE.Mesh(qubitGeo, qubitMat);
            qubit.userData = { orbitAngle: (i / 6) * Math.PI * 2, orbitRadius: 0.8, orbitSpeed: 1 + i * 0.2 };
            keyGroup.add(qubit);
            this.orbits = this.orbits || [];
            this.orbits.push(qubit);
        }
        
        // Quantum uncertainty cloud
        const cloudGeo = new THREE.IcosahedronGeometry(0.7, 1);
        const cloudMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.1,
            wireframe: true
        });
        const cloud = new THREE.Mesh(cloudGeo, cloudMat);
        keyGroup.add(cloud);
        this.quantumCloud = cloud;
        
        // Label
        this.createKeyLabel(keyGroup, 'ML-KEM', 0x67D4E4, -0.5);
        
        this.quantumKey = keyGroup;
        keyGroup.position.set(1.5, 2, 0);
        keyGroup.rotation.y = -Math.PI / 4;
        this.add(keyGroup);
    }
    
    createKeyLabel(parent, text, color, yOffset) {
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 64;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = 'transparent';
        ctx.fillRect(0, 0, 256, 64);
        
        ctx.fillStyle = '#' + color.toString(16).padStart(6, '0');
        ctx.font = 'bold 28px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(text, 128, 40);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(1.5, 0.375);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.y = yOffset;
        parent.add(label);
    }
    
    createMergePoint() {
        // Central merge point where classical + quantum combine
        const mergeGroup = new THREE.Group();
        
        // Core sphere
        const coreGeo = new THREE.IcosahedronGeometry(0.4, 2);
        const coreMat = new THREE.MeshPhysicalMaterial({
            color: 0xFFFFFF,
            metalness: 0.5,
            roughness: 0.1,
            emissive: 0xD4AF37,
            emissiveIntensity: 0.3,
            clearcoat: 1.0
        });
        this.mergeCore = new THREE.Mesh(coreGeo, coreMat);
        mergeGroup.add(this.mergeCore);
        
        // Energy arcs connecting to both keys
        this.createEnergyArc(mergeGroup, new THREE.Vector3(-1.5, 0, 0), 0xD4AF37);
        this.createEnergyArc(mergeGroup, new THREE.Vector3(1.5, 0, 0), 0x67D4E4);
        
        // "Hybrid" label
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 64;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = 'transparent';
        ctx.fillRect(0, 0, 256, 64);
        ctx.fillStyle = '#FFFFFF';
        ctx.font = 'bold 24px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('HYBRID', 128, 40);
        
        const texture = new THREE.CanvasTexture(canvas);
        const labelGeo = new THREE.PlaneGeometry(1.2, 0.3);
        const labelMat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.y = -0.7;
        mergeGroup.add(label);
        
        this.mergePoint = mergeGroup;
        mergeGroup.position.set(0, 2.5, 0);
        this.add(mergeGroup);
    }
    
    createEnergyArc(parent, targetOffset, color) {
        const curve = new THREE.QuadraticBezierCurve3(
            new THREE.Vector3(0, 0, 0),
            new THREE.Vector3(targetOffset.x * 0.5, 0.3, 0),
            targetOffset
        );
        
        const arcGeo = new THREE.TubeGeometry(curve, 32, 0.03, 8, false);
        const arcMat = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.6
        });
        const arc = new THREE.Mesh(arcGeo, arcMat);
        parent.add(arc);
    }
    
    createDataStream() {
        // Data packets flowing between components
        const packetCount = 30;
        this.dataPackets = [];
        
        const packetGeo = new THREE.BoxGeometry(0.1, 0.1, 0.1);
        
        for (let i = 0; i < packetCount; i++) {
            const packet = new THREE.Mesh(
                packetGeo,
                new THREE.MeshBasicMaterial({
                    color: Math.random() > 0.5 ? 0xD4AF37 : 0x67D4E4,
                    transparent: true,
                    opacity: 0
                })
            );
            packet.userData = {
                active: false,
                progress: 0,
                path: Math.floor(Math.random() * 3), // 0: classical->merge, 1: quantum->merge, 2: merge->out
                speed: 0.3 + Math.random() * 0.3
            };
            this.dataPackets.push(packet);
            this.add(packet);
        }
    }
    
    createEncryptionDisplay() {
        // Display showing encryption in action
        const displayGroup = new THREE.Group();
        
        // Screen background
        const screenGeo = new THREE.PlaneGeometry(2.5, 1.5);
        const screenMat = new THREE.MeshBasicMaterial({
            color: 0x0A0A15,
            transparent: true,
            opacity: 0.9
        });
        const screen = new THREE.Mesh(screenGeo, screenMat);
        displayGroup.add(screen);
        
        // Border
        const borderGeo = new THREE.PlaneGeometry(2.6, 1.6);
        const borderMat = new THREE.MeshBasicMaterial({
            color: 0xD4AF37,
            transparent: true,
            opacity: 0.5
        });
        const border = new THREE.Mesh(borderGeo, borderMat);
        border.position.z = -0.01;
        displayGroup.add(border);
        
        // Text display (will be updated)
        this.displayCanvas = document.createElement('canvas');
        this.displayCanvas.width = 512;
        this.displayCanvas.height = 256;
        this.displayTexture = new THREE.CanvasTexture(this.displayCanvas);
        
        const textGeo = new THREE.PlaneGeometry(2.4, 1.4);
        const textMat = new THREE.MeshBasicMaterial({
            map: this.displayTexture,
            transparent: true
        });
        const textMesh = new THREE.Mesh(textGeo, textMat);
        textMesh.position.z = 0.01;
        displayGroup.add(textMesh);
        
        displayGroup.position.set(0, 1, 3.5);
        displayGroup.rotation.x = -0.3;
        this.add(displayGroup);
        
        // Initial display update
        this.updateEncryptionDisplay('Ready', 'SECURE');
    }
    
    updateEncryptionDisplay(plaintext, ciphertext) {
        const ctx = this.displayCanvas.getContext('2d');
        
        ctx.fillStyle = '#0A0A15';
        ctx.fillRect(0, 0, 512, 256);
        
        // Header
        ctx.fillStyle = '#D4AF37';
        ctx.font = '16px "IBM Plex Mono", monospace';
        ctx.fillText('QUANTUM-SAFE ENCRYPTION', 20, 30);
        
        // Plaintext
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.fillText('INPUT:', 20, 70);
        ctx.fillStyle = '#F5F0E8';
        ctx.font = '18px "IBM Plex Mono", monospace';
        ctx.fillText(plaintext.substring(0, 30), 20, 95);
        
        // Arrow
        ctx.fillStyle = '#67D4E4';
        ctx.font = '24px sans-serif';
        ctx.fillText('↓ ML-KEM + AES-256-GCM', 100, 140);
        
        // Ciphertext
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.fillText('OUTPUT:', 20, 185);
        ctx.fillStyle = '#67D4E4';
        ctx.font = '18px "IBM Plex Mono", monospace';
        ctx.fillText(ciphertext.substring(0, 30), 20, 210);
        
        // Status
        ctx.fillStyle = '#7EB77F';
        ctx.font = 'bold 14px "IBM Plex Sans", sans-serif';
        ctx.fillText('● QUANTUM RESISTANT', 20, 245);
        
        this.displayTexture.needsUpdate = true;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ANIMATION
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        this.time += deltaTime;
        
        // Rotate classical key gently
        if (this.classicalKey) {
            this.classicalKey.rotation.z = Math.sin(this.time * 0.5) * 0.1;
        }
        
        // Animate quantum key orbits
        if (this.orbits) {
            this.orbits.forEach(qubit => {
                const angle = qubit.userData.orbitAngle + this.time * qubit.userData.orbitSpeed;
                const r = qubit.userData.orbitRadius;
                qubit.position.x = Math.cos(angle) * r;
                qubit.position.y = Math.sin(angle * 1.5) * r * 0.5;
                qubit.position.z = Math.sin(angle) * r;
            });
        }
        
        // Quantum uncertainty cloud shimmer
        if (this.quantumCloud) {
            this.quantumCloud.rotation.x = this.time * 0.3;
            this.quantumCloud.rotation.y = this.time * 0.5;
            this.quantumCloud.scale.setScalar(1 + Math.sin(this.time * 2) * 0.1);
        }
        
        // Pulse merge core
        if (this.mergeCore) {
            const pulse = Math.sin(this.time * 3) * 0.5 + 0.5;
            this.mergeCore.material.emissiveIntensity = 0.3 + pulse * 0.3;
            this.mergeCore.scale.setScalar(1 + Math.sin(this.time * 2) * 0.05);
            
            // Alternate emissive color between gold and cyan
            const colorLerp = Math.sin(this.time) * 0.5 + 0.5;
            this.mergeCore.material.emissive.setHex(
                colorLerp > 0.5 ? 0xD4AF37 : 0x67D4E4
            );
        }
        
        // Animate data packets
        this.dataPackets.forEach(packet => {
            if (packet.userData.active) {
                packet.userData.progress += deltaTime * packet.userData.speed;
                
                if (packet.userData.progress >= 1) {
                    packet.userData.active = false;
                    packet.material.opacity = 0;
                } else {
                    const t = packet.userData.progress;
                    
                    // Different paths
                    switch (packet.userData.path) {
                        case 0: // Classical to merge
                            packet.position.lerpVectors(
                                new THREE.Vector3(-1.5, 2, 0),
                                new THREE.Vector3(0, 2.5, 0),
                                t
                            );
                            packet.material.color.setHex(0xD4AF37);
                            break;
                        case 1: // Quantum to merge
                            packet.position.lerpVectors(
                                new THREE.Vector3(1.5, 2, 0),
                                new THREE.Vector3(0, 2.5, 0),
                                t
                            );
                            packet.material.color.setHex(0x67D4E4);
                            break;
                        case 2: // Merge to output
                            packet.position.lerpVectors(
                                new THREE.Vector3(0, 2.5, 0),
                                new THREE.Vector3(0, 1, 3),
                                t
                            );
                            packet.material.color.setHex(0xFFFFFF);
                            break;
                    }
                    
                    packet.material.opacity = Math.sin(t * Math.PI);
                    packet.rotation.x = t * Math.PI * 2;
                    packet.rotation.y = t * Math.PI * 3;
                }
            } else if (Math.random() < deltaTime * 0.5) {
                // Spawn new packet
                packet.userData.active = true;
                packet.userData.progress = 0;
                packet.userData.path = Math.floor(Math.random() * 3);
            }
        });
        
        // Track active packet count for interaction intensity
        const activePackets = this.dataPackets.filter(p => p.userData.active).length;
        const intensity = activePackets / this.dataPackets.length;
        
        // Qubits orbit faster during high encryption activity
        if (this.orbits) {
            this.orbits.forEach(qubit => {
                const speedBoost = 1 + intensity * 2;
                const angle = qubit.userData.orbitAngle + this.time * qubit.userData.orbitSpeed * speedBoost;
                const r = qubit.userData.orbitRadius;
                qubit.position.x = Math.cos(angle) * r;
                qubit.position.y = Math.sin(angle * 1.5) * r * 0.5;
                qubit.position.z = Math.sin(angle) * r;
                
                // Brighter during activity
                qubit.material.emissiveIntensity = 0.3 + intensity * 0.7;
            });
        }
        
        // Merge core sparkles when packets arrive (path 0 or 1 at progress ~1)
        let arrivalSparkle = 0;
        this.dataPackets.forEach(packet => {
            if (packet.userData.active && packet.userData.path < 2) {
                if (packet.userData.progress > 0.8 && packet.userData.progress < 1.0) {
                    arrivalSparkle += 0.3;
                }
            }
        });
        if (this.mergeCore && arrivalSparkle > 0) {
            this.mergeCore.material.emissiveIntensity += arrivalSparkle;
            this.mergeCore.scale.setScalar(1 + arrivalSparkle * 0.15);
        }
        
        // Keys drift toward merge during activity
        if (this.classicalKey && intensity > 0.3) {
            const drift = Math.sin(this.time * 3) * 0.1 * intensity;
            this.classicalKey.position.x = -1.5 + drift;
        }
        if (this.quantumGroup && intensity > 0.3) {
            const drift = Math.sin(this.time * 3 + Math.PI) * 0.1 * intensity;
            this.quantumGroup.position.x = 1.5 - drift;
        }
        
        // Update display periodically with typing animation feel
        if (Math.floor(this.time * 2) !== Math.floor((this.time - deltaTime) * 2)) {
            const plaintexts = ['Hello World', 'h(x) >= 0', 'SECURE DATA', 'Kagami 鏡'];
            const ciphertexts = ['0x7f3b2c...9e4d', '0xa1b2c3...f0e1', '0x48656c...6f21', '0x4b6167...616d'];
            const idx = Math.floor(this.time * 0.5) % plaintexts.length;
            this.updateEncryptionDisplay(plaintexts[idx], ciphertexts[idx]);
        }
    }
    
    dispose() {
        this.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
        });
    }
}

export function createQuantumSafeArtwork() {
    return new QuantumSafeArtwork();
}

export default QuantumSafeArtwork;
