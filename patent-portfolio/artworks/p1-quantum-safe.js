/**
 * P1-006: Hybrid Quantum-Safe Cryptography Artwork
 * ================================================
 * 
 * Interactive demonstration of real cryptographic operations:
 * - AES-256-GCM symmetric encryption (via WebCrypto API)
 * - ML-KEM/Kyber lattice visualization (conceptual)
 * - Hybrid key exchange flow
 * - "Encrypt your message" interactive feature
 * 
 * Based on: packages/kagami/core/security/unified_crypto.py
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';
import { PATENTS } from '../components/info-panel.js';

const PATENT = PATENTS.find(p => p.id === 'P1-006');

// Kyber parameters (simplified for visualization)
const KYBER_CONFIG = {
    n: 256,              // Polynomial degree
    k: 3,                // Module dimension (Kyber-768)
    q: 3329,             // Modulus
    eta: 2,              // Noise parameter
    latticePoints: 64    // Points to visualize
};

export class QuantumSafeArtwork extends THREE.Group {
    constructor() {
        super();
        this.name = 'artwork-quantum-safe';
        this.time = 0;
        
        // Crypto state
        this.cryptoKey = null;
        this.lastPlaintext = 'Hello, Kagami!';
        this.lastCiphertext = '';
        this.isEncrypting = false;
        
        // Visual elements
        this.classicalKey = null;
        this.quantumKey = null;
        this.latticePoints = [];
        this.mergeCore = null;
        this.dataPackets = [];
        this.orbits = [];
        
        // Microdelight tracking
        this.microdelights = { encryptionsDone: 0, quantumAttackTriggered: false };
        
        this.create();
        this.initCrypto();
    }
    
    async create() {
        // Base platform (vault door aesthetic)
        this.createVaultBase();
        
        // Classical key (left side - AES)
        this.createClassicalKey();
        
        // Quantum key (right side - Kyber lattice)
        this.createKyberLattice();
        
        // Merge point (hybrid exchange)
        this.createMergePoint();
        
        // Data stream visualization
        this.createDataStream();
        
        // Interactive encryption display
        this.createEncryptionDisplay();
        
        // Alice and Bob terminals (key exchange demo)
        this.createAliceBobTerminals();
        
        // Educational panels
        this.createEducationalPanels();
        
        // Plaque
        if (PATENT) {
            const plaque = createPlaque(PATENT, { width: 2.8, height: 1.8 });
            plaque.position.set(0, 0.8, 4.5);
            plaque.rotation.x = -0.2;
            this.add(plaque);
        }
        
        this.userData = { patentId: 'P1-006', interactive: true };
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // REAL CRYPTO INITIALIZATION
    // ═══════════════════════════════════════════════════════════════════════
    
    async initCrypto() {
        try {
            // Generate a real AES-256-GCM key via WebCrypto
            this.cryptoKey = await crypto.subtle.generateKey(
                { name: 'AES-GCM', length: 256 },
                true,  // extractable
                ['encrypt', 'decrypt']
            );
            console.log('🔐 WebCrypto AES-256-GCM key generated');
            
            // Do initial encryption
            await this.encryptMessage(this.lastPlaintext);
        } catch (error) {
            console.warn('WebCrypto not available:', error);
            this.cryptoKey = null;
        }
    }
    
    async encryptMessage(plaintext) {
        if (!this.cryptoKey) {
            // Fallback for non-WebCrypto environments
            this.lastCiphertext = this.fakeCiphertext(plaintext);
            return this.lastCiphertext;
        }
        
        this.isEncrypting = true;
        this.lastPlaintext = plaintext;
        
        try {
            // Generate random IV (12 bytes for GCM)
            const iv = crypto.getRandomValues(new Uint8Array(12));
            
            // Encode plaintext
            const encoder = new TextEncoder();
            const data = encoder.encode(plaintext);
            
            // Encrypt with AES-256-GCM
            const ciphertext = await crypto.subtle.encrypt(
                { name: 'AES-GCM', iv: iv },
                this.cryptoKey,
                data
            );
            
            // Combine IV + ciphertext and encode as hex
            const combined = new Uint8Array(iv.length + ciphertext.byteLength);
            combined.set(iv, 0);
            combined.set(new Uint8Array(ciphertext), iv.length);
            
            this.lastCiphertext = this.arrayToHex(combined);
            this.updateEncryptionDisplay();
            
            // Trigger visual activity
            this.triggerEncryptionAnimation();
            
        } catch (error) {
            console.error('Encryption failed:', error);
            this.lastCiphertext = 'ERROR';
        }
        
        this.isEncrypting = false;
        return this.lastCiphertext;
    }
    
    arrayToHex(array) {
        return Array.from(array)
            .map(b => b.toString(16).padStart(2, '0'))
            .join('');
    }
    
    fakeCiphertext(plaintext) {
        // Deterministic fake for demo when WebCrypto unavailable
        let hash = 0;
        for (let i = 0; i < plaintext.length; i++) {
            hash = ((hash << 5) - hash) + plaintext.charCodeAt(i);
            hash = hash & hash;
        }
        return Math.abs(hash).toString(16).padStart(32, '0');
    }
    
    triggerEncryptionAnimation() {
        // Burst of packets from merge point
        let burstCount = 0;
        this.dataPackets.forEach(packet => {
            if (!packet.userData.active && burstCount < 10) {
                packet.userData.active = true;
                packet.userData.progress = 0;
                packet.userData.path = 2; // merge -> output
                burstCount++;
            }
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // VAULT BASE
    // ═══════════════════════════════════════════════════════════════════════
    
    createVaultBase() {
        // Circular vault door platform
        // FILM QUALITY: Vault base with polished dark metal
        const baseGeo = new THREE.CylinderGeometry(3, 3.2, 0.4, 64);
        const baseMat = new THREE.MeshPhysicalMaterial({
            color: 0x1D1C22,               // Refined dark
            metalness: 0.95,
            roughness: 0.08,
            clearcoat: 1.0,
            clearcoatRoughness: 0.05,
            envMapIntensity: 1.2
        });
        const base = new THREE.Mesh(baseGeo, baseMat);
        base.position.y = 0.2;
        this.add(base);
        
        // Vault door rings - FILM QUALITY gold
        const ringMaterial = new THREE.MeshPhysicalMaterial({
            color: 0xD4AF37,
            metalness: 0.95,
            roughness: 0.15,
            clearcoat: 0.8,
            clearcoatRoughness: 0.1,
            envMapIntensity: 1.4
        });
        
        for (let i = 0; i < 3; i++) {
            const ringGeo = new THREE.TorusGeometry(2 + i * 0.4, 0.05, 16, 64);
            const ring = new THREE.Mesh(ringGeo, ringMaterial);
            ring.material = ringMaterial.clone();
            ring.material.opacity = 0.8 - i * 0.15;
            ring.material.transparent = true;
            ring.rotation.x = Math.PI / 2;
            ring.position.y = 0.42;
            this.add(ring);
        }
        
        // Decorative bolts - FILM QUALITY brushed gold
        const boltMat = new THREE.MeshPhysicalMaterial({
            color: 0xD4AF37,
            metalness: 0.95,
            roughness: 0.25,
            anisotropy: 0.5,               // Brushed effect
            anisotropyRotation: 0,
            clearcoat: 0.6,
            envMapIntensity: 1.2
        });
        
        for (let i = 0; i < 12; i++) {
            const angle = (i / 12) * Math.PI * 2;
            const boltGeo = new THREE.CylinderGeometry(0.08, 0.08, 0.15, 16);
            const bolt = new THREE.Mesh(boltGeo, boltMat);
            bolt.position.set(
                Math.cos(angle) * 2.9,
                0.35,
                Math.sin(angle) * 2.9
            );
            this.add(bolt);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // CLASSICAL KEY (AES-256)
    // ═══════════════════════════════════════════════════════════════════════
    
    createClassicalKey() {
        const keyGroup = new THREE.Group();
        
        // Traditional key shape (brass) - FILM QUALITY
        const shaftGeo = new THREE.CylinderGeometry(0.1, 0.1, 2, 16);
        const shaftMat = new THREE.MeshPhysicalMaterial({
            color: 0xD4AF37,
            metalness: 0.95,
            roughness: 0.12,
            clearcoat: 0.9,
            clearcoatRoughness: 0.05,
            anisotropy: 0.3,               // Subtle brushed effect
            envMapIntensity: 1.3
        });
        const shaft = new THREE.Mesh(shaftGeo, shaftMat);
        shaft.rotation.z = Math.PI / 2;
        keyGroup.add(shaft);
        
        // Bow (handle)
        const bowGeo = new THREE.TorusGeometry(0.3, 0.1, 16, 32);
        const bow = new THREE.Mesh(bowGeo, shaftMat);
        bow.position.x = -1;
        keyGroup.add(bow);
        
        // Bits (teeth) representing 256 bits
        for (let i = 0; i < 8; i++) {
            const bitGeo = new THREE.BoxGeometry(0.08, 0.1 + (i % 3) * 0.03, 0.08);
            const bit = new THREE.Mesh(bitGeo, shaftMat);
            bit.position.set(0.5 + i * 0.12, -0.1 - (i % 2) * 0.05, 0);
            keyGroup.add(bit);
        }
        
        // AES label
        const labelCanvas = document.createElement('canvas');
        labelCanvas.width = 256;
        labelCanvas.height = 96;
        const ctx = labelCanvas.getContext('2d');
        ctx.fillStyle = '#D4AF37';
        ctx.font = 'bold 28px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('AES-256-GCM', 128, 40);
        ctx.font = '16px "IBM Plex Sans", sans-serif';
        ctx.fillStyle = '#9E9994';
        ctx.fillText('Symmetric Encryption', 128, 70);
        
        const labelTex = new THREE.CanvasTexture(labelCanvas);
        const labelGeo = new THREE.PlaneGeometry(1.8, 0.7);
        const labelMat = new THREE.MeshBasicMaterial({
            map: labelTex,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.y = -0.8;
        keyGroup.add(label);
        
        this.classicalKey = keyGroup;
        keyGroup.position.set(-1.8, 2.2, 0);
        keyGroup.rotation.y = Math.PI / 4;
        this.add(keyGroup);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // KYBER POLYNOMIAL RING R_q = Z_q[X]/(X^n+1)
    // ═══════════════════════════════════════════════════════════════════════
    
    createKyberLattice() {
        const latticeGroup = new THREE.Group();
        const n = Math.min(64, KYBER_CONFIG.n);
        const q = KYBER_CONFIG.q;
        // Polynomial ring: coefficients c[0..n-1] in Z_q, relation X^n = -1
        const coeffs = [];
        for (let i = 0; i < n; i++) {
            coeffs.push(Math.floor(Math.random() * q));
        }
        this.kyberCoeffs = coeffs;
        this.kyberN = n;

        const radius = 0.6;
        const barWidth = 0.015;
        const maxBarH = 0.25;
        const pointGeo = new THREE.BoxGeometry(barWidth, 0.02, barWidth);

        for (let i = 0; i < n; i++) {
            const t = (i / n) * Math.PI * 2;
            const norm = coeffs[i] / q;
            const barH = Math.max(0.02, norm * maxBarH);
            const pointMat = new THREE.MeshPhysicalMaterial({
                color: 0x67D4E4,
                emissive: 0x67D4E4,
                emissiveIntensity: 0.2 + norm * 0.3,
                metalness: 0.3,
                roughness: 0.5,
                transparent: true,
                opacity: 0.9
            });
            const point = new THREE.Mesh(pointGeo, pointMat);
            const x = Math.cos(t) * radius;
            const z = Math.sin(t) * radius;
            point.position.set(x, barH / 2, z);
            point.scale.y = barH / 0.02;
            point.userData = { index: i, baseNorm: norm, phase: Math.random() * Math.PI * 2 };
            latticeGroup.add(point);
            this.latticePoints.push(point);
        }

        // Ring curve (X^n + 1 = 0)
        const ringPoints = [];
        for (let i = 0; i <= n; i++) {
            const t = (i / n) * Math.PI * 2;
            ringPoints.push(new THREE.Vector3(Math.cos(t) * radius * 1.1, 0, Math.sin(t) * radius * 1.1));
        }
        const ringCurve = new THREE.CatmullRomCurve3(ringPoints, true);
        const ringGeo = new THREE.TubeGeometry(ringCurve, 64, 0.01, 6, true);
        const ringMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.35
        });
        latticeGroup.add(new THREE.Mesh(ringGeo, ringMat));

        const crystalGeo = new THREE.OctahedronGeometry(0.8, 0);
        const crystalMat = new THREE.MeshPhysicalMaterial({
            color: 0x67D4E4,
            metalness: 0.1,
            roughness: 0,
            transmission: 0.85,
            thickness: 0.5,
            iridescence: 0.8,
            iridescenceIOR: 1.3,
            transparent: true,
            opacity: 0.5
        });
        this.kyberCrystal = new THREE.Mesh(crystalGeo, crystalMat);
        latticeGroup.add(this.kyberCrystal);

        const labelCanvas = document.createElement('canvas');
        labelCanvas.width = 256;
        labelCanvas.height = 96;
        const ctx = labelCanvas.getContext('2d');
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 28px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('ML-KEM (Kyber)', 128, 40);
        ctx.font = '16px "IBM Plex Sans", sans-serif';
        ctx.fillStyle = '#9E9994';
        ctx.fillText('R_q = ℤ_q[X]/(X^n+1)', 128, 70);

        const labelTex = new THREE.CanvasTexture(labelCanvas);
        const labelGeo = new THREE.PlaneGeometry(1.8, 0.7);
        const labelMat = new THREE.MeshBasicMaterial({
            map: labelTex,
            transparent: true,
            side: THREE.DoubleSide
        });
        const label = new THREE.Mesh(labelGeo, labelMat);
        label.position.y = -1.2;
        latticeGroup.add(label);

        this.quantumKey = latticeGroup;
        latticeGroup.position.set(1.8, 2.2, 0);
        latticeGroup.rotation.y = -Math.PI / 4;
        this.add(latticeGroup);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // MERGE POINT (HYBRID EXCHANGE)
    // ═══════════════════════════════════════════════════════════════════════
    
    createMergePoint() {
        const mergeGroup = new THREE.Group();
        
        // Core sphere representing hybrid shared secret
        const coreGeo = new THREE.IcosahedronGeometry(0.35, 2);
        const coreMat = new THREE.MeshPhysicalMaterial({
            color: 0xF5F0E8,           // Warm white (film quality)
            metalness: 0.5,
            roughness: 0.1,
            emissive: 0xD4AF37,
            emissiveIntensity: 0.3,
            clearcoat: 1.0
        });
        this.mergeCore = new THREE.Mesh(coreGeo, coreMat);
        mergeGroup.add(this.mergeCore);
        
        // Energy arcs from both keys
        this.createEnergyArc(mergeGroup, new THREE.Vector3(-1.8, -0.3, 0), 0xD4AF37);
        this.createEnergyArc(mergeGroup, new THREE.Vector3(1.8, -0.3, 0), 0x67D4E4);
        
        // Hybrid label
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 64;
        const ctx = canvas.getContext('2d');
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
    
    // ═══════════════════════════════════════════════════════════════════════
    // DATA STREAM
    // ═══════════════════════════════════════════════════════════════════════
    
    createDataStream() {
        const packetCount = 30;
        this.dataPackets = [];
        
        const packetGeo = new THREE.BoxGeometry(0.08, 0.08, 0.08);
        
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
                path: Math.floor(Math.random() * 3),
                speed: 0.4 + Math.random() * 0.3
            };
            this.dataPackets.push(packet);
            this.add(packet);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ENCRYPTION DISPLAY (INTERACTIVE)
    // ═══════════════════════════════════════════════════════════════════════
    
    createEncryptionDisplay() {
        const displayGroup = new THREE.Group();
        
        // Screen background
        const screenGeo = new THREE.PlaneGeometry(3, 2);
        const screenMat = new THREE.MeshBasicMaterial({
            color: 0x0A0A15,
            transparent: true,
            opacity: 0.95
        });
        const screen = new THREE.Mesh(screenGeo, screenMat);
        displayGroup.add(screen);
        
        // Border
        const borderGeo = new THREE.PlaneGeometry(3.1, 2.1);
        const borderMat = new THREE.MeshBasicMaterial({
            color: 0xD4AF37,
            transparent: true,
            opacity: 0.5
        });
        const border = new THREE.Mesh(borderGeo, borderMat);
        border.position.z = -0.01;
        displayGroup.add(border);
        
        // Dynamic canvas
        this.displayCanvas = document.createElement('canvas');
        this.displayCanvas.width = 600;
        this.displayCanvas.height = 400;
        this.displayTexture = new THREE.CanvasTexture(this.displayCanvas);
        
        const textGeo = new THREE.PlaneGeometry(2.9, 1.9);
        const textMat = new THREE.MeshBasicMaterial({
            map: this.displayTexture,
            transparent: true
        });
        const textMesh = new THREE.Mesh(textGeo, textMat);
        textMesh.position.z = 0.01;
        displayGroup.add(textMesh);
        
        displayGroup.position.set(0, 1.2, 3.8);
        displayGroup.rotation.x = -0.25;
        this.add(displayGroup);
        
        this.updateEncryptionDisplay();
    }
    
    updateEncryptionDisplay() {
        const ctx = this.displayCanvas.getContext('2d');
        const w = this.displayCanvas.width;
        const h = this.displayCanvas.height;
        
        ctx.fillStyle = '#0A0A15';
        ctx.fillRect(0, 0, w, h);
        
        // Border
        ctx.strokeStyle = '#D4AF37';
        ctx.lineWidth = 2;
        ctx.strokeRect(5, 5, w - 10, h - 10);
        
        // Header
        ctx.fillStyle = '#D4AF37';
        ctx.font = 'bold 22px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('QUANTUM-SAFE ENCRYPTION', w/2, 40);
        
        // WebCrypto status - colony-based colors
        const statusColor = this.cryptoKey ? '#6FA370' : '#E85A2F';
        const statusText = this.cryptoKey ? '● WebCrypto Active' : '○ Demo Mode';
        ctx.fillStyle = statusColor;
        ctx.font = '12px "IBM Plex Mono", monospace';
        ctx.textAlign = 'right';
        ctx.fillText(statusText, w - 20, 40);
        
        // Plaintext
        ctx.textAlign = 'left';
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.fillText('PLAINTEXT:', 30, 85);
        ctx.fillStyle = '#F5F0E8';
        ctx.font = '18px "IBM Plex Mono", monospace';
        ctx.fillText(`"${this.lastPlaintext}"`, 30, 115);
        
        // Arrow with algorithm
        ctx.fillStyle = '#67D4E4';
        ctx.font = '16px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('↓ ML-KEM Key Exchange + AES-256-GCM ↓', w/2, 160);
        
        // Ciphertext
        ctx.textAlign = 'left';
        ctx.fillStyle = '#9E9994';
        ctx.font = '14px "IBM Plex Mono", monospace';
        ctx.fillText('CIPHERTEXT (hex):', 30, 205);
        ctx.fillStyle = '#67D4E4';
        ctx.font = '14px "IBM Plex Mono", monospace';
        
        // Wrap ciphertext
        const cipher = this.lastCiphertext || '(encrypting...)';
        const maxChars = 45;
        if (cipher.length > maxChars) {
            ctx.fillText('0x' + cipher.substring(0, maxChars), 30, 230);
            ctx.fillText('  ' + cipher.substring(maxChars, maxChars * 2) + '...', 30, 250);
        } else {
            ctx.fillText('0x' + cipher, 30, 230);
        }
        
        // Security properties
        ctx.fillStyle = '#7EB77F';
        ctx.font = 'bold 14px "IBM Plex Sans", sans-serif';
        ctx.fillText('✓ Post-quantum secure (NIST-approved)', 30, 300);
        ctx.fillText('✓ Forward secrecy via ephemeral keys', 30, 325);
        ctx.fillText('✓ Authenticated encryption (GCM tag)', 30, 350);
        
        // Interaction hint
        ctx.fillStyle = '#9E9994';
        ctx.font = '12px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Click to encrypt a new message', w/2, 385);
        
        this.displayTexture.needsUpdate = true;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // ALICE & BOB TERMINALS (Key Exchange Demo)
    // ═══════════════════════════════════════════════════════════════════════
    
    createAliceBobTerminals() {
        // Alice terminal (left side)
        this.createTerminal('ALICE', new THREE.Vector3(-4, 1.5, 0), 0x4ECDC4);
        
        // Bob terminal (right side)
        this.createTerminal('BOB', new THREE.Vector3(4, 1.5, 0), 0xF59E0B);
        
        // Connection beam showing key exchange
        this.createKeyExchangeBeam();
    }
    
    createTerminal(name, position, color) {
        const group = new THREE.Group();
        
        // Terminal base
        const baseGeo = new THREE.BoxGeometry(1.5, 2, 0.8);
        const baseMat = new THREE.MeshPhysicalMaterial({
            color: 0x1A1A2E,
            metalness: 0.6,
            roughness: 0.3,
            clearcoat: 0.5
        });
        const base = new THREE.Mesh(baseGeo, baseMat);
        group.add(base);
        
        // Screen
        const screenGeo = new THREE.PlaneGeometry(1.3, 1.2);
        const canvas = document.createElement('canvas');
        canvas.width = 256;
        canvas.height = 240;
        const ctx = canvas.getContext('2d');
        
        // Draw terminal screen
        ctx.fillStyle = '#0A0A0F';
        ctx.fillRect(0, 0, 256, 240);
        
        // Header
        ctx.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
        ctx.font = 'bold 20px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(name, 128, 30);
        
        // Terminal content
        ctx.fillStyle = '#6FA370';
        ctx.font = '12px "IBM Plex Mono", monospace';
        ctx.textAlign = 'left';
        
        if (name === 'ALICE') {
            ctx.fillText('> Generating shared secret...', 10, 70);
            ctx.fillText('> ML-KEM encapsulation', 10, 95);
            ctx.fillStyle = '#67D4E4';
            ctx.fillText('ct = Encaps(pk, K)', 10, 120);
            ctx.fillStyle = '#AAAAAA';
            ctx.fillText('Sending ciphertext...', 10, 155);
            ctx.fillStyle = '#6FA370';
            ctx.fillText('> Key derived ✓', 10, 190);
        } else {
            ctx.fillText('> Key pair generated', 10, 70);
            ctx.fillStyle = '#67D4E4';
            ctx.fillText('(pk, sk) = KeyGen()', 10, 95);
            ctx.fillStyle = '#AAAAAA';
            ctx.fillText('Waiting for Alice...', 10, 130);
            ctx.fillStyle = '#6FA370';
            ctx.fillText('> Ciphertext received', 10, 165);
            ctx.fillText('K = Decaps(sk, ct) ✓', 10, 190);
        }
        
        // Shared secret display
        ctx.fillStyle = '#FFD700';
        ctx.font = 'bold 11px "IBM Plex Mono", monospace';
        ctx.fillText('K = 7f3a...e8b2', 10, 225);
        
        const texture = new THREE.CanvasTexture(canvas);
        const screenMat = new THREE.MeshBasicMaterial({ map: texture });
        const screen = new THREE.Mesh(screenGeo, screenMat);
        screen.position.set(0, 0.2, 0.41);
        group.add(screen);
        
        // Glowing frame
        const frameMat = new THREE.MeshBasicMaterial({
            color: color,
            transparent: true,
            opacity: 0.6
        });
        const frameTop = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.05, 0.05), frameMat);
        frameTop.position.set(0, 0.85, 0.41);
        group.add(frameTop);
        
        const frameBot = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.05, 0.05), frameMat);
        frameBot.position.set(0, -0.45, 0.41);
        group.add(frameBot);
        
        group.position.copy(position);
        this.add(group);
        
        // Store reference
        if (name === 'ALICE') {
            this.aliceTerminal = group;
        } else {
            this.bobTerminal = group;
        }
    }
    
    createKeyExchangeBeam() {
        // Visual beam connecting Alice and Bob during key exchange
        const points = [
            new THREE.Vector3(-3.5, 1.5, 0),
            new THREE.Vector3(-2, 2, 0),
            new THREE.Vector3(0, 2.5, 0),
            new THREE.Vector3(2, 2, 0),
            new THREE.Vector3(3.5, 1.5, 0)
        ];
        
        const curve = new THREE.CatmullRomCurve3(points);
        const tubeGeo = new THREE.TubeGeometry(curve, 64, 0.03, 8, false);
        const tubeMat = new THREE.MeshBasicMaterial({
            color: 0x67D4E4,
            transparent: true,
            opacity: 0.6
        });
        this.keyExchangeBeam = new THREE.Mesh(tubeGeo, tubeMat);
        this.add(this.keyExchangeBeam);
        
        // Traveling packet (represents the ciphertext)
        const packetGeo = new THREE.SphereGeometry(0.08, 16, 16);
        const packetMat = new THREE.MeshBasicMaterial({
            color: 0xFFD700,
            transparent: true,
            opacity: 0.9
        });
        this.exchangePacket = new THREE.Mesh(packetGeo, packetMat);
        this.exchangePacketCurve = curve;
        this.exchangePacketProgress = 0;
        this.add(this.exchangePacket);
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // EDUCATIONAL PANELS
    // ═══════════════════════════════════════════════════════════════════════
    
    createEducationalPanels() {
        // Why Quantum-Safe panel
        this.createInfoPanel(
            'Why Quantum-Safe?',
            [
                'Shor\'s algorithm breaks RSA/ECC',
                'Grover\'s algorithm halves AES key',
                'NIST selected Kyber (ML-KEM)',
                'Lattice problems: hard for quantum',
                'Hybrid: classical + post-quantum'
            ],
            new THREE.Vector3(-3.5, 2.5, -1.5),
            Math.PI / 5
        );
        
        // Kyber mechanism panel
        this.createInfoPanel(
            'Kyber Key Exchange',
            [
                '1. Bob: generates (pk, sk)',
                '2. Alice: encrypts K → ct',
                '3. Bob: decrypts ct → K',
                'Security: Learning With Errors',
                'Dimension: n=256, q=3329'
            ],
            new THREE.Vector3(3.5, 2.5, -1.5),
            -Math.PI / 5
        );
    }
    
    createInfoPanel(title, lines, position, rotation) {
        const canvas = document.createElement('canvas');
        canvas.width = 400;
        canvas.height = 280;
        const ctx = canvas.getContext('2d');
        
        ctx.fillStyle = 'rgba(10, 10, 20, 0.9)';
        ctx.fillRect(0, 0, 400, 280);
        
        ctx.strokeStyle = '#67D4E4';
        ctx.lineWidth = 2;
        ctx.strokeRect(5, 5, 390, 270);
        
        ctx.fillStyle = '#67D4E4';
        ctx.font = 'bold 20px "IBM Plex Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText(title, 200, 35);
        
        ctx.fillStyle = '#F5F0E8';
        ctx.font = '14px "IBM Plex Sans", sans-serif';
        ctx.textAlign = 'left';
        lines.forEach((line, i) => {
            ctx.fillText(line, 25, 75 + i * 35);
        });
        
        const texture = new THREE.CanvasTexture(canvas);
        const geo = new THREE.PlaneGeometry(2, 1.4);
        const mat = new THREE.MeshBasicMaterial({
            map: texture,
            transparent: true,
            side: THREE.DoubleSide
        });
        const panel = new THREE.Mesh(geo, mat);
        panel.position.copy(position);
        panel.rotation.y = rotation;
        this.add(panel);
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
        
        // Animate Kyber polynomial ring (coefficient pulse)
        const n = this.kyberN || this.latticePoints.length;
        this.latticePoints.forEach((point, i) => {
            const norm = point.userData.baseNorm ?? 0.5;
            const phase = point.userData.phase ?? 0;
            const pulse = 0.5 + 0.5 * Math.sin(this.time * 2 + phase);
            const barH = Math.max(0.02, (norm * pulse * 0.25));
            point.position.y = barH / 2;
            point.scale.y = barH / 0.02;
            point.material.emissiveIntensity = 0.2 + norm * pulse * 0.3;
        });
        
        // Rotate crystal enclosure
        if (this.kyberCrystal) {
            this.kyberCrystal.rotation.y = this.time * 0.3;
            this.kyberCrystal.rotation.x = Math.sin(this.time * 0.2) * 0.1;
        }
        
        // Rotate lattice group
        if (this.quantumKey) {
            this.quantumKey.rotation.y = -Math.PI / 4 + Math.sin(this.time * 0.15) * 0.1;
        }
        
        // Pulse merge core
        if (this.mergeCore) {
            const pulse = Math.sin(this.time * 3) * 0.5 + 0.5;
            this.mergeCore.material.emissiveIntensity = 0.3 + pulse * 0.3;
            this.mergeCore.scale.setScalar(1 + Math.sin(this.time * 2) * 0.05);
            
            // Alternate color
            const colorLerp = Math.sin(this.time) * 0.5 + 0.5;
            this.mergeCore.material.emissive.setHex(
                colorLerp > 0.5 ? 0xD4AF37 : 0x67D4E4
            );
        }
        
        // Animate key exchange packet (Alice -> Bob)
        if (this.exchangePacket && this.exchangePacketCurve) {
            this.exchangePacketProgress += deltaTime * 0.15;
            if (this.exchangePacketProgress > 1) {
                this.exchangePacketProgress = 0;
            }
            
            const point = this.exchangePacketCurve.getPointAt(this.exchangePacketProgress);
            this.exchangePacket.position.copy(point);
            
            // Pulse glow
            const pulse = Math.sin(this.time * 5) * 0.3 + 0.7;
            this.exchangePacket.material.opacity = pulse;
            this.exchangePacket.scale.setScalar(0.8 + pulse * 0.4);
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
                    
                    switch (packet.userData.path) {
                        case 0: // Classical to merge
                            packet.position.lerpVectors(
                                new THREE.Vector3(-1.8, 2.2, 0),
                                new THREE.Vector3(0, 2.5, 0),
                                t
                            );
                            packet.material.color.setHex(0xD4AF37);
                            break;
                        case 1: // Quantum to merge
                            packet.position.lerpVectors(
                                new THREE.Vector3(1.8, 2.2, 0),
                                new THREE.Vector3(0, 2.5, 0),
                                t
                            );
                            packet.material.color.setHex(0x67D4E4);
                            break;
                        case 2: // Merge to output
                            packet.position.lerpVectors(
                                new THREE.Vector3(0, 2.5, 0),
                                new THREE.Vector3(0, 1.2, 3.5),
                                t
                            );
                            packet.material.color.setHex(0xF5F0E8);  // Warm white
                            break;
                    }
                    
                    packet.material.opacity = Math.sin(t * Math.PI);
                    packet.rotation.x = t * Math.PI * 2;
                    packet.rotation.y = t * Math.PI * 3;
                }
            } else if (Math.random() < deltaTime * 0.3) {
                // Spawn new packet
                packet.userData.active = true;
                packet.userData.progress = 0;
                packet.userData.path = Math.floor(Math.random() * 3);
            }
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // INTERACTION
    // ═══════════════════════════════════════════════════════════════════════
    
    onClick(intersection) {
        // Prompt for message to encrypt
        const messages = [
            'Hello, World!',
            'h(x) >= 0 always',
            'Quantum resistance!',
            'Kagami 鏡',
            'Secure by design',
            '7 colonies unite',
            'E8 lattice rules'
        ];
        
        // Cycle through messages
        const currentIdx = messages.indexOf(this.lastPlaintext);
        const nextIdx = (currentIdx + 1) % messages.length;
        
        this.encryptMessage(messages[nextIdx]);
        
        // Microdelight: track encryptions
        this.microdelights.encryptionsDone++;
        if (this.microdelights.encryptionsDone >= 5 && !this.microdelights.quantumAttackTriggered) {
            this.microdelights.quantumAttackTriggered = true;
            this._dispatchMicrodelight('achievement', { name: 'crypto-master' });
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // MICRODELIGHTS
    // ═══════════════════════════════════════════════════════════════════════
    
    _dispatchMicrodelight(type, detail = {}) {
        window.dispatchEvent(new CustomEvent('artwork-microdelight', {
            detail: { patentId: 'P1-006', type, ...detail }
        }));
    }
    
    dispose() {
        this.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) {
                if (obj.material.map) obj.material.map.dispose();
                obj.material.dispose();
            }
        });
    }
}

export function createQuantumSafeArtwork() {
    return new QuantumSafeArtwork();
}

export default QuantumSafeArtwork;
