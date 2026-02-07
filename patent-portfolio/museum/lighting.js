/**
 * Museum Lighting — Light as material (Turrell)
 * Volumetric fog, color temperature gradients, Ganzfeld at gallery boundaries,
 * light leaks (slits), slow wing cycles (60–120s). Subtle, barely perceptible.
 */

import * as THREE from 'three';
import { COLONY_DATA, COLONY_ORDER, DIMENSIONS } from './architecture.js';

const COLONY_COLORS = {
    spark: 0xFF6B35, forge: 0xD4AF37, flow: 0x4ECDC4, nexus: 0x9B7EBD,
    beacon: 0xF59E0B, grove: 0x7EB77F, crystal: 0x67D4E4
};

// Kelvin to RGB (approx). 3200K warm, 5600K neutral-cool
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

// Slow cycles: 60–120s, amount 0.02–0.05 (barely perceptible)
const WING_PROFILES = {
    spark:   { color: 0xE85D04, cycleSec: 90,  amount: 0.03 },
    forge:   { color: 0xD4AF37, cycleSec: 120, amount: 0.025 },
    flow:    { color: 0x4ECDC4, cycleSec: 75,  amount: 0.04 },
    nexus:   { color: 0x9B7EBD, cycleSec: 100, amount: 0.03 },
    beacon:  { color: 0xF59E0B, cycleSec: 60,  amount: 0.035 },
    grove:   { color: 0x7EB77F, cycleSec: 110, amount: 0.025 },
    crystal: { color: 0x67D4E4, cycleSec: 80,  amount: 0.03 }
};

export class TurrellLighting {
    constructor(scene, camera) {
        this.scene = scene;
        this.camera = camera;
        this.currentZone = 'rotunda';
        this.lights = [];
        this.wingLights = {};
        this.lightLeaks = [];
        this._time = 0;
        this.init();
    }

    init() {
        const rotH = DIMENSIONS.rotunda.height;
        const rotR = DIMENSIONS.rotunda.radius;

        // 1. Hemisphere — very subtle, color shifts with zone in setZone
        this.hemisphere = new THREE.HemisphereLight(
            kelvinToHex(3400),  // Slightly warm sky
            0x060508,
            0.25
        );
        this.hemisphere.position.set(0, 50, 0);
        this.scene.add(this.hemisphere);
        this.lights.push(this.hemisphere);

        // 2. Main directional (sun through aperture) — primary “god ray” source
        this.sunlight = new THREE.DirectionalLight(kelvinToHex(3500), 1.2);
        this.sunlight.position.set(
            DIMENSIONS.rotunda.apertureOffset,
            rotH + 6,
            DIMENSIONS.rotunda.apertureOffset * 0.5
        );
        this.sunlight.castShadow = true;
        this.sunlight.shadow.mapSize.set(2048, 2048);
        this.sunlight.shadow.camera.near = 1;
        this.sunlight.shadow.camera.far = 100;
        this.sunlight.shadow.camera.left = -50;
        this.sunlight.shadow.camera.right = 50;
        this.sunlight.shadow.camera.top = 50;
        this.sunlight.shadow.camera.bottom = -50;
        this.sunlight.shadow.bias = -0.0001;
        this.sunlight.shadow.radius = 2;
        this.scene.add(this.sunlight);
        this.lights.push(this.sunlight);

        // 3. No RectAreaLight — replaced by volumetric feel via fog + directional
        // Center fill (very low) so Fano sculpture reads
        this.centerLight = new THREE.PointLight(0xF5F0E8, 0.25, 20, 2);
        this.centerLight.position.set(0, rotH * 0.45, 0);
        this.scene.add(this.centerLight);
        this.lights.push(this.centerLight);

        // 4. Floor uplights — keep but reduce intensity
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

        // 5. Wing spotlights + accent + light leaks (slits)
        const wingLen = DIMENSIONS.wing.length;
        const wingH = DIMENSIONS.wing.corridorHeight;
        const vestibuleDepth = DIMENSIONS.wing.vestibuleDepth ?? 6;
        const galleryDepth = DIMENSIONS.gallery.depth;
        const galleryCenterOffset = wingLen + vestibuleDepth + galleryDepth / 2;

        COLONY_ORDER.forEach(colony => {
            const data = COLONY_DATA[colony];
            const profile = WING_PROFILES[colony] || { color: COLONY_COLORS[colony], cycleSec: 90, amount: 0.03 };
            const angle = data.wingAngle;
            const cos = Math.cos(angle), sin = Math.sin(angle);

            const centerX = cos * (rotR + wingLen / 2);
            const centerZ = sin * (rotR + wingLen / 2);

            const wingLight = new THREE.SpotLight(
                profile.color,
                1.2,
                wingLen,
                Math.PI / 6,
                0.5,
                1.5
            );
            wingLight.position.set(centerX, wingH - 0.5, centerZ);
            wingLight.target.position.set(centerX, 0, centerZ);
            wingLight.castShadow = true;
            wingLight.shadow.mapSize.set(512, 512);
            wingLight.shadow.bias = -0.0005;
            this.scene.add(wingLight.target);
            this.scene.add(wingLight);
            this.wingLights[colony] = { spotlight: wingLight, profile };
            this.lights.push(wingLight);

            const galleryX = cos * (rotR + galleryCenterOffset);
            const galleryZ = sin * (rotR + galleryCenterOffset);
            const accentLight = new THREE.PointLight(profile.color, 0.35, 18, 2);
            accentLight.position.set(galleryX, DIMENSIONS.gallery.height * 0.6, galleryZ);
            this.scene.add(accentLight);
            this.lights.push(accentLight);

            // Light leaks: 2 narrow slits per wing along corridor
            for (let s = 0; s < 2; s++) {
                const along = rotR + 12 + s * 18;
                const slit = new THREE.SpotLight(
                    profile.color,
                    0.5,
                    25,
                    Math.PI / 24,
                    0.2,
                    2
                );
                slit.position.set(cos * along, wingH - 1.5, sin * along);
                slit.target.position.set(cos * (along + 10), 0, sin * (along + 10));
                this.scene.add(slit.target);
                this.scene.add(slit);
                this.lightLeaks.push(slit);
                this.lights.push(slit);
            }
        });

        // 6. Volumetric fog — color driven by setZone (Ganzfeld / color temp)
        this._fogColor = new THREE.Color(0x0A0912);
        this.scene.fog = new THREE.FogExp2(0x0A0912, 0.006);
    }

    setZone(zone) {
        if (zone === this.currentZone) return;
        this.currentZone = zone;

        // Color temperature: rotunda warm (3200K), wings cooler (4500K), gallery = Ganzfeld (colony tint)
        const isColony = COLONY_ORDER.includes(zone);
        const warm = kelvinToHex(3200);
        const cool = kelvinToHex(5600);
        const colonyHex = isColony ? COLONY_COLORS[zone] : warm;

        if (zone === 'rotunda' || zone === 'vestibule') {
            this._fogColor.setHex(warm);
            this.hemisphere.color.setHex(kelvinToHex(3400));
            this.sunlight.color.setHex(kelvinToHex(3500));
        } else if (isColony) {
            this._fogColor.setHex(colonyHex);
            this.hemisphere.color.lerpColors(new THREE.Color(kelvinToHex(4000)), new THREE.Color(colonyHex), 0.12);
            this.sunlight.color.setHex(kelvinToHex(4500));
        } else {
            this._fogColor.setHex(cool);
            this.hemisphere.color.setHex(kelvinToHex(5000));
            this.sunlight.color.setHex(cool);
        }

        this.scene.fog.color.copy(this._fogColor);

        COLONY_ORDER.forEach(colony => {
            const entry = this.wingLights[colony];
            if (!entry?.spotlight) return;
            const base = colony === zone ? 1.2 : 0.7;
            entry.spotlight.intensity = base;
        });
    }

    update(delta) {
        this._time += delta;

        // Wing profiles: slow sine, period = cycleSec, amount tiny
        COLONY_ORDER.forEach(colony => {
            const entry = this.wingLights[colony];
            if (!entry?.spotlight) return;
            const { spotlight, profile } = entry;
            const period = profile.cycleSec || 90;
            const phase = (this._time / period) * Math.PI * 2;
            const mult = 1 + Math.sin(phase) * (profile.amount || 0.03);
            const base = colony === this.currentZone ? 1.2 : 0.7;
            spotlight.intensity = Math.max(0.2, base * mult);
        });
    }

    updateGanzfeldEffect() {}
    updateGodRays() {}
    updateArtworkLighting() {}

    dispose() {
        this.lights.forEach(light => {
            this.scene.remove(light);
            if (light.dispose) light.dispose();
        });
        this.lights = [];
        this.wingLights = {};
        this.lightLeaks = [];
    }
}

export const LIGHTING_PROFILES = WING_PROFILES;
export const LIGHTING_CONFIG = { fog: { color: 0x0A0912, density: 0.006 } };
