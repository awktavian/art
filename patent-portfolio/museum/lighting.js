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

        // Cached colors for smooth lerping
        this._currentFogColor = new THREE.Color(0x0A0912);
        this._targetFogColor = new THREE.Color(0x0A0912);
        this._currentHemiColor = new THREE.Color(kelvinToHex(3400));
        this._targetHemiColor = new THREE.Color(kelvinToHex(3400));

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
            wingLight.castShadow = true;
            wingLight.shadow.mapSize.set(512, 512);
            wingLight.shadow.bias = -0.0005;
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

            // Artwork approach spotlights (3 per wing, initially dim)
            for (let s = 0; s < 3; s++) {
                const along = rotR + 15 + s * 12;
                const spotX = cos * along;
                const spotZ = sin * along;
                const spot = new THREE.SpotLight(
                    profile.color, 0.0, 10, Math.PI / 10, 0.7, 2
                );
                spot.position.set(spotX, wingH - 0.5, spotZ);
                spot.target.position.set(spotX, 0, spotZ);
                spot.userData.isArtworkSpot = true;
                spot.userData.baseIntensity = 0.8;
                spot.userData.approachRadius = 8;
                spot.userData.fullRadius = 3;
                this.scene.add(spot.target);
                this.scene.add(spot);
                this.artworkSpots.push(spot);
                this.lights.push(spot);
            }

            // ─── LAYER 4: ATMOSPHERIC ───
            // Light leak slits along corridor
            for (let s = 0; s < 2; s++) {
                const along = rotR + 12 + s * 18;
                const slit = new THREE.SpotLight(
                    profile.color, 0.5, 25, Math.PI / 24, 0.2, 2
                );
                slit.position.set(cos * along, wingH - 1.5, sin * along);
                slit.target.position.set(cos * (along + 10), 0, sin * (along + 10));
                this.scene.add(slit.target);
                this.scene.add(slit);
                this.lightLeaks.push(slit);
                this.lights.push(slit);
            }

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

        // Volumetric fog
        this._currentFogColor.setHex(0x0A0912);
        this._targetFogColor.setHex(0x0A0912);
        this.scene.fog = new THREE.FogExp2(0x0A0912, 0.006);
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
            this._targetHemiColor.lerpColors(
                new THREE.Color(kelvinToHex(profile.kelvin)),
                new THREE.Color(profile.color),
                0.12
            );
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
        this.updateArtworkSpots(playerPosition);
        this.updateStripLights();
    }

    updateGanzfeldEffect(playerPosition) {
        if (!playerPosition || !this.scene.fog) return;
        const isColony = COLONY_ORDER.includes(this._targetZone);
        const targetDensity = isColony ? 0.009 : 0.006;
        this.scene.fog.density += (targetDensity - this.scene.fog.density) * 0.02;

        if (isColony) {
            const colonyHex = COLONY_COLORS[this._targetZone];
            if (colonyHex) {
                const target = new THREE.Color(colonyHex);
                this._currentFogColor.lerp(target, 0.005);
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

    /**
     * Approach-triggered artwork spotlights.
     * Fade in when visitor enters radius, full brightness at close range.
     */
    updateArtworkSpots(playerPosition) {
        if (!playerPosition) return;
        this.artworkSpots.forEach(spot => {
            const dist = playerPosition.distanceTo(spot.position);
            const approachR = spot.userData.approachRadius;
            const fullR = spot.userData.fullRadius;
            const baseI = spot.userData.baseIntensity;

            let targetIntensity = 0;
            if (dist < fullR) {
                targetIntensity = baseI;
            } else if (dist < approachR) {
                targetIntensity = baseI * (1 - (dist - fullR) / (approachR - fullR));
            }
            spot.intensity += (targetIntensity - spot.intensity) * 0.05;
        });

        // Gallery accent lights proximity effect
        this.lights.forEach(light => {
            if (!light.userData?.isAccentLight) return;
            const dist = playerPosition.distanceTo(light.position);
            const proximityFactor = Math.max(0, 1 - dist / 15);
            const baseIntensity = light.userData.baseIntensity;
            const target = baseIntensity * (0.3 + 0.7 * proximityFactor);
            light.intensity += (target - light.intensity) * 0.05;
        });
    }

    /**
     * Corridor strip lights pulse gently in current wing
     */
    updateStripLights() {
        this.stripLights.forEach(strip => {
            if (!strip.material) return;
            const colonyMatch = strip.name.split('-')[1];
            const isActive = colonyMatch === this._targetZone;
            const targetOpacity = isActive ? 0.25 + Math.sin(this._time * 0.8) * 0.05 : 0.1;
            strip.material.opacity += (targetOpacity - strip.material.opacity) * 0.05;
        });
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
