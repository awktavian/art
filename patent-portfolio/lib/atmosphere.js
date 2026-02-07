/**
 * Atmosphere Effects for Patent Museum
 * =====================================
 *
 * Volumetric light from skylights, dust motes in light beams,
 * wing-specific ambient particles, fog density by wing.
 *
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { DIMENSIONS, COLONY_ORDER } from '../museum/architecture.js';

const FOG_BY_WING = {
    spark: 0.009,
    forge: 0.011,
    flow: 0.006,
    nexus: 0.008,
    beacon: 0.008,
    grove: 0.007,
    crystal: 0.005,
    rotunda: 0.006
};

/**
 * Volumetric light cone from dome aperture downward
 */
function createVolumetricCone() {
    const r = DIMENSIONS.rotunda.apertureRadius || 4;
    const h = 20;
    const geometry = new THREE.ConeGeometry(r, h, 32, 1, true);
    const material = new THREE.MeshBasicMaterial({
        color: 0xF5F0E8,
        transparent: true,
        opacity: 0.04,
        side: THREE.BackSide,
        depthWrite: false
    });
    const cone = new THREE.Mesh(geometry, material);
    cone.position.set(DIMENSIONS.rotunda.apertureOffset || 0, DIMENSIONS.rotunda.height - h * 0.5, 0);
    cone.rotation.x = 0;
    cone.name = 'atmosphere-volumetric-cone';
    return cone;
}

/**
 * Dust motes in a box volume (simple Points)
 */
function createDustMotes(count = 200) {
    const positions = new Float32Array(count * 3);
    const size = 25;
    for (let i = 0; i < count; i++) {
        positions[i * 3] = (Math.random() - 0.5) * size * 2;
        positions[i * 3 + 1] = Math.random() * DIMENSIONS.rotunda.height * 0.8;
        positions[i * 3 + 2] = (Math.random() - 0.5) * size * 2;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    const material = new THREE.PointsMaterial({
        color: 0xE8E4DC,
        size: 0.12,
        transparent: true,
        opacity: 0.4,
        sizeAttenuation: true,
        depthWrite: false
    });
    const points = new THREE.Points(geometry, material);
    points.name = 'atmosphere-dust';
    return points;
}

/**
 * Wing-specific ambient particles (color tint by zone)
 */
function createWingParticles() {
    const count = 80;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const wingColors = {
        spark: new THREE.Color(0xFF6B35),
        forge: new THREE.Color(0xD4AF37),
        flow: new THREE.Color(0x4ECDC4),
        nexus: new THREE.Color(0x9B7EBD),
        beacon: new THREE.Color(0xF59E0B),
        grove: new THREE.Color(0x7EB77F),
        crystal: new THREE.Color(0x67D4E4)
    };
    const r = DIMENSIONS.rotunda.radius + 15;
    for (let i = 0; i < count; i++) {
        const angle = (i / count) * Math.PI * 2;
        positions[i * 3] = Math.cos(angle) * (r + (Math.random() - 0.5) * 10);
        positions[i * 3 + 1] = 2 + Math.random() * 12;
        positions[i * 3 + 2] = Math.sin(angle) * (r + (Math.random() - 0.5) * 10);
        const col = wingColors[COLONY_ORDER[i % COLONY_ORDER.length]] || wingColors.crystal;
        colors[i * 3] = col.r;
        colors[i * 3 + 1] = col.g;
        colors[i * 3 + 2] = col.b;
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const material = new THREE.PointsMaterial({
        size: 0.25,
        vertexColors: true,
        transparent: true,
        opacity: 0.35,
        sizeAttenuation: true,
        depthWrite: false
    });
    const points = new THREE.Points(geometry, material);
    points.name = 'atmosphere-wing-particles';
    return points;
}

export class AtmosphereManager {
    constructor(scene, options = {}) {
        this.scene = scene;
        this.currentZone = 'rotunda';
        this.volumetricCone = null;
        this.dustMotes = null;
        this.wingParticles = null;
        this.enabled = options.enabled !== false;
        this.init();
    }

    init() {
        this.volumetricCone = createVolumetricCone();
        this.scene.add(this.volumetricCone);
        this.dustMotes = createDustMotes(200);
        this.scene.add(this.dustMotes);
        this.wingParticles = createWingParticles();
        this.scene.add(this.wingParticles);
    }

    /**
     * Set current zone (wing or rotunda); updates fog density and particle emphasis
     */
    setZone(zone) {
        if (zone === this.currentZone) return;
        this.currentZone = zone;
        const density = FOG_BY_WING[zone] ?? FOG_BY_WING.rotunda;
        if (this.scene.fog && this.scene.fog.isFogExp2) {
            this.scene.fog.density = density;
        }
    }

    update(delta) {
        if (!this.enabled) return;
        // Optional: subtle motion on dust (CPU-driven slight drift)
        if (this.dustMotes?.geometry?.attributes?.position) {
            const pos = this.dustMotes.geometry.attributes.position.array;
            for (let i = 0; i < pos.length; i += 3) {
                pos[i + 1] += Math.sin(Date.now() * 0.001 + i) * 0.002;
                if (pos[i + 1] > DIMENSIONS.rotunda.height * 0.8) pos[i + 1] = 0;
            }
            this.dustMotes.geometry.attributes.position.needsUpdate = true;
        }
    }

    dispose() {
        [this.volumetricCone, this.dustMotes, this.wingParticles].forEach((obj) => {
            if (obj) {
                this.scene.remove(obj);
                if (obj.geometry) obj.geometry.dispose();
                if (obj.material) obj.material.dispose();
            }
        });
        this.volumetricCone = null;
        this.dustMotes = null;
        this.wingParticles = null;
    }
}

export { FOG_BY_WING };
