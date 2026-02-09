/**
 * P3 Bespoke Artworks
 * ===================
 *
 * Unique visualization per P3 patent. Config-driven to keep 30 patents maintainable.
 * Each type now has: detailed geometry, educational labels, category-specific animation.
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

// Educational label utility (canvas → sprite)
function createEducationalLabel(text, options = {}) {
    const { fontSize = 24, maxWidth = 320, bgColor = 'rgba(10, 10, 21, 0.85)', textColor = '#E0E0E0' } = options;
    const canvas = document.createElement('canvas');
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width = maxWidth * dpr;
    canvas.height = (fontSize + 16) * dpr;
    const ctx = canvas.getContext('2d');
    ctx.scale(dpr, dpr);
    ctx.fillStyle = bgColor;
    ctx.roundRect?.(0, 0, maxWidth, fontSize + 16, 6);
    ctx.fill();
    ctx.fillStyle = textColor;
    ctx.font = `${fontSize}px 'IBM Plex Sans', sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(text, maxWidth / 2, (fontSize + 16) / 2, maxWidth - 16);
    const tex = new THREE.CanvasTexture(canvas);
    tex.minFilter = THREE.LinearFilter;
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
    sprite.userData.isLabel = true;
    return sprite;
}

// Per-patent visual config + educational text
const P3_VISUALS = {
    'P3-A7': { type: 'kaleidoscope', count: 6, title: 'Lie Algebra Kaleidoscope', desc: 'Symmetry-preserving reflections in representation space' },
    'P3-A8': { type: 'octonion', rings: 4, title: 'Octonion Normalization', desc: '8-dimensional non-associative algebra · Frey octave layers' },
    'P3-B4': { type: 'landscape', peaks: 5, title: 'Safety Landscape Mapping', desc: 'Topographic h(x) ≥ 0 constraint surface visualization' },
    'P3-B5': { type: 'recovery', arcs: 3, title: 'Graceful Recovery Arcs', desc: 'Barrier violation recovery · Smooth return to safe set' },
    'P3-B6': { type: 'frontier', radius: 0.8, title: 'Safety Frontier Explorer', desc: 'Boundary of the safe operating region in state space' },
    'P3-C4': { type: 'gossip', nodes: 8, title: 'Gossip Protocol Network', desc: 'Epidemic-style eventual consistency · Random peer sync' },
    'P3-C5': { type: 'sync', views: 4, title: 'View Synchronization', desc: 'Distributed view alignment across 4 replicas' },
    'P3-D5': { type: 'dream', bubbles: 5, title: 'Dream Replay Learning', desc: 'Offline imagination training · RSSM dream sequences' },
    'P3-D6': { type: 'contrast', branches: 6, title: 'Contrastive Learning Tree', desc: 'Positive/negative pair separation in embedding space' },
    'P3-D7': { type: 'multiscale', layers: 4, title: 'Multi-Scale Attention', desc: '4-level hierarchical feature extraction · Progressive pooling' },
    'P3-E3': { type: 'zk', reveal: true, title: 'Zero-Knowledge Proof', desc: 'Prove knowledge without revealing data · Commitment scheme' },
    'P3-E4': { type: 'threshold', shards: 5, title: 'Threshold Encryption', desc: '3-of-5 secret sharing · Shamir polynomial reconstruction' },
    'P3-F3': { type: 'presence', rooms: 4, title: 'Presence Detection', desc: 'Room-level occupancy sensing · Multi-zone awareness' },
    'P3-F4': { type: 'circadian', arc: true, title: 'Circadian Light Tuning', desc: 'Color temperature follows solar arc · Melatonin-aware' },
    'P3-F5': { type: 'audioSync', speakers: 6, title: 'Multi-Room Audio Sync', desc: '6-speaker coordination · Sub-millisecond alignment' },
    'P3-F6': { type: 'comfort', orb: true, title: 'Comfort Index Orb', desc: 'Ambient wellbeing indicator · Temperature + humidity + noise' },
    'P3-F7': { type: 'energy', curve: true, title: 'Energy Optimization', desc: 'Consumption prediction · Solar + grid balancing' },
    'P3-G2': { type: 'routing', paths: 5, title: 'Intent Routing Engine', desc: '5-path skill dispatch · Context-weighted selection' },
    'P3-G3': { type: 'earcons', symbols: 5, title: 'Earcon Symbol Library', desc: '5 semantic audio symbols · Action confirmation sounds' },
    'P3-G4': { type: 'spatial', sources: 4, title: 'Spatial Audio Engine', desc: '4-source 3D positioning · HRTF-based spatialization' },
    'P3-H3': { type: 'signal', wave: true, title: 'Market Signal Analysis', desc: 'Economic trend detection · Fourier decomposition' },
    'P3-H4': { type: 'risk', cloud: true, title: 'Risk Assessment Cloud', desc: 'Monte Carlo uncertainty · Decision-time risk quantification' },
    'P3-I3': { type: 'mesh', routes: 6, title: 'Service Mesh Router', desc: '6-route load balancing · Health-aware failover' },
    'P3-I4': { type: 'hotReload', ripple: true, title: 'Hot Reload Engine', desc: 'Zero-downtime module update · Ripple propagation' },
    'P3-I5': { type: 'metrics', streams: 5, title: 'Telemetry Streams', desc: '5-stream real-time metrics · Anomaly detection' },
    'P3-J1': { type: 'searchAugment', links: 4, title: 'Search-Augmented Generation', desc: 'Retrieval + generation fusion · 4 knowledge sources' },
    'P3-J2': { type: 'verification', steps: 5, title: 'Output Verification Chain', desc: '5-step cascading validation · Confidence scoring' },
    'P3-J3': { type: 'toolSelect', tools: 4, title: 'Dynamic Tool Selection', desc: '4-tool repertoire · EFE-guided tool dispatch' },
    'P3-K1': { type: 'genux', generate: true, title: 'Generative UX Engine', desc: 'AI-driven interface generation · Context-adaptive layout' },
    'P3-K2': { type: 'adaptive', reflow: true, title: 'Adaptive Reflow System', desc: 'Responsive layout optimization · Content-aware grid' }
};

export class BespokeP3Artwork extends THREE.Group {
    constructor(patent, config = {}) {
        super();
        this.patent = patent;
        this.config = { type: 'default', ...P3_VISUALS[patent.id], ...config };
        this.time = 0;
        this.name = `artwork-${patent.id}`;
        this.userData = { patentId: patent.id, interactive: true };
        this._animatedElements = []; // Targeted animation tracking
        this._labelsVisible = true;
        this._build();
    }
    
    onClick() {
        // Open info panel via event dispatch
        window.dispatchEvent(new CustomEvent('patent-select', {
            detail: { patentId: this.patent.id }
        }));
    }

    _build() {
        const color = getColor(this.patent);
        this._pedestal(color);
        this._visual(color);
        this._addLabels();
        const plaque = createPlaque(this.patent, { width: 1.8, height: 1.0, showDescription: true });
        plaque.position.set(0, 0.7, 1.8);
        plaque.rotation.x = -0.2;
        this.add(plaque);
    }

    _addLabels() {
        const cfg = this.config;
        if (cfg.title) {
            const title = createEducationalLabel(cfg.title, { fontSize: 22, maxWidth: 380 });
            title.position.set(0, 2.0, 0);
            title.scale.set(1.5, 0.22, 1);
            this.add(title);
        }
        if (cfg.desc) {
            const desc = createEducationalLabel(cfg.desc, { fontSize: 15, maxWidth: 440 });
            desc.position.set(0, 0.45, 0);
            desc.scale.set(2, 0.17, 1);
            this.add(desc);
        }
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
        // Kaleidoscope: symmetric rays with mirrored pairs + center crystal
        const centerGeo = new THREE.OctahedronGeometry(0.12, 1);
        const center = new THREE.Mesh(centerGeo, new THREE.MeshPhysicalMaterial({
            color, emissive: color, emissiveIntensity: 0.5, metalness: 0.8, roughness: 0.1
        }));
        center.position.y = 1.3;
        center.userData.animType = 'spin';
        this.add(center);
        
        for (let i = 0; i < count; i++) {
            const angle = (i / count) * Math.PI * 2;
            // Primary ray
            const geo = new THREE.CylinderGeometry(0.015, 0.04, 0.7, 8);
            const hue = i / count;
            const rayColor = new THREE.Color().setHSL(hue * 0.3 + 0.7, 0.7, 0.6);
            const m = new THREE.MeshPhysicalMaterial({ color: rayColor, emissive: rayColor, emissiveIntensity: 0.3 });
            const ray = new THREE.Mesh(geo, m);
            ray.position.set(Math.cos(angle) * 0.3, 1.3, Math.sin(angle) * 0.3);
            ray.lookAt(center.position);
            this.add(ray);
            // Mirror ray (reflected)
            const mirrorRay = ray.clone();
            mirrorRay.position.set(Math.cos(angle) * 0.55, 1.3, Math.sin(angle) * 0.55);
            mirrorRay.material = m.clone();
            mirrorRay.material.opacity = 0.5;
            mirrorRay.material.transparent = true;
            this.add(mirrorRay);
        }
        // Reflection ring
        const ringGeo = new THREE.TorusGeometry(0.42, 0.008, 8, count * 4);
        const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.25 }));
        ring.rotation.x = Math.PI / 2;
        ring.position.y = 1.3;
        ring.userData.animType = 'orbit';
        this.add(ring);
    }

    _addRings(color, n) {
        // Octonion: nested tilted rings representing 8D algebra
        for (let i = 0; i < n; i++) {
            const r = 0.15 + i * 0.15;
            const geo = new THREE.TorusGeometry(r, 0.015, 12, 48);
            const hue = i / n * 0.2;
            const ringColor = new THREE.Color().setHSL(hue + 0.5, 0.7, 0.55);
            const m = new THREE.MeshPhysicalMaterial({ color: ringColor, emissive: ringColor, emissiveIntensity: 0.25, transparent: true, opacity: 0.6 });
            const ring = new THREE.Mesh(geo, m);
            ring.rotation.x = Math.PI / 2 + i * 0.3;
            ring.rotation.y = i * Math.PI / n;
            ring.position.y = 1.25;
            ring.userData.animType = 'tilt';
            ring.userData.idx = i;
            this.add(ring);
        }
        // Central octonion marker
        const coreGeo = new THREE.IcosahedronGeometry(0.08, 0);
        const core = new THREE.Mesh(coreGeo, new THREE.MeshPhysicalMaterial({
            color, emissive: color, emissiveIntensity: 0.6
        }));
        core.position.y = 1.25;
        core.userData.animType = 'spin';
        this.add(core);
    }

    _addPeaks(color, n) {
        // Safety landscape: mountain range of barrier functions
        for (let i = 0; i < n; i++) {
            const height = 0.3 + Math.sin(i * 1.2) * 0.4 + 0.5;
            const geo = new THREE.ConeGeometry(0.15, height, 6);
            const safe = height > 0.5;
            const peakColor = safe ? 0x4CFF4C : 0xFF4444;
            const m = new THREE.MeshPhysicalMaterial({
                color: peakColor, emissive: peakColor, emissiveIntensity: 0.2,
                transparent: true, opacity: 0.7
            });
            const peak = new THREE.Mesh(geo, m);
            peak.position.set((i - n / 2) * 0.22, 0.8 + height / 2, 0);
            this.add(peak);
        }
        // Zero-level plane
        const planeGeo = new THREE.PlaneGeometry(1.4, 0.005);
        const plane = new THREE.Mesh(planeGeo, new THREE.MeshBasicMaterial({
            color: 0xFFD700, transparent: true, opacity: 0.3, side: THREE.DoubleSide
        }));
        plane.rotation.x = Math.PI / 2;
        plane.position.y = 1.05;
        this.add(plane);
    }

    _addArcs(color, n) {
        // Recovery arcs: trajectories returning to safe set
        for (let i = 0; i < n; i++) {
            const startX = -0.5 + i * 0.15;
            const curve = new THREE.QuadraticBezierCurve3(
                new THREE.Vector3(startX, 0.7, (i - 1) * 0.1),
                new THREE.Vector3(startX * 0.3, 1.5 + i * 0.15, i * 0.05),
                new THREE.Vector3(0, 1.2, 0)  // All converge to safe center
            );
            const pts = curve.getPoints(24);
            const geo = new THREE.BufferGeometry().setFromPoints(pts);
            const arcColor = new THREE.Color().setHSL(0.35 - i * 0.1, 0.7, 0.55);
            this.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ color: arcColor, transparent: true, opacity: 0.6 })));
            // Arrowhead at safe center
            const arrow = new THREE.Mesh(
                new THREE.ConeGeometry(0.025, 0.06, 6),
                new THREE.MeshBasicMaterial({ color: arcColor })
            );
            arrow.position.set(0, 1.2, 0);
            this.add(arrow);
        }
        // Safe center marker
        const safeGeo = new THREE.SphereGeometry(0.06, 16, 16);
        const safe = new THREE.Mesh(safeGeo, new THREE.MeshPhysicalMaterial({
            color: 0x4CFF4C, emissive: 0x4CFF4C, emissiveIntensity: 0.5
        }));
        safe.position.y = 1.2;
        safe.userData.animType = 'pulse';
        this.add(safe);
    }

    _addFrontier(color, r = 0.8) {
        // Safety frontier: pulsing boundary with inner safe zone
        const ringGeo = new THREE.TorusGeometry(r, 0.02, 12, 64);
        const ring = new THREE.Mesh(ringGeo, new THREE.MeshPhysicalMaterial({
            color, emissive: color, emissiveIntensity: 0.3, transparent: true, opacity: 0.6
        }));
        ring.rotation.x = -Math.PI / 2;
        ring.position.y = 1.2;
        ring.userData.animType = 'pulse';
        this.add(ring);
        // Inner safe zone (green disc)
        const discGeo = new THREE.CircleGeometry(r * 0.7, 32);
        const disc = new THREE.Mesh(discGeo, new THREE.MeshBasicMaterial({
            color: 0x4CFF4C, transparent: true, opacity: 0.15, side: THREE.DoubleSide
        }));
        disc.rotation.x = -Math.PI / 2;
        disc.position.y = 1.19;
        this.add(disc);
        // Outer unsafe zone marker
        const outerGeo = new THREE.RingGeometry(r, r + 0.15, 32);
        const outer = new THREE.Mesh(outerGeo, new THREE.MeshBasicMaterial({
            color: 0xFF4444, transparent: true, opacity: 0.1, side: THREE.DoubleSide
        }));
        outer.rotation.x = -Math.PI / 2;
        outer.position.y = 1.18;
        this.add(outer);
        // Agent sphere that moves along the frontier boundary
        const agent = new THREE.Mesh(
            new THREE.SphereGeometry(0.04, 16, 16),
            new THREE.MeshPhysicalMaterial({ color: 0xFFD700, emissive: 0xFFD700, emissiveIntensity: 0.6 })
        );
        agent.position.set(r * 0.9, 1.2, 0);
        agent.userData.animType = 'frontierAgent';
        agent.userData.frontierR = r;
        this.add(agent);
        // Probe points along the frontier boundary
        const probeCount = 8;
        for (let i = 0; i < probeCount; i++) {
            const probeAngle = (i / probeCount) * Math.PI * 2;
            const probe = new THREE.Mesh(
                new THREE.SphereGeometry(0.015, 8, 8),
                new THREE.MeshBasicMaterial({ color: 0x4CFF4C, transparent: true, opacity: 0.5 })
            );
            probe.position.set(Math.cos(probeAngle) * r * 0.9, 1.2, Math.sin(probeAngle) * r * 0.9);
            this.add(probe);
        }
    }

    _addNetwork(color, n) {
        // Gossip protocol: nodes with probabilistic connections + message propagation
        const nodes = [];
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const node = new THREE.Mesh(
                new THREE.SphereGeometry(0.06, 12, 12),
                new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.3 })
            );
            node.position.set(Math.cos(angle) * 0.5, 1.2, Math.sin(angle) * 0.5);
            node.userData.animType = 'gossipNode';
            node.userData.idx = i;
            nodes.push(node);
            this.add(node);
        }
        // Deterministic sparse connections (gossip topology)
        const lineMat = new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.25 });
        for (let i = 0; i < n; i++) {
            // Each node talks to 2-3 neighbors
            const targets = [(i + 1) % n, (i + 3) % n];
            targets.forEach(j => {
                this.add(new THREE.Line(
                    new THREE.BufferGeometry().setFromPoints([nodes[i].position.clone(), nodes[j].position.clone()]),
                    lineMat
                ));
            });
        }
        // Gossip "infection" indicator at center
        const indicator = new THREE.Mesh(
            new THREE.SphereGeometry(0.04, 8, 8),
            new THREE.MeshBasicMaterial({ color: 0x4CFF4C, transparent: true, opacity: 0.6 })
        );
        indicator.position.y = 1.2;
        indicator.userData.animType = 'pulse';
        this.add(indicator);
    }

    _addSyncViews(color, n) {
        // View sync: 4 screen panels in a fan with canvas-textured content
        const screenColors = [0xFF6B35, 0x4ECDC4, 0xD4AF37, 0x9B7EBD];
        for (let i = 0; i < n; i++) {
            const angle = -0.4 + (i / (n - 1)) * 0.8;
            // Create canvas texture with colored rectangles
            const canvas = document.createElement('canvas');
            canvas.width = 128;
            canvas.height = 96;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#111';
            ctx.fillRect(0, 0, 128, 96);
            const rects = [
                { x: 10, y: 10, w: 40, h: 20 },
                { x: 60, y: 10, w: 50, h: 30 },
                { x: 10, y: 40, w: 108, h: 15 },
                { x: 10, y: 60, w: 60, h: 25 }
            ];
            rects.forEach((r, j) => {
                const offset = i * 5 + j * 3;
                ctx.fillStyle = `hsl(${(j * 60 + offset * 10) % 360}, 60%, 50%)`;
                ctx.fillRect(r.x + (i - 1) * 3, r.y + (i - 1) * 2, r.w, r.h);
            });
            const tex = new THREE.CanvasTexture(canvas);
            tex.minFilter = THREE.LinearFilter;
            const screen = new THREE.Mesh(
                new THREE.PlaneGeometry(0.28, 0.21),
                new THREE.MeshPhysicalMaterial({
                    map: tex, emissive: color, emissiveIntensity: 0.1,
                    transparent: true, opacity: 0.9, side: THREE.DoubleSide
                })
            );
            screen.position.set((i - (n - 1) / 2) * 0.3, 1.25, 0);
            screen.rotation.y = angle;
            screen.userData.animType = 'syncView';
            screen.userData.idx = i;
            this.add(screen);
        }
        // Sync beam
        const beamPts = [];
        for (let i = 0; i < n; i++) {
            beamPts.push(new THREE.Vector3((i - (n - 1) / 2) * 0.3, 1.05, 0));
        }
        this.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(beamPts),
            new THREE.LineBasicMaterial({ color: 0x4CFF4C, transparent: true, opacity: 0.3 })
        ));
    }

    _addBubbles(color, n) {
        // Dream replay: floating thought bubbles with inner dream content
        const innerShapes = ['tetrahedron', 'box', 'octahedron', 'icosahedron', 'dodecahedron'];
        for (let i = 0; i < n; i++) {
            const size = 0.08 + i * 0.03;
            const geo = new THREE.SphereGeometry(size, 16, 16);
            const b = new THREE.Mesh(geo, new THREE.MeshPhysicalMaterial({
                color, emissive: color, emissiveIntensity: 0.2,
                transparent: true, opacity: 0.4, roughness: 0.1
            }));
            const spread = 0.5;
            b.position.set(
                Math.sin(i * 2.1) * spread * 0.6,
                0.9 + i * 0.2,
                Math.cos(i * 1.7) * spread * 0.3
            );
            b.userData.animType = 'float';
            b.userData.baseY = b.position.y;
            b.userData.idx = i;
            // Inner dream content shape
            const innerSize = size * 0.35;
            let innerGeo;
            switch (innerShapes[i % innerShapes.length]) {
                case 'tetrahedron': innerGeo = new THREE.TetrahedronGeometry(innerSize, 0); break;
                case 'box': innerGeo = new THREE.BoxGeometry(innerSize, innerSize, innerSize); break;
                case 'octahedron': innerGeo = new THREE.OctahedronGeometry(innerSize, 0); break;
                case 'icosahedron': innerGeo = new THREE.IcosahedronGeometry(innerSize, 0); break;
                case 'dodecahedron': innerGeo = new THREE.DodecahedronGeometry(innerSize, 0); break;
            }
            const hue = i / n * 0.3 + 0.6;
            const innerColor = new THREE.Color().setHSL(hue, 0.8, 0.6);
            const inner = new THREE.Mesh(innerGeo, new THREE.MeshPhysicalMaterial({
                color: innerColor, emissive: innerColor, emissiveIntensity: 0.4,
                transparent: true, opacity: 0.7
            }));
            inner.userData.animType = 'spin';
            b.add(inner);
            this.add(b);
        }
    }

    _addBranches(color, n) {
        // Contrastive learning: positive (attract) vs negative (repel) embedding branches
        const root = new THREE.Mesh(
            new THREE.SphereGeometry(0.08, 16, 16),
            new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.4 })
        );
        root.position.y = 1.5;
        this.add(root);
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const positive = i % 2 === 0;
            const branchColor = positive ? 0x4CFF4C : 0xFF6B6B;
            const end = new THREE.Vector3(Math.cos(angle) * 0.45, 1.05, Math.sin(angle) * 0.45);
            this.add(new THREE.Line(
                new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(0, 1.5, 0), end]),
                new THREE.LineBasicMaterial({ color: branchColor, transparent: true, opacity: 0.5 })
            ));
            const leaf = new THREE.Mesh(
                new THREE.SphereGeometry(0.04, 8, 8),
                new THREE.MeshPhysicalMaterial({ color: branchColor, emissive: branchColor, emissiveIntensity: 0.3 })
            );
            leaf.position.copy(end);
            leaf.userData.animType = positive ? 'attract' : 'repel';
            leaf.userData.baseY = end.y;
            this.add(leaf);
        }
    }

    _addLayers(color, n) {
        // Multi-scale attention: stacked feature extraction levels
        for (let i = 0; i < n; i++) {
            const size = 0.6 - i * 0.1;
            // Filled translucent plane instead of grid
            const planeGeo = new THREE.PlaneGeometry(size, size);
            const hue = i / n * 0.2 + 0.45;
            const layerColor = new THREE.Color().setHSL(hue, 0.6, 0.5);
            const plane = new THREE.Mesh(planeGeo, new THREE.MeshPhysicalMaterial({
                color: layerColor, emissive: layerColor, emissiveIntensity: 0.1,
                transparent: true, opacity: 0.35, side: THREE.DoubleSide
            }));
            plane.rotation.x = -Math.PI / 2;
            plane.position.y = 0.8 + i * 0.25;
            this.add(plane);
            // Grid overlay
            const grid = new THREE.GridHelper(size, 3 + i, layerColor, layerColor);
            grid.position.y = 0.81 + i * 0.25;
            grid.material.transparent = true;
            grid.material.opacity = 0.3;
            this.add(grid);
            // Attention arrow from layer to next
            if (i < n - 1) {
                const arrowGeo = new THREE.ConeGeometry(0.02, 0.06, 6);
                const arrow = new THREE.Mesh(arrowGeo, new THREE.MeshBasicMaterial({ color: layerColor }));
                arrow.position.set(0, 0.95 + i * 0.25, 0);
                this.add(arrow);
            }
        }
    }

    _addZK(color) {
        // Zero-knowledge: hidden inner secret + proof boundary
        const inner = new THREE.Mesh(
            new THREE.DodecahedronGeometry(0.12, 0),
            new THREE.MeshPhysicalMaterial({ color: 0xFF6B6B, emissive: 0xFF6B6B, emissiveIntensity: 0.4, transparent: true, opacity: 0.4 })
        );
        inner.position.y = 1.2;
        inner.userData.animType = 'spin';
        this.add(inner);
        // Proof envelope (wireframe)
        const outer = new THREE.Mesh(
            new THREE.IcosahedronGeometry(0.3, 1),
            new THREE.MeshBasicMaterial({ color, wireframe: true, transparent: true, opacity: 0.4 })
        );
        outer.position.y = 1.2;
        outer.userData.animType = 'orbit';
        this.add(outer);
        // "Verified" ring
        const ringGeo = new THREE.TorusGeometry(0.35, 0.008, 8, 48);
        const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({ color: 0x4CFF4C, transparent: true, opacity: 0.3 }));
        ring.rotation.x = Math.PI / 2;
        ring.position.y = 1.2;
        this.add(ring);
    }

    _addShards(color, n) {
        // Threshold encryption: key shards arranged in reconstruct pattern
        const centerGeo = new THREE.SphereGeometry(0.08, 16, 16);
        const center = new THREE.Mesh(centerGeo, new THREE.MeshPhysicalMaterial({
            color: 0xFFD700, emissive: 0xFFD700, emissiveIntensity: 0.4, transparent: true, opacity: 0.5
        }));
        center.position.y = 1.3;
        center.userData.animType = 'pulse';
        this.add(center);
        
        const threshold = 3; // 3-of-5
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const active = i < threshold;
            const shardColor = active ? color : 0x444444;
            const s = new THREE.Mesh(
                new THREE.BoxGeometry(0.06, 0.18, 0.04),
                new THREE.MeshPhysicalMaterial({
                    color: shardColor, emissive: shardColor,
                    emissiveIntensity: active ? 0.4 : 0.05
                })
            );
            s.position.set(Math.cos(angle) * 0.35, 1.15 + (i % 2) * 0.15, Math.sin(angle) * 0.35);
            s.rotation.y = -angle;
            // Connection to center when active
            if (active) {
                this.add(new THREE.Line(
                    new THREE.BufferGeometry().setFromPoints([s.position.clone(), center.position.clone()]),
                    new THREE.LineBasicMaterial({ color: shardColor, transparent: true, opacity: 0.3 })
                ));
            }
            this.add(s);
        }
    }

    _addRooms(color, n) {
        // Presence detection: rooms with occupancy glow
        for (let i = 0; i < n; i++) {
            const occupied = i % 3 !== 2;  // Some rooms occupied
            const roomColor = occupied ? color : 0x333333;
            const box = new THREE.Mesh(
                new THREE.BoxGeometry(0.22, 0.18, 0.18),
                new THREE.MeshPhysicalMaterial({
                    color: roomColor, emissive: roomColor,
                    emissiveIntensity: occupied ? 0.25 : 0.02, transparent: true, opacity: 0.7
                })
            );
            box.position.set((i - (n - 1) / 2) * 0.32, 1.1, 0);
            box.userData.animType = 'presence';
            box.userData.idx = i;
            this.add(box);
            // Door opening
            const door = new THREE.Mesh(
                new THREE.PlaneGeometry(0.04, 0.12),
                new THREE.MeshBasicMaterial({ color: 0x222222, side: THREE.DoubleSide })
            );
            door.position.set(0, -0.03, 0.091);
            box.add(door);
        }
        // Walking figure (capsule) that moves between rooms
        const walker = new THREE.Mesh(
            new THREE.CapsuleGeometry(0.02, 0.06, 4, 8),
            new THREE.MeshPhysicalMaterial({ color: 0xFFD700, emissive: 0xFFD700, emissiveIntensity: 0.5 })
        );
        walker.position.set(0, 1.1, 0);
        walker.userData.animType = 'roomWalker';
        this.add(walker);
    }

    _addArc(color) {
        // Circadian: full solar arc with color temperature gradient
        const pts = [];
        const colors = [];
        for (let i = 0; i <= 48; i++) {
            const t = i / 48;
            const angle = t * Math.PI;
            pts.push(new THREE.Vector3(Math.cos(angle) * 0.5, 1.1 + Math.sin(angle) * 0.35, 0));
            // Color temperature: warm (morning) → cool (noon) → warm (evening)
            const kelvin = t < 0.5 ? t * 2 : (1 - t) * 2;
            colors.push(1 - kelvin * 0.3, 0.8 - kelvin * 0.2, 0.4 + kelvin * 0.5);
        }
        const geo = new THREE.BufferGeometry().setFromPoints(pts);
        geo.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
        this.add(new THREE.Line(geo, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.8 })));
        // Sun position indicator
        const sun = new THREE.Mesh(
            new THREE.SphereGeometry(0.04, 12, 12),
            new THREE.MeshPhysicalMaterial({ color: 0xFFD700, emissive: 0xFFD700, emissiveIntensity: 0.8 })
        );
        sun.position.set(0, 1.45, 0);
        sun.userData.animType = 'circadian';
        this.add(sun);
    }

    _addSpeakers(color, n) {
        // Multi-room audio: speakers with sync waves
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const s = new THREE.Mesh(
                new THREE.CylinderGeometry(0.04, 0.05, 0.12, 16),
                new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.25, metalness: 0.6 })
            );
            const x = Math.cos(angle) * 0.5;
            const z = Math.sin(angle) * 0.5;
            s.position.set(x, 1.1, z);
            this.add(s);
            // Sound wave rings emanating from each speaker
            for (let w = 1; w <= 2; w++) {
                const waveGeo = new THREE.TorusGeometry(0.04 * w, 0.003, 8, 24);
                const wave = new THREE.Mesh(waveGeo, new THREE.MeshBasicMaterial({
                    color, transparent: true, opacity: 0.3 / w
                }));
                wave.rotation.x = Math.PI / 2;
                wave.position.set(x, 1.2, z);
                this.add(wave);
            }
        }
    }

    _addOrb(color) {
        // Comfort orb: layered sphere with zone indicators
        const outerGeo = new THREE.SphereGeometry(0.3, 32, 32);
        const outer = new THREE.Mesh(outerGeo, new THREE.MeshPhysicalMaterial({
            color, emissive: color, emissiveIntensity: 0.3, transparent: true, opacity: 0.4, roughness: 0.05
        }));
        outer.position.y = 1.25;
        outer.userData.animType = 'pulse';
        this.add(outer);
        // Inner comfort core (green = comfortable)
        const innerGeo = new THREE.SphereGeometry(0.15, 24, 24);
        const inner = new THREE.Mesh(innerGeo, new THREE.MeshPhysicalMaterial({
            color: 0x4CFF4C, emissive: 0x4CFF4C, emissiveIntensity: 0.5
        }));
        inner.position.y = 1.25;
        this.add(inner);
        // Comfort zone ring
        const ringGeo = new THREE.TorusGeometry(0.35, 0.008, 8, 48);
        const ring = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({
            color: 0x4CFF4C, transparent: true, opacity: 0.25
        }));
        ring.rotation.x = Math.PI / 2;
        ring.position.y = 1.25;
        this.add(ring);
    }

    _addCurve(color) {
        // Energy optimization: consumption curve with prediction
        const pts = [];
        const predPts = [];
        for (let i = 0; i <= 30; i++) {
            const x = -0.5 + i * 0.033;
            const y = 1.1 + Math.sin(i * 0.4) * 0.15 + Math.sin(i * 0.7) * 0.08;
            pts.push(new THREE.Vector3(x, y, 0));
            if (i > 20) {
                predPts.push(new THREE.Vector3(x, y + 0.05, 0));
            }
        }
        // Actual consumption
        this.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(pts),
            new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.8 })
        ));
        // Predicted (dashed effect via opacity)
        if (predPts.length > 0) {
            this.add(new THREE.Line(
                new THREE.BufferGeometry().setFromPoints(predPts),
                new THREE.LineBasicMaterial({ color: 0x4CFF4C, transparent: true, opacity: 0.5 })
            ));
        }
        // Solar generation overlay
        const solarPts = [];
        for (let i = 0; i <= 30; i++) {
            const x = -0.5 + i * 0.033;
            const y = 0.9 + Math.max(0, Math.sin((i / 30) * Math.PI)) * 0.2;
            solarPts.push(new THREE.Vector3(x, y, 0));
        }
        this.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(solarPts),
            new THREE.LineBasicMaterial({ color: 0xFFD700, transparent: true, opacity: 0.4 })
        ));
    }

    _addPaths(color, n) {
        // Intent routing: hub + skill paths with selection indicator
        const centerGeo = new THREE.OctahedronGeometry(0.08, 0);
        const center = new THREE.Mesh(centerGeo, new THREE.MeshPhysicalMaterial({
            color, emissive: color, emissiveIntensity: 0.5
        }));
        center.position.y = 1.3;
        center.userData.animType = 'spin';
        this.add(center);
        
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const end = new THREE.Vector3(Math.cos(angle) * 0.5, 0.9, Math.sin(angle) * 0.5);
            const hue = i / n;
            const pathColor = new THREE.Color().setHSL(hue, 0.7, 0.55);
            // Curved path
            const mid = new THREE.Vector3(
                Math.cos(angle) * 0.25, 1.15, Math.sin(angle) * 0.25
            );
            const curve = new THREE.QuadraticBezierCurve3(center.position.clone(), mid, end);
            const curvePts = curve.getPoints(16);
            this.add(new THREE.Line(
                new THREE.BufferGeometry().setFromPoints(curvePts),
                new THREE.LineBasicMaterial({ color: pathColor, transparent: true, opacity: 0.4 })
            ));
            // Skill endpoint
            const skill = new THREE.Mesh(
                new THREE.BoxGeometry(0.06, 0.06, 0.06),
                new THREE.MeshPhysicalMaterial({ color: pathColor, emissive: pathColor, emissiveIntensity: 0.2 })
            );
            skill.position.copy(end);
            this.add(skill);
        }
    }

    _addSymbols(color, n) {
        // Earcon symbols: distinct audio icon shapes
        const shapes = ['sphere', 'octahedron', 'tetrahedron', 'cylinder', 'torus'];
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            let geo;
            switch (shapes[i % shapes.length]) {
                case 'sphere': geo = new THREE.SphereGeometry(0.05, 12, 12); break;
                case 'octahedron': geo = new THREE.OctahedronGeometry(0.06, 0); break;
                case 'tetrahedron': geo = new THREE.TetrahedronGeometry(0.06, 0); break;
                case 'cylinder': geo = new THREE.CylinderGeometry(0.03, 0.03, 0.1, 8); break;
                case 'torus': geo = new THREE.TorusGeometry(0.04, 0.015, 8, 24); break;
            }
            const hue = i / n;
            const symColor = new THREE.Color().setHSL(hue, 0.7, 0.55);
            const sym = new THREE.Mesh(geo, new THREE.MeshPhysicalMaterial({
                color: symColor, emissive: symColor, emissiveIntensity: 0.3
            }));
            sym.position.set(Math.cos(angle) * 0.4, 1.2, Math.sin(angle) * 0.4);
            sym.userData.animType = 'earcon';
            sym.userData.idx = i;
            this.add(sym);
            // Sound wave ring
            const ring = new THREE.Mesh(
                new THREE.RingGeometry(0.06, 0.08, 16),
                new THREE.MeshBasicMaterial({ color: symColor, transparent: true, opacity: 0.3, side: THREE.DoubleSide })
            );
            ring.rotation.x = -Math.PI / 2;
            ring.position.set(Math.cos(angle) * 0.4, 1.1, Math.sin(angle) * 0.4);
            this.add(ring);
        }
    }

    _addSources(color, n) {
        // Spatial audio: positioned sources with HRTF-inspired arcs
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const x = Math.cos(angle) * 0.4;
            const z = Math.sin(angle) * 0.4;
            const s = new THREE.Mesh(
                new THREE.SphereGeometry(0.06, 16, 16),
                new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.4 })
            );
            s.position.set(x, 1.2, z);
            s.userData.animType = 'spatialSource';
            s.userData.idx = i;
            this.add(s);
            // Directional arc (HRTF cone)
            const arcGeo = new THREE.ConeGeometry(0.08, 0.15, 8, 1, true);
            const arc = new THREE.Mesh(arcGeo, new THREE.MeshBasicMaterial({
                color, transparent: true, opacity: 0.15, side: THREE.DoubleSide
            }));
            arc.position.set(x * 0.7, 1.2, z * 0.7);
            arc.lookAt(new THREE.Vector3(0, 1.2, 0));
            this.add(arc);
        }
        // Listener position (center)
        const listener = new THREE.Mesh(
            new THREE.SphereGeometry(0.04, 12, 12),
            new THREE.MeshPhysicalMaterial({ color: 0xFFFFFF, emissive: 0xFFFFFF, emissiveIntensity: 0.3 })
        );
        listener.position.y = 1.2;
        this.add(listener);
    }

    _addWave(color) {
        // Market signal: animated waveform with Fourier components
        const pts = [];
        for (let i = 0; i <= 40; i++) {
            const x = -0.6 + i * 0.03;
            const y = 1.2 + Math.sin(i * 0.3) * 0.12 + Math.sin(i * 0.7) * 0.06 + Math.sin(i * 1.1) * 0.03;
            pts.push(new THREE.Vector3(x, y, 0));
        }
        const waveLine = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(pts),
            new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.8 })
        );
        waveLine.userData.animType = 'wave';
        this.add(waveLine);
        // Trend line
        this.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(-0.6, 1.15, 0),
                new THREE.Vector3(0.6, 1.3, 0)
            ]),
            new THREE.LineBasicMaterial({ color: 0x4CFF4C, transparent: true, opacity: 0.3 })
        ));
        // Fourier decomposition: 3 component sine waves
        const components = [
            { freq: 0.3, amp: 0.06, baseY: 0.9, color: 0xFF6B35 },
            { freq: 0.7, amp: 0.04, baseY: 0.78, color: 0x4ECDC4 },
            { freq: 1.1, amp: 0.025, baseY: 0.68, color: 0x9B7EBD }
        ];
        components.forEach(comp => {
            const cPts = [];
            for (let i = 0; i <= 40; i++) {
                const x = -0.6 + i * 0.03;
                const y = comp.baseY + Math.sin(i * comp.freq) * comp.amp;
                cPts.push(new THREE.Vector3(x, y, 0));
            }
            this.add(new THREE.Line(
                new THREE.BufferGeometry().setFromPoints(cPts),
                new THREE.LineBasicMaterial({ color: comp.color, transparent: true, opacity: 0.4 })
            ));
        });
    }

    _addCloud(color) {
        // Risk cloud: Monte Carlo particles with density gradient
        const g = new THREE.BufferGeometry();
        const count = 60;
        const pos = new Float32Array(count * 3);
        const colors = new Float32Array(count * 3);
        for (let i = 0; i < count; i++) {
            const r = Math.random() * 0.5;
            const theta = Math.random() * Math.PI * 2;
            const phi = Math.random() * Math.PI;
            pos[i * 3] = r * Math.sin(phi) * Math.cos(theta);
            pos[i * 3 + 1] = 1.1 + r * Math.cos(phi) * 0.5;
            pos[i * 3 + 2] = r * Math.sin(phi) * Math.sin(theta) * 0.5;
            // Redder toward edges (higher risk)
            const risk = r / 0.5;
            colors[i * 3] = 0.3 + risk * 0.7;
            colors[i * 3 + 1] = 0.7 - risk * 0.5;
            colors[i * 3 + 2] = 0.2;
        }
        g.setAttribute('position', new THREE.BufferAttribute(pos, 3));
        g.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        this.add(new THREE.Points(g, new THREE.PointsMaterial({
            size: 0.04, vertexColors: true, transparent: true, opacity: 0.7
        })));
        // Decision boundary surface — semi-transparent angled plane
        const boundaryGeo = new THREE.PlaneGeometry(0.7, 0.5);
        const boundary = new THREE.Mesh(boundaryGeo, new THREE.MeshPhysicalMaterial({
            color: 0x4ECDC4, emissive: 0x4ECDC4, emissiveIntensity: 0.1,
            transparent: true, opacity: 0.2, side: THREE.DoubleSide
        }));
        boundary.position.set(0, 1.1, 0);
        boundary.rotation.x = -0.3;
        boundary.rotation.z = 0.4;
        this.add(boundary);
    }

    _addRoutes(color, n) {
        // Service mesh: hub + routes with health indicators
        const hubGeo = new THREE.IcosahedronGeometry(0.08, 0);
        const hub = new THREE.Mesh(hubGeo, new THREE.MeshPhysicalMaterial({
            color, emissive: color, emissiveIntensity: 0.5
        }));
        hub.position.y = 1.2;
        hub.userData.animType = 'spin';
        this.add(hub);
        
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            const healthy = i !== 2;  // One unhealthy route
            const routeColor = healthy ? color : 0xFF4444;
            const end = new THREE.Vector3(Math.cos(angle) * 0.5, 1.0 + (i % 2) * 0.2, Math.sin(angle) * 0.5);
            
            const tubeGeo = new THREE.CylinderGeometry(0.015, 0.015, hub.position.distanceTo(end), 8);
            const tube = new THREE.Mesh(tubeGeo, new THREE.MeshBasicMaterial({
                color: routeColor, transparent: true, opacity: healthy ? 0.5 : 0.3
            }));
            tube.position.copy(hub.position.clone().add(end).multiplyScalar(0.5));
            tube.lookAt(end);
            tube.rotateX(Math.PI / 2);
            this.add(tube);
            
            // Service node
            const nodeGeo = new THREE.BoxGeometry(0.06, 0.06, 0.06);
            const node = new THREE.Mesh(nodeGeo, new THREE.MeshPhysicalMaterial({
                color: routeColor, emissive: routeColor, emissiveIntensity: healthy ? 0.3 : 0.1
            }));
            node.position.copy(end);
            this.add(node);
        }
    }

    _addRipple(color) {
        // Hot reload: module replacement visualization
        // Old module (fading out)
        const oldModule = new THREE.Mesh(
            new THREE.BoxGeometry(0.18, 0.14, 0.06),
            new THREE.MeshPhysicalMaterial({
                color: 0xFF6B6B, emissive: 0xFF6B6B, emissiveIntensity: 0.2,
                transparent: true, opacity: 0.6
            })
        );
        oldModule.position.set(-0.25, 1.2, 0);
        oldModule.userData.animType = 'ripple';
        oldModule.userData.role = 'oldModule';
        this.add(oldModule);
        // New module (fading in)
        const newModule = new THREE.Mesh(
            new THREE.BoxGeometry(0.18, 0.14, 0.06),
            new THREE.MeshPhysicalMaterial({
                color: 0x4CFF4C, emissive: 0x4CFF4C, emissiveIntensity: 0.3,
                transparent: true, opacity: 0.3
            })
        );
        newModule.position.set(0.25, 1.2, 0);
        newModule.userData.animType = 'ripple';
        newModule.userData.role = 'newModule';
        this.add(newModule);
        // Ripple ring between them
        const rippleRing = new THREE.Mesh(
            new THREE.TorusGeometry(0.12, 0.008, 8, 48),
            new THREE.MeshPhysicalMaterial({
                color, emissive: color, emissiveIntensity: 0.3,
                transparent: true, opacity: 0.5
            })
        );
        rippleRing.position.set(0, 1.2, 0);
        rippleRing.rotation.y = Math.PI / 2;
        rippleRing.userData.animType = 'ripple';
        rippleRing.userData.role = 'ring';
        this.add(rippleRing);
        // Transition arrow from old to new
        const arrow = new THREE.Mesh(
            new THREE.ConeGeometry(0.02, 0.08, 6),
            new THREE.MeshBasicMaterial({ color: 0xFFD700 })
        );
        arrow.position.set(0, 1.35, 0);
        arrow.rotation.z = -Math.PI / 2;
        this.add(arrow);
        this.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(-0.16, 1.35, 0), new THREE.Vector3(0.16, 1.35, 0)
            ]),
            new THREE.LineBasicMaterial({ color: 0xFFD700, transparent: true, opacity: 0.4 })
        ));
        // Status indicators
        const oldStatus = new THREE.Mesh(
            new THREE.SphereGeometry(0.015, 8, 8),
            new THREE.MeshBasicMaterial({ color: 0xFF4444 })
        );
        oldStatus.position.set(-0.25, 1.05, 0);
        this.add(oldStatus);
        const newStatus = new THREE.Mesh(
            new THREE.SphereGeometry(0.015, 8, 8),
            new THREE.MeshBasicMaterial({ color: 0x4CFF4C })
        );
        newStatus.position.set(0.25, 1.05, 0);
        this.add(newStatus);
    }

    _addStreams(color, n) {
        // Telemetry: flowing data streams with anomaly markers
        for (let i = 0; i < n; i++) {
            const y = 1.4 - i * 0.12;
            const pts = [];
            const hasAnomaly = i === 2;
            for (let j = 0; j <= 20; j++) {
                const x = -0.4 + j * 0.04;
                const spike = hasAnomaly && j > 12 && j < 16 ? 0.08 : 0;
                pts.push(new THREE.Vector3(x, y + Math.sin(j * 0.5 + i) * 0.02 + spike, 0));
            }
            const streamColor = hasAnomaly ? 0xFF6B6B : color;
            this.add(new THREE.Line(
                new THREE.BufferGeometry().setFromPoints(pts),
                new THREE.LineBasicMaterial({ color: streamColor, transparent: true, opacity: 0.6 })
            ));
        }
        // Anomaly marker
        const marker = new THREE.Mesh(
            new THREE.SphereGeometry(0.025, 8, 8),
            new THREE.MeshBasicMaterial({ color: 0xFF4444 })
        );
        marker.position.set(0.12, 1.16 + 0.08, 0);
        marker.userData.animType = 'pulse';
        this.add(marker);
    }

    _addLinks(color, n) {
        // RAG pipeline: central generator + knowledge source nodes + output panel
        const center = new THREE.Mesh(
            new THREE.DodecahedronGeometry(0.12, 0),
            new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: 0.5, metalness: 0.6 })
        );
        center.position.y = 1.3;
        center.userData.animType = 'spin';
        this.add(center);
        // 4 knowledge source nodes in semicircle (left side)
        const sourceColors = [0x4ECDC4, 0xD4AF37, 0x9B7EBD, 0xFF6B35];
        for (let i = 0; i < n; i++) {
            const angle = Math.PI * 0.3 + (i / (n - 1)) * Math.PI * 0.9;
            const x = -Math.cos(angle) * 0.55;
            const y = 1.3 + Math.sin(angle) * 0.35;
            const node = new THREE.Mesh(
                new THREE.BoxGeometry(0.09, 0.07, 0.05),
                new THREE.MeshPhysicalMaterial({
                    color: sourceColors[i], emissive: sourceColors[i], emissiveIntensity: 0.15
                })
            );
            node.position.set(x, y, 0);
            node.userData.animType = 'searchPulse';
            node.userData.idx = i;
            this.add(node);
            // Retrieval arrow (cone pointing from source to center)
            const arrow = new THREE.Mesh(
                new THREE.ConeGeometry(0.018, 0.07, 6),
                new THREE.MeshBasicMaterial({ color: sourceColors[i], transparent: true, opacity: 0.7 })
            );
            const midX = (x + center.position.x) / 2;
            const midY = (y + center.position.y) / 2;
            arrow.position.set(midX, midY, 0);
            arrow.lookAt(center.position);
            arrow.rotateX(Math.PI / 2);
            this.add(arrow);
            // Connection line
            this.add(new THREE.Line(
                new THREE.BufferGeometry().setFromPoints([
                    new THREE.Vector3(x, y, 0), center.position.clone()
                ]),
                new THREE.LineBasicMaterial({ color: sourceColors[i], transparent: true, opacity: 0.25 })
            ));
        }
        // Generated output panel (right side)
        const outputPanel = new THREE.Mesh(
            new THREE.PlaneGeometry(0.25, 0.18),
            new THREE.MeshPhysicalMaterial({
                color: 0x4CFF4C, emissive: 0x4CFF4C, emissiveIntensity: 0.15,
                transparent: true, opacity: 0.6, side: THREE.DoubleSide
            })
        );
        outputPanel.position.set(0.45, 1.3, 0);
        this.add(outputPanel);
        // Output arrow from center to panel
        const outArrow = new THREE.Mesh(
            new THREE.ConeGeometry(0.02, 0.08, 6),
            new THREE.MeshBasicMaterial({ color: 0x4CFF4C })
        );
        outArrow.position.set(0.25, 1.3, 0);
        outArrow.rotation.z = -Math.PI / 2;
        this.add(outArrow);
        this.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([
                center.position.clone(), new THREE.Vector3(0.45, 1.3, 0)
            ]),
            new THREE.LineBasicMaterial({ color: 0x4CFF4C, transparent: true, opacity: 0.3 })
        ));
    }

    _addSteps(color, n) {
        // Verification chain: diagonal staircase with connecting lines + check/pending indicators
        for (let i = 0; i < n; i++) {
            const x = -0.3 + i * 0.15;
            const y = 0.8 + i * 0.15;
            // Step box
            const box = new THREE.Mesh(
                new THREE.BoxGeometry(0.12, 0.08, 0.08),
                new THREE.MeshPhysicalMaterial({
                    color, emissive: color, emissiveIntensity: 0.05
                })
            );
            box.position.set(x, y, 0);
            box.userData.animType = 'verifyStep';
            box.userData.idx = i;
            this.add(box);
            // Check indicator: sphere (done) or ring (pending)
            const done = i < 3;
            if (done) {
                const sphere = new THREE.Mesh(
                    new THREE.SphereGeometry(0.025, 10, 10),
                    new THREE.MeshPhysicalMaterial({ color: 0x4CFF4C, emissive: 0x4CFF4C, emissiveIntensity: 0.4 })
                );
                sphere.position.set(x + 0.1, y, 0);
                this.add(sphere);
            } else {
                const ring = new THREE.Mesh(
                    new THREE.TorusGeometry(0.025, 0.005, 8, 24),
                    new THREE.MeshBasicMaterial({ color: 0x666666, transparent: true, opacity: 0.5 })
                );
                ring.position.set(x + 0.1, y, 0);
                this.add(ring);
            }
            // Connecting line to next step
            if (i < n - 1) {
                this.add(new THREE.Line(
                    new THREE.BufferGeometry().setFromPoints([
                        new THREE.Vector3(x + 0.06, y + 0.04, 0),
                        new THREE.Vector3(x + 0.09, y + 0.11, 0)
                    ]),
                    new THREE.LineBasicMaterial({ color, transparent: true, opacity: 0.3 })
                ));
            }
        }
    }

    _addTools(color, n) {
        // Dynamic tool selection: orbital tools with selection highlight
        const hubGeo = new THREE.SphereGeometry(0.06, 12, 12);
        const hub = new THREE.Mesh(hubGeo, new THREE.MeshPhysicalMaterial({
            color, emissive: color, emissiveIntensity: 0.5
        }));
        hub.position.y = 1.2;
        this.add(hub);
        
        const toolShapes = ['box', 'cone', 'cylinder', 'octahedron'];
        for (let i = 0; i < n; i++) {
            const angle = (i / n) * Math.PI * 2;
            let toolGeo;
            switch (toolShapes[i % toolShapes.length]) {
                case 'box': toolGeo = new THREE.BoxGeometry(0.08, 0.12, 0.05); break;
                case 'cone': toolGeo = new THREE.ConeGeometry(0.05, 0.12, 6); break;
                case 'cylinder': toolGeo = new THREE.CylinderGeometry(0.04, 0.04, 0.12, 8); break;
                case 'octahedron': toolGeo = new THREE.OctahedronGeometry(0.06, 0); break;
            }
            const selected = i === 0;
            const toolColor = selected ? 0x4CFF4C : color;
            const tool = new THREE.Mesh(toolGeo, new THREE.MeshPhysicalMaterial({
                color: toolColor, emissive: toolColor, emissiveIntensity: selected ? 0.5 : 0.15
            }));
            tool.position.set(Math.cos(angle) * 0.35, 1.2, Math.sin(angle) * 0.35);
            tool.rotation.y = -angle;
            tool.userData.animType = 'toolOrbit';
            tool.userData.idx = i;
            this.add(tool);
        }
    }

    _addGenUX(color) {
        // Generative UX: 3-panel wireframe-to-filled morphing sequence
        const panelConfigs = [
            { x: -0.35, wireframe: true, opacity: 0.3, emissive: 0.05 },
            { x: 0, wireframe: false, opacity: 0.5, emissive: 0.15 },
            { x: 0.35, wireframe: false, opacity: 0.8, emissive: 0.35 }
        ];
        panelConfigs.forEach((cfg, i) => {
            const panel = new THREE.Mesh(
                new THREE.BoxGeometry(0.25, 0.2, 0.02),
                cfg.wireframe
                    ? new THREE.MeshBasicMaterial({ color, wireframe: true, transparent: true, opacity: cfg.opacity })
                    : new THREE.MeshPhysicalMaterial({ color, emissive: color, emissiveIntensity: cfg.emissive, transparent: true, opacity: cfg.opacity })
            );
            panel.position.set(cfg.x, 1.25, 0);
            if (i === 0) panel.userData.animType = 'morph';
            this.add(panel);
            // Semi-filled: add some solid face rectangles
            if (i === 1) {
                for (let r = 0; r < 3; r++) {
                    const rect = new THREE.Mesh(
                        new THREE.PlaneGeometry(0.06, 0.04),
                        new THREE.MeshPhysicalMaterial({
                            color, emissive: color, emissiveIntensity: 0.2,
                            transparent: true, opacity: 0.6, side: THREE.DoubleSide
                        })
                    );
                    rect.position.set(-0.05 + r * 0.05, -0.04 + r * 0.04, 0.011);
                    panel.add(rect);
                }
            }
            // Filled: add content lines
            if (i === 2) {
                for (let l = 0; l < 4; l++) {
                    const line = new THREE.Mesh(
                        new THREE.PlaneGeometry(0.18, 0.015),
                        new THREE.MeshBasicMaterial({ color: 0xFFFFFF, transparent: true, opacity: 0.3, side: THREE.DoubleSide })
                    );
                    line.position.set(0, 0.06 - l * 0.035, 0.011);
                    panel.add(line);
                }
            }
        });
        // Progress indicator sphere (moves left-to-right)
        const progress = new THREE.Mesh(
            new THREE.SphereGeometry(0.025, 12, 12),
            new THREE.MeshPhysicalMaterial({ color: 0x4CFF4C, emissive: 0x4CFF4C, emissiveIntensity: 0.6 })
        );
        progress.position.set(-0.35, 1.1, 0);
        progress.userData.animType = 'morph';
        this.add(progress);
        // Connecting arrows between panels
        for (let i = 0; i < 2; i++) {
            const arrow = new THREE.Mesh(
                new THREE.ConeGeometry(0.015, 0.05, 6),
                new THREE.MeshBasicMaterial({ color: 0x4CFF4C, transparent: true, opacity: 0.6 })
            );
            arrow.position.set(-0.175 + i * 0.35, 1.25, 0);
            arrow.rotation.z = -Math.PI / 2;
            this.add(arrow);
        }
    }

    _addReflow(color) {
        // Adaptive reflow: 6 content blocks in responsive grid with breakpoint indicator
        const grid = new THREE.GridHelper(0.8, 4, color, color);
        grid.position.y = 1.0;
        grid.material.transparent = true;
        grid.material.opacity = 0.25;
        this.add(grid);
        // 6 content blocks of varying sizes — layout A positions + layout B targets
        const blocks = [
            { w: 0.2, h: 0.1, x: -0.25, y: 1.35, tx: -0.15, ty: 1.4 },
            { w: 0.12, h: 0.15, x: 0.0, y: 1.35, tx: 0.1, ty: 1.4 },
            { w: 0.25, h: 0.08, x: 0.22, y: 1.35, tx: 0.3, ty: 1.35 },
            { w: 0.15, h: 0.12, x: -0.2, y: 1.15, tx: -0.25, ty: 1.2 },
            { w: 0.18, h: 0.06, x: 0.05, y: 1.15, tx: 0.0, ty: 1.18 },
            { w: 0.1, h: 0.14, x: 0.28, y: 1.15, tx: 0.25, ty: 1.2 }
        ];
        blocks.forEach((b, i) => {
            const hue = i / blocks.length * 0.15 + 0.5;
            const blockColor = new THREE.Color().setHSL(hue, 0.5, 0.5);
            const block = new THREE.Mesh(
                new THREE.BoxGeometry(b.w, b.h, 0.02),
                new THREE.MeshPhysicalMaterial({
                    color: blockColor, emissive: blockColor, emissiveIntensity: 0.2,
                    transparent: true, opacity: 0.65
                })
            );
            block.position.set(b.x, b.y, 0);
            block.userData.animType = 'reflow';
            block.userData.targetX = b.tx;
            block.userData.targetY = b.ty;
            block.userData.baseX = b.x;
            block.userData.baseY = b.y;
            this.add(block);
        });
        // Breakpoint indicator line
        const bpLine = new THREE.Line(
            new THREE.BufferGeometry().setFromPoints([
                new THREE.Vector3(0.35, 0.95, 0), new THREE.Vector3(0.35, 1.5, 0)
            ]),
            new THREE.LineBasicMaterial({ color: 0xFF6B6B, transparent: true, opacity: 0.4 })
        );
        bpLine.userData.animType = 'reflow';
        this.add(bpLine);
    }

    _addDefault(color) {
        const cube = new THREE.Mesh(
            new THREE.BoxGeometry(0.35, 0.35, 0.35),
            new THREE.MeshPhysicalMaterial({ color, metalness: 0.5, roughness: 0.3 })
        );
        cube.position.y = 1.2;
        cube.userData.animType = 'spin';
        this.add(cube);
    }

    update(deltaTime, camera = null) {
        this.time += deltaTime;
        const t = this.time;
        
        // Proximity-based label fade (within 5m)
        if (camera) {
            const worldPos = new THREE.Vector3();
            this.getWorldPosition(worldPos);
            const cameraPos = camera.position || camera;
            const dist = worldPos.distanceTo(cameraPos);
            const labelAlpha = dist < 3 ? 1.0 : dist < 5 ? 1.0 - (dist - 3) / 2 : 0;
            this.traverse(obj => {
                if (obj.userData?.isLabel || obj.isSprite) {
                    if (obj.material) obj.material.opacity = labelAlpha;
                    obj.visible = labelAlpha > 0.01;
                }
            });
        }
        
        // Category-specific animations
        this.traverse(obj => {
            if (!obj.userData.animType) {
                // Generic emissive pulse for non-tagged objects
                if (obj.material?.emissiveIntensity !== undefined && !obj.userData.isLabel) {
                    const base = obj.material._baseEmissive ?? obj.material.emissiveIntensity;
                    if (!obj.material._baseEmissive) obj.material._baseEmissive = base;
                    obj.material.emissiveIntensity = base + Math.sin(t * 2) * 0.08;
                }
                return;
            }
            switch (obj.userData.animType) {
                case 'spin':
                    obj.rotation.y += deltaTime * 0.5;
                    break;
                case 'orbit':
                    obj.rotation.y += deltaTime * 0.3;
                    obj.rotation.x = Math.sin(t * 0.5) * 0.1;
                    break;
                case 'pulse':
                    if (obj.material?.emissiveIntensity !== undefined) {
                        obj.material.emissiveIntensity = 0.4 + Math.sin(t * 3) * 0.2;
                    }
                    obj.scale.setScalar(1 + Math.sin(t * 2) * 0.1);
                    break;
                case 'float':
                    obj.position.y = (obj.userData.baseY || 1.2) + Math.sin(t * 0.8 + (obj.userData.idx || 0) * 0.7) * 0.05;
                    break;
                case 'tilt':
                    obj.rotation.y = t * 0.1 * (1 + (obj.userData.idx || 0) * 0.2);
                    break;
                case 'gossipNode': {
                    const active = Math.floor(t * 2) % 8 === obj.userData.idx;
                    if (obj.material) obj.material.emissiveIntensity = active ? 0.7 : 0.2;
                    break;
                }
                case 'syncView': {
                    const synced = Math.sin(t * 2) > 0;
                    const offset = synced ? 0 : (obj.userData.idx || 0) * 0.02;
                    obj.position.y = 1.2 + offset;
                    break;
                }
                case 'presence': {
                    const cycleIdx = Math.floor(t * 0.5) % 4;
                    const occupied = cycleIdx !== obj.userData.idx;
                    if (obj.material) obj.material.emissiveIntensity = occupied ? 0.25 + Math.sin(t * 2) * 0.05 : 0.02;
                    break;
                }
                case 'circadian': {
                    const dayPhase = (t * 0.2) % 1;
                    const sunAngle = dayPhase * Math.PI;
                    obj.position.x = Math.cos(sunAngle) * 0.5;
                    obj.position.y = 1.1 + Math.sin(sunAngle) * 0.35;
                    break;
                }
                case 'earcon': {
                    const playing = Math.floor(t * 1.5) % 5 === obj.userData.idx;
                    obj.scale.setScalar(playing ? 1.3 : 1.0);
                    if (obj.material) obj.material.emissiveIntensity = playing ? 0.6 : 0.2;
                    break;
                }
                case 'spatialSource':
                    if (obj.material) obj.material.emissiveIntensity = 0.3 + Math.sin(t * 3 + (obj.userData.idx || 0) * 1.5) * 0.15;
                    break;
                case 'wave':
                    if (obj.geometry) {
                        const pos = obj.geometry.attributes.position;
                        for (let i = 0; i < pos.count; i++) {
                            const x = pos.getX(i);
                            pos.setY(i, 1.2 + Math.sin(x * 6 + t * 3) * 0.12 + Math.sin(x * 10 - t * 5) * 0.04);
                        }
                        pos.needsUpdate = true;
                    }
                    break;
                case 'ripple':
                    if (obj.material) {
                        const phase = (t * 0.5) % 1;
                        obj.material.opacity = 0.4 * (1 - phase);
                        obj.scale.setScalar(1 + phase * 0.3);
                    }
                    break;
                case 'toolOrbit': {
                    const selected = Math.floor(t * 0.8) % 4 === obj.userData.idx;
                    if (obj.material) {
                        obj.material.emissiveIntensity = selected ? 0.6 : 0.1;
                        obj.material.color.set(selected ? 0x4CFF4C : getColor(this.patent));
                        obj.material.emissive.set(selected ? 0x4CFF4C : getColor(this.patent));
                    }
                    break;
                }
                case 'reflow':
                    obj.position.x += Math.sin(t * 0.5 + obj.position.y * 10) * deltaTime * 0.01;
                    break;
                case 'searchPulse': {
                    const active = Math.floor(t * 1.5) % 4 === obj.userData.idx;
                    if (obj.material) obj.material.emissiveIntensity = active ? 0.6 : 0.15;
                    obj.scale.setScalar(active ? 1.2 : 1.0);
                    break;
                }
                case 'morph': {
                    const morphPhase = (t * 0.3) % 1;
                    if (obj.material) obj.material.opacity = 0.2 + morphPhase * 0.5;
                    break;
                }
                case 'verifyStep': {
                    const stepTime = 1.5;
                    const currentStep = Math.floor(t / stepTime) % 5;
                    const isVerified = (obj.userData.idx || 0) <= currentStep;
                    if (obj.material) obj.material.emissiveIntensity = isVerified ? 0.5 : 0.05;
                    break;
                }
                case 'frontierAgent': {
                    const probeAngle = t * 0.8;
                    const r = obj.userData.frontierR || 0.8;
                    obj.position.x = Math.cos(probeAngle) * r * 0.9;
                    obj.position.z = Math.sin(probeAngle) * r * 0.9;
                    break;
                }
                case 'roomWalker': {
                    const roomIdx = Math.floor(t * 0.4) % 4;
                    const targetAngle = (roomIdx / 4) * Math.PI * 2;
                    const walkerR = 0.35;
                    const tx = Math.cos(targetAngle) * walkerR;
                    const tz = Math.sin(targetAngle) * walkerR;
                    obj.position.x += (tx - obj.position.x) * 0.03;
                    obj.position.z += (tz - obj.position.z) * 0.03;
                    break;
                }
                case 'attract':
                    obj.position.y = (obj.userData.baseY || 1.3) + Math.sin(t * 2) * 0.02;
                    break;
                case 'repel':
                    obj.position.y = (obj.userData.baseY || 1.3) - Math.sin(t * 2) * 0.02;
                    break;
            }
        });
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
