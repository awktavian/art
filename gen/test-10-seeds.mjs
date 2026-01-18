/**
 * Test 10 Random Seeds — Generative Art Refinement
 *
 * This script generates 10 random seeds and analyzes the parameter distributions
 * to identify potential issues in the algorithm.
 *
 * Run: node test-10-seeds.mjs
 */

// PRNG implementation (same as lib/prng.js)
class PRNG {
    constructor(seed) {
        this.state = this._hashSeed(String(seed));
    }

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

        if (h1 === 0 && h2 === 0 && h3 === 0 && h4 === 0) h1 = 0x12345678;
        return [h1 >>> 0, h2 >>> 0, h3 >>> 0, h4 >>> 0];
    }

    next() {
        let [s0, s1, s2, s3] = this.state;
        const result = (s0 + s3) >>> 0;
        const t = s1 << 9;
        s2 ^= s0; s3 ^= s1; s1 ^= s2; s0 ^= s3;
        s2 ^= t; s3 = (s3 << 11) | (s3 >>> 21);
        this.state = [s0 >>> 0, s1 >>> 0, s2 >>> 0, s3 >>> 0];
        return result / 0xffffffff;
    }

    range(min, max) { return min + this.next() * (max - min); }
    int(min, max) { return Math.floor(this.range(min, max + 1)); }
    bool(prob = 0.5) { return this.next() < prob; }
}

// Generate parameters for Spark algorithm
// REFINED: Jan 12, 2026 — raised minimums based on first test batch
function generateSparkParams(seed) {
    const rng = new PRNG(seed);

    return {
        seed,
        burstCount: rng.int(4, 8),        // was 3-8
        particleCount: rng.int(100, 200), // was 80-200
        connectionDensity: rng.range(0.3, 0.7),
        energyIntensity: rng.range(0.65, 1.0), // was 0.6-1.0
        trailLength: rng.int(4, 8),       // was 3-8
        asymmetry: rng.range(0.2, 0.8)
    };
}

// Generate 10 random seeds
function generateSeeds(count = 10) {
    const seeds = [];
    for (let i = 0; i < count; i++) {
        seeds.push(Math.random().toString(36).slice(2, 10));
    }
    return seeds;
}

// Evaluate quality heuristics
function evaluateParams(params) {
    const issues = [];
    let score = 100;

    // Check for potential issues
    if (params.burstCount <= 3) {
        issues.push('Low burst count may feel sparse');
        score -= 15;
    }

    if (params.particleCount < 100) {
        issues.push('Low particle count may feel empty');
        score -= 10;
    }

    if (params.energyIntensity < 0.7) {
        issues.push('Low energy may feel muted');
        score -= 10;
    }

    if (params.trailLength < 4) {
        issues.push('Short trails may feel abrupt');
        score -= 5;
    }

    if (params.asymmetry < 0.3 || params.asymmetry > 0.7) {
        // Extremes can be interesting, not always bad
    }

    // Positive factors
    if (params.burstCount >= 5 && params.energyIntensity >= 0.8) {
        score += 5; // High energy composition
    }

    if (params.particleCount >= 150) {
        score += 5; // Rich texture
    }

    return { score: Math.max(0, Math.min(100, score)), issues };
}

// Main
console.log('═══════════════════════════════════════════════════════════════════');
console.log('  🔥 SPARK ALGORITHM — 10 SEED TEST');
console.log('═══════════════════════════════════════════════════════════════════');
console.log('');

const seeds = generateSeeds(10);
const results = [];

seeds.forEach((seed, i) => {
    const params = generateSparkParams(seed);
    const evaluation = evaluateParams(params);

    results.push({ ...params, ...evaluation });

    const statusIcon = evaluation.score >= 85 ? '✓' : evaluation.score >= 70 ? '○' : '✗';
    const statusColor = evaluation.score >= 85 ? '\x1b[32m' : evaluation.score >= 70 ? '\x1b[33m' : '\x1b[31m';

    console.log(`${statusColor}${statusIcon}\x1b[0m Seed: \x1b[36m${seed}\x1b[0m`);
    console.log(`  Bursts: ${params.burstCount} | Particles: ${params.particleCount} | Energy: ${(params.energyIntensity * 100).toFixed(0)}%`);
    console.log(`  Score: ${evaluation.score}/100`);
    if (evaluation.issues.length > 0) {
        console.log(`  Issues: ${evaluation.issues.join(', ')}`);
    }
    console.log('');
});

// Summary statistics
console.log('═══════════════════════════════════════════════════════════════════');
console.log('  SUMMARY');
console.log('═══════════════════════════════════════════════════════════════════');

const avgScore = results.reduce((sum, r) => sum + r.score, 0) / results.length;
const galleryWorthy = results.filter(r => r.score >= 85).length;
const acceptable = results.filter(r => r.score >= 70 && r.score < 85).length;
const needsWork = results.filter(r => r.score < 70).length;

console.log(`  Average Score: ${avgScore.toFixed(1)}/100`);
console.log(`  Gallery-worthy (≥85): ${galleryWorthy}/10`);
console.log(`  Acceptable (70-84): ${acceptable}/10`);
console.log(`  Needs Work (<70): ${needsWork}/10`);
console.log('');

// Parameter ranges
const avgBursts = results.reduce((sum, r) => sum + r.burstCount, 0) / results.length;
const avgParticles = results.reduce((sum, r) => sum + r.particleCount, 0) / results.length;
const avgEnergy = results.reduce((sum, r) => sum + r.energyIntensity, 0) / results.length;

console.log('  Parameter Averages:');
console.log(`    Bursts: ${avgBursts.toFixed(1)} (range: 3-8)`);
console.log(`    Particles: ${avgParticles.toFixed(0)} (range: 80-200)`);
console.log(`    Energy: ${(avgEnergy * 100).toFixed(0)}% (range: 60-100%)`);
console.log('');

// Common issues
const allIssues = results.flatMap(r => r.issues);
const issueCounts = {};
allIssues.forEach(i => issueCounts[i] = (issueCounts[i] || 0) + 1);

if (Object.keys(issueCounts).length > 0) {
    console.log('  Common Issues:');
    Object.entries(issueCounts)
        .sort((a, b) => b[1] - a[1])
        .forEach(([issue, count]) => {
            console.log(`    - ${issue} (×${count})`);
        });
    console.log('');
}

// Refinement recommendations
console.log('═══════════════════════════════════════════════════════════════════');
console.log('  REFINEMENT RECOMMENDATIONS');
console.log('═══════════════════════════════════════════════════════════════════');

if (avgBursts < 5) {
    console.log('  → Consider raising minimum burst count from 3 to 4');
}

if (avgParticles < 140) {
    console.log('  → Consider raising minimum particle count from 80 to 100');
}

if (avgEnergy < 0.75) {
    console.log('  → Consider raising minimum energy from 0.6 to 0.7');
}

if (galleryWorthy >= 8) {
    console.log('  ✓ Algorithm performing well! 8+/10 gallery-worthy.');
} else if (galleryWorthy >= 6) {
    console.log('  ○ Algorithm acceptable. Consider minor parameter tuning.');
} else {
    console.log('  ✗ Algorithm needs work. Review parameter ranges.');
}

console.log('');
console.log('═══════════════════════════════════════════════════════════════════');
console.log('  View at: file:///Users/schizodactyl/projects/art/gen/test-harness.html');
console.log('═══════════════════════════════════════════════════════════════════');
