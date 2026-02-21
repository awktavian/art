/**
 * Museum Lighting — Light as material (Turrell)
 * 4-layer system: base ambient, architectural bounce, artwork accent, atmospheric
 * Smooth zone transitions, per-wing color programs, approach-triggered spotlights.
 *
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { COLONY_DATA, COLONY_ORDER, DIMENSIONS } from './architecture.js';

const COLONY_COLORS = {
    spark: 0xFF6B35, forge: 0xD4AF37, flow: 0x4ECDC4, nexus: 0x9B7EBD,
    beacon: 0xF59E0B, grove: 0x7EB77F, crystal: 0x67D4E4
};

function kelvinToHex(k) {
    const t = k / 100;
    let r, g, b;
    if (t <= 66) {
        r = 255;
        g = Math.min(255, 99.4708025861 * Math.log(t) - 161.1195681661);
        b = t <= 19 ? 0 : Math.min(255, 138.5177312231 * Math.log(t - 10) - 305.0447927307);
    } else {
        r = Math.min(255, 329.698727446 * Math.pow(t - 60, -0.1332047592));
        g = Math.min(255, 288.1221695283 * Math.pow(t - 60, -0.0755148492));
        b = 255;
    }
    return (Math.round(r) << 16) | (Math.round(g) << 8) | Math.round(b);
}

// Per-wing lighting programs
const WING_PROFILES = {
    spark:   { color: 0xFF6B35, kelvin: 5000, cycleSec: 90,  amount: 0.03, character: 'dynamic' },
    forge:   { color: 0xD4AF37, kelvin: 2700, cycleSec: 120, amount: 0.025, character: 'warm' },
    flow:    { color: 0x4ECDC4, kelvin: 4000, cycleSec: 75,  amount: 0.04, character: 'dappled' },
    nexus:   { color: 0x9B7EBD, kelvin: 6500, cycleSec: 100, amount: 0.03, character: 'pulse' },
    beacon:  { color: 0xF59E0B, kelvin: 3000, cycleSec: 60,  amount: 0.035, character: 'sweep' },
    grove:   { color: 0x7EB77F, kelvin: 3500, cycleSec: 110, amount: 0.025, character: 'canopy' },
    crystal: { color: 0x67D4E4, kelvin: 7500, cycleSec: 80,  amount: 0.03, character: 'cold' }
};

export class TurrellLighting {
    constructor(scene, camera) {
        this.scene = scene;
        this.camera = camera;
        this.currentZone = 'rotunda';
        this._targetZone = 'rotunda';
        this._zoneTransition = 1.0; // 1 = fully transitioned
        this.lights = [];
        this.wingLights = {};
        this.artworkSpots = [];
        this.stripLights = [];
        this.lightLeaks = [];
        this._time = 0;

        // Cached colors for smooth lerping (reused every frame — zero allocs in update)
        this._currentFogColor = new THREE.Color(0x0A0912);
        this._targetFogColor = new THREE.Color(0x0A0912);
        this._currentHemiColor = new THREE.Color(kelvinToHex(3400));
        this._targetHemiColor = new THREE.Color(kelvinToHex(3400));
        this._tmpColor = new THREE.Color();
        this._tmpColor2 = new THREE.Color();

        this.init();
    }

    init() {
        const rotH = DIMENSIONS.rotunda.height;
        const rotR = DIMENSIONS.rotunda.radius;

        // ─── LAYER 1: BASE AMBIENT ───
        // Ultra-low warm ambient prevents pure black anywhere
        this.baseAmbient = new THREE.AmbientLight(kelvinToHex(3200), 0.05);
        this.scene.add(this.baseAmbient);
        this.lights.push(this.baseAmbient);

        // ─── LAYER 2: ARCHITECTURAL (hemisphere + directional) ───
        this.hemisphere = new THREE.HemisphereLight(
            kelvinToHex(3400), 0x060508, 0.3
        );
        this.hemisphere.position.set(0, 50, 0);
        this.scene.add(this.hemisphere);
        this.lights.push(this.hemisphere);

        // Main directional (sun through aperture)
        this.sunlight = new THREE.DirectionalLight(kelvinToHex(3500), 1.2);
        this.sunlight.position.set(
            DIMENSIONS.rotunda.apertureOffset,
            rotH + 6,
            DIMENSIONS.rotunda.apertureOffset * 0.5
        );
        this.sunlight.castShadow = false;
        this.scene.add(this.sunlight);
        this.lights.push(this.sunlight);

        // Center fill for Fano sculpture
        this.centerLight = new THREE.PointLight(0xF5F0E8, 0.25, 20, 2);
        this.centerLight.position.set(0, rotH * 0.45, 0);
        this.scene.add(this.centerLight);
        this.lights.push(this.centerLight);

        // Floor uplights in rotunda
        for (let i = 0; i < 4; i++) {
            const angle = (i / 4) * Math.PI * 2 + Math.PI / 8;
            const r = 6;
            const uplight = new THREE.SpotLight(0xF5E6D3, 0.4, 22, Math.PI / 8, 0.6, 2);
            uplight.position.set(Math.cos(angle) * r, 0.2, Math.sin(angle) * r);
            uplight.target.position.set(Math.cos(angle) * r * 0.5, rotH / 2, Math.sin(angle) * r * 0.5);
            this.scene.add(uplight.target);
            this.scene.add(uplight);
            this.lights.push(uplight);
        }

        // ─── LAYER 3: ARTWORK ACCENT (per-wing spots + gallery accent) ───
        const wingLen = DIMENSIONS.wing.length;
        const wingH = DIMENSIONS.wing.corridorHeight;
        const vestibuleDepth = DIMENSIONS.wing.vestibuleDepth ?? 6;
        const galleryDepth = DIMENSIONS.gallery.depth;
        const galleryCenterOffset = wingLen + vestibuleDepth + galleryDepth / 2;

        COLONY_ORDER.forEach(colony => {
            const data = COLONY_DATA[colony];
            const profile = WING_PROFILES[colony];
            const angle = data.wingAngle;
            const cos = Math.cos(angle), sin = Math.sin(angle);

            const centerX = cos * (rotR + wingLen / 2);
            const centerZ = sin * (rotR + wingLen / 2);

            // Per-wing hemisphere light for architectural bounce
            const wingHemi = new THREE.HemisphereLight(
                profile.color, 0x050508, 0.15
            );
            wingHemi.position.set(centerX, wingH, centerZ);
            this.scene.add(wingHemi);
            this.lights.push(wingHemi);

            // Wing corridor spotlight
            const wingLight = new THREE.SpotLight(
                profile.color, 1.0, wingLen, Math.PI / 6, 0.5, 1.5
            );
            wingLight.position.set(centerX, wingH - 0.5, centerZ);
            wingLight.target.position.set(centerX, 0, centerZ);
            wingLight.castShadow = false;
            this.scene.add(wingLight.target);
            this.scene.add(wingLight);
            this.wingLights[colony] = { spotlight: wingLight, hemi: wingHemi, profile };
            this.lights.push(wingLight);

            // Gallery accent light with proper userData
            const galleryX = cos * (rotR + galleryCenterOffset);
            const galleryZ = sin * (rotR + galleryCenterOffset);
            const accentLight = new THREE.PointLight(profile.color, 0.6, 22, 2);
            accentLight.position.set(galleryX, DIMENSIONS.gallery.height * 0.6, galleryZ);
            accentLight.userData.isAccentLight = true;
            accentLight.userData.baseIntensity = 0.6;
            this.scene.add(accentLight);
            this.lights.push(accentLight);

            // Artwork approach and light leaks handled via emissive materials only

            // Corridor strip lighting (wayfinding + atmosphere)
            const stripMat = new THREE.MeshBasicMaterial({
                color: profile.color, transparent: true, opacity: 0.15
            });
            for (let side = -1; side <= 1; side += 2) {
                const stripGeo = new THREE.BoxGeometry(0.05, 0.03, wingLen);
                const strip = new THREE.Mesh(stripGeo, stripMat.clone());
                const lateralOffset = (DIMENSIONS.wing.width / 2 + 0.3) * side;
                strip.position.set(
                    cos * (rotR + wingLen / 2) - sin * lateralOffset,
                    0.05,
                    sin * (rotR + wingLen / 2) + cos * lateralOffset
                );
                strip.rotation.y = angle;
                strip.name = `strip-${colony}-${side > 0 ? 'right' : 'left'}`;
                this.scene.add(strip);
                this.stripLights.push(strip);
            }
        });

        // Sync with existing fog (created by initScene)
        if (this.scene.fog) {
            this._currentFogColor.copy(this.scene.fog.color);
            this._targetFogColor.copy(this.scene.fog.color);
        }
    }

    setZone(zone) {
        if (zone === this._targetZone) return;
        this._targetZone = zone;
        this._zoneTransition = 0;

        const isColony = COLONY_ORDER.includes(zone);
        const warm = kelvinToHex(3200);

        if (zone === 'rotunda' || zone === 'vestibule') {
            this._targetFogColor.setHex(warm);
            this._targetHemiColor.setHex(kelvinToHex(3400));
        } else if (isColony) {
            const profile = WING_PROFILES[zone];
            this._targetFogColor.setHex(profile.color);
            this._tmpColor.setHex(kelvinToHex(profile.kelvin));
            this._tmpColor2.setHex(profile.color);
            this._targetHemiColor.lerpColors(this._tmpColor, this._tmpColor2, 0.12);
        } else {
            this._targetFogColor.setHex(kelvinToHex(5600));
            this._targetHemiColor.setHex(kelvinToHex(5000));
        }
    }

    update(delta, playerPosition) {
        this._time += delta;

        // Smooth zone transition (lerp over ~3 seconds)
        if (this._zoneTransition < 1) {
            this._zoneTransition = Math.min(1, this._zoneTransition + delta * 0.35);
            const t = this._zoneTransition;
            const eased = t * t * (3 - 2 * t); // smoothstep

            this._currentFogColor.lerp(this._targetFogColor, eased * 0.1);
            this._currentHemiColor.lerp(this._targetHemiColor, eased * 0.1);

            this.scene.fog.color.copy(this._currentFogColor);
            this.hemisphere.color.copy(this._currentHemiColor);

            if (t >= 1) this.currentZone = this._targetZone;

            // Adjust wing spotlight intensities during transition
            COLONY_ORDER.forEach(colony => {
                const entry = this.wingLights[colony];
                if (!entry?.spotlight) return;
                const base = colony === this._targetZone ? 1.2 : 0.6;
                entry.spotlight.intensity += (base - entry.spotlight.intensity) * 0.05;
                const hemiBase = colony === this._targetZone ? 0.25 : 0.1;
                entry.hemi.intensity += (hemiBase - entry.hemi.intensity) * 0.05;
            });
        }

        // Wing profile cycling
        COLONY_ORDER.forEach(colony => {
            const entry = this.wingLights[colony];
            if (!entry?.spotlight) return;
            const { spotlight, profile } = entry;
            const period = profile.cycleSec;
            const phase = (this._time / period) * Math.PI * 2;
            const mult = 1 + Math.sin(phase) * profile.amount;
            const base = colony === this._targetZone ? 1.2 : 0.6;
            spotlight.intensity = Math.max(0.2, base * mult);
        });

        this.updateGanzfeldEffect(playerPosition);
        this.updateGodRays();
    }

    updateGanzfeldEffect(playerPosition) {
        if (!playerPosition || !this.scene.fog) return;
        const isColony = COLONY_ORDER.includes(this._targetZone);
        const targetDensity = isColony ? 0.009 : 0.006;
        this.scene.fog.density += (targetDensity - this.scene.fog.density) * 0.02;

        if (isColony) {
            const colonyHex = COLONY_COLORS[this._targetZone];
            if (colonyHex) {
                this._tmpColor.setHex(colonyHex);
                this._currentFogColor.lerp(this._tmpColor, 0.005);
                this.scene.fog.color.copy(this._currentFogColor);
            }
        }
    }

    updateGodRays() {
        if (!this.sunlight) return;
        const breathe = 1 + Math.sin(this._time * 0.14) * 0.06;
        this.sunlight.intensity = 1.0 * breathe;
        const drift = Math.sin(this._time * 0.02) * 2;
        this.sunlight.position.x = DIMENSIONS.rotunda.apertureOffset + drift;
    }

    enableShadows(mapSize = 1024) {
        if (this.sunlight) {
            this.sunlight.castShadow = true;
            this.sunlight.shadow.mapSize.set(mapSize, mapSize);
            this.sunlight.shadow.camera.near = 1;
            this.sunlight.shadow.camera.far = 100;
            this.sunlight.shadow.camera.left = -50;
            this.sunlight.shadow.camera.right = 50;
            this.sunlight.shadow.camera.top = 50;
            this.sunlight.shadow.camera.bottom = -50;
            this.sunlight.shadow.bias = -0.0001;
            this.sunlight.shadow.radius = 2;
        }
    }

    dispose() {
        this.lights.forEach(light => {
            this.scene.remove(light);
            if (light.dispose) light.dispose();
        });
        this.stripLights.forEach(strip => {
            this.scene.remove(strip);
            if (strip.geometry) strip.geometry.dispose();
            if (strip.material) strip.material.dispose();
        });
        this.lights = [];
        this.wingLights = {};
        this.artworkSpots = [];
        this.stripLights = [];
        this.lightLeaks = [];
    }
}

export const LIGHTING_PROFILES = WING_PROFILES;
export const LIGHTING_CONFIG = { fog: { color: 0x0A0912, density: 0.006 } };
