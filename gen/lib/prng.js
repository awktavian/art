/**
 * Seedable PRNG — xorshift128+ algorithm
 * Deterministic random generation from any string seed.
 *
 * Usage:
 *   const rng = new PRNG('my-seed-string');
 *   rng.next();        // 0-1 float
 *   rng.range(0, 100); // float in range
 *   rng.int(1, 6);     // integer in range (inclusive)
 *   rng.pick(['a','b']); // random array element
 */

export class PRNG {
    constructor(seed) {
        this.state = this._hashSeed(String(seed));
    }

    /**
     * Convert any string to 128-bit state via FNV-1a hash
     */
    _hashSeed(str) {
        let h1 = 0x811c9dc5;
        let h2 = 0x811c9dc5 ^ 0xdeadbeef;
        let h3 = 0x811c9dc5 ^ 0xcafebabe;
        let h4 = 0x811c9dc5 ^ 0x12345678;

        for (let i = 0; i < str.length; i++) {
            const c = str.charCodeAt(i);
            h1 ^= c; h1 = Math.imul(h1, 0x01000193);
            h2 ^= c; h2 = Math.imul(h2, 0x01000193);
            h3 ^= c; h3 = Math.imul(h3, 0x01000193);
            h4 ^= c; h4 = Math.imul(h4, 0x01000193);
        }

        // Ensure non-zero state (xorshift requirement)
        if (h1 === 0 && h2 === 0 && h3 === 0 && h4 === 0) {
            h1 = 0x12345678;
        }

        return [h1 >>> 0, h2 >>> 0, h3 >>> 0, h4 >>> 0];
    }

    /**
     * xorshift128+ — fast, high-quality PRNG
     * Returns float in [0, 1)
     */
    next() {
        let [s0, s1, s2, s3] = this.state;
        const result = (s0 + s3) >>> 0;

        const t = s1 << 9;
        s2 ^= s0;
        s3 ^= s1;
        s1 ^= s2;
        s0 ^= s3;
        s2 ^= t;
        s3 = (s3 << 11) | (s3 >>> 21);

        this.state = [s0 >>> 0, s1 >>> 0, s2 >>> 0, s3 >>> 0];
        return result / 0xffffffff;
    }

    /**
     * Float in [min, max)
     */
    range(min, max) {
        return min + this.next() * (max - min);
    }

    /**
     * Integer in [min, max] (inclusive)
     */
    int(min, max) {
        return Math.floor(this.range(min, max + 1));
    }

    /**
     * Random element from array
     */
    pick(arr) {
        if (arr.length === 0) return undefined;
        return arr[this.int(0, arr.length - 1)];
    }

    /**
     * Boolean with given probability of true
     */
    bool(prob = 0.5) {
        return this.next() < prob;
    }

    /**
     * Gaussian distribution via Box-Muller transform
     * mean=0, stddev=1 by default
     */
    gaussian(mean = 0, stddev = 1) {
        const u1 = this.next();
        const u2 = this.next();
        const z = Math.sqrt(-2 * Math.log(u1 || 0.0001)) * Math.cos(2 * Math.PI * u2);
        return mean + z * stddev;
    }

    /**
     * Shuffle array in place (Fisher-Yates)
     */
    shuffle(arr) {
        for (let i = arr.length - 1; i > 0; i--) {
            const j = this.int(0, i);
            [arr[i], arr[j]] = [arr[j], arr[i]];
        }
        return arr;
    }

    /**
     * Generate n unique integers in [min, max]
     */
    uniqueInts(n, min, max) {
        const range = max - min + 1;
        if (n > range) n = range;

        const set = new Set();
        while (set.size < n) {
            set.add(this.int(min, max));
        }
        return [...set];
    }

    /**
     * Weighted random selection
     * weights array should sum to 1 (or will be normalized)
     */
    weighted(items, weights) {
        const total = weights.reduce((a, b) => a + b, 0);
        let r = this.next() * total;

        for (let i = 0; i < items.length; i++) {
            r -= weights[i];
            if (r <= 0) return items[i];
        }
        return items[items.length - 1];
    }

    /**
     * 2D point in unit square
     */
    point2D() {
        return { x: this.next(), y: this.next() };
    }

    /**
     * HSL color with optional constraints
     */
    color(hueRange = [0, 360], satRange = [50, 100], lightRange = [40, 60]) {
        const h = this.range(hueRange[0], hueRange[1]);
        const s = this.range(satRange[0], satRange[1]);
        const l = this.range(lightRange[0], lightRange[1]);
        return `hsl(${h}, ${s}%, ${l}%)`;
    }
}

export default PRNG;
