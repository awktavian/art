/**
 * P3 Bespoke Artworks
 * ===================
 *
 * Unique visualization per P3 patent. Config-driven to keep 30 patents maintainable.
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { createPlaque } from '../components/plaque.js';

const COLONY_COLORS = {
    spark: 0xFF6B35, forge: 0xD4AF37, flow: 0x4ECDC4, nexus: 0x9B7EBD,
    beacon: 0xF59E0B, grove: 0x7EB77F, crystal: 0x67D4E4
};

function getColor(patent) {
    return COLONY_COLORS[patent.colony] || 0x67D4E4;
}

// Per-patent visual config: type + optional params
const P3_VISUALS = {
    'P3-A7': { type: 'kaleidoscope', count: 6 },
    'P3-A8': { type: 'octonion', rings: 4 },
    'P3-B4': { type: 'landscape', peaks: 5 },
    'P3-B5': { type: 'recovery', arcs: 3 },
    'P3-B6': { type: 'frontier', radius: 0.8 },
    'P3-C4': { type: 'gossip', nodes: 8 },
    'P3-C5': { type: 'sync', views: 4 },
    'P3-D5': { type: 'dream', bubbles: 5 },
    'P3-D6': { type: 'contrast', branches: 6 },
    'P3-D7': { type: 'multiscale', layers: 4 },
    'P3-E3': { type: 'zk', reveal: true },
    'P3-E4': { type: 'threshold', shards: 5 },
    'P3-F3': { type: 'presence', rooms: 4 },
    'P3-F4': { type: 'circadian', arc: true },
    'P3-F5': { type: 'audioSync', speakers: 6 },
    'P3-F6': { type: 'comfort', orb: true },
    'P3-F7': { type: 'energy', curve: true },
    'P3-G2': { type: 'routing', paths: 5 },
    'P3-G3': { type: 'earcons', symbols: 5 },
    'P3-G4': { type: 'spatial', sources: 4 },
    'P3-H3': { type: 'signal', wave: true },
    'P3-H4': { type: 'risk', cloud: true },
    'P3-I3': { type: 'mesh', routes: 6 },
    'P3-I4': { type: 'hotReload', ripple: true },
    'P3-I5': { type: 'metrics', streams: 5 },
    'P3-J1': { type: 'searchAugment', links: 4 },
    'P3-J2': { type: 'verification', steps: 5 },
    'P3-J3': { type: 'toolSelect', tools: 4 },
    'P3-K1': { type: 'genux', generate: true },
    'P3-K2': { type: 'adaptive', reflow: true }
};

export class BespokeP3Artwork extends THREE.Group {
    constructor(patent, config = {}) {
        super();
        this.patent = patent;
        this.config = { type: 'default', ...P3_VISUALS[patent.id], ...config };
        this.time = 0;
        this.name = `artwork-${patent.id}`;
        this.userData = { patentId: patent.id, interactive: true };
        this._build();
    }

    _build() {
        const color = getColor(this.patent);
        this._pedestal(color);
        this._visual(color);
        const plaque = createPlaque(this.patent, { width: 1.8, height: 1.0, showDescription: true });
        plaque.position.set(0, 0.7, 1.8);
        plaque.rotation.x = -0.2;
        this.add(plaque);
    }

    _pedestal(color) {
        const geo = new THREE.CylinderGeometry(1, 1.2, 0.2, 32);
        const mat = new THREE.MeshPhysicalMaterial({ color: 0x0A0A15, metalness: 0.8, roughness: 0.2 });
        const p = new THREE.Mesh(geo, mat);
        p.position.y = 0.1;
        p.userData.isPedestal = true;
        this.add(p);
        const rimGeo = new THREE.TorusGeometry(1.1, 0.03, 16, 64);
        const rim = new THREE.Mesh(rimGeo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6 }));
        rim.rotation.x = Math.PI / 2;
        rim.position.y = 0.21;
        this.add(rim);
    }

    _visual(color) {
        const cfg = this.config;
        const types = {
            kaleidoscope: () => this._addReflectionRays(color, cfg.count || 6),
            octonion: () => this._addRings(color, cfg.rings || 4),
            landscape: () => this._addPeaks(color, cfg.peaks || 5),
            recovery: () => this._addArcs(color, cfg.arcs || 3),
            frontier: () => this._addFrontier(color, cfg.radius),
            gossip: () => this._addNetwork(color, cfg.nodes || 8),
            sync: () => this._addSyncViews(color, cfg.views || 4),
            dream: () => this._addBubbles(color, cfg.bubbles || 5),
            contrast: () => this._addBranches(color, cfg.branches || 6),
            multiscale: () => this._addLayers(color, cfg.layers || 4),
            zk: () => this._addZK(color),
            threshold: () => this._addShards(color, cfg.shards || 5),
            presence: () => this._addRooms(color, cfg.rooms || 4),
            circadian: () => this._addArc(color),
            audioSync: () => this._addSpeakers(color, cfg.speakers || 6),
            comfort: () => this._addOrb(color),
            energy: () => this._addCurve(color),
            routing: () => this._addPaths(color, cfg.paths || 5),
            earcons: () => this._addSymbols(color, cfg.symbols || 5),
            spatial: () => this._addSources(color, cfg.sources || 4),
            signal: () => this._addWave(color),
            risk: () => this._addCloud(color),
            mesh: () => this._addRoutes(color, cfg.routes || 6),
            hotReload: () => this._addRipple(color),
            metrics: () => this._addStreams(color, cfg.streams || 5),
            searchAugment: () => this._addLinks(color, cfg.links || 4),
            verification: () => this._addSteps(color, cfg.steps || 5),
            toolSelect: () => this._addTools(color, cfg.tools || 4),
            genux: () => this._addGenUX(color),
            adaptive: () => this._addReflow(color)
        };
        (types[cfg.type] || (() => this._addDefault(color)))();
    }

    _addReflectionRays(color, count) {
        for (let i = 0; i < count; i++) {
            const angle = (i / count) * Math.PI * 2;
            const geo = new THREE.CylinderGeometry(0.02, 0.06, 0.8, 8);
            const m = new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.3 });
            const ray = new THREE.Mesh(geo, m);
            ray.rotation.z = angle;
            ray.position.set(Math.cos(angle) * 0.3, 1.2, Math.sin(angle) * 0.3);
            this.add(ray);
        }
    }

    _addRings(color, n) {
        for (let i = 0; i < n; i++) {
            const r = 0.2 + i * 0.2;
            const geo = new THREE.TorusGeometry(r, 0.03, 16, 32);
            const m = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 });
            const ring = new THREE.Mesh(geo, m);
            ring.rotation.x = Math.PI / 2;
            ring.position.y = 1 + i * 0.15;
            this.add(ring);
        }
    }

    _addPeaks(color, n) {
        const geo = new THREE.ConeGeometry(0.4, 0.9, 6);
        const m = new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.2, transparent: true, opacity: 0.8 });
        for (let i = 0; i < n; i++) {
            const peak = new THREE.Mesh(geo, m.clone());
            peak.position.set((i - n / 2) * 0.25, 0.9, 0);
            peak.rotation.z = (i % 2) * 0.1;
            this.add(peak);
        }
    }

    _addArcs(color, n) {
        for (let i = 0; i < n; i++) {
            const curve = new THREE.QuadraticBezierCurve3(
                new THREE.Vector3(-0.3, 0.8, 0),
                new THREE.Vector3(0, 1.4 + i * 0.2, 0.2),
                new THREE.Vector3(0.3, 0.8, 0)
            );
            const pts = curve.getPoints(20);
            const geo = new THREE.BufferGeometry().setFromPoints(pts);
            const line = new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.6 }));
            this.add(line);
        }
    }

    _addFrontier(color, r = 0.8) {
        const ringGeo = new THREE.RingGeometry(r - 0.05, r + 0.05, 32);
        const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6, side: THREE.DoubleSide }));
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = 1.2;
        this.add(ring);
    }

    _addNetwork(color, n) {
        const nodes = [];
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const node = new THREE.Mesh(
                new THREE.SphereGeometry(0.06, 12, 12),
                new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.3 })
            );
            node.position.set(Math.cos(angle) * 0.5, 1.2, Math.sin(angle) * 0.5);
            nodes.push(node);
            this.add(node);
        }
        const lineMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.3 });
        for (let i = 0; i < n; i++)
            for (let j = i + 1; j < n; j++)
                if (Math.random() < 0.4)
                    this.add(new THREE.Line(
                        new THREE.BufferGeometry().setFromPoints([nodes[i].position.clone(), nodes[j].position.clone()]),
                        lineMat
                    ));
    }

    _addSyncViews(color, n) {
        for (let i = 0; i < n; i++) {
            const box = new THREE.Mesh(
                new THREE.BoxGeometry(0.2, 0.25, 0.05),
                new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.2, transparent: true, opacity: 0.8 })
            );
            box.position.set((i - n / 2) * 0.3, 1.2, 0);
            this.add(box);
        }
    }

    _addBubbles(color, n) {
        for (let i = 0; i < n; i++) {
            const geo = new THREE.SphereGeometry(0.1 + Math.random() * 0.08, 16, 16);
            const b = new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 }));
            b.position.set((Math.random() - 0.5) * 0.6, 1 + i * 0.2, (Math.random() - 0.5) * 0.3);
            this.add(b);
        }
    }

    _addBranches(color, n) {
        const root = new THREE.Mesh(new THREE.SphereGeometry(0.08, 16, 16), new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.4 }));
        root.position.y = 1.5;
        this.add(root);
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const end = new THREE.Vector3(Math.cos(angle) * 0.4, 1.1, Math.sin(angle) * 0.4);
            this.add(new THREE.Line(
                new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 1.5, 0), end]),
                new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 })
            ));
            const leaf = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 8), new THREE.MeshBasicMaterial({ color }));
            leaf.position.copy(end);
            this.add(leaf);
        }
    }

    _addLayers(color, n) {
        for (let i = 0; i < n; i++) {
            const size = 0.6 - i * 0.1;
            const grid = new THREE.GridHelper(size, 4, color, color);
            grid.position.y = 0.8 + i * 0.25;
            grid.material.transparent = true;
            grid.material.opacity = 0.4;
            this.add(grid);
        }
    }

    _addZK(color) {
        const inner = new THREE.Mesh(new THREE.SphereGeometry(0.15, 24, 24), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.3 }));
        inner.position.y = 1.2;
        this.add(inner);
        const outer = new THREE.Mesh(new THREE.SphereGeometry(0.28, 24, 24), new THREE.MeshBasicMaterial({ color, wireframe: true, transparent: true, opacity: 0.5 }));
        outer.position.y = 1.2;
        this.add(outer);
    }

    _addShards(color, n) {
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const s = new THREE.Mesh(
                new THREE.BoxGeometry(0.08, 0.2, 0.04),
                new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.2 })
            );
            s.position.set(Math.cos(angle) * 0.35, 1.1 + (i % 2) * 0.15, Math.sin(angle) * 0.35);
            s.rotation.y = -angle;
            this.add(s);
        }
    }

    _addRooms(color, n) {
        for (let i = 0; i < n; i++) {
            const box = new THREE.Mesh(
                new THREE.BoxGeometry(0.25, 0.2, 0.2),
                new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.1 + i * 0.05 })
            );
            box.position.set((i - n / 2) * 0.35, 1.1, 0);
            this.add(box);
        }
    }

    _addArc(color) {
        const curve = new THREE.EllipseCurve(0, 0, 0.5, 0.25, 0, Math.PI, false, 0);
        const pts = curve.getPoints(32).map(p => new THREE.Vector3(p.x, 1.2 + p.y, 0));
        const geo = new THREE.BufferGeometry().setFromPoints(pts);
        this.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.7 })));
    }

    _addSpeakers(color, n) {
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const s = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.06, 0.15, 16), new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.2 }));
            s.position.set(Math.cos(angle) * 0.5, 1.1, Math.sin(angle) * 0.5);
            this.add(s);
        }
    }

    _addOrb(color) {
        const o = new THREE.Mesh(new THREE.SphereGeometry(0.35, 32, 32), new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.4, transparent: true, opacity: 0.9 }));
        o.position.y = 1.2;
        this.add(o);
    }

    _addCurve(color) {
        const pts = [];
        for (let i = 0; i <= 20; i++) pts.push(new THREE.Vector3(-0.5 + i * 0.05, 0.9 + Math.sin(i * 0.5) * 0.3, 0));
        this.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.8 })));
    }

    _addPaths(color, n) {
        const center = new THREE.Vector3(0, 1.3, 0);
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const end = new THREE.Vector3(Math.cos(angle) * 0.5, 0.9, Math.sin(angle) * 0.5);
            this.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([center.clone(), end]), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 })));
        }
    }

    _addSymbols(color, n) {
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const ring = new THREE.Mesh(new THREE.RingGeometry(0.06, 0.1, 16), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.7, side: THREE.DoubleSide }));
            ring.rotation.x = -Math.PI / 2;
            ring.position.set(Math.cos(angle) * 0.45, 1.2, Math.sin(angle) * 0.45);
            this.add(ring);
        }
    }

    _addSources(color, n) {
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const s = new THREE.Mesh(new THREE.SphereGeometry(0.08, 16, 16), new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.4 }));
            s.position.set(Math.cos(angle) * 0.4, 1.1 + (i % 2) * 0.2, Math.sin(angle) * 0.4);
            this.add(s);
        }
    }

    _addWave(color) {
        const pts = [];
        for (let i = 0; i <= 30; i++) pts.push(new THREE.Vector3(-0.6 + i * 0.04, 1.2 + Math.sin(i * 0.4) * 0.15, 0));
        this.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.8 })));
    }

    _addCloud(color) {
        const g = new THREE.BufferGeometry();
        const pos = new Float32Array(40 * 3);
        for (let i = 0; i < 40; i++) {
            pos[i * 3] = (Math.random() - 0.5) * 0.8;
            pos[i * 3 + 1] = 0.8 + Math.random() * 0.6;
            pos[i * 3 + 2] = (Math.random() - 0.5) * 0.4;
        }
        g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        this.add(new THREE.Points(g, new THREE.PointsMaterial({ size: 0.05, color, transparent: true, opacity: 0.7 })));
    }

    _addRoutes(color, n) {
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const tube = new THREE.Mesh(new THREE.CylinderGeometry(0.02, 0.02, 0.5, 8), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.5 }));
            tube.rotation.z = Math.PI / 2;
            tube.position.set(Math.cos(angle) * 0.4, 1.2, Math.sin(angle) * 0.4);
            this.add(tube);
        }
    }

    _addRipple(color) {
        for (let r = 0.2; r <= 0.6; r += 0.15) {
            const ring = new THREE.Mesh(new THREE.RingGeometry(r, r + 0.04, 32), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.4, side: THREE.DoubleSide }));
            ring.rotation.x = -Math.PI / 2;
            ring.position.y = 1.1;
            this.add(ring);
        }
    }

    _addStreams(color, n) {
        for (let i = 0; i < n; i++) {
            const pts = [new THREE.Vector3(-0.4, 1.5 - i * 0.15, 0), new THREE.Vector3(0.4, 1.2 - i * 0.15, 0)];
            this.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.4 })));
        }
    }

    _addLinks(color, n) {
        const center = new THREE.Mesh(new THREE.SphereGeometry(0.12, 16, 16), new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.4 }));
        center.position.y = 1.3;
        this.add(center);
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const end = new THREE.Vector3(Math.cos(angle) * 0.45, 0.9, Math.sin(angle) * 0.45);
            this.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([center.position.clone(), end]), new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.5 })));
            const node = new THREE.Mesh(new THREE.SphereGeometry(0.05, 8, 8), new THREE.MeshBasicMaterial({ color }));
            node.position.copy(end);
            this.add(node);
        }
    }

    _addSteps(color, n) {
        for (let i = 0; i < n; i++) {
            const box = new THREE.Mesh(new THREE.BoxGeometry(0.15, 0.08, 0.1), new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.2 }));
            box.position.set(0, 0.9 + i * 0.12, 0);
            this.add(box);
        }
    }

    _addTools(color, n) {
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const tool = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.15, 0.05), new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.2 }));
            tool.position.set(Math.cos(angle) * 0.4, 1.1, Math.sin(angle) * 0.4);
            tool.rotation.y = -angle;
            this.add(tool);
        }
    }

    _addGenUX(color) {
        const panel = new THREE.Mesh(new THREE.PlaneGeometry(0.5, 0.4), new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.6, side: THREE.DoubleSide }));
        panel.position.set(0, 1.2, 0);
        panel.rotation.y = 0.2;
        this.add(panel);
    }

    _addReflow(color) {
        const grid = new THREE.GridHelper(0.6, 3, color, color);
        grid.position.y = 1.1;
        grid.material.transparent = true;
        grid.material.opacity = 0.5;
        this.add(grid);
    }

    _addDefault(color) {
        const cube = new THREE.Mesh(
            new THREE.BoxGeometry(0.35, 0.35, 0.35),
            new THREE.MeshPhysicalMaterial({ color, metalness: 0.5, roughness: 0.3 })
        );
        cube.position.y = 1.2;
        this.add(cube);
    }

    update(deltaTime, camera = null) {
        this.time += deltaTime;
        this.traverse(obj => {
            if (obj.material?.emissiveIntensity !== undefined)
                obj.material.emissiveIntensity = (obj.material.emissiveIntensity || 0.2) + Math.sin(this.time * 2) * 0.1;
        });
        const defaultViz = this.children.find(c => c.type === 'Mesh' && c.geometry?.type === 'BoxGeometry' && c.position.y > 1);
        if (defaultViz) {
            defaultViz.rotation.x = this.time * 0.3;
            defaultViz.rotation.y = this.time * 0.5;
        }
    }

    dispose() {
        this.traverse(o => {
            if (o.geometry) o.geometry.dispose();
            if (o.material) o.material.dispose();
        });
    }
}

export function createP3Artwork(patent) {
    return new BespokeP3Artwork(patent);
}

export default { BespokeP3Artwork, createP3Artwork, P3_VISUALS };
