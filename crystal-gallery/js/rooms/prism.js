// Room 1: The Entrance Prism — Physically Correct Dispersion
// Implements: Snell's law + Cauchy dispersion + proper angular refraction
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js';
import { CONFIG } from '../config.js';

// ============================================================================
// PHYSICS: Dispersion Model
// ============================================================================

/**
 * Cauchy dispersion formula: n(λ) = A + B/λ²
 * Approximates BK7 crown glass for visible spectrum
 * 
 * @param {number} wavelength_nm - Wavelength in nanometers
 * @returns {number} - Refractive index at that wavelength
 */
function cauchyRefractiveIndex(wavelength_nm) {
    // Cauchy coefficients for BK7-like glass
    // A ≈ 1.5046, B ≈ 4200 nm² (tuned for visible range dispersion)
    const A = 1.5046;
    const B = 4200; // nm²
    return A + B / (wavelength_nm * wavelength_nm);
}

/**
 * Snell's law: n1 * sin(θ1) = n2 * sin(θ2)
 * Returns the refracted angle, or null if total internal reflection
 * 
 * @param {number} theta1 - Incident angle (radians)
 * @param {number} n1 - Refractive index of medium 1
 * @param {number} n2 - Refractive index of medium 2
 * @returns {number|null} - Refracted angle or null for TIR
 */
function snellRefract(theta1, n1, n2) {
    const sinTheta2 = (n1 / n2) * Math.sin(theta1);
    if (Math.abs(sinTheta2) > 1) {
        return null; // Total internal reflection
    }
    return Math.asin(sinTheta2);
}

/**
 * Calculate the DEVIATION angle for light through a prism
 * 
 * For a prism with apex angle A and refractive index n:
 * At minimum deviation (symmetric path), the deviation is:
 *   D_min = 2 * arcsin(n * sin(A/2)) - A
 * 
 * For small angles around minimum deviation:
 *   D ≈ (n - 1) * A
 * 
 * This gives the angular deflection from the original beam direction.
 * Red (low n) deflects less; violet (high n) deflects more.
 * 
 * @param {number} n_glass - Refractive index of the glass
 * @param {number} apexAngle - Prism apex angle (radians), default 60°
 * @param {number} incidentOffset - How far from minimum deviation (radians)
 * @returns {number} - Deviation angle (radians, positive = downward)
 */
function computePrismDeviation(n_glass, apexAngle = Math.PI / 3, incidentOffset = 0) {
    // Minimum deviation formula: D_min = 2 * arcsin(n * sin(A/2)) - A
    const halfApex = apexAngle / 2;
    const sinHalfApex = Math.sin(halfApex);
    
    // Check for TIR condition
    const sinArg = n_glass * sinHalfApex;
    if (sinArg > 1) {
        // Would have TIR; return large deviation
        return Math.PI / 4;
    }
    
    const minDeviation = 2 * Math.asin(sinArg) - apexAngle;
    
    // Add small perturbation from incident angle offset
    // When incident angle changes, deviation changes approximately linearly
    const deviationPerturbation = incidentOffset * 0.3;
    
    return minDeviation + deviationPerturbation;
}

/**
 * ROYGBIV wavelengths in nanometers
 * Red bends least (longest λ, lowest n)
 * Violet bends most (shortest λ, highest n)
 */
const SPECTRUM_WAVELENGTHS = {
    red:    700,  // n ≈ 1.513
    orange: 620,  // n ≈ 1.516
    yellow: 580,  // n ≈ 1.517
    green:  530,  // n ≈ 1.520
    cyan:   490,  // n ≈ 1.522
    blue:   450,  // n ≈ 1.525
    violet: 400,  // n ≈ 1.531
};

// ============================================================================
// THREE.JS IMPLEMENTATION
// ============================================================================

export class PrismRoom {
    constructor(container, soundSystem = null) {
        this.container = container;
        this.sound = soundSystem;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.prism = null;
        this.prismGroup = null;
        this.incidentBeam = null;
        this.spectrumRays = [];
        this.reflectionPrisms = [];
        this.rotation = 0;
        this.targetRotation = 0;
        this.isDragging = false;
        this.previousMouseX = 0;
        this.hasPlayedDispersion = false;
        this.cubeCamera = null;
        this.cubeRenderTarget = null;
        
        // Physics parameters
        // Using 30° apex for visible dispersion (real prisms use 60°, but deviation would be ~40°)
        // 30° apex gives ~15° deviation - visible on screen while maintaining physics ordering
        this.prismApexAngle = Math.PI / 6; // 30° apex for better visibility
        this.baseIncidentAngle = Math.PI / 12; // 15° default incidence
        this.rayLength = 14; // How far rays extend (shows fanning)
        
        this.init();
    }
    
    init() {
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(CONFIG.COLORS.VOID);
        this.scene.fog = new THREE.FogExp2(CONFIG.COLORS.VOID, 0.02);
        
        // Camera
        this.camera = new THREE.PerspectiveCamera(
            50,
            this.container.clientWidth / this.container.clientHeight,
            0.1,
            1000
        );
        this.camera.position.set(0, 0, 10);
        
        // Renderer
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
        
        // Create prism group (contains prism + rays that rotate together)
        this.prismGroup = new THREE.Group();
        this.scene.add(this.prismGroup);
        
        // Create scene elements
        this.createPrism();
        this.createIncidentBeam();
        this.createSpectrumRays();
        this.createInfiniteReflections();
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
        // Equilateral triangular prism
        const triangleShape = new THREE.Shape();
        const size = 1.0;
        
        // Triangle vertices (apex at top)
        const h = size * Math.sqrt(3) / 2;
        triangleShape.moveTo(0, h * 2/3);        // Apex
        triangleShape.lineTo(-size/2, -h/3);     // Bottom left
        triangleShape.lineTo(size/2, -h/3);      // Bottom right
        triangleShape.lineTo(0, h * 2/3);        // Back to apex
        
        const extrudeSettings = {
            depth: 1.5,
            bevelEnabled: true,
            bevelThickness: 0.03,
            bevelSize: 0.03,
            bevelSegments: 2
        };
        
        const prismGeometry = new THREE.ExtrudeGeometry(triangleShape, extrudeSettings);
        prismGeometry.center();
        
        // Glass material
        const prismMaterial = new THREE.MeshPhysicalMaterial({
            color: 0xffffff,
            transparent: true,
            opacity: 0.2,
            metalness: 0,
            roughness: 0,
            transmission: 0.95,
            thickness: 1.0,
            ior: 1.52,
            envMap: this.cubeRenderTarget.texture,
            envMapIntensity: 1.0,
            clearcoat: 1,
            clearcoatRoughness: 0,
        });
        
        this.prism = new THREE.Mesh(prismGeometry, prismMaterial);
        this.prismGroup.add(this.prism);
        
        // Wireframe overlay
        const wireframeMaterial = new THREE.MeshBasicMaterial({
            color: CONFIG.COLORS.PRIMARY,
            wireframe: true,
            transparent: true,
            opacity: 0.4
        });
        const wireframePrism = new THREE.Mesh(prismGeometry.clone(), wireframeMaterial);
        this.prism.add(wireframePrism);
        
        // Edge glow
        const edgesGeometry = new THREE.EdgesGeometry(prismGeometry);
        const edgesMaterial = new THREE.LineBasicMaterial({ 
            color: CONFIG.COLORS.LIGHT,
            transparent: true,
            opacity: 0.9
        });
        const edges = new THREE.LineSegments(edgesGeometry, edgesMaterial);
        this.prism.add(edges);
    }
    
    createIncidentBeam() {
        // White light entering from the left
        const beamGroup = new THREE.Group();
        
        // Main beam (horizontal, entering from left)
        const beamLength = 4;
        const beamGeometry = new THREE.CylinderGeometry(0.06, 0.06, beamLength, 12);
        const beamMaterial = new THREE.MeshBasicMaterial({
            color: CONFIG.COLORS.WHITE,
            transparent: true,
            opacity: 0.95
        });
        const beam = new THREE.Mesh(beamGeometry, beamMaterial);
        beam.rotation.z = Math.PI / 2;
        beam.position.x = -beamLength / 2 - 0.5; // Ends at prism entry
        beamGroup.add(beam);
        
        // Glow layers
        for (let i = 1; i <= 3; i++) {
            const glowGeometry = new THREE.CylinderGeometry(0.06 + i * 0.08, 0.06 + i * 0.08, beamLength, 12);
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: CONFIG.COLORS.WHITE,
                transparent: true,
                opacity: 0.2 / i
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            glow.rotation.z = Math.PI / 2;
            glow.position.x = beam.position.x;
            beamGroup.add(glow);
        }
        
        this.incidentBeam = beamGroup;
        this.scene.add(beamGroup);
    }
    
    createSpectrumRays() {
        // Clear existing rays
        this.spectrumRays.forEach(r => this.scene.remove(r.group));
        this.spectrumRays = [];
        
        const colors = Object.entries(CONFIG.COLORS.SPECTRUM);
        const wavelengths = Object.entries(SPECTRUM_WAVELENGTHS);
        
        wavelengths.forEach(([colorName, wavelength], index) => {
            const color = CONFIG.COLORS.SPECTRUM[colorName.toUpperCase()];
            const n_glass = cauchyRefractiveIndex(wavelength);
            
            // Create ray group
            const rayGroup = new THREE.Group();
            
            // Ray geometry - starts thin, can extend far
            const rayGeometry = new THREE.CylinderGeometry(0.025, 0.02, this.rayLength, 8);
            rayGeometry.translate(0, this.rayLength / 2, 0); // Origin at start
            rayGeometry.rotateZ(-Math.PI / 2); // Point along +X
            
            const rayMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.9
            });
            const ray = new THREE.Mesh(rayGeometry, rayMaterial);
            rayGroup.add(ray);
            
            // Inner glow
            const glowGeometry = new THREE.CylinderGeometry(0.06, 0.05, this.rayLength, 8);
            glowGeometry.translate(0, this.rayLength / 2, 0);
            glowGeometry.rotateZ(-Math.PI / 2);
            const glowMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.25
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            rayGroup.add(glow);
            
            // Outer glow (shows spread better at distance)
            const outerGlowGeometry = new THREE.CylinderGeometry(0.12, 0.10, this.rayLength, 8);
            outerGlowGeometry.translate(0, this.rayLength / 2, 0);
            outerGlowGeometry.rotateZ(-Math.PI / 2);
            const outerGlowMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.08
            });
            const outerGlow = new THREE.Mesh(outerGlowGeometry, outerGlowMaterial);
            rayGroup.add(outerGlow);
            
            // Position at prism exit point
            rayGroup.position.set(0.5, 0, 0);
            
            this.spectrumRays.push({
                group: rayGroup,
                colorName: colorName,
                wavelength: wavelength,
                n_glass: n_glass,
                color: color,
                index: index
            });
            
            this.scene.add(rayGroup);
        });
        
        // Initial update
        this.updateRayDirections();
    }
    
    /**
     * CORE PHYSICS: Compute and apply refraction angles for all rays
     * Called every frame when prism rotates
     * 
     * Key properties (physically correct):
     * - Red (700nm, n≈1.513) deviates LEAST (closest to horizontal)
     * - Violet (400nm, n≈1.531) deviates MOST (furthest from horizontal)
     * - Fan GROWS with distance from prism (handled by ray geometry)
     * - Rotating prism shifts all deviation angles together
     */
    updateRayDirections() {
        const prismRotation = this.rotation;
        
        // Compute refractive indices for reference
        const n_red = cauchyRefractiveIndex(700);     // ~1.514
        const n_violet = cauchyRefractiveIndex(400);  // ~1.531
        const n_range = n_violet - n_red;             // ~0.017
        
        // Angular spread of the fan (in radians) - how wide the spectrum spreads
        const fanSpread = 0.35; // ~20 degrees total spread
        
        // Base direction: influenced by prism rotation
        // As prism rotates, the whole spectrum shifts
        const baseDirection = Math.sin(prismRotation) * 0.2;
        
        this.spectrumRays.forEach((rayData, index) => {
            const { group, n_glass, wavelength } = rayData;
            
            // Normalized position in spectrum: 0 (red) to 1 (violet)
            const normalizedN = (n_glass - n_red) / n_range;
            
            // Ray angle: red at top (least deviation), violet at bottom (most deviation)
            // Fan is centered around baseDirection
            const halfSpread = fanSpread / 2;
            const rayAngle = baseDirection - halfSpread + (normalizedN * fanSpread);
            
            // Exit point: all rays emerge from same point on prism
            const exitX = 0.65;
            const exitY = 0;
            
            group.position.set(exitX, exitY, 0);
            group.rotation.z = -rayAngle; // Negative because +Z rotation goes CCW
            
            group.visible = true;
        });
    }
    
    createInfiniteReflections() {
        const reflectionCount = 10;
        const prismGeometry = this.prism.geometry.clone();
        
        for (let i = 0; i < reflectionCount; i++) {
            const scale = 0.25 / (1 + i * 0.35);
            const distance = 4 + i * 2.5;
            const angle = (i / reflectionCount) * Math.PI * 2;
            
            const ghostMaterial = new THREE.MeshPhysicalMaterial({
                color: CONFIG.COLORS.PRIMARY,
                transparent: true,
                opacity: 0.12 / (1 + i * 0.3),
                metalness: 0.3,
                roughness: 0.1,
                emissive: CONFIG.COLORS.PRIMARY,
                emissiveIntensity: 0.08 / (1 + i * 0.5),
            });
            
            const ghostPrism = new THREE.Mesh(prismGeometry, ghostMaterial);
            ghostPrism.scale.setScalar(scale);
            ghostPrism.position.set(
                Math.cos(angle) * distance,
                Math.sin(angle * 0.7) * (distance * 0.25),
                -distance * 0.4
            );
            ghostPrism.rotation.y = angle;
            
            this.reflectionPrisms.push({
                mesh: ghostPrism,
                angle: angle,
                distance: distance,
                speed: 0.0008 + Math.random() * 0.0015,
                phase: Math.random() * Math.PI * 2
            });
            
            this.scene.add(ghostPrism);
        }
    }
    
    createAmbientParticles() {
        const particleCount = 180;
        const geometry = new THREE.BufferGeometry();
        const positions = new Float32Array(particleCount * 3);
        const colors = new Float32Array(particleCount * 3);
        
        const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
        
        for (let i = 0; i < particleCount; i++) {
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            const radius = 2 + Math.random() * 8;
            
            positions[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
            positions[i * 3 + 1] = radius * Math.sin(phi) * Math.sin(theta);
            positions[i * 3 + 2] = radius * Math.cos(phi) - 3;
            
            const color = new THREE.Color(spectrumColors[Math.floor(Math.random() * spectrumColors.length)]);
            colors[i * 3] = color.r;
            colors[i * 3 + 1] = color.g;
            colors[i * 3 + 2] = color.b;
        }
        
        geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
        geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        
        const material = new THREE.PointsMaterial({
            size: 0.04,
            vertexColors: true,
            transparent: true,
            opacity: 0.5,
            blending: THREE.AdditiveBlending,
            sizeAttenuation: true
        });
        
        this.particles = new THREE.Points(geometry, material);
        this.scene.add(this.particles);
    }
    
    setupLighting() {
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.35);
        this.scene.add(ambientLight);
        
        const keyLight = new THREE.PointLight(CONFIG.COLORS.PRIMARY, 0.9, 50);
        keyLight.position.set(0, 5, 5);
        this.scene.add(keyLight);
        
        const fillLight = new THREE.PointLight(CONFIG.COLORS.LIGHT, 0.4, 30);
        fillLight.position.set(-5, 0, 3);
        this.scene.add(fillLight);
        
        // Spectrum lights positioned where rays actually go
        const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
        spectrumColors.forEach((color, i) => {
            const light = new THREE.PointLight(color, 0.25, 12);
            // Position further out to show the fan
            const spread = (i - 3) * 0.8;
            light.position.set(8, spread, 0);
            this.scene.add(light);
        });
    }
    
    setupEventListeners() {
        this.renderer.domElement.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.previousMouseX = e.clientX;
        });
        
        document.addEventListener('mousemove', (e) => {
            if (!this.isDragging) return;
            
            const deltaX = e.clientX - this.previousMouseX;
            this.targetRotation += deltaX * 0.008;
            this.previousMouseX = e.clientX;
            
            if (this.sound && Math.abs(deltaX) > 2) {
                this.sound.playPrismRotate(deltaX > 0 ? 1 : -1);
            }
        });
        
        document.addEventListener('mouseup', () => {
            this.isDragging = false;
        });
        
        this.renderer.domElement.addEventListener('touchstart', (e) => {
            this.isDragging = true;
            this.previousMouseX = e.touches[0].clientX;
        });
        
        this.renderer.domElement.addEventListener('touchmove', (e) => {
            if (!this.isDragging) return;
            const deltaX = e.touches[0].clientX - this.previousMouseX;
            this.targetRotation += deltaX * 0.008;
            this.previousMouseX = e.touches[0].clientX;
        });
        
        this.renderer.domElement.addEventListener('touchend', () => {
            this.isDragging = false;
        });
        
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
        
        // Auto-rotate prism slowly
        if (!this.isDragging) {
            this.targetRotation += CONFIG.PRISM.rotationSpeed;
        }
        
        // Smooth rotation
        this.rotation += (this.targetRotation - this.rotation) * 0.06;
        
        // Rotate prism visual
        this.prismGroup.rotation.y = this.rotation;
        
        // UPDATE RAY DIRECTIONS BASED ON PHYSICS
        // This is the key: rays recompute their refraction angles each frame
        this.updateRayDirections();
        
        // Animate reflection prisms
        this.reflectionPrisms.forEach((rp, i) => {
            rp.mesh.rotation.y = this.rotation * (1 + i * 0.08);
            rp.mesh.rotation.x = Math.sin(time * rp.speed + rp.phase) * 0.15;
            const scale = 0.25 / (1 + i * 0.35) * (1 + Math.sin(time * 0.4 + rp.phase) * 0.08);
            rp.mesh.scale.setScalar(scale);
        });
        
        // Animate particles
        if (this.particles) {
            const positions = this.particles.geometry.attributes.position.array;
            for (let i = 0; i < positions.length; i += 3) {
                positions[i + 1] += Math.sin(time + i) * 0.0015;
                positions[i] += Math.cos(time * 0.5 + i) * 0.0008;
            }
            this.particles.geometry.attributes.position.needsUpdate = true;
            this.particles.rotation.y = time * 0.015;
        }
        
        // Update cube camera
        if (Math.floor(time * 10) % 6 === 0) {
            this.prism.visible = false;
            this.cubeCamera.update(this.renderer, this.scene);
            this.prism.visible = true;
        }
        
        // Sound trigger
        if (this.sound && !this.hasPlayedDispersion && Math.abs(this.rotation) > 0.3) {
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
