// Room 1: The Entrance Prism — Infinite Refraction
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js';
import { CONFIG } from '../config.js';

export class PrismRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.prism = null;
        this.rays = [];
        this.reflectionPrisms = [];
        this.rotation = 0;
        this.targetRotation = 0;
        this.isDragging = false;
        this.previousMouseX = 0;
        this.hasPlayedDispersion = false;
        this.cubeCamera = null;
        this.cubeRenderTarget = null;
        
        this.init();
    }
    
    init() {
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(CONFIG.COLORS.VOID);
        
        // Add fog for depth
        this.scene.fog = new THREE.FogExp2(CONFIG.COLORS.VOID, 0.03);
        
        // Camera
        this.camera = new THREE.PerspectiveCamera(
            50,
            this.container.clientWidth / this.container.clientHeight,
            0.1,
            1000
        );
        this.camera.position.set(0, 0, 8);
        
        // Renderer with better settings
        this.renderer = new THREE.WebGLRenderer({ 
            antialias: true, 
            alpha: true,
            powerPreference: 'high-performance'
        });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
        this.renderer.toneMappingExposure = 1.2;
        this.container.appendChild(this.renderer.domElement);
        
        // Create CubeCamera for reflections
        this.cubeRenderTarget = new THREE.WebGLCubeRenderTarget(256, {
            format: THREE.RGBAFormat,
            generateMipmaps: true,
            minFilter: THREE.LinearMipmapLinearFilter
        });
        this.cubeCamera = new THREE.CubeCamera(0.1, 100, this.cubeRenderTarget);
        this.scene.add(this.cubeCamera);
        
        // Create the scene
        this.createPrism();
        this.createInfiniteReflections();
        this.createSpectrumRays();
        this.createLightBeam();
        this.createAmbientParticles();
        this.setupLighting();
        
        // Event listeners
        this.setupEventListeners();
        
        // Play entrance sound
        if (this.sound) {
            this.sound.playLightEnter();
        }
        
        // Start animation
        this.animate();
    }
    
    createPrism() {
        // Create PROPER triangular prism using ExtrudeGeometry
        const triangleShape = new THREE.Shape();
        const size = 1.2;
        
        // Equilateral triangle
        triangleShape.moveTo(0, size);
        triangleShape.lineTo(-size * Math.cos(Math.PI / 6), -size * Math.sin(Math.PI / 6));
        triangleShape.lineTo(size * Math.cos(Math.PI / 6), -size * Math.sin(Math.PI / 6));
        triangleShape.lineTo(0, size);
        
        const extrudeSettings = {
            depth: 2,
            bevelEnabled: true,
            bevelThickness: 0.05,
            bevelSize: 0.05,
            bevelSegments: 3
        };
        
        const prismGeometry = new THREE.ExtrudeGeometry(triangleShape, extrudeSettings);
        prismGeometry.center();
        
        // Crystalline material with actual refraction
        const prismMaterial = new THREE.MeshPhysicalMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.15,
            metalness: 0,
            roughness: 0,
            transmission: 0.95,      // Glass transmission
            thickness: 1.5,          // Glass thickness
            ior: 1.52,               // Crown glass index of refraction
            envMap: this.cubeRenderTarget.texture,
            envMapIntensity: 1.5,
            clearcoat: 1,
            clearcoatRoughness: 0,
            reflectivity: 1,
        });
        
        this.prism = new THREE.Mesh(prismGeometry, prismMaterial);
        this.prism.rotation.y = Math.PI / 4;
        this.scene.add(this.prism);
        
        // Add wireframe overlay for crystalline edge effect
        const wireframeMaterial = new THREE.MeshBasicMaterial({
            color: CONFIG.COLORS.PRIMARY,
            wireframe: true,
            transparent: true,
            opacity: 0.3
        });
        const wireframePrism = new THREE.Mesh(prismGeometry.clone(), wireframeMaterial);
        this.prism.add(wireframePrism);
        
        // Add edge glow
        const edgesGeometry = new THREE.EdgesGeometry(prismGeometry);
        const edgesMaterial = new THREE.LineBasicMaterial({ 
            color: CONFIG.COLORS.LIGHT,
            transparent: true,
            opacity: 0.8
        });
        const edges = new THREE.LineSegments(edgesGeometry, edgesMaterial);
        this.prism.add(edges);
    }
    
    createInfiniteReflections() {
        // Create multiple smaller prisms at various depths for infinite reflection illusion
        const reflectionCount = 12;
        const prismGeometry = this.prism.geometry.clone();
        
        for (let i = 0; i < reflectionCount; i++) {
            const scale = 0.3 / (1 + i * 0.4);
            const distance = 3 + i * 2;
            const angle = (i / reflectionCount) * Math.PI * 2;
            
            // Create ghost prism
            const ghostMaterial = new THREE.MeshPhysicalMaterial({
                color: CONFIG.COLORS.PRIMARY,
                transparent: true,
                opacity: 0.15 / (1 + i * 0.3),
                metalness: 0.3,
                roughness: 0.1,
                emissive: CONFIG.COLORS.PRIMARY,
                emissiveIntensity: 0.1 / (1 + i * 0.5),
            });
            
            const ghostPrism = new THREE.Mesh(prismGeometry, ghostMaterial);
            ghostPrism.scale.setScalar(scale);
            ghostPrism.position.set(
                Math.cos(angle) * distance,
                Math.sin(angle * 0.7) * (distance * 0.3),
                -distance * 0.5
            );
            ghostPrism.rotation.y = angle;
            
            this.reflectionPrisms.push({
                mesh: ghostPrism,
                angle: angle,
                distance: distance,
                speed: 0.001 + Math.random() * 0.002,
                phase: Math.random() * Math.PI * 2
            });
            
            this.scene.add(ghostPrism);
        }
        
        // Create mirror planes for actual reflections
        this.createMirrorPlanes();
    }
    
    createMirrorPlanes() {
        // Left mirror
        const mirrorGeometry = new THREE.PlaneGeometry(20, 20);
        const mirrorMaterial = new THREE.MeshPhysicalMaterial({
            color: 0x111122,
            metalness: 0.9,
            roughness: 0.1,
            envMap: this.cubeRenderTarget.texture,
            envMapIntensity: 0.8,
            transparent: true,
            opacity: 0.3,
        });
        
        const leftMirror = new THREE.Mesh(mirrorGeometry, mirrorMaterial);
        leftMirror.position.set(-8, 0, 0);
        leftMirror.rotation.y = Math.PI / 2;
        this.scene.add(leftMirror);
        
        const rightMirror = new THREE.Mesh(mirrorGeometry, mirrorMaterial.clone());
        rightMirror.position.set(8, 0, 0);
        rightMirror.rotation.y = -Math.PI / 2;
        this.scene.add(rightMirror);
    }
    
    createLightBeam() {
        // Incoming white light beam (volumetric-ish)
        const beamGroup = new THREE.Group();
        
        // Core beam
        const beamGeometry = new THREE.CylinderGeometry(0.08, 0.08, 5, 16);
        const beamMaterial = new THREE.MeshBasicMaterial({
            color: CONFIG.COLORS.WHITE,
            transparent: true,
            opacity: 0.9
        });
        const beam = new THREE.Mesh(beamGeometry, beamMaterial);
        beam.rotation.z = Math.PI / 2;
        beam.position.x = -4;
        beamGroup.add(beam);
        
        // Glow effect (multiple transparent layers)
        for (let i = 1; i <= 4; i++) {
            const glowGeometry = new THREE.CylinderGeometry(0.08 + i * 0.1, 0.08 + i * 0.1, 5, 16);
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: CONFIG.COLORS.WHITE,
                transparent: true,
                opacity: 0.15 / i
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            glow.rotation.z = Math.PI / 2;
            glow.position.x = -4;
            beamGroup.add(glow);
        }
        
        this.scene.add(beamGroup);
    }
    
    createSpectrumRays() {
        const colors = Object.entries(CONFIG.COLORS.SPECTRUM);
        const startX = 1.5;
        const endX = 8;
        
        colors.forEach(([name, color], index) => {
            // Calculate dispersion angle (red bends least, violet bends most)
            const baseAngle = -0.25;
            const dispersionFactor = index / (colors.length - 1);
            const angle = baseAngle + (dispersionFactor * 0.5);
            
            const rayGroup = new THREE.Group();
            
            // Main ray
            const length = 6 + index * 0.3;
            const rayGeometry = new THREE.CylinderGeometry(0.03, 0.02, length, 8);
            const rayMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.85
            });
            const ray = new THREE.Mesh(rayGeometry, rayMaterial);
            ray.rotation.z = Math.PI / 2 - angle;
            ray.position.set(startX + length / 2 * Math.cos(angle), length / 2 * Math.sin(angle), 0);
            rayGroup.add(ray);
            
            // Ray glow
            const glowGeometry = new THREE.CylinderGeometry(0.08, 0.06, length, 8);
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.2
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            glow.rotation.z = Math.PI / 2 - angle;
            glow.position.copy(ray.position);
            rayGroup.add(glow);
            
            // Outer glow
            const outerGlowGeometry = new THREE.CylinderGeometry(0.15, 0.12, length, 8);
            const outerGlowMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.08
            });
            const outerGlow = new THREE.Mesh(outerGlowGeometry, outerGlowMaterial);
            outerGlow.rotation.z = Math.PI / 2 - angle;
            outerGlow.position.copy(ray.position);
            rayGroup.add(outerGlow);
            
            this.rays.push({
                group: rayGroup,
                baseAngle: angle,
                color: color,
                index: index
            });
            
            this.scene.add(rayGroup);
        });
    }
    
    createAmbientParticles() {
        // Floating crystal dust particles
        const particleCount = 200;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        const sizes = new Float32Array(particleCount);
        
        const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
        
        for (let i = 0; i < particleCount; i++) {
            // Spread particles in a sphere around the prism
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            const radius = 2 + Math.random() * 6;
            
            positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            positions[i * 3 + 2] = radius * Math.cos(phi) - 2;
            
            // Random spectrum color
            const color = new THREE.Color(spectrumColors[Math.floor(Math.random() * spectrumColors.length)]);
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
            
            sizes[i] = Math.random() * 3 + 1;
        }
        
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        geometry.setAttribute('size', new THREE.BufferAttribute(sizes, 1));
        
        const material = new THREE.PointsMaterial({
            size: 0.05,
            vertexColors: true,
            transparent: true,
            opacity: 0.6,
            blending: THREE.AdditiveBlending,
            sizeAttenuation: true
        });
        
        this.particles = new THREE.Points(geometry, material);
        this.scene.add(this.particles);
    }
    
    setupLighting() {
        // Ambient
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.3);
        this.scene.add(ambientLight);
        
        // Key light (blue, from above)
        const keyLight = new THREE.PointLight(CONFIG.COLORS.PRIMARY, 1, 50);
        keyLight.position.set(0, 5, 5);
        this.scene.add(keyLight);
        
        // Fill light (subtle)
        const fillLight = new THREE.PointLight(CONFIG.COLORS.LIGHT, 0.5, 30);
        fillLight.position.set(-5, 0, 3);
        this.scene.add(fillLight);
        
        // Spectrum lights (one for each color, positioned along output rays)
        const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
        spectrumColors.forEach((color, i) => {
            const light = new THREE.PointLight(color, 0.3, 10);
            const angle = -0.25 + (i / 6) * 0.5;
            light.position.set(5 + i * 0.5, i * 0.5 - 1.5, 0);
            this.scene.add(light);
        });
    }
    
    setupEventListeners() {
        // Mouse drag to rotate prism
        this.renderer.domElement.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.previousMouseX = e.clientX;
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!this.isDragging) return;
            
            const deltaX = e.clientX - this.previousMouseX;
            this.targetRotation += deltaX * 0.01;
            this.previousMouseX = e.clientX;
            
            // Sound feedback
            if (this.sound && Math.abs(deltaX) > 2) {
                this.sound.playPrismRotate(deltaX > 0 ? 1 : -1);
            }
        });
        
        document.addEventListener('mouseup', () => {
            this.isDragging = false;
        });
        
        // Touch support
        this.renderer.domElement.addEventListener('touchstart', (e) => {
            this.isDragging = true;
            this.previousMouseX = e.touches[0].clientX;
        });
        
        this.renderer.domElement.addEventListener('touchmove', (e) => {
            if (!this.isDragging) return;
            const deltaX = e.touches[0].clientX - this.previousMouseX;
            this.targetRotation += deltaX * 0.01;
            this.previousMouseX = e.touches[0].clientX;
        });
        
        this.renderer.domElement.addEventListener('touchend', () => {
            this.isDragging = false;
        });
        
        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize());
    }
    
    onWindowResize() {
        this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    }
    
    animate() {
        requestAnimationFrame(() => this.animate());
        
        const time = performance.now() * 0.001;
        
        // Auto-rotate prism slowly when not dragging
        if (!this.isDragging) {
            this.targetRotation += CONFIG.PRISM.rotationSpeed;
        }
        
        // Smooth rotation
        this.rotation += (this.targetRotation - this.rotation) * 0.08;
        this.prism.rotation.y = this.rotation;
        
        // Animate reflection prisms (infinite reflection effect)
        this.reflectionPrisms.forEach((rp, i) => {
            rp.mesh.rotation.y = this.rotation * (1 + i * 0.1);
            rp.mesh.rotation.x = Math.sin(time * rp.speed + rp.phase) * 0.2;
            
            // Subtle breathing/pulsing
            const scale = 0.3 / (1 + i * 0.4) * (1 + Math.sin(time * 0.5 + rp.phase) * 0.1);
            rp.mesh.scale.setScalar(scale);
        });
        
        // Animate spectrum rays based on rotation
        this.rays.forEach((ray, index) => {
            const rotationInfluence = Math.sin(this.rotation) * 0.15;
            const newAngle = ray.baseAngle + rotationInfluence;
            
            // Rotate the ray group
            ray.group.rotation.z = rotationInfluence * (index * 0.1);
            ray.group.position.y = Math.sin(time + index * 0.3) * 0.05;
        });
        
        // Animate particles
        if (this.particles) {
            const positions = this.particles.geometry.attributes.position.array;
            for (let i = 0; i < positions.length; i += 3) {
                positions[i + 1] += Math.sin(time + i) * 0.002;
                positions[i] += Math.cos(time * 0.5 + i) * 0.001;
            }
            this.particles.geometry.attributes.position.needsUpdate = true;
            this.particles.rotation.y = time * 0.02;
        }
        
        // Update cube camera for reflections (every few frames for performance)
        if (Math.floor(time * 10) % 5 === 0) {
            this.prism.visible = false;
            this.cubeCamera.update(this.renderer, this.scene);
            this.prism.visible = true;
        }
        
        // Play dispersion sound once when visible and rotated enough
        if (this.sound && !this.hasPlayedDispersion && Math.abs(this.rotation) > 0.5) {
            this.sound.playDispersion();
            this.hasPlayedDispersion = true;
        }
        
        this.renderer.render(this.scene, this.camera);
    }
    
    destroy() {
        this.renderer.dispose();
        this.container.innerHTML = '';
    }
}
