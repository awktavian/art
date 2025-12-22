// Room 2: The Proof Lattice
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js';
import { CONFIG, TEST_DATA } from '../config.js';

export class LatticeRoom {
    constructor(container, nodeInfoElement) {
        this.container = container;
        this.nodeInfoElement = nodeInfoElement;
        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.nodes = [];
        this.connections = [];
        this.rotation = { x: 0, y: 0 };
        this.isDragging = false;
        this.previousMouse = { x: 0, y: 0 };
        this.raycaster = new THREE.Raycaster();
        this.mouse = new THREE.Vector2();

        this.init();
    }

    init() {
        // Scene setup
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(CONFIG.COLORS.VOID);

        // Camera
        this.camera = new THREE.PerspectiveCamera(
            60,
            this.container.clientWidth / this.container.clientHeight,
            0.1,
            1000
        );
        this.camera.position.set(0, 0, 15);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.container.appendChild(this.renderer.domElement);

        // Create lattice (simplified cubic lattice)
        this.createLattice();

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);

        const pointLight = new THREE.PointLight(CONFIG.COLORS.PRIMARY, 0.8, 100);
        pointLight.position.set(10, 10, 10);
        this.scene.add(pointLight);

        // Event listeners
        this.setupEventListeners();

        // Start animation
        this.animate();
    }

    createLattice() {
        const gridSize = CONFIG.LATTICE.gridSize;
        const spacing = 2;
        const offset = (gridSize - 1) * spacing / 2;

        // Create nodes
        for (let x = 0; x < gridSize; x++) {
            for (let y = 0; y < gridSize; y++) {
                for (let z = 0; z < gridSize; z++) {
                    const geometry = new THREE.SphereGeometry(CONFIG.LATTICE.nodeRadius * 0.1, 16, 16);
                    const material = new THREE.MeshPhongMaterial({
                        color: CONFIG.COLORS.PRIMARY,
                        emissive: CONFIG.COLORS.PRIMARY,
                        emissiveIntensity: 0.3,
                        transparent: true,
                        opacity: 0.8
                    });
                    const node = new THREE.Mesh(geometry, material);
                    node.position.set(
                        x * spacing - offset,
                        y * spacing - offset,
                        z * spacing - offset
                    );

                    // Store metadata for hover
                    node.userData = {
                        id: `node_${x}_${y}_${z}`,
                        testData: TEST_DATA.nodes[Math.floor(Math.random() * TEST_DATA.nodes.length)]
                    };

                    this.nodes.push(node);
                    this.scene.add(node);
                }
            }
        }

        // Create connections between nearby nodes
        const lineMaterial = new THREE.LineBasicMaterial({
            color: CONFIG.COLORS.PRIMARY,
            transparent: true,
            opacity: 0.15
        });

        for (let i = 0; i < this.nodes.length; i++) {
            for (let j = i + 1; j < this.nodes.length; j++) {
                const distance = this.nodes[i].position.distanceTo(this.nodes[j].position);
                if (distance < spacing * CONFIG.LATTICE.connectionDistance) {
                    const points = [this.nodes[i].position, this.nodes[j].position];
                    const geometry = new THREE.BufferGeometry().setFromPoints(points);
                    const line = new THREE.Line(geometry, lineMaterial);
                    this.connections.push(line);
                    this.scene.add(line);
                }
            }
        }
    }

    setupEventListeners() {
        // Mouse drag to rotate lattice
        this.renderer.domElement.addEventListener('mousedown', (e) => {
            this.isDragging = true;
            this.previousMouse = { x: e.clientX, y: e.clientY };
        });

        document.addEventListener('mousemove', (e) => {
            // Update mouse position for raycasting
            const rect = this.renderer.domElement.getBoundingClientRect();
            this.mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
            this.mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

            if (!this.isDragging) {
                // Check for node hover
                this.checkNodeHover();
                return;
            }

            const deltaX = e.clientX - this.previousMouse.x;
            const deltaY = e.clientY - this.previousMouse.y;
            this.rotation.y += deltaX * 0.005;
            this.rotation.x += deltaY * 0.005;
            this.previousMouse = { x: e.clientX, y: e.clientY };
        });

        document.addEventListener('mouseup', () => {
            this.isDragging = false;
        });

        // Click to select node
        this.renderer.domElement.addEventListener('click', (e) => {
            this.checkNodeClick();
        });

        // Handle window resize
        window.addEventListener('resize', () => this.onWindowResize());
    }

    checkNodeHover() {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.nodes);

        // Reset all nodes
        this.nodes.forEach(node => {
            node.material.emissiveIntensity = 0.3;
            node.scale.set(1, 1, 1);
        });

        if (intersects.length > 0) {
            const hoveredNode = intersects[0].object;
            hoveredNode.material.emissiveIntensity = 0.8;
            hoveredNode.scale.set(1.5, 1.5, 1.5);
        }
    }

    checkNodeClick() {
        this.raycaster.setFromCamera(this.mouse, this.camera);
        const intersects = this.raycaster.intersectObjects(this.nodes);

        if (intersects.length > 0) {
            const clickedNode = intersects[0].object;
            const data = clickedNode.userData.testData;

            this.nodeInfoElement.querySelector('.node-info-data').innerHTML = `
                <strong>Test:</strong> ${data.name}<br>
                <strong>Status:</strong> <span style="color: ${CONFIG.COLORS.PRIMARY}">${data.status}</span><br>
                <strong>Coverage:</strong> ${data.coverage}%<br>
                <strong>ID:</strong> ${data.id}
            `;
            this.nodeInfoElement.classList.add('visible');

            // Position info box near cursor
            const rect = this.renderer.domElement.getBoundingClientRect();
            this.nodeInfoElement.style.left = (rect.left + rect.width / 2) + 'px';
            this.nodeInfoElement.style.top = (rect.top + 20) + 'px';
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

        // Auto-rotate if not dragging
        if (!this.isDragging) {
            this.rotation.y += CONFIG.LATTICE.rotationSpeed;
        }

        // Apply rotation to all nodes and connections
        const pivot = new THREE.Object3D();
        this.scene.add(pivot);
        pivot.rotation.set(this.rotation.x, this.rotation.y, 0);

        this.nodes.forEach(node => {
            const worldPos = node.position.clone();
            worldPos.applyEuler(pivot.rotation);
        });

        this.renderer.render(this.scene, this.camera);
    }

    destroy() {
        this.renderer.dispose();
        this.container.innerHTML = '';
    }
}
