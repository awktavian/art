// Fano Plane 3D Visualization using Three.js

import { COLONIES, FANO_LINES } from '../data/colonies.js';

export class FanoVisualization {
    constructor() {
        this.container = document.getElementById('fano-3d-container');
        this.linesGrid = document.querySelector('.fano-lines-grid');

        this.scene = null;
        this.camera = null;
        this.renderer = null;
        this.controls = null;

        this.colonyMeshes = {};
        this.lineMeshes = [];

        this.init();
    }

    init() {
        if (!this.container || !window.THREE) {
            console.warn('Three.js not loaded or container missing');
            return;
        }

        this.setupScene();
        this.createColonyNodes();
        this.createFanoLines();
        this.setupControls();
        this.setupLinesGrid();
        this.animate();
    }

    setupScene() {
        // Scene
        this.scene = new THREE.Scene();
        this.scene.background = new THREE.Color(0x0A0A0C);

        // Camera
        const aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera = new THREE.PerspectiveCamera(60, aspect, 0.1, 1000);
        this.camera.position.set(3, 3, 3);
        this.camera.lookAt(0, 0, 0);

        // Renderer
        this.renderer = new THREE.WebGLRenderer({ antialias: true });
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
        this.container.appendChild(this.renderer.domElement);

        // Lights
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
        this.scene.add(ambientLight);

        const pointLight = new THREE.PointLight(0xD4AF37, 1);
        pointLight.position.set(5, 5, 5);
        this.scene.add(pointLight);

        // Resize handler
        window.addEventListener('resize', this.onResize.bind(this));
    }

    createColonyNodes() {
        Object.entries(COLONIES).forEach(([key, colony]) => {
            const geometry = new THREE.SphereGeometry(0.15, 32, 32);
            const material = new THREE.MeshStandardMaterial({
                color: colony.color,
                emissive: colony.color,
                emissiveIntensity: 0.3,
                metalness: 0.5,
                roughness: 0.3
            });

            const mesh = new THREE.Mesh(geometry, material);
            mesh.position.set(colony.position.x * 2, colony.position.y * 2, colony.position.z * 2);
            mesh.userData = { key, colony };

            this.scene.add(mesh);
            this.colonyMeshes[key] = mesh;

            // Add label (sprite)
            const canvas = document.createElement('canvas');
            const context = canvas.getContext('2d');
            canvas.width = 256;
            canvas.height = 64;
            context.fillStyle = colony.color;
            context.font = 'bold 32px monospace';
            context.textAlign = 'center';
            context.fillText(key.toUpperCase(), 128, 40);

            const texture = new THREE.CanvasTexture(canvas);
            const spriteMaterial = new THREE.SpriteMaterial({ map: texture });
            const sprite = new THREE.Sprite(spriteMaterial);
            sprite.scale.set(0.8, 0.2, 1);
            sprite.position.y = 0.3;
            mesh.add(sprite);
        });
    }

    createFanoLines() {
        FANO_LINES.forEach(line => {
            const points = line.colonies.map(key => {
                const colony = COLONIES[key];
                return new THREE.Vector3(
                    colony.position.x * 2,
                    colony.position.y * 2,
                    colony.position.z * 2
                );
            });

            // Close the loop
            points.push(points[0]);

            const geometry = new THREE.BufferGeometry().setFromPoints(points);
            const material = new THREE.LineBasicMaterial({
                color: 0xD4AF37,
                opacity: 0.3,
                transparent: true
            });

            const lineMesh = new THREE.Line(geometry, material);
            lineMesh.userData = { line };
            this.scene.add(lineMesh);
            this.lineMeshes.push(lineMesh);
        });
    }

    setupControls() {
        const controls = document.querySelectorAll('.fano-control');
        controls.forEach(btn => {
            btn.addEventListener('click', () => {
                controls.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                const view = btn.dataset.view;
                this.setView(view);
            });
        });

        // Default to orbit view
        this.setView('orbit');
    }

    setView(view) {
        switch (view) {
            case 'top':
                this.camera.position.set(0, 5, 0);
                this.camera.lookAt(0, 0, 0);
                break;
            case 'side':
                this.camera.position.set(5, 0, 0);
                this.camera.lookAt(0, 0, 0);
                break;
            case 'orbit':
            default:
                this.camera.position.set(3, 3, 3);
                this.camera.lookAt(0, 0, 0);
                break;
        }
    }

    setupLinesGrid() {
        if (!this.linesGrid) return;

        FANO_LINES.forEach(line => {
            const card = this.createLineCard(line);
            this.linesGrid.appendChild(card);
        });
    }

    createLineCard(line) {
        const card = document.createElement('div');
        card.className = 'fano-line-card';
        card.tabIndex = 0;

        const header = document.createElement('div');
        header.className = 'line-header';
        header.innerHTML = `
            <span class="line-number">Line ${line.index}</span>
        `;

        const composition = document.createElement('div');
        composition.className = 'line-composition';
        line.colonies.forEach((key, i) => {
            const colony = COLONIES[key];
            const span = document.createElement('span');
            span.className = 'line-colony';
            span.dataset.colony = key;
            span.style.color = colony.color;
            span.textContent = key.charAt(0).toUpperCase() + key.slice(1);
            composition.appendChild(span);

            if (i < line.colonies.length - 1) {
                const op = document.createElement('span');
                op.className = 'line-operator';
                op.textContent = i === 0 ? '×' : '=';
                composition.appendChild(op);
            }
        });

        const meaning = document.createElement('p');
        meaning.className = 'line-meaning';
        meaning.textContent = line.meaning;

        const useCase = document.createElement('p');
        useCase.className = 'line-use-case';
        useCase.textContent = line.useCase;

        const pattern = document.createElement('div');
        pattern.className = 'line-pattern';
        pattern.innerHTML = `
            <strong>Pattern</strong>
            <p>${line.pattern}</p>
        `;

        card.appendChild(header);
        card.appendChild(composition);
        card.appendChild(meaning);
        card.appendChild(useCase);
        card.appendChild(pattern);

        return card;
    }

    animate() {
        requestAnimationFrame(this.animate.bind(this));

        // Gentle rotation
        if (this.scene) {
            this.scene.rotation.y += 0.001;
        }

        // Pulse colony nodes
        Object.values(this.colonyMeshes).forEach(mesh => {
            const scale = 1 + Math.sin(Date.now() * 0.001) * 0.05;
            mesh.scale.setScalar(scale);
        });

        if (this.renderer && this.scene && this.camera) {
            this.renderer.render(this.scene, this.camera);
        }
    }

    onResize() {
        if (!this.container || !this.camera || !this.renderer) return;

        const aspect = this.container.clientWidth / this.container.clientHeight;
        this.camera.aspect = aspect;
        this.camera.updateProjectionMatrix();
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
    }
}
