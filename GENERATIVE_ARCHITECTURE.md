# Generative Art Site Architecture

**Last Updated:** January 12, 2026
**System:** GENUX + fxhash-inspired deterministic generation

---

## Core Philosophy

The art repo is currently a **curated collection of interactive experiences** (home automation showcase, orchestral visualizations, changelogs). To transform it into a **proper generative site**, we add a hash-seeded generation system that produces infinite unique variations from a single algorithm.

### What Makes It Generative

```
seed → algorithm → unique artwork
```

Every piece is:
1. **Deterministic** — Same seed always produces same output
2. **Hashable** — URL-addressable: `/gen/spark?seed=abc123`
3. **Mintable** — Each seed locks a unique variation forever
4. **Explorable** — Random button discovers new variations

---

## Architecture

```
/Users/schizodactyl/projects/art/
├── gen/                          # NEW: Generative system
│   ├── index.html               # Generator gallery/browser
│   ├── lib/
│   │   ├── prng.js              # Seedable random (xorshift128+)
│   │   ├── noise.js             # Seeded Perlin/Simplex
│   │   ├── palette.js           # Colony-based color generation
│   │   └── genux.js             # GENUX primitives (breath, particles)
│   ├── algorithms/
│   │   ├── spark/               # 🔥 Ideation patterns
│   │   │   ├── index.html
│   │   │   └── algo.js
│   │   ├── forge/               # ⚒️ Structure patterns
│   │   ├── flow/                # 🌊 Fluid dynamics
│   │   ├── nexus/               # 🔗 Connection graphs
│   │   ├── beacon/              # 🗼 Light patterns
│   │   ├── grove/               # 🌿 Organic growth
│   │   └── crystal/             # 💎 Geometric facets
│   └── viewer.html              # Individual piece viewer
├── [existing curated pieces]    # home/, mop/, weather/, etc.
└── index.html                   # Main gallery (updated)
```

---

## Technical Implementation

### 1. Seedable PRNG (Required)

```javascript
// gen/lib/prng.js
export class PRNG {
    constructor(seed) {
        this.state = this._hashSeed(seed);
    }

    _hashSeed(str) {
        // Convert any string to consistent 128-bit state
        let h = 0x811c9dc5;
        for (let i = 0; i < str.length; i++) {
            h ^= str.charCodeAt(i);
            h = Math.imul(h, 0x01000193);
        }
        return [h >>> 0, (h * 2) >>> 0, (h * 3) >>> 0, (h * 4) >>> 0];
    }

    // xorshift128+ algorithm
    next() {
        let [s0, s1, s2, s3] = this.state;
        const result = (s0 + s3) >>> 0;
        const t = s1 << 9;
        s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3;
        s2 ^= t; s3 = (s3 << 11) | (s3 >>> 21);
        this.state = [s0, s1, s2, s3];
        return result / 0xffffffff;
    }

    // Convenience methods
    range(min, max) { return min + this.next() * (max - min); }
    int(min, max) { return Math.floor(this.range(min, max + 1)); }
    pick(arr) { return arr[this.int(0, arr.length - 1)]; }
    bool(prob = 0.5) { return this.next() < prob; }
    gaussian() {
        // Box-Muller transform
        const u1 = this.next(), u2 = this.next();
        return Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    }
}
```

### 2. Colony Palettes (GENUX Colors)

```javascript
// gen/lib/palette.js
const COLONY_PALETTES = {
    spark: {
        primary: '#FF6B35',
        secondary: '#FFB347',
        accent: '#F59E0B',
        bg: ['#1a0a05', '#2d1408', '#401a0a'],
        glow: 'rgba(255, 107, 53, 0.3)'
    },
    forge: {
        primary: '#FFB347',
        secondary: '#FFD700',
        accent: '#F59E0B',
        bg: ['#1a1505', '#2d2408', '#403508'],
        glow: 'rgba(255, 179, 71, 0.3)'
    },
    flow: {
        primary: '#4DD0E1',
        secondary: '#06B6D4',
        accent: '#0EA5E9',
        bg: ['#051a1e', '#082830', '#0a3642'],
        glow: 'rgba(77, 208, 225, 0.3)'
    },
    nexus: {
        primary: '#B388FF',
        secondary: '#A855F7',
        accent: '#8B5CF6',
        bg: ['#150a1e', '#220f30', '#2f1542'],
        glow: 'rgba(179, 136, 255, 0.3)'
    },
    beacon: {
        primary: '#FFE082',
        secondary: '#FFC107',
        accent: '#F59E0B',
        bg: ['#1a1a05', '#2d2d08', '#40400a'],
        glow: 'rgba(255, 224, 130, 0.3)'
    },
    grove: {
        primary: '#81C784',
        secondary: '#10B981',
        accent: '#059669',
        bg: ['#051a0a', '#082d12', '#0a401a'],
        glow: 'rgba(129, 199, 132, 0.3)'
    },
    crystal: {
        primary: '#4FC3F7',
        secondary: '#03A9F4',
        accent: '#0284C7',
        bg: ['#051520', '#0a2535', '#0f354a'],
        glow: 'rgba(79, 195, 247, 0.3)'
    }
};

export function getPalette(colony, rng) {
    const base = COLONY_PALETTES[colony] || COLONY_PALETTES.spark;
    return {
        ...base,
        // Add RNG-derived variations
        variation: rng.range(0.8, 1.2),
        saturation: rng.range(0.9, 1.1)
    };
}
```

### 3. Algorithm Template

```javascript
// gen/algorithms/spark/algo.js
import { PRNG } from '../../lib/prng.js';
import { getPalette } from '../../lib/palette.js';
import { createBreathingBackground } from '../../lib/genux.js';

export default function generate(canvas, seed) {
    const ctx = canvas.getContext('2d');
    const rng = new PRNG(seed);
    const palette = getPalette('spark', rng);

    // Clear with void
    ctx.fillStyle = '#07060B';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Add breathing background
    createBreathingBackground(ctx, palette, rng);

    // Algorithm-specific generation
    const particleCount = rng.int(50, 200);
    for (let i = 0; i < particleCount; i++) {
        drawParticle(ctx, rng, palette);
    }

    // Return metadata
    return {
        seed,
        colony: 'spark',
        particleCount,
        palette: palette.primary
    };
}

function drawParticle(ctx, rng, palette) {
    // ... particle logic
}
```

### 4. Viewer HTML Template

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>鏡 Gen · [COLONY] · [SEED]</title>
    <style>
        :root {
            --void: #07060B;
            --text: #F5F0E8;
            --amber: #F59E0B;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background: var(--void);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            font-family: 'IBM Plex Mono', monospace;
        }
        canvas {
            max-width: 100vmin;
            max-height: 100vmin;
            border: 1px solid rgba(255,255,255,0.08);
        }
        .controls {
            position: fixed;
            bottom: 2rem;
            display: flex;
            gap: 1rem;
        }
        button {
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.12);
            color: var(--text);
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.233s cubic-bezier(0.16, 1, 0.3, 1);
        }
        button:hover {
            background: var(--amber);
            color: var(--void);
        }
        .seed-display {
            position: fixed;
            top: 2rem;
            font-size: 0.75rem;
            color: rgba(245, 240, 232, 0.5);
            letter-spacing: 0.1em;
        }
    </style>
</head>
<body>
    <div class="seed-display">seed: <span id="seed"></span></div>
    <canvas id="canvas" width="1024" height="1024"></canvas>
    <div class="controls">
        <button id="random">Random</button>
        <button id="save">Save PNG</button>
        <button id="copy">Copy Link</button>
    </div>
    <script type="module">
        import generate from './algo.js';

        const canvas = document.getElementById('canvas');
        const seedEl = document.getElementById('seed');

        function getSeed() {
            const params = new URLSearchParams(window.location.search);
            return params.get('seed') || Math.random().toString(36).slice(2, 10);
        }

        function render(seed) {
            history.replaceState({}, '', `?seed=${seed}`);
            seedEl.textContent = seed;
            generate(canvas, seed);
        }

        document.getElementById('random').onclick = () => {
            render(Math.random().toString(36).slice(2, 10));
        };

        document.getElementById('save').onclick = () => {
            const link = document.createElement('a');
            link.download = `gen-${getSeed()}.png`;
            link.href = canvas.toDataURL('image/png');
            link.click();
        };

        document.getElementById('copy').onclick = () => {
            navigator.clipboard.writeText(window.location.href);
        };

        render(getSeed());
    </script>
</body>
</html>
```

---

## Algorithm Categories (7 Colonies)

### Spark (🔥 Ideation)
- Particle explosions
- Energy bursts
- Fire/flame simulations
- Stochastic spray patterns

### Forge (⚒️ Implementation)
- Structural grids
- Blueprint patterns
- Construction geometry
- Lattice formations

### Flow (🌊 Debugging)
- Fluid simulations
- Stream lines
- Wave patterns
- Curl noise fields

### Nexus (🔗 Integration)
- Network graphs
- Connection diagrams
- Constellation patterns
- Force-directed layouts

### Beacon (🗼 Planning)
- Radial projections
- Lighthouse sweeps
- Spotlight patterns
- Illumination gradients

### Grove (🌿 Research)
- L-system trees
- Organic growth
- Cellular automata
- Moss/lichen patterns

### Crystal (💎 Verification)
- Voronoi tessellations
- Geometric facets
- Recursive subdivisions
- Kaleidoscopic symmetry

---

## GENUX Integration

Every generated piece includes:

1. **Breathing background** — Three layers, offset animations
2. **Void palette** — #07060B base, colony accent
3. **Fibonacci timing** — 89, 144, 233, 377, 610ms
4. **Catastrophe easings** — fold, cusp, swallowtail
5. **Hidden layers** — data-seed, data-colony attributes
6. **Console easter egg** — `window.鏡.gen` object

---

## URL Schema

```
/gen/                           # Gallery of all algorithms
/gen/spark/                     # Spark algorithm browser
/gen/spark/?seed=abc123         # Specific piece
/gen/viewer/?algo=spark&seed=x  # Universal viewer
```

---

## Refinement Process

For each algorithm:

1. **Generate 10 random seeds**
2. **Evaluate each** on:
   - Visual coherence (does it hold together?)
   - Colony alignment (does it match the theme?)
   - Edge cases (what breaks at extremes?)
3. **Iterate algorithm** to handle weak outputs
4. **Lock algorithm** when 9/10 outputs are gallery-worthy

---

## Next Steps

1. Create `/gen/lib/` with PRNG, noise, palette utilities
2. Build first algorithm (spark — particle systems)
3. Create viewer template
4. Generate 10 test pieces
5. Refine based on outputs
6. Repeat for each colony

---

*Generative art is not about one perfect piece. It's about a system that produces infinite perfect pieces.*

鏡
