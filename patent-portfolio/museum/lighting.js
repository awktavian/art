/**
 * Museum Lighting — Light as material (Turrell)
 * 4-layer system: base ambient, architectural bounce, artwork accent, atmospheric
 * Smooth zone transitions, per-wing color programs, approach-triggered spotlights.
 *
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { COLONY_DATA, COLONY_ORDER, DIMENSIONS } from './architecture.js';
import { COLONY_COLORS as DESIGN_COLONY_COLORS } from '../../lib/design-tokens.js';
import { damp, smoothstep, clampStep, rateFromStepFraction } from '../lib/motion.js';

// ═══════════════════════════════════════════════════════════════════════════
// SMOOTHING RATES (V5-1102)
// ═══════════════════════════════════════════════════════════════════════════
//
// Every smoother in this file used to be a fixed FRACTION PER STEP
// (`intensity += (target - intensity) * 0.05`). This subsystem is stepped once
// every 6 frames and handed `clampedDelta * 6` (main.js:2280-2286), so the
// number of steps per second WAS the frame rate divided by 6 — a zone change
// took ~2 s on a 60 fps machine and ~4 s on a 30 fps one.
//
// `rateFromStepFraction` recovers the time constant each legacy fraction
// encodes, evaluated at the stagger's own 10 steps/s (60 fps / 6). The tuned
// feel at 60 fps is therefore unchanged and the duration stops depending on
// the visitor's hardware.
const MUSEUM_STEP_HZ = 10;
const WING_BASE_RATE = rateFromStepFraction(0.05, MUSEUM_STEP_HZ);
const ZONE_COLOUR_RATE = rateFromStepFraction(0.15, MUSEUM_STEP_HZ);
const GANZFELD_DENSITY_RATE = rateFromStepFraction(0.02, MUSEUM_STEP_HZ);
const GANZFELD_COLOUR_RATE = rateFromStepFraction(0.005, MUSEUM_STEP_HZ);

// DERIVED from art/lib/design-tokens.js (single waddle mirror) —
// identity-coherence.test.mjs bans re-inlined colony hexes here (DICT-B 2026-09-29).
const COLONY_COLORS = Object.fromEntries(
    Object.entries(DESIGN_COLONY_COLORS).map(([colony, t]) => [colony, t.num])
);

function kelvinToHex(k) {
    const t = k / 100;
    let r, g, b;
    if (t <= 66) {
        r = 255;
        g = Math.max(0, Math.min(255, 99.4708025861 * Math.log(t) - 161.1195681661));
        b = t <= 19 ? 0 : Math.max(0, Math.min(255, 138.5177312231 * Math.log(t - 10) - 305.0447927307));
    } else {
        r = Math.max(0, Math.min(255, 329.698727446 * Math.pow(t - 60, -0.1332047592)));
        g = Math.max(0, Math.min(255, 288.1221695283 * Math.pow(t - 60, -0.0755148492)));
        b = 255;
    }
    return (Math.round(r) << 16) | (Math.round(g) << 8) | Math.round(b);
}

// Per-wing lighting programs — colors DERIVED from art/lib/design-tokens.js
// (DICT-B sweep 2026-09-29; zero value change, literals removed).
const WING_PROFILES = {
    spark:   { color: COLONY_COLORS.spark,   kelvin: 5000, cycleSec: 90,  amount: 0.03, character: 'dynamic' },
    forge:   { color: COLONY_COLORS.forge,   kelvin: 2700, cycleSec: 120, amount: 0.025, character: 'warm' },
    flow:    { color: COLONY_COLORS.flow,    kelvin: 4000, cycleSec: 75,  amount: 0.04, character: 'dappled' },
    nexus:   { color: COLONY_COLORS.nexus,   kelvin: 6500, cycleSec: 100, amount: 0.03, character: 'pulse' },
    beacon:  { color: COLONY_COLORS.beacon,  kelvin: 3000, cycleSec: 60,  amount: 0.035, character: 'sweep' },
    grove:   { color: COLONY_COLORS.grove,   kelvin: 3500, cycleSec: 110, amount: 0.025, character: 'canopy' },
    crystal: { color: COLONY_COLORS.crystal, kelvin: 7500, cycleSec: 80,  amount: 0.03, character: 'cold' }
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

        // Eased per-colony light state (V5-1102, L1). Keyed by colony; seeded
        // from the constructor's authored intensity on the first update so the
        // easing continues the authored value instead of jumping to it.
        this._wingBase = {};
        this._wingHemiBase = {};

        this.init();
    }

    init() {
        const rotH = DIMENSIONS.rotunda.height;
        const rotR = DIMENSIONS.rotunda.radius;

        // ─── LAYER 1: BASE AMBIENT ───
        // Ultra-low warm ambient prevents pure black anywhere
        this.baseAmbient = new THREE.AmbientLight(kelvinToHex(3200), 0.35);
        this.scene.add(this.baseAmbient);
        this.lights.push(this.baseAmbient);

        // ─── LAYER 2: ARCHITECTURAL (hemisphere + directional) ───
        this.hemisphere = new THREE.HemisphereLight(
            kelvinToHex(3400), 0x2A2530, 0.8
        );
        this.hemisphere.position.set(0, 50, 0);
        this.scene.add(this.hemisphere);
        this.lights.push(this.hemisphere);

        // Main directional (sun through aperture)
        this.sunlight = new THREE.DirectionalLight(kelvinToHex(3500), 2.2);
        this.sunlight.position.set(
            DIMENSIONS.rotunda.apertureOffset,
            rotH + 6,
            DIMENSIONS.rotunda.apertureOffset * 0.5
        );
        this.sunlight.castShadow = false;
        this.scene.add(this.sunlight);
        this.lights.push(this.sunlight);

        // Center fill for Fano sculpture
        this.centerLight = new THREE.PointLight(0xF5F0E8, 0.9, 40, 2);
        this.centerLight.position.set(0, rotH * 0.45, 0);
        this.scene.add(this.centerLight);
        this.lights.push(this.centerLight);

        // Floor uplights in rotunda
        for (let i = 0; i < 4; i++) {
            const angle = (i / 4) * Math.PI * 2 + Math.PI / 8;
            const r = 6;
            const uplight = new THREE.SpotLight(0xF5E6D3, 0.8, 30, Math.PI / 8, 0.6, 2);
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
                profile.color, 0x151018, 0.35
            );
            wingHemi.position.set(centerX, wingH, centerZ);
            this.scene.add(wingHemi);
            this.lights.push(wingHemi);

            // Wing corridor spotlight
            const wingLight = new THREE.SpotLight(
                profile.color, 1.5, wingLen, Math.PI / 6, 0.5, 1.5
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
            const accentLight = new THREE.PointLight(profile.color, 1.0, 28, 2);
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

        // NOTE on `delta` (V5-1102): main.js steps this subsystem once every
        // 6 frames and hands it `clampedDelta * 6` (main.js:2289-2292), so
        // `delta` here is ALREADY an accumulated span in seconds. That makes
        // it the correct argument for a time-based smoother — and it is why
        // the fixed fractions below (`* 0.05`, `* 0.15`, `* 0.02`, `* 0.005`)
        // were never going to be frame-rate independent: they ignored `delta`
        // entirely while the 6-frame stagger only rescaled `_time`.
        const dt = clampStep(delta);

        // Smooth zone transition (lerp over ~3 seconds)
        if (this._zoneTransition < 1) {
            this._zoneTransition = Math.min(1, this._zoneTransition + delta * 0.35);
            const t = this._zoneTransition;
            const eased = smoothstep(t);

            // V5-1102: `lerp(target, eased * 0.15)` multiplied the step
            // fraction by the ramp, so the colour approach was a fraction per
            // STEP times a ramp — it sped up as it went instead of easing, and
            // its duration was the frame rate. Now a time constant, with the
            // ramp kept as the deliberate part: the approach still accelerates
            // into the eased window but at 30 fps covers the same seconds.
            const colourRate = ZONE_COLOUR_RATE * (0.25 + 0.75 * eased);
            this._currentFogColor.r = damp(this._currentFogColor.r, this._targetFogColor.r, colourRate, dt);
            this._currentFogColor.g = damp(this._currentFogColor.g, this._targetFogColor.g, colourRate, dt);
            this._currentFogColor.b = damp(this._currentFogColor.b, this._targetFogColor.b, colourRate, dt);
            this._currentHemiColor.r = damp(this._currentHemiColor.r, this._targetHemiColor.r, colourRate, dt);
            this._currentHemiColor.g = damp(this._currentHemiColor.g, this._targetHemiColor.g, colourRate, dt);
            this._currentHemiColor.b = damp(this._currentHemiColor.b, this._targetHemiColor.b, colourRate, dt);

            this.scene.fog.color.copy(this._currentFogColor);
            this.hemisphere.color.copy(this._currentHemiColor);

            if (t >= 1) this.currentZone = this._targetZone;
        }

        // Wing profile cycling.
        //
        // V5-1102 — this is the L1 defect: the zone-transition block above
        // eased `spotlight.intensity` toward 1.2 / 0.6 with a `* 0.05` step,
        // and then THIS unconditional assignment overwrote the result one
        // frame later with `base * mult`, base taken straight from
        // `_targetZone`. So the easing never ran: `_targetZone` flips
        // instantly in setZone(), and the light stepped 0.6 -> 1.2 in a single
        // frame at the 6-frame stagger. The eased value is now the state and
        // the cycling multiplies it, so the two legs cooperate instead of
        // fighting over one property.
        COLONY_ORDER.forEach(colony => {
            const entry = this.wingLights[colony];
            if (!entry?.spotlight) return;
            const { spotlight, profile } = entry;
            if (!Number.isFinite(this._wingBase[colony])) {
                // Seed from the authored constructor value, not from 0, so the
                // first eased step is a continuation rather than a jump.
                this._wingBase[colony] = spotlight.intensity;
            }
            const target = colony === this._targetZone ? 1.2 : 0.6;
            this._wingBase[colony] = damp(this._wingBase[colony], target, WING_BASE_RATE, dt);
            if (this._zoneTransition < 1) {
                const hemiBase = colony === this._targetZone ? 0.25 : 0.1;
                if (!Number.isFinite(this._wingHemiBase[colony])) {
                    this._wingHemiBase[colony] = entry.hemi?.intensity ?? hemiBase;
                }
                this._wingHemiBase[colony] = damp(this._wingHemiBase[colony], hemiBase, WING_BASE_RATE, dt);
                if (entry.hemi) entry.hemi.intensity = this._wingHemiBase[colony];
            }
            const period = profile.cycleSec;
            const phase = (this._time / period) * Math.PI * 2;
            const mult = 1 + Math.sin(phase) * profile.amount;
            spotlight.intensity = Math.max(0.2, this._wingBase[colony] * mult);
        });

        this.updateGanzfeldEffect(playerPosition, dt);
        this.updateGodRays();
    }

    updateGanzfeldEffect(playerPosition, dt = 0) {
        if (!playerPosition || !this.scene.fog) return;
        const isColony = COLONY_ORDER.includes(this._targetZone);
        const targetDensity = isColony ? 0.006 : 0.004;
        this.scene.fog.density = damp(this.scene.fog.density, targetDensity, GANZFELD_DENSITY_RATE, dt);

        if (isColony) {
            const colonyHex = COLONY_COLORS[this._targetZone];
            if (colonyHex) {
                this._tmpColor.setHex(colonyHex);
                this._currentFogColor.r = damp(this._currentFogColor.r, this._tmpColor.r, GANZFELD_COLOUR_RATE, dt);
                this._currentFogColor.g = damp(this._currentFogColor.g, this._tmpColor.g, GANZFELD_COLOUR_RATE, dt);
                this._currentFogColor.b = damp(this._currentFogColor.b, this._tmpColor.b, GANZFELD_COLOUR_RATE, dt);
                this.scene.fog.color.copy(this._currentFogColor);
            }
        }
    }

    updateGodRays() {
        if (!this.sunlight) return;
        const breathe = 1 + Math.sin(this._time * 0.14) * 0.06;
        this.sunlight.intensity = 2.2 * breathe;
        const drift = Math.sin(this._time * 0.02) * 2;
        this.sunlight.position.x = DIMENSIONS.rotunda.apertureOffset + drift;
    }

    /**
     * Shadow configuration for the aperture sun.
     *
     * V5-1102 — two changes, both measured defects rather than taste:
     *
     * 1. `normalBias` was absent from the entire repository (zero occurrences
     *    repo-wide; only `shadow.bias = -0.0001` at :357 and
     *    lib/performance.js:433). A depth bias alone cannot fix acne on a
     *    surface that is nearly parallel to the light, which is exactly the
     *    museum's shadow receivers — `floor.receiveShadow = true` at
     *    artworks/p1-fano-consensus.js:147, p1-efe-cbf.js:236,
     *    p1-s15-hopf.js:387. The remedy is a bias along the surface NORMAL,
     *    scaled to the shadow texel so it is not a magic number: this frustum
     *    spans 100 m across `mapSize` texels, so one texel is 100/mapSize m.
     *    Acne is a sub-texel artefact; a normal offset of one texel removes it
     *    without the peter-panning a multi-texel value would cause at this
     *    resolution.
     *
     * 2. `shadow.radius = 2` had no effect. `radius` is honoured only by
     *    THREE.BasicShadowMap/PCFShadowMap (and VSM); the renderer sets
     *    PCFSoftShadowMap (main.js:727 and lib/performance.js:371), whose
     *    kernel is fixed. It was kept as a documented no-op rather than
     *    deleted, and rather than switched on by changing the shadow type —
     *    changing the filter is a restyle of every shadow edge in the museum,
     *    which is a lighting-owned decision, not a defect cure.
     *
     * NOT fixed here, reported instead: the frustum spans +-50 m while the
     * museum reaches +-101 m (DIMENSIONS: rotunda.radius 20 + wing.length 45
     * + vestibuleDepth 6 + gallery.depth 30/2), so the gallery tier — where the
     * patented artworks sit, and where p1-fano-consensus.js:242 sets
     * `platform.castShadow = true` — is outside the shadow volume entirely.
     * Widening the frustum to cover it would halve the rotunda's shadow
     * resolution to buy shadows that were never authored to appear, so it is a
     * coverage decision for the lighting owner, not a bug this lane can settle.
     */
    enableShadows(mapSize = 1024) {
        if (this.sunlight) {
            const size = Number.isFinite(mapSize) && mapSize > 0 ? mapSize : 1024;
            this.sunlight.castShadow = true;
            this.sunlight.shadow.mapSize.set(size, size);
            this.sunlight.shadow.camera.near = 1;
            this.sunlight.shadow.camera.far = 100;
            this.sunlight.shadow.camera.left = -50;
            this.sunlight.shadow.camera.right = 50;
            this.sunlight.shadow.camera.top = 50;
            this.sunlight.shadow.camera.bottom = -50;
            this.sunlight.shadow.bias = -0.0001;
            // One shadow texel, in world metres: the frustum is 100 m wide.
            this.sunlight.shadow.normalBias = (100 / size);
            this.sunlight.shadow.radius = 2; // no-op under PCFSoftShadowMap — see above
            this.sunlight.shadow.camera.updateProjectionMatrix();
        }
    }

    dispose() {
        this.lights.forEach(light => {
            if (light.target) this.scene.remove(light.target);
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
