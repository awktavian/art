// Room 2: The Proof Lattice — Infinite Crystal Matrix
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js';
import { CONFIG, TEST_DATA } from '../config.js';

export class LatticeRoom {
    constructor(container, nodeInfoElement, soundSystem = null) {
        this.container = container;
        this.nodeInfoElement = nodeInfoElement;
        this.sound = soundSystem;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.nodes = [];
        this.connections = [];
        this.latticeGroup = null;  // Single group for rotation (FIX for the bug)
        this.mirrorLattices = [];
        this.rotation = { x: 0, y: 0 };
        this.targetRotation = { x: 0, y: 0 };
        this.isDragging = false;
        this.previousMouse = { x: 0, y: 0 };
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();
        this.hoveredNode = null;
        this.hasPlayedActivation = false;
        
        this.init();
    }
    
    init() {
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(CONFIG.COLORS.VOID);
        this.scene.fog = new THREE.FogExp2(CONFIG.COLORS.VOID, 0.02);
        
        // Camera
        this.camera = new THREE.PerspectiveCamera(
            60,
            this.container.clientWidth / this.container.clientHeight,
            0.1,
            1000
        );
        this.camera.position.set(0, 0, 18);
        
        // Renderer
        this.renderer = new THREE.WebGLRenderer({ 
            antialias: true, 
            alpha: true,
            powerPreference: 'high-performance'
        });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.container.appendChild(this.renderer.domElement);
        
        // Create main lattice group (this fixes the rotation bug)
        this.latticeGroup = new THREE.Group();
        this.scene.add(this.latticeGroup);
        
        // Create the lattice
        this.createLattice();
        this.createInfiniteMirrors();
        this.createAmbientParticles();
        this.setupLighting();
        
        // Event listeners
        this.setupEventListeners();
        
        // Play activation sound
        if (this.sound && !this.hasPlayedActivation) {
            setTimeout(() => {
                this.sound.playLatticeActivate();
                this.hasPlayedActivation = true;
            }, 500);
        }
        
        // Start animation
        this.animate();
    }
    
    createLattice() {
        const gridSize = CONFIG.LATTICE.gridSize;
        const spacing = 1.8;
        const offset = (gridSize - 1) * spacing / 2;
        
        // Create nodes in a more interesting pattern (face-centered cubic for crystal structure)
        const nodePositions = [];
        
        // Regular grid
        for (let x = 0; x < gridSize; x++) {
            for (let y = 0; y < gridSize; y++) {
                for (let z = 0; z < gridSize; z++) {
                    nodePositions.push({
                        x: x * spacing - offset,
                        y: y * spacing - offset,
                        z: z * spacing - offset,
                        type: 'corner'
                    });
                }
            }
        }
        
        // Face-centered positions (FCC lattice, like diamond)
        for (let x = 0; x < gridSize - 1; x++) {
            for (let y = 0; y < gridSize - 1; y++) {
                for (let z = 0; z < gridSize - 1; z++) {
                    // Face centers
                    nodePositions.push({
                        x: (x + 0.5) * spacing - offset,
                        y: (y + 0.5) * spacing - offset,
                        z: z * spacing - offset,
                        type: 'face'
                    });
                }
            }
        }
        
        // Create visual nodes
        const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
        
        nodePositions.forEach((pos, i) => {
            // Vary node appearance based on position
            const distFromCenter = Math.sqrt(pos.x * pos.x + pos.y * pos.y + pos.z * pos.z);
            const colorIndex = Math.floor((distFromCenter / 8) * 7) % 7;
            
            const geometry = new THREE.IcosahedronGeometry(
                pos.type === 'corner' ? 0.2 : 0.12,
                1
            );
            
            const material = new THREE.MeshPhysicalMaterial({
                color: spectrumColors[colorIndex],
                emissive: spectrumColors[colorIndex],
                emissiveIntensity: 0.4,
                transparent: true,
                opacity: 0.85,
                metalness: 0.3,
                roughness: 0.2,
            });
            
            const node = new THREE.Mesh(geometry, material);
            node.position.set(pos.x, pos.y, pos.z);
            
            // Add glow
            const glowGeometry = new THREE.IcosahedronGeometry(
                (pos.type === 'corner' ? 0.2 : 0.12) * 2,
                0
            );
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: spectrumColors[colorIndex],
                transparent: true,
                opacity: 0.15
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            node.add(glow);
            
            // Store metadata
            node.userData = {
                id: `node_${i}`,
                position: pos,
                colorIndex: colorIndex,
                testData: TEST_DATA.nodes[i % TEST_DATA.nodes.length],
                originalScale: pos.type === 'corner' ? 1 : 0.6
            };
            
            this.nodes.push(node);
            this.latticeGroup.add(node);
        });
        
        // Create connections with gradient colors
        this.createConnections(spacing);
    }
    
    createConnections(spacing) {
        const connectionDistance = spacing * 1.2;
        
        for (let i = 0; i < this.nodes.length; i++) {
            for (let j = i + 1; j < this.nodes.length; j++) {
                const distance = this.nodes[i].position.distanceTo(this.nodes[j].position);
                if (distance < connectionDistance) {
                    // Create gradient line
                    const points = [this.nodes[i].position.clone(), this.nodes[j].position.clone()];
                    const geometry = new THREE.BufferGeometry().setFromPoints(points);
                    
                    // Color based on average of connected nodes
                    const colorI = this.nodes[i].userData.colorIndex;
                    const colorJ = this.nodes[j].userData.colorIndex;
                    const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
                    
                    const material = new THREE.LineBasicMaterial({
                        color: spectrumColors[Math.floor((colorI + colorJ) / 2)],
                        transparent: true,
                        opacity: 0.12
                    });
                    
                    const line = new THREE.Line(geometry, material);
                    this.connections.push(line);
                    this.latticeGroup.add(line);
                }
            }
        }
    }
    
    createInfiniteMirrors() {
        // Create reflected lattice copies for infinite mirror effect
        const reflectionCount = 6;
        const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
        
        for (let i = 0; i < reflectionCount; i++) {
            const angle = (i / reflectionCount) * Math.PI * 2;
            const distance = 25 + i * 8;
            
            // Create ghost lattice (simplified)
            const ghostGroup = new THREE.Group();
            
            // Just create sparse nodes for the reflection
            for (let j = 0; j < 20; j++) {
                const geometry = new THREE.IcosahedronGeometry(0.15, 0);
                const material = new THREE.MeshBasicMaterial({
                    color: spectrumColors[j % 7],
                    transparent: true,
                    opacity: 0.2 / (1 + i * 0.5)
                });
                const node = new THREE.Mesh(geometry, material);
                node.position.set(
                    (Math.random() - 0.5) * 8,
                    (Math.random() - 0.5) * 8,
                    (Math.random() - 0.5) * 8
                );
                ghostGroup.add(node);
            }
            
            ghostGroup.position.set(
                Math.cos(angle) * distance,
                Math.sin(angle * 0.5) * 5,
                Math.sin(angle) * distance
            );
            ghostGroup.scale.setScalar(0.5 / (1 + i * 0.3));
            
            this.mirrorLattices.push({
                group: ghostGroup,
                angle: angle,
                distance: distance,
                speed: 0.0005 + Math.random() * 0.001
            });
            
            this.scene.add(ghostGroup);
        }
    }
    
    createAmbientParticles() {
        const particleCount = 300;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
        
        for (let i = 0; i < particleCount; i++) {
            positions[i * 3] = (Math.random() - 0.5) * 40;
            positions[i * 3 + 1] = (Math.random() - 0.5) * 40;
            positions[i * 3 + 2] = (Math.random() - 0.5) * 40;
            
            const color = new THREE.Color(spectrumColors[Math.floor(Math.random() * 7)]);
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
        }
        
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const material = new THREE.PointsMaterial({
            size: 0.08,
            vertexColors: true,
            transparent: true,
            opacity: 0.4,
            blending: THREE.AdditiveBlending
        });
        
        this.particles = new THREE.Points(geometry, material);
        this.scene.add(this.particles);
    }
    
    setupLighting() {
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.4);
        this.scene.add(ambientLight);
        
        // Multiple colored point lights
        const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
        spectrumColors.forEach((color, i) => {
            const angle = (i / 7) * Math.PI * 2;
            const light = new THREE.PointLight(color, 0.4, 20);
            light.position.set(
                Math.cos(angle) * 8,
                Math.sin(angle) * 8,
                5
            );
            this.scene.add(light);
        });
        
        // Key light
        const keyLight = new THREE.PointLight(CONFIG.COLORS.PRIMARY, 0.8, 50);
        keyLight.position.set(0, 10, 10);
        this.scene.add(keyLight);
    }
    
    setupEventListeners() {
        // Mouse drag to rotate lattice
        this.renderer.domElement.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.previousMouse = { x: e.clientX, y: e.clientY };
        });
        
        document.addEventListener('mousemove', (e) => {
            // Update mouse for raycasting
            const rect = this.renderer.domElement.getBoundingClientRect();
            this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
            
            if (!this.isDragging) {
                this.checkNodeHover();
                return;
            }
            
            const deltaX = e.clientX - this.previousMouse.x;
            const deltaY = e.clientY - this.previousMouse.y;
            this.targetRotation.y += deltaX * 0.005;
            this.targetRotation.x += deltaY * 0.005;
            this.previousMouse = { x: e.clientX, y: e.clientY };
        });
        
        document.addEventListener('mouseup', () => {
            this.isDragging = false;
        });
        
        // Touch support
        this.renderer.domElement.addEventListener('touchstart', (e) => {
            this.isDragging = true;
            this.previousMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        });
        
        this.renderer.domElement.addEventListener('touchmove', (e) => {
            if (!this.isDragging) return;
            const deltaX = e.touches[0].clientX - this.previousMouse.x;
            const deltaY = e.touches[0].clientY - this.previousMouse.y;
            this.targetRotation.y += deltaX * 0.005;
            this.targetRotation.x += deltaY * 0.005;
            this.previousMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        });
        
        this.renderer.domElement.addEventListener('touchend', () => {
            this.isDragging = false;
        });
        
        // Click to select node
        this.renderer.domElement.addEventListener('click', () => {
            this.checkNodeClick();
        });
        
        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize());
    }
    
    checkNodeHover() {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.nodes);
        
        // Reset previously hovered node
        if (this.hoveredNode) {
            const scale = this.hoveredNode.userData.originalScale;
            this.hoveredNode.scale.set(scale, scale, scale);
            this.hoveredNode.material.emissiveIntensity = 0.4;
            this.hoveredNode = null;
        }
        
        if (intersects.length > 0) {
            this.hoveredNode = intersects[0].object;
            this.hoveredNode.scale.set(1.8, 1.8, 1.8);
            this.hoveredNode.material.emissiveIntensity = 1;
            
            if (this.sound) {
                this.sound.playNodeHover();
            }
        }
    }
    
    checkNodeClick() {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.nodes);
        
        if (intersects.length > 0) {
            const clickedNode = intersects[0].object;
            const data = clickedNode.userData.testData;
            const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
            const nodeColor = spectrumColors[clickedNode.userData.colorIndex];
            
            this.nodeInfoElement.querySelector('.node-info-data').innerHTML = `
                <strong style="color: ${nodeColor}">Test:</strong> ${data.name}<br>
                <strong style="color: ${nodeColor}">Status:</strong> 
                    <span style="color: #00FF00">✓ ${data.status}</span><br>
                <strong style="color: ${nodeColor}">Coverage:</strong> ${data.coverage}%<br>
                <strong style="color: ${nodeColor}">ID:</strong> ${data.id}<br>
                <span style="font-size: 0.7rem; color: var(--text-whisper)">
                    Position: (${clickedNode.position.x.toFixed(1)}, 
                              ${clickedNode.position.y.toFixed(1)}, 
                              ${clickedNode.position.z.toFixed(1)})
                </span>
            `;
            this.nodeInfoElement.classList.add('visible');
            
            if (this.sound) {
                this.sound.playNodeClick();
            }
            
            // Flash effect on clicked node
            clickedNode.material.emissiveIntensity = 2;
            setTimeout(() => {
                clickedNode.material.emissiveIntensity = 0.4;
            }, 200);
        } else {
            this.nodeInfoElement.classList.remove('visible');
        }
    }
    
    onWindowResize() {
        this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        
        const time = performance.now() * 0.001;
        
        // Auto-rotate if not dragging
        if (!this.isDragging) {
            this.targetRotation.y += CONFIG.LATTICE.rotationSpeed;
        }
        
        // Smooth rotation interpolation
        this.rotation.x += (this.targetRotation.x - this.rotation.x) * 0.05;
        this.rotation.y += (this.targetRotation.y - this.rotation.y) * 0.05;
        
        // Apply rotation to the lattice group (FIXED - no longer creating new Object3D each frame)
        this.latticeGroup.rotation.x = this.rotation.x;
        this.latticeGroup.rotation.y = this.rotation.y;
        
        // Animate individual nodes (subtle pulsing)
        this.nodes.forEach((node, i) => {
            const pulse = 1 + Math.sin(time * 2 + i * 0.1) * 0.05;
            const baseScale = node.userData.originalScale;
            if (!this.hoveredNode || node !== this.hoveredNode) {
                node.scale.setScalar(baseScale * pulse);
            }
        });
        
        // Animate mirror lattices
        this.mirrorLattices.forEach((ml, i) => {
            ml.group.rotation.y = this.rotation.y * (1 + i * 0.2);
            ml.group.rotation.x = Math.sin(time * 0.3 + i) * 0.2;
            
            // Orbit slowly
            const orbitAngle = ml.angle + time * ml.speed;
            ml.group.position.x = Math.cos(orbitAngle) * ml.distance;
            ml.group.position.z = Math.sin(orbitAngle) * ml.distance;
        });
        
        // Animate particles
        if (this.particles) {
            this.particles.rotation.y = time * 0.02;
            this.particles.rotation.x = Math.sin(time * 0.1) * 0.1;
        }
        
        this.renderer.render(this.scene, this.camera);
    }
    
    destroy() {
        this.renderer.dispose();
        this.container.innerHTML = '';
    }
}
