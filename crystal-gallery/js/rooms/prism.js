// Room 1: The Entrance Prism
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js';
import { CONFIG } from '../config.js';

export class PrismRoom {
    constructor(container) {
        this.container = container;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.prism = null;
        this.rays = [];
        this.rotation = 0;
        this.isDragging = false;
        this.previousMouseX = 0;

        this.init();
    }

    init() {
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(CONFIG.COLORS.VOID);

        // Camera
        this.camera = new THREE.PerspectiveCamera(
            50,
            this.container.clientWidth / this.container.clientHeight,
            0.1,
            1000
        );
        this.camera.position.set(0, 0, 5);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.container.appendChild(this.renderer.domElement);

        // Create prism (triangular prism geometry)
        const prismGeometry = new THREE.CylinderGeometry(0, 1.5, 2, 3);
        const prismMaterial = new THREE.MeshPhysicalMaterial({
            color: CONFIG.COLORS.LIGHT,
            transparent: true,
            opacity: 0.3,
            metalness: 0.1,
            roughness: 0.1,
            transmission: 0.9,
            thickness: 0.5,
            envMapIntensity: 1,
            clearcoat: 1,
            clearcoatRoughness: 0.1
        });
        this.prism = new THREE.Mesh(prismGeometry, prismMaterial);
        this.prism.rotation.z = Math.PI / 2;
        this.scene.add(this.prism);

        // Create white light beam
        const lightGeometry = new THREE.CylinderGeometry(0.05, 0.05, 3, 8);
        const lightMaterial = new THREE.MeshBasicMaterial({
            color: CONFIG.COLORS.WHITE,
            transparent: true,
            opacity: 0.8
        });
        const lightBeam = new THREE.Mesh(lightGeometry, lightMaterial);
        lightBeam.position.set(-3, 0, 0);
        lightBeam.rotation.z = Math.PI / 2;
        this.scene.add(lightBeam);

        // Create spectrum rays (7 colors)
        this.createSpectrumRays();

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);

        const pointLight = new THREE.PointLight(CONFIG.COLORS.PRIMARY, 1, 100);
        pointLight.position.set(0, 3, 3);
        this.scene.add(pointLight);

        // Event listeners
        this.setupEventListeners();

        // Start animation
        this.animate();
    }

    createSpectrumRays() {
        const colors = Object.values(CONFIG.COLORS.SPECTRUM);
        const angleSpread = 0.4;
        const startAngle = -angleSpread / 2;

        colors.forEach((color, index) => {
            const angle = startAngle + (angleSpread / (colors.length - 1)) * index;
            const rayGeometry = new THREE.CylinderGeometry(0.02, 0.02, 2, 8);
            const rayMaterial = new THREE.MeshBasicMaterial({
                color: color,
                transparent: true,
                opacity: 0.8
            });
            const ray = new THREE.Mesh(rayGeometry, rayMaterial);
            ray.position.set(2, 0, 0);
            ray.rotation.z = Math.PI / 2 - angle;
            this.rays.push(ray);
            this.scene.add(ray);
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
            this.rotation += deltaX * 0.01;
            this.previousMouseX = e.clientX;
        });

        document.addEventListener('mouseup', () => {
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

        // Auto-rotate prism slowly
        if (!this.isDragging) {
            this.rotation += CONFIG.PRISM.rotationSpeed;
        }

        this.prism.rotation.y = this.rotation;

        // Update ray angles based on prism rotation
        this.rays.forEach((ray, index) => {
            const baseAngle = -0.2 + (0.4 / (this.rays.length - 1)) * index;
            const rotationInfluence = Math.sin(this.rotation) * 0.1;
            ray.rotation.z = Math.PI / 2 - (baseAngle + rotationInfluence);
        });

        this.renderer.render(this.scene, this.camera);
    }

    destroy() {
        this.renderer.dispose();
        this.container.innerHTML = '';
    }
}
