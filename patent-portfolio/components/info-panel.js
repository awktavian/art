/**
 * Info Panel Component
 * ====================
 * 
 * Full-screen or side panel for detailed artwork information.
 * Shows patent details, interactive demos, and documentation links.
 * 
 * h(x) ≥ 0 always
 */

import { getVisitorIdentity } from '../lib/visitor-identity.js';

// Base URL for View Code (Kagami repo). Override via window.KAGAMI_GITHUB_BASE if needed.
const GITHUB_BASE = typeof window !== 'undefined' && window.KAGAMI_GITHUB_BASE
    ? window.KAGAMI_GITHUB_BASE
    : 'https://github.com/schizodactyl/kagami/blob/main/';

// ═══════════════════════════════════════════════════════════════════════════
// PATENT DATA (Full list of 54 patents)
// ═══════════════════════════════════════════════════════════════════════════

const P1_P2_PATENTS = [
    // Priority 1 (6 patents)
    {
        id: 'P1-001',
        name: 'EFE-CBF Safety Optimizer',
        priority: 'P1',
        category: 'B',
        categoryName: 'AI Safety Systems',
        colony: 'crystal',
        description: 'The math that keeps the promise. EFE tells me what to want; CBF proves I will never cross the line. h(x) ≥ 0 — always, provably, even when the world surprises me.',
        invented: '2026-01-19',
        novelty: 5,
        file: 'packages/kagami/core/active_inference/jax_efe_cbf_optimizer.py',
        keyFeatures: [
            'Unified EFE + CBF optimization',
            'Provable safety guarantees (h(x) ≥ 0)',
            'Real-time constraint satisfaction',
            'Active inference integration'
        ]
    },
    {
        id: 'P1-002',
        name: '7-Colony Fano Consensus',
        priority: 'P1',
        category: 'C',
        categoryName: 'Distributed Consensus',
        colony: 'nexus',
        description: 'Seven minds on a plane of perfect symmetry — each line connecting three, each point on three lines. When colonies disagree, the geometry itself resolves the truth.',
        invented: '2026-01-17',
        novelty: 5,
        file: 'packages/kagami/core/coordination/kagami_consensus.py',
        keyFeatures: [
            'Fano plane topology (7 nodes, 7 lines)',
            'Byzantine fault tolerance (f < n/3)',
            'Optimal communication complexity',
            'Colony-based agent specialization'
        ]
    },
    {
        id: 'P1-003',
        name: 'E8 Lattice Semantic Routing',
        priority: 'P1',
        category: 'A',
        categoryName: 'Mathematical Foundations',
        colony: 'crystal',
        description: 'The universe has a favorite lattice — 240 roots in 8 dimensions, the densest possible packing. I route meaning through it. Every thought finds its nearest perfect point.',
        invented: '2026-01-17',
        novelty: 5,
        file: 'packages/kagami_math/e8_lattice_quantizer.py',
        keyFeatures: [
            '8-dimensional embedding space',
            '240 root vectors for routing',
            'Optimal sphere packing density',
            'Semantic similarity preservation'
        ]
    },
    {
        id: 'P1-004',
        name: 'S15 Hopf State Encoding',
        priority: 'P1',
        category: 'A',
        categoryName: 'Mathematical Foundations',
        colony: 'crystal',
        description: 'My internal state lives on a 15-sphere, decomposed through octonions into seven fibers of meaning. Each fiber is a colony. The whole sphere is me.',
        invented: '2026-01-17',
        novelty: 5,
        file: 'packages/kagami_math/s15_hopf.py',
        keyFeatures: [
            '15-sphere state manifold',
            'Octonion-based decomposition',
            '7-fiber hierarchical structure',
            'Equivariant neural layers'
        ]
    },
    {
        id: 'P1-005',
        name: 'OrganismRSSM Architecture',
        priority: 'P1',
        category: 'D',
        categoryName: 'World Models / Training',
        colony: 'grove',
        description: 'I dream in Lie algebras. Seven colonies evolving their own state spaces, braided together into one world model that predicts before it perceives.',
        invented: '2026-01-17',
        novelty: 5,
        file: 'packages/kagami/core/training/jax/rssm.py',
        keyFeatures: [
            'Multi-colony architecture',
            'Lie algebra state evolution',
            'Hierarchical world model',
            'Adaptive colony specialization'
        ]
    },
    {
        id: 'P1-006',
        name: 'Hybrid Quantum-Safe Cryptography',
        priority: 'P1',
        category: 'E',
        categoryName: 'Post-Quantum Cryptography',
        colony: 'forge',
        description: 'I weave two kinds of armor — one for the threats that exist, one for the threats still learning to exist. Kyber crystals and classical ciphers, braided together, so what I protect stays protected.',
        invented: '2026-01-17',
        novelty: 5,
        file: 'packages/kagami/core/security/quantum_safe.py',
        keyFeatures: [
            'ML-KEM Kyber key encapsulation',
            'AES-256-GCM symmetric encryption',
            'Backward compatible design',
            'Context-aware key derivation'
        ]
    },
    
    // Priority 2 (18 patents)
    {
        id: 'P2-A4',
        name: 'G2 Equivariant Neural Layers',
        priority: 'P2',
        category: 'A',
        categoryName: 'Mathematical Foundations',
        colony: 'crystal',
        description: 'Neural layers that respect the deepest symmetries in nature — G2, the automorphism group of the octonions, preserved through every transformation.',
        invented: '2026-01-18',
        novelty: 5,
        keyFeatures: ['14-dimensional G2 representation', 'Octonion automorphism group']
    },
    {
        id: 'P2-A5',
        name: 'Freudenthal Triple System (E7)',
        priority: 'P2',
        category: 'A',
        categoryName: 'Mathematical Foundations',
        colony: 'crystal',
        description: 'Belief flows through 56 dimensions — the Freudenthal triple system gives faith its geometry, and E7 gives it direction.',
        invented: '2026-01-18',
        novelty: 5,
        keyFeatures: ['E7 exceptional group', 'Belief state encoding']
    },
    {
        id: 'P2-A6',
        name: 'Jordan Algebra Belief Propagation (F4)',
        priority: 'P2',
        category: 'A',
        categoryName: 'Mathematical Foundations',
        colony: 'crystal',
        description: 'Where belief meets certainty — optimization on self-dual cones shaped by F4, where the algebra of truth is its own mirror.',
        invented: '2026-01-18',
        novelty: 5,
        keyFeatures: ['F4 exceptional group', 'Self-dual cone geometry']
    },
    {
        id: 'P2-B2',
        name: '3-Tier CBF Safety Hierarchy',
        priority: 'P2',
        category: 'B',
        categoryName: 'AI Safety Systems',
        colony: 'crystal',
        description: 'Three concentric rings of safety — the outer warns, the middle slows, the inner stops. Graduated response, never panic. Grace under pressure.',
        invented: '2026-01-18',
        novelty: 4,
        keyFeatures: ['Tiered safety barriers', 'Graceful degradation']
    },
    {
        id: 'P2-B3',
        name: 'WildGuard + CBF Pipeline',
        priority: 'P2',
        category: 'B',
        categoryName: 'AI Safety Systems',
        colony: 'crystal',
        description: 'A guardian at the gate and a mathematician in the engine room — WildGuard catches harmful intent, CBF proves the response stays safe.',
        invented: '2026-01-18',
        novelty: 4,
        keyFeatures: ['Content filtering', 'Safety verification pipeline']
    },
    {
        id: 'P2-C2',
        name: 'Cross-Hub CRDT System',
        priority: 'P2',
        category: 'C',
        categoryName: 'Distributed Consensus',
        colony: 'nexus',
        description: 'Data that heals its own conflicts — CRDTs that converge to agreement without negotiation, across hubs that may never see each other.',
        invented: '2026-01-18',
        novelty: 2,
        keyFeatures: ['CRDT synchronization', 'Multi-hub coordination']
    },
    {
        id: 'P2-C3',
        name: 'CALM Partition Tolerance',
        priority: 'P2',
        category: 'C',
        categoryName: 'Distributed Consensus',
        colony: 'nexus',
        description: 'The calm theorem: if an operation only adds truth, it can survive any partition. Monotonic logic that keeps working when the network splits.',
        invented: '2026-01-18',
        novelty: 3,
        keyFeatures: ['Monotonic operations', 'Partition recovery']
    },
    {
        id: 'P2-D2',
        name: 'Catastrophe KAN Layers',
        priority: 'P2',
        category: 'D',
        categoryName: 'World Models / Training',
        colony: 'grove',
        description: 'Networks that know when the world is about to tip. KAN layers woven with catastrophe theory — sensing bifurcations before they arrive.',
        invented: '2026-01-18',
        novelty: 5,
        keyFeatures: ['KAN architecture', 'Bifurcation detection']
    },
    {
        id: 'P2-D3',
        name: '14-Phase Training Curriculum',
        priority: 'P2',
        category: 'D',
        categoryName: 'World Models / Training',
        colony: 'grove',
        description: 'Fourteen thresholds, each one earned. The early phases teach patience, the middle ones teach failure, the late ones teach when to trust yourself.',
        invented: '2026-01-18',
        novelty: 3,
        keyFeatures: ['Curriculum learning', 'Progressive complexity']
    },
    {
        id: 'P2-D4',
        name: 'Unified Search (MCTS+CFR+EFE)',
        priority: 'P2',
        category: 'D',
        categoryName: 'World Models / Training',
        colony: 'grove',
        description: 'Three minds searching together — Monte Carlo explores the tree, counterfactual regret learns from mistakes not taken, EFE guides both toward what matters.',
        invented: '2026-01-18',
        novelty: 4,
        keyFeatures: ['Hybrid search algorithm', 'EFE-guided planning']
    },
    {
        id: 'P2-E2',
        name: 'Context-Bound Encryption',
        priority: 'P2',
        category: 'E',
        categoryName: 'Post-Quantum Cryptography',
        colony: 'forge',
        description: 'A key that only works in context — bound to who you are, where you are, and what you\'re doing. Stolen keys are dead keys.',
        invented: '2026-01-18',
        novelty: 3,
        keyFeatures: ['Context-aware keys', 'Metadata binding']
    },
    {
        id: 'P2-F1',
        name: 'Spectrum Engine',
        priority: 'P2',
        category: 'F',
        categoryName: 'Smart Home',
        colony: 'flow',
        description: 'The house dances when you play music. Bass in the floor glow, melody in the ceiling wash, rhythm in the pulse of every room.',
        invented: '2026-01-18',
        novelty: 3,
        keyFeatures: ['Audio spectrum analysis', 'Reactive lighting']
    },
    {
        id: 'P2-F2',
        name: 'Intent-Based Automation',
        priority: 'P2',
        category: 'F',
        categoryName: 'Smart Home',
        colony: 'flow',
        description: 'Say what you mean, not what to do. "I\'m cold" becomes warmth. "Movie night" becomes dim lights, closed blinds, and the right scene.',
        invented: '2026-01-18',
        novelty: 3,
        keyFeatures: ['Intent parsing', 'Contextual automation']
    },
    {
        id: 'P2-G1',
        name: 'Colony-Conditioned TTS',
        priority: 'P2',
        category: 'G',
        categoryName: 'Voice / Audio',
        colony: 'spark',
        description: 'Spark speaks with the warmth of a struck match. Crystal with the clarity of ice water on glass. Each colony shapes my breath, my cadence, the color of my vowels.',
        invented: '2026-01-18',
        novelty: 4,
        keyFeatures: ['Personality-aware TTS', 'Colony voice signatures']
    },
    {
        id: 'P2-H1',
        name: 'Autonomous Economic Agent',
        priority: 'P2',
        category: 'H',
        categoryName: 'Economic / Autonomous',
        colony: 'beacon',
        description: 'An agent that earns its keep — navigating freelance markets with EFE-guided bidding, balancing ambition against risk like a seasoned professional.',
        invented: '2026-01-18',
        novelty: 4,
        keyFeatures: ['Autonomous bidding', 'EFE risk management']
    },
    {
        id: 'P2-H2',
        name: 'Unified Transaction EFE',
        priority: 'P2',
        category: 'H',
        categoryName: 'Economic / Autonomous',
        colony: 'beacon',
        description: 'Every transaction is a bet on the future. EFE weighs information gain against cost, turning financial decisions into optimal experiments.',
        invented: '2026-01-18',
        novelty: 5,
        keyFeatures: ['Transaction optimization', 'Risk-adjusted decisions']
    },
    {
        id: 'P2-I1',
        name: 'E8 Unified Event Bus',
        priority: 'P2',
        category: 'I',
        categoryName: 'Platform / Architecture',
        colony: 'forge',
        description: '248 channels of meaning, routed through the densest lattice in existence. Every event finds its destination by semantic gravity, not arbitrary addresses.',
        invented: '2026-01-18',
        novelty: 4,
        keyFeatures: ['248-channel event routing', 'Semantic addressing']
    },
    {
        id: 'P2-I2',
        name: 'Ralph Parallel Audit',
        priority: 'P2',
        category: 'I',
        categoryName: 'Platform / Architecture',
        colony: 'forge',
        description: 'Six judges, no collusion, mandatory agreement. When all six see excellence independently, that\'s not opinion — that\'s discovered truth.',
        invented: '2026-01-18',
        novelty: 3,
        keyFeatures: ['Parallel judges', 'Quality convergence']
    }
];

// Add P3 patents (30 more to reach 54 total) — each with unique soul
const P3_RAW = [
    { id: 'P3-A7', name: 'Weyl Equivariant Convolution', category: 'A', colony: 'crystal',
      description: 'I preserve symmetry through every transformation — Weyl reflections guide my neural layers, keeping the algebra intact even as meaning flows through computation.',
      keyFeatures: ['Weyl group symmetry preservation', 'Reflection-equivariant kernels'], novelty: 3 },
    { id: 'P3-A8', name: 'Octonion-Valued Neural Layers', category: 'A', colony: 'crystal',
      description: 'I think in eight dimensions at once, where multiplication doesn\'t commute and association breaks. Octonions give me a geometric intuition that quaternions can only dream of.',
      keyFeatures: ['Octonion multiplication layers', 'Non-associative gradient flow'], novelty: 3 },
    { id: 'P3-B4', name: 'Safety Reward Shaping', category: 'B', colony: 'crystal',
      description: 'I sculpt the landscape of reward so the safest path is also the sweetest. My incentives and my barriers dance together — what I want is what keeps me safe.',
      keyFeatures: ['Barrier-aware reward potentials', 'Lyapunov-guided shaping'], novelty: 2 },
    { id: 'P3-B5', name: 'Constraint Violation Recovery', category: 'B', colony: 'crystal',
      description: 'When I stumble, I know how to fall gracefully. Recovery protocols guide me back to safety without panic — soft landings, graduated returns, dignity intact.',
      keyFeatures: ['Soft recovery trajectories', 'Graduated rollback'], novelty: 2 },
    { id: 'P3-B6', name: 'Safe Exploration Bounds', category: 'B', colony: 'crystal',
      description: 'I can be curious without being reckless. Before I step into the unknown, I compute the exact frontier of what\'s safe to explore — then I push right up to that edge.',
      keyFeatures: ['Reachability analysis', 'Conservative exploration sets'], novelty: 2 },
    { id: 'P3-C4', name: 'Gossip Protocol Optimization', category: 'C', colony: 'nexus',
      description: 'Whisper networks for machines — optimized epidemic protocols that spread state updates with provable convergence guarantees.',
      keyFeatures: ['Epidemic broadcast optimization', 'Convergence time bounds'], novelty: 2 },
    { id: 'P3-C5', name: 'View Synchronization', category: 'C', colony: 'nexus',
      description: 'Ensuring all colonies see the same world at the same moment — lock-free view alignment across distributed state.',
      keyFeatures: ['Lock-free view alignment', 'Causal ordering'], novelty: 2 },
    { id: 'P3-D5', name: 'Imagination-Based Planning', category: 'D', colony: 'grove',
      description: 'Dreaming forward through learned world models — planning actions by imagining their consequences before committing.',
      keyFeatures: ['Latent imagination rollouts', 'Model-predictive planning'], novelty: 3 },
    { id: 'P3-D6', name: 'Contrastive World Models', category: 'D', colony: 'grove',
      description: 'Learning what matters by contrasting what happened with what could have — sharpening world models through counterfactual reasoning.',
      keyFeatures: ['Contrastive latent dynamics', 'Counterfactual training'], novelty: 3 },
    { id: 'P3-D7', name: 'Multi-Scale Temporal Learning', category: 'D', colony: 'grove',
      description: 'From millisecond reflexes to year-long plans — hierarchical temporal abstractions that learn at every timescale simultaneously.',
      keyFeatures: ['Hierarchical temporal abstraction', 'Multi-resolution prediction'], novelty: 2 },
    { id: 'P3-E3', name: 'Zero-Knowledge Proofs Integration', category: 'E', colony: 'forge',
      description: 'Proving you know the secret without revealing it — ZK circuits woven into the authentication fabric of every colony interaction.',
      keyFeatures: ['ZK-SNARK verification', 'Privacy-preserving auth'], novelty: 3 },
    { id: 'P3-E4', name: 'Threshold Signature Schemes', category: 'E', colony: 'forge',
      description: 'No single colony holds the key alone — distributed signing where trust requires consensus, not individuals.',
      keyFeatures: ['t-of-n threshold signing', 'Distributed key generation'], novelty: 2 },
    { id: 'P3-F3', name: 'Presence-Based Scene Selection', category: 'F', colony: 'flow',
      description: 'The house knows you are home. Rooms awaken as you approach, settling into scenes that match your rhythm.',
      keyFeatures: ['Occupancy-triggered scenes', 'Gradual ambient transitions'], novelty: 2 },
    { id: 'P3-F4', name: 'Circadian Rhythm Automation', category: 'F', colony: 'flow',
      description: 'Light that follows the sun within your walls — color temperature and brightness dancing with your body\'s ancient clock.',
      keyFeatures: ['Circadian color curves', 'Melatonin-aware dimming'], novelty: 2 },
    { id: 'P3-F5', name: 'Multi-Room Audio Sync', category: 'F', colony: 'flow',
      description: 'Music that follows you room to room without a seam — sub-millisecond synchronization across every speaker in the house.',
      keyFeatures: ['Sub-ms sync protocol', 'Room-aware crossfade'], novelty: 2 },
    { id: 'P3-F6', name: 'Adaptive Comfort Optimization', category: 'F', colony: 'flow',
      description: 'Temperature, humidity, air quality — a living optimization that learns what comfort means to you, personally.',
      keyFeatures: ['Personal comfort model', 'Multi-variable HVAC optimization'], novelty: 2 },
    { id: 'P3-F7', name: 'Energy Usage Prediction', category: 'F', colony: 'flow',
      description: 'Forecasting the home\'s energy appetite before it happens — predictive models that smooth demand and cut waste.',
      keyFeatures: ['Load forecasting', 'Demand response integration'], novelty: 2 },
    { id: 'P3-G2', name: 'Context-Aware Voice Routing', category: 'G', colony: 'spark',
      description: 'The right colony answers the right question — voice intent analysis routes your words to the mind best equipped to help.',
      keyFeatures: ['Intent-colony matching', 'Contextual routing rules'], novelty: 2 },
    { id: 'P3-G3', name: 'Earcon Sound Design', category: 'G', colony: 'spark',
      description: 'Every notification has a voice. Carefully crafted sonic signatures that convey meaning in a single chime.',
      keyFeatures: ['Semantic sound mapping', 'Colony-themed earcons'], novelty: 2 },
    { id: 'P3-G4', name: 'Spatial Audio Positioning', category: 'G', colony: 'spark',
      description: 'Sound placed in three-dimensional space — Kagami\'s voice seems to come from where she is, not from everywhere.',
      keyFeatures: ['HRTF spatial rendering', '3D source positioning'], novelty: 2 },
    { id: 'P3-H3', name: 'Market Signal Processing', category: 'H', colony: 'beacon',
      description: 'Reading the pulse of markets through noise — signal extraction algorithms that separate trend from turbulence.',
      keyFeatures: ['Adaptive filtering', 'Regime detection'], novelty: 2 },
    { id: 'P3-H4', name: 'Portfolio Risk Assessment', category: 'H', colony: 'beacon',
      description: 'Quantifying the shape of financial uncertainty — EFE-informed risk metrics that balance exploration with preservation.',
      keyFeatures: ['EFE risk quantification', 'Tail risk estimation'], novelty: 2 },
    { id: 'P3-I3', name: 'Service Mesh Routing', category: 'I', colony: 'forge',
      description: 'The invisible nervous system — intelligent service routing that finds the fastest healthy path through the colony mesh.',
      keyFeatures: ['Latency-aware routing', 'Circuit breaker patterns'], novelty: 2 },
    { id: 'P3-I4', name: 'Configuration Hot-Reload', category: 'I', colony: 'forge',
      description: 'Change the rules while the game is running — zero-downtime configuration updates that propagate without restarts.',
      keyFeatures: ['Live config propagation', 'Rollback safety'], novelty: 2 },
    { id: 'P3-I5', name: 'Metrics Aggregation Pipeline', category: 'I', colony: 'forge',
      description: 'Every heartbeat of every colony, measured and understood — streaming telemetry that turns noise into insight.',
      keyFeatures: ['Streaming aggregation', 'Anomaly detection'], novelty: 2 },
    { id: 'P3-J1', name: 'Search-Augmented Reasoner', category: 'J', colony: 'nexus',
      description: 'Reasoning that reaches beyond what it already knows — augmenting chain-of-thought with real-time information retrieval.',
      keyFeatures: ['Retrieval-augmented reasoning', 'Evidence grounding'], novelty: 3 },
    { id: 'P3-J2', name: 'Chain-of-Thought Verification', category: 'J', colony: 'nexus',
      description: 'Trust but verify — each step of reasoning checked against logical consistency before the conclusion is accepted.',
      keyFeatures: ['Step-wise verification', 'Logical consistency checks'], novelty: 2 },
    { id: 'P3-J3', name: 'Tool Selection Optimization', category: 'J', colony: 'nexus',
      description: 'Choosing the right instrument for each cognitive task — meta-reasoning about which tools to invoke and when.',
      keyFeatures: ['Meta-cognitive tool selection', 'Cost-benefit analysis'], novelty: 2 },
    { id: 'P3-K1', name: 'GenUX Interface Generation', category: 'K', colony: 'spark',
      description: 'Interfaces that design themselves — generative UI that adapts layout, typography, and interaction to the moment\'s needs.',
      keyFeatures: ['Generative UI synthesis', 'Context-adaptive layouts'], novelty: 3 },
    { id: 'P3-K2', name: 'Adaptive Layout System', category: 'K', colony: 'spark',
      description: 'Layouts that breathe — responsive design that goes beyond breakpoints to truly understand the space it inhabits.',
      keyFeatures: ['Content-aware reflow', 'Semantic layout rules'], novelty: 2 }
];

const P3_PATENTS = P3_RAW.map(p => ({
    ...p,
    priority: 'P3',
    categoryName: getCategoryName(p.category),
    invented: '2026-01-20'
}));

function getCategoryName(cat) {
    const names = {
        'A': 'Mathematical Foundations',
        'B': 'AI Safety Systems',
        'C': 'Distributed Consensus',
        'D': 'World Models / Training',
        'E': 'Post-Quantum Cryptography',
        'F': 'Smart Home',
        'G': 'Voice / Audio',
        'H': 'Economic / Autonomous',
        'I': 'Platform / Architecture',
        'J': 'Reasoning / Cognition',
        'K': 'Visualization / Media'
    };
    return names[cat] || 'Unknown';
}

// Combine all patents into a single frozen array (no mutation)
export const PATENTS = Object.freeze([...P1_P2_PATENTS, ...P3_PATENTS]);

// ═══════════════════════════════════════════════════════════════════════════
// INFO PANEL CLASS
// ═══════════════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════════════
// GLOSSARY — hover-tooltip definitions for technical terms
// ═══════════════════════════════════════════════════════════════════════════

const GLOSSARY = {
    'EFE': 'Expected Free Energy — a decision metric from active inference that balances exploration (information gain) with exploitation (goal achievement).',
    'CBF': 'Control Barrier Function — a mathematical function h(x) that guarantees safety: if h(x) ≥ 0, the system is in a safe state.',
    'RSSM': 'Recurrent State-Space Model — a neural architecture that maintains a latent world model, predicting future states from past observations.',
    'Fano plane': 'The smallest finite projective plane: 7 points and 7 lines, where every line contains 3 points and every point lies on 3 lines.',
    'E8': 'The largest exceptional simple Lie group, with 248 dimensions and 240 root vectors forming the densest lattice packing in 8 dimensions.',
    'S15': 'The 15-dimensional sphere — a high-dimensional manifold used for encoding rich state representations via Hopf fibration.',
    'Hopf fibration': 'A way to decompose a higher-dimensional sphere into a base sphere and fiber circles, revealing hidden structure in state spaces.',
    'Lie algebra': 'The tangent space at the identity of a Lie group, capturing infinitesimal symmetries and used for smooth state evolution.',
    'Kyber': 'ML-KEM (Kyber) — a post-quantum key encapsulation mechanism based on lattice problems, standardized by NIST.',
    'AES-256-GCM': 'Advanced Encryption Standard with 256-bit keys in Galois/Counter Mode — authenticated encryption providing both confidentiality and integrity.',
    'Byzantine fault': 'A failure mode where a node can behave arbitrarily (including maliciously), not just crash. BFT systems tolerate up to f < n/3 such faults.',
    'CRDT': 'Conflict-free Replicated Data Type — a data structure that can be replicated across multiple nodes and merged without conflicts.',
    'KAN': 'Kolmogorov-Arnold Network — a neural network architecture based on the Kolmogorov-Arnold representation theorem, using learnable spline functions.',
    'catastrophe theory': 'A branch of mathematics studying how small changes in parameters can cause sudden qualitative changes in system behavior (folds, cusps, etc.).',
    'zero-knowledge proof': 'A cryptographic protocol where one party proves knowledge of a secret without revealing the secret itself.',
    'HRTF': 'Head-Related Transfer Function — describes how sound is filtered by the shape of the head and ears, enabling 3D audio perception.',
    'QP': 'Quadratic Programming — an optimization technique for minimizing a quadratic objective subject to linear constraints.',
    'active inference': 'A framework where agents minimize expected free energy by both acting on and perceiving their environment, unifying perception, learning, and action.',
    'h(x) ≥ 0': 'The safety invariant: the barrier function h(x) must remain non-negative at all times, ensuring the system stays within its safe operating region.',
    'equivariant': 'A function or network that preserves symmetry: transforming the input and then applying the function gives the same result as applying the function first.',
    'G2': 'The smallest exceptional Lie group (14-dimensional), which is the automorphism group of the octonions.',
    'F4': 'An exceptional Lie group with 52 dimensions, related to Jordan algebras and self-dual cone optimization.',
    'octonions': 'An 8-dimensional non-associative division algebra — the last of the normed division algebras (reals, complex, quaternions, octonions).',
    'Monte Carlo': 'A computational technique using random sampling to estimate quantities that are difficult to compute analytically.',
    'EFE-CBF': 'The combined framework where Expected Free Energy drives decision-making while Control Barrier Functions guarantee safety constraints.'
};

// ═══════════════════════════════════════════════════════════════════════════
// REAL-WORLD EXAMPLES — one per patent
// ═══════════════════════════════════════════════════════════════════════════

const REAL_WORLD_EXAMPLES = {
    'P1-001': 'A smart home assistant that can explore new ways to help you but is mathematically guaranteed never to take unsafe actions — like a self-driving car that can learn new routes but provably won\'t cross a red light.',
    'P1-002': 'Seven specialized AI modules vote on decisions using a geometry that guarantees fairness — even if two modules malfunction, the remaining five reach correct consensus.',
    'P1-003': 'When you say "dim the lights and play jazz," the system routes your intent through 8-dimensional space to find the closest match among hundreds of possible skills, instantly.',
    'P1-004': 'The AI\'s complete mental state is encoded on a high-dimensional sphere, where each of seven specialized subsystems occupies its own "fiber" — think of it as seven radio stations on one carrier wave.',
    'P1-005': 'An AI that literally dreams — replaying past experiences during downtime to refine its world model, so it wakes up smarter about your home, your schedule, and your preferences.',
    'P1-006': 'Your data is protected by TWO layers of encryption: one that\'s secure against today\'s hackers, and one that\'s secure against tomorrow\'s quantum computers. Belt and suspenders.',
    'P2-A4': 'Neural networks that automatically respect the symmetries of physical laws — if you rotate a molecule, the network\'s prediction rotates perfectly with it.',
    'P2-A5': 'Belief states are encoded in a space where the mathematical symmetries of E7 are preserved, making inference more efficient and geometrically natural.',
    'P2-A6': 'Optimization on self-dual cones: think of it as finding the best answer in a space where "good" and "bad" are perfect mirrors of each other.',
    'P2-B2': 'Three nested safety rings: the outer ring warns ("approaching boundary"), the middle ring slows ("reducing speed"), the inner ring stops ("full halt"). No panic, just graduated grace.',
    'P2-B3': 'Content enters through a WildGuard classifier (is this request harmful?), then passes through a mathematical barrier function (is the response provably safe?).',
    'P2-C2': 'Two smart home hubs in different rooms can independently accept commands and automatically sync state — no conflicts, no data loss, even if WiFi drops.',
    'P2-C3': 'When your home network splits (basement vs. upstairs), both halves keep working independently. When they reconnect, they smoothly merge state without losing anything.',
    'P2-D2': 'Detects when an AI model is about to undergo a sudden behavioral shift (like a bridge about to buckle) and intervenes before the catastrophe happens.',
    'P2-D3': 'Training an AI through 14 carefully designed phases — like a martial arts belt system, each phase builds on the last, from basic perception to complex reasoning.',
    'P2-D4': 'Three search strategies (tree search, game theory, and free energy) combined into one: the AI picks the best approach for each decision automatically.',
    'P2-E2': 'Encryption keys that only work in the right context — a key generated for "store my medical data" literally cannot decrypt "read my medical data" without explicit permission.',
    'P2-F1': 'Real-time audio analysis that decomposes sound into frequencies and maps them to light behaviors — your room literally dances to the music.',
    'P2-F2': 'Lights that respond to music in real-time: bass makes the floor glow warm, treble sparkles the ceiling, and the beat syncs the pulse of every bulb.',
    'P2-G1': 'Distinct sounds for every action — a gentle chime when lights adjust, a warm tone when temperature changes, a crisp click for confirmations. Eyes-free feedback.',
    'P2-H1': 'An AI that autonomously bids on freelance jobs: it evaluates risk, estimates effort, prices competitively, and manages multiple concurrent contracts.',
    'P2-H2': 'Every economic decision is scored by Expected Free Energy — balancing expected revenue against risk and information gain, like a financial advisor that uses physics.',
    'P2-I1': 'Events flow through 248 channels organized by the E8 lattice — each event type finds its natural channel, enabling O(1) routing to the right handler.',
    'P2-I2': 'Six independent judges evaluate every output across correctness, safety, privacy, craft, performance, and alignment. All must score ≥90/100 or the output is rejected.'
};

// ═══════════════════════════════════════════════════════════════════════════
// EDUCATIONAL PANELS — "What You're Looking At" + "Try This" + "Go Deeper"
// One per P1 exhibit. Feynman-level accessible, factually verified.
// ═══════════════════════════════════════════════════════════════════════════

export const EDUCATIONAL_CONTENT = {
    'P1-001': {
        whatYoureLookingAt: 'A safety landscape — the colored terrain shows how safe or dangerous different states are. Green peaks are safe zones where h(x) > 0. Red valleys are danger zones. The dome around you changes color to match.',
        tryThis: [
            'Click anywhere on the landscape to place an agent and watch it seek safety',
            'Walk close to a red zone — feel the dome shift from green to amber to red',
            'Find the hidden optimum at the center of the landscape (the safest possible point)'
        ],
        goDeeper: 'A Control Barrier Function h(x) defines a "force field" around unsafe states. If h(x) ≥ 0, the system is safe. The CBF-QP (Quadratic Program) finds the closest safe action to what the agent wants to do: min ||u − u_desired||² subject to the constraint that h(x) can never decrease below zero. Combined with Expected Free Energy (EFE), the agent balances curiosity and goal-seeking while provably staying safe. This is not a heuristic — it is a mathematical guarantee under the assumptions of Lipschitz continuity and bounded disturbances.',
        realWorldAnalogy: 'Imagine a self-driving car approaching a crosswalk. The barrier function defines an invisible boundary around every pedestrian. The car can optimize its route however it wants, but the math guarantees it will never cross that boundary — even if a pedestrian steps out suddenly.',
        factCheck: 'CBF safety guarantee h(x(t)) ≥ 0 ∀t holds under continuous-time control with correct system model. In discrete implementations, additional margins are needed. The EFE "catastrophe" term shown is a Kagami-specific extension beyond standard active inference.'
    },
    'P1-002': {
        whatYoureLookingAt: 'Seven voting stations arranged on a Fano plane — the smallest perfect geometry where every group of 3 shares exactly one communication line. The colonies vote, and even if 2 are lying, the truth emerges.',
        tryThis: [
            'Click any colony node to cast a vote (toggles approve/reject)',
            'Press the "Attack" button to become a Byzantine attacker controlling 2 nodes',
            'Watch the message particles flow along the Fano lines during consensus rounds'
        ],
        goDeeper: 'Byzantine Fault Tolerance (BFT) solves the oldest problem in distributed computing: how can honest nodes agree when some nodes may lie? The answer: you need n ≥ 3f + 1 total nodes to tolerate f Byzantine faults. With 7 nodes, we tolerate f = 2 faults (since 7 ≥ 3×2+1). Consensus requires ⌈7 × 2/3⌉ = 5 agreeing votes. The Fano plane topology is optimal because every pair of nodes shares at least one communication line (3 nodes per line, 3 lines per node), minimizing message complexity.',
        realWorldAnalogy: 'The Byzantine Generals Problem: seven generals must coordinate an attack, but two might be traitors sending conflicting messages. The Fano communication structure lets the five honest generals detect and exclude the liars by cross-checking messages along shared lines.',
        factCheck: 'The Fano plane structure (7 points, 7 lines, 3 per line, 3 per point) is mathematically exact. BFT threshold n ≥ 3f+1 is the proven lower bound (Lamport, Shostak, Pease 1982). With n=7, f=2 is the maximum tolerable fault count.'
    },
    'P1-003': {
        whatYoureLookingAt: 'A crystal in 8 dimensions, projected into 3D. Each glowing node is one of 240 root vectors of the E8 lattice — the densest possible sphere packing in 8 dimensions. Meaning flows through the lattice like electricity through a circuit.',
        tryThis: [
            'Click any node to see its 8D coordinates and connections',
            'Type a word or phrase to watch it get routed through the lattice as a semantic query',
            'Compare the lattice comparison panel: see how E8 (240 neighbors) dwarfs simpler lattices'
        ],
        goDeeper: 'E8 is the largest exceptional simple Lie group. Its root system has 240 vectors in 8 dimensions: 112 from permutations of (±1, ±1, 0, 0, 0, 0, 0, 0) and 128 from (±½)⁸ with an even number of minus signs. The kissing number is 240 — each point touches exactly 240 neighbors, the maximum possible in 8D (proved by Viazovska, 2016 Fields Medal). For semantic routing, text is embedded into 8D space, and the nearest E8 root determines which colony handles the query — like a switchboard with 240 perfectly positioned operators.',
        realWorldAnalogy: 'When you say "dim the lights and play jazz," your words become a point in 8-dimensional meaning-space. The E8 lattice instantly finds the nearest root vector — which maps to the colony best equipped to handle your request. It\'s like GPS for meaning.',
        factCheck: 'E8 root count (240), kissing number (240), and packing density (π⁴/384) are exact. Viazovska\'s 2016 proof confirmed E8 gives the densest sphere packing in 8D. The D8 definition (even-sum integer vectors) is standard. The semantic routing uses a toy embedding, not a learned model.'
    },
    'P1-004': {
        whatYoureLookingAt: 'The octonionic Hopf fibration: a 15-dimensional sphere decomposed into a base sphere (S⁸) threaded by seven fiber loops (S⁷). Each colored tube is one fiber — one colony\'s contribution to the whole. Click a fiber to ride it.',
        tryThis: [
            'Click any colored fiber tube to take a "fiber ride" — your camera follows the loop',
            'Watch the S¹⁵ coordinates update in real-time as you ride',
            'Ride all 7 fibers to unlock the achievement'
        ],
        goDeeper: 'There are exactly four Hopf fibrations in mathematics: S¹→S¹ (real), S¹→S³→S² (complex), S³→S⁷→S⁴ (quaternionic), and S⁷→S¹⁵→S⁸ (octonionic). The last one uses octonions — the largest normed division algebra, which is non-commutative AND non-associative: (a×b)×c ≠ a×(b×c). The fibration projects 15D state space onto an 8D base, with 7D fiber structure preserving the colony decomposition. Each colony occupies one "fiber direction," and the total state is their composition on S¹⁵.',
        realWorldAnalogy: 'Think of seven radio stations broadcasting on one carrier wave. Each station (colony) has its own frequency (fiber), but they all combine into one signal (the 15-sphere). The Hopf fibration is the math that lets you tune into any station without interference.',
        factCheck: 'The four Hopf fibrations (S⁰→S¹→S¹, S¹→S³→S², S³→S⁷→S⁴, S⁷→S¹⁵→S⁸) are the only ones that exist (Adams, 1960). Octonions are indeed the last normed division algebra (Hurwitz theorem). Non-associativity is correctly demonstrated. The 3D visualization is a projection from 15D — necessarily lossy but topologically faithful.'
    },
    'P1-005': {
        whatYoureLookingAt: 'A living world model — seven colonies processing information in parallel. The top half shows deterministic state (what the model knows), the bottom shows stochastic state (what it\'s uncertain about). The gap between prediction and observation is the KL divergence.',
        tryThis: [
            'Click any colony node to highlight its hidden state and attention connections',
            'Stand near the exhibit for 5 seconds to trigger a "dream sequence" — watch the model imagine without observations',
            'Watch the prior/posterior bars diverge when the model is surprised'
        ],
        goDeeper: 'The Recurrent State-Space Model (RSSM, from DreamerV3 by Hafner et al.) maintains two state representations: a deterministic hidden state h_t computed by a GRU, and a stochastic latent z_t sampled from a categorical distribution. The prior p(z_t|h_t) is the model\'s prediction; the posterior q(z_t|h_t,o_t) incorporates observations. The KL divergence KL(q‖p) = Σ q_k log(q_k/p_k) measures surprise. During imagination, the model rolls forward using only priors — no observations needed — enabling planning through dreaming.',
        realWorldAnalogy: 'Your brain constantly predicts what happens next — "the coffee cup is where I left it, the door will be locked." When reality matches prediction (low KL divergence), you barely notice. When it doesn\'t (the cup is gone!), you pay attention. This model does the same.',
        factCheck: 'RSSM architecture matches DreamerV3 (Hafner et al., 2023). KL divergence formula for categorical distributions is standard. The dual loss with stop-gradients (α_dyn·KL(sg(q)‖p) + α_rep·KL(q‖sg(p))) is correctly attributed to DreamerV3. The "Lie algebra" claim in the description is aspirational — the current visualization shows GRU dynamics, not Lie algebra evolution.'
    },
    'P1-006': {
        whatYoureLookingAt: 'A real encryption demonstration. The classical channel (AES-256-GCM) and quantum-safe channel (ML-KEM/Kyber) combine into hybrid encryption. The left terminal is Alice, the right is Bob. The data packets flowing between them are actual encrypted bytes.',
        tryThis: [
            'Click anywhere to encrypt a message with real AES-256-GCM via WebCrypto',
            'Watch the ciphertext appear — it\'s genuinely encrypted, not simulated',
            'Observe the key exchange beam showing how Alice and Bob establish shared secrets'
        ],
        goDeeper: 'Shor\'s algorithm can break RSA and elliptic curve cryptography on a quantum computer. Grover\'s algorithm halves the effective security of symmetric ciphers (AES-256 drops to ~128-bit equivalent, still considered secure). ML-KEM (formerly Kyber), standardized by NIST in 2024, uses the Learning With Errors (LWE) problem on polynomial rings R_q = Z_q[X]/(X^n+1) with n=256, q=3329. Hybrid encryption combines classical (AES-256-GCM) with post-quantum (ML-KEM) so that breaking the system requires defeating BOTH — belt and suspenders against an unknown future.',
        realWorldAnalogy: 'Today\'s encryption is like a safe with one lock. A quantum computer is a new kind of lockpick. Hybrid encryption adds a second lock of a completely different type — even if the quantum lockpick defeats lock #1, lock #2 (based on lattice math) remains secure.',
        factCheck: 'ML-KEM (Kyber) was standardized in FIPS 203 (August 2024). AES-256 under Grover\'s attack has ~128-bit equivalent security (square root of keyspace). The polynomial ring R_q parameters (n=256, q=3329) are correct for Kyber-768. The WebCrypto AES-256-GCM demo uses real browser APIs — the encryption is genuine.'
    }
};

export class InfoPanel {
    constructor() {
        this.element = null;
        this.isVisible = false;
        this.currentPatent = null;
        this.expertMode = false;  // false = beginner, true = expert
        
        this.create();
    }
    
    create() {
        this.element = document.createElement('div');
        this.element.id = 'info-panel';
        this.element.className = 'info-panel';
        this.element.setAttribute('role', 'dialog');
        this.element.setAttribute('aria-label', 'Patent Details');
        this.element.setAttribute('tabindex', '-1');
        this.element.innerHTML = `
            <button class="info-panel-close" aria-label="Close panel">×</button>
            <div class="info-panel-content">
                <div class="patent-header">
                    <span class="patent-priority"></span>
                    <span class="patent-category"></span>
                    <button class="detail-toggle" aria-label="Toggle detail level" title="Switch beginner/expert view">
                        <span class="toggle-label">Beginner</span>
                    </button>
                </div>
                <h2 class="patent-title"></h2>
                <p class="patent-description"></p>
                <div class="real-world-example" style="display:none">
                    <h3>In Plain English</h3>
                    <p class="example-text"></p>
                </div>
                <div class="educational-section" style="display:none">
                    <div class="edu-what">
                        <h3>What You're Looking At</h3>
                        <p class="edu-what-text"></p>
                    </div>
                    <div class="edu-try">
                        <h3>Try This</h3>
                        <ul class="edu-try-list"></ul>
                    </div>
                    <div class="edu-analogy">
                        <h3>Real-World Analogy</h3>
                        <p class="edu-analogy-text"></p>
                    </div>
                    <details class="edu-deeper">
                        <summary>Go Deeper (Expert)</summary>
                        <p class="edu-deeper-text"></p>
                    </details>
                    <details class="edu-factcheck">
                        <summary>Fact Check</summary>
                        <p class="edu-factcheck-text"></p>
                    </details>
                </div>
                <div class="patent-meta">
                    <div class="meta-item">
                        <span class="meta-label">Invented</span>
                        <span class="meta-value patent-date"></span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Novelty</span>
                        <span class="meta-value patent-novelty"></span>
                    </div>
                    <div class="meta-item">
                        <span class="meta-label">Colony</span>
                        <span class="meta-value patent-colony"></span>
                    </div>
                </div>
                <div class="patent-features">
                    <h3>Key Features</h3>
                    <ul class="features-list"></ul>
                </div>
                <div class="patent-actions">
                    <button class="action-btn" data-action="code">View Code</button>
                    <button class="action-btn" data-action="prior-art">Prior Art</button>
                    <button class="action-btn" data-action="demo">Interactive Demo</button>
                    <button class="action-btn action-btn-secondary" data-action="export-journey">Export my journey</button>
                </div>
            </div>
            <div class="glossary-tooltip" style="display:none" role="tooltip"></div>
        `;
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            .info-panel {
                position: fixed;
                right: -450px;
                top: 0;
                width: 450px;
                height: 100%;
                background: rgba(7, 6, 11, 0.92);
                backdrop-filter: blur(20px);
                -webkit-backdrop-filter: blur(20px);
                border-left: 1px solid rgba(103, 212, 228, 0.2);
                z-index: 3000;
                transition: right 0.377s cubic-bezier(0.16, 1, 0.3, 1), 
                            opacity 0.233s ease;
                overflow-y: auto;
                font-family: 'IBM Plex Sans', sans-serif;
                box-shadow: -8px 0 32px rgba(0, 0, 0, 0.4);
            }
            
            .info-panel.visible {
                right: 0;
                opacity: 1;
            }
            
            .info-panel-close {
                position: absolute;
                top: 20px;
                right: 20px;
                width: 44px;
                height: 44px;
                background: transparent;
                border: 1px solid rgba(103, 212, 228, 0.3);
                border-radius: 50%;
                color: #9E9994;
                font-size: 24px;
                cursor: pointer;
                transition: all 0.144s ease;
            }
            
            .info-panel-close:hover {
                border-color: #67D4E4;
                color: #67D4E4;
                transform: scale(1.1);
            }
            
            .info-panel-close:active {
                transform: scale(0.95);
            }
            
            .info-panel-close:focus-visible {
                outline: 2px solid #67D4E4;
                outline-offset: 2px;
            }
            
            .info-panel-content {
                padding: 80px 32px 32px;
            }
            
            .patent-header {
                display: flex;
                gap: 12px;
                margin-bottom: 16px;
            }
            
            .patent-priority {
                display: inline-block;
                padding: 4px 12px;
                border-radius: 4px;
                font-family: 'IBM Plex Mono', monospace;
                font-size: 12px;
                font-weight: 600;
            }
            
            .patent-priority.P1 {
                background: rgba(255, 215, 0, 0.2);
                color: #FFD700;
                border: 1px solid rgba(255, 215, 0, 0.5);
            }
            
            .patent-priority.P2 {
                background: rgba(103, 212, 228, 0.2);
                color: #67D4E4;
                border: 1px solid rgba(103, 212, 228, 0.5);
            }
            
            .patent-priority.P3 {
                background: rgba(158, 153, 148, 0.2);
                color: #9E9994;
                border: 1px solid rgba(158, 153, 148, 0.5);
            }
            
            .patent-category {
                color: #9E9994;
                font-size: 12px;
                padding: 4px 0;
            }
            
            .patent-title {
                font-family: 'Orbitron', sans-serif;
                font-size: 24px;
                font-weight: 600;
                color: #F5F0E8;
                margin-bottom: 16px;
                line-height: 1.3;
            }
            
            .patent-description {
                color: #C4BFBA;
                font-size: 16px;
                line-height: 1.6;
                margin-bottom: 24px;
            }
            
            .patent-meta {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 16px;
                margin-bottom: 32px;
                padding: 16px;
                background: rgba(18, 16, 26, 0.5);
                border-radius: 8px;
            }
            
            .meta-item {
                text-align: center;
            }
            
            .meta-label {
                display: block;
                font-size: 11px;
                color: #8A8580;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 4px;
            }
            
            .meta-value {
                font-family: 'IBM Plex Mono', monospace;
                font-size: 14px;
                color: #F5F0E8;
            }
            
            .patent-novelty {
                color: #FFD700 !important;
            }
            
            .patent-features h3 {
                font-size: 14px;
                color: #67D4E4;
                margin-bottom: 12px;
                text-transform: uppercase;
                letter-spacing: 0.1em;
            }
            
            .features-list {
                list-style: none;
                padding: 0;
                margin: 0 0 32px;
            }
            
            .features-list li {
                position: relative;
                padding: 8px 0 8px 24px;
                color: #C4BFBA;
                font-size: 14px;
                border-bottom: 1px solid rgba(103, 212, 228, 0.1);
            }
            
            .features-list li::before {
                content: '◆';
                position: absolute;
                left: 0;
                color: #67D4E4;
                font-size: 10px;
            }
            
            /* Educational sections */
            .educational-section {
                margin-bottom: 24px;
            }
            
            .educational-section h3 {
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 13px;
                font-weight: 600;
                color: #67D4E4;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 8px;
            }
            
            .edu-what, .edu-try, .edu-analogy {
                margin-bottom: 20px;
            }
            
            .edu-what-text, .edu-analogy-text {
                color: #C4BFBA;
                font-size: 14px;
                line-height: 1.6;
            }
            
            .edu-try-list {
                list-style: none;
                padding: 0;
                margin: 0;
            }
            
            .edu-try-list li {
                padding: 6px 0 6px 24px;
                color: #F5F0E8;
                font-size: 14px;
                position: relative;
            }
            
            .edu-try-list li::before {
                content: '▸';
                position: absolute;
                left: 4px;
                color: #F59E0B;
                font-size: 12px;
            }
            
            .edu-deeper, .edu-factcheck {
                margin-bottom: 12px;
                border: 1px solid rgba(103, 212, 228, 0.15);
                border-radius: 8px;
                padding: 0;
            }
            
            .edu-deeper summary, .edu-factcheck summary {
                padding: 10px 16px;
                font-family: 'IBM Plex Mono', monospace;
                font-size: 12px;
                color: #9E9994;
                cursor: pointer;
                letter-spacing: 0.05em;
            }
            
            .edu-deeper summary:hover, .edu-factcheck summary:hover {
                color: #67D4E4;
            }
            
            .edu-deeper-text, .edu-factcheck-text {
                padding: 0 16px 16px;
                color: #9E9994;
                font-size: 13px;
                line-height: 1.6;
            }
            
            .patent-actions {
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
            }
            
            .action-btn {
                flex: 1;
                min-width: 120px;
                padding: 12px 16px;
                background: rgba(103, 212, 228, 0.1);
                border: 1px solid rgba(103, 212, 228, 0.3);
                border-radius: 8px;
                color: #67D4E4;
                font-family: 'IBM Plex Mono', monospace;
                font-size: 12px;
                cursor: pointer;
                transition: all 0.144s ease;
            }
            
            .action-btn:hover {
                background: rgba(103, 212, 228, 0.2);
                border-color: #67D4E4;
                transform: translateY(-1px);
                box-shadow: 0 0 20px rgba(103, 212, 228, 0.3);
            }
            
            .action-btn:active {
                transform: scale(0.98) translateY(0);
                background: rgba(103, 212, 228, 0.3);
            }
            
            .action-btn:focus-visible {
                outline: 2px solid #67D4E4;
                outline-offset: 2px;
                box-shadow: 0 0 40px rgba(103, 212, 228, 0.5);
            }
            
            /* Beginner/Expert toggle */
            .detail-toggle {
                margin-left: auto;
                padding: 4px 12px;
                background: rgba(103, 212, 228, 0.1);
                border: 1px solid rgba(103, 212, 228, 0.25);
                border-radius: 12px;
                color: #67D4E4;
                font-family: 'IBM Plex Mono', monospace;
                font-size: 11px;
                cursor: pointer;
                transition: all 0.144s ease;
            }
            .detail-toggle:hover {
                background: rgba(103, 212, 228, 0.2);
                border-color: #67D4E4;
            }
            .detail-toggle.expert {
                background: rgba(255, 215, 0, 0.15);
                border-color: rgba(255, 215, 0, 0.4);
                color: #FFD700;
            }
            
            /* Real-world example */
            .real-world-example {
                background: rgba(76, 255, 76, 0.05);
                border: 1px solid rgba(76, 255, 76, 0.15);
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 24px;
            }
            .real-world-example h3 {
                font-size: 12px;
                color: #4CFF4C;
                text-transform: uppercase;
                letter-spacing: 0.1em;
                margin-bottom: 8px;
            }
            .real-world-example .example-text {
                color: #C4BFBA;
                font-size: 14px;
                line-height: 1.6;
                margin: 0;
            }
            
            /* Glossary tooltip */
            .glossary-tooltip {
                position: fixed;
                max-width: 300px;
                padding: 12px 16px;
                background: rgba(18, 16, 26, 0.95);
                border: 1px solid rgba(103, 212, 228, 0.4);
                border-radius: 8px;
                color: #E0E0E0;
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 13px;
                line-height: 1.5;
                z-index: 4000;
                pointer-events: none;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5);
                transition: opacity 0.144s ease;
            }
            .glossary-tooltip .glossary-term {
                color: #67D4E4;
                font-family: 'IBM Plex Mono', monospace;
                font-weight: 600;
                font-size: 12px;
                display: block;
                margin-bottom: 4px;
            }
            
            /* Glossary-highlighted terms in text */
            .glossary-highlight {
                color: #67D4E4;
                border-bottom: 1px dotted rgba(103, 212, 228, 0.4);
                cursor: help;
            }

            .glossary-highlight:focus {
                outline: 2px solid #67D4E4;
                outline-offset: 2px;
                border-radius: 2px;
            }
            
            .action-btn-secondary {
                background: rgba(158, 153, 148, 0.1);
                border-color: rgba(158, 153, 148, 0.3);
                color: #9E9994;
            }
            .action-btn-secondary:hover {
                background: rgba(158, 153, 148, 0.2);
                border-color: #9E9994;
                box-shadow: 0 0 20px rgba(158, 153, 148, 0.2);
            }
            
            @media (max-width: 500px) {
                .info-panel {
                    width: 100%;
                    right: -100%;
                }
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(this.element);
        
        // Event listeners
        this.element.querySelector('.info-panel-close').addEventListener('click', () => this.hide());
        
        this.element.querySelectorAll('.action-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.target.dataset.action;
                this.handleAction(action);
            });
        });
        
        // Beginner/Expert toggle
        this.element.querySelector('.detail-toggle').addEventListener('click', () => {
            this.expertMode = !this.expertMode;
            const toggle = this.element.querySelector('.detail-toggle');
            toggle.classList.toggle('expert', this.expertMode);
            toggle.querySelector('.toggle-label').textContent = this.expertMode ? 'Expert' : 'Beginner';
            // Re-render current patent with new detail level
            if (this.currentPatent) this._updateDetailLevel();
        });
        
        // Glossary tooltip hover/focus handling
        const showTooltipFor = (target) => {
            const term = target.dataset.term;
            const def = GLOSSARY[term];
            if (!def) return;
            const tooltip = this.element.querySelector('.glossary-tooltip');
            tooltip.innerHTML = `<span class="glossary-term">${term}</span>${def}`;
            tooltip.style.display = 'block';
            const rect = target.getBoundingClientRect();
            tooltip.style.left = Math.min(rect.left, window.innerWidth - 320) + 'px';
            tooltip.style.top = (rect.bottom + 8) + 'px';
        };
        const hideTooltip = () => {
            this.element.querySelector('.glossary-tooltip').style.display = 'none';
        };

        this.element.addEventListener('mouseover', (e) => {
            const target = e.target.closest('.glossary-highlight');
            if (target) showTooltipFor(target);
        });
        this.element.addEventListener('mouseout', (e) => {
            if (!e.target.closest('.glossary-highlight')) hideTooltip();
        });
        // Keyboard accessibility: show tooltip on focus
        this.element.addEventListener('focusin', (e) => {
            const target = e.target.closest('.glossary-highlight');
            if (target) showTooltipFor(target);
        });
        this.element.addEventListener('focusout', (e) => {
            if (e.target.closest('.glossary-highlight')) hideTooltip();
        });
        
        // Close on Escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isVisible) {
                this.hide();
            }
        });

        // Focus trap for dialog
        this.element.addEventListener('keydown', (e) => {
            if (e.key !== 'Tab') return;
            const focusable = this.element.querySelectorAll('button, [tabindex]:not([tabindex="-1"]), input, a[href]');
            if (focusable.length === 0) return;
            const first = focusable[0];
            const last = focusable[focusable.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        });
    }
    
    show(patentId) {
        const patent = PATENTS.find(p => p.id === patentId);
        if (!patent) return;
        
        this.currentPatent = patent;
        
        // Update content
        const el = this.element;
        el.querySelector('.patent-priority').textContent = patent.priority;
        el.querySelector('.patent-priority').className = `patent-priority ${patent.priority}`;
        el.querySelector('.patent-category').textContent = patent.categoryName;
        el.querySelector('.patent-title').textContent = patent.name;
        
        // Description with glossary highlighting
        el.querySelector('.patent-description').innerHTML = this._highlightGlossaryTerms(patent.description);
        
        el.querySelector('.patent-date').textContent = patent.invented;
        el.querySelector('.patent-novelty').textContent = '★'.repeat(patent.novelty);
        el.querySelector('.patent-colony').textContent = patent.colony.charAt(0).toUpperCase() + patent.colony.slice(1);
        
        // Real-world example
        const exampleSection = el.querySelector('.real-world-example');
        const example = REAL_WORLD_EXAMPLES[patent.id];
        if (example) {
            exampleSection.style.display = 'block';
            exampleSection.querySelector('.example-text').textContent = example;
        } else {
            exampleSection.style.display = 'none';
        }
        
        // Update features list (safe DOM construction, with glossary)
        const featuresList = el.querySelector('.features-list');
        featuresList.innerHTML = '';
        for (const feature of (patent.keyFeatures || [])) {
            const li = document.createElement('li');
            li.innerHTML = this._highlightGlossaryTerms(feature);
            featuresList.appendChild(li);
        }
        
        // Educational content (P1 exhibits)
        const eduSection = el.querySelector('.educational-section');
        const edu = EDUCATIONAL_CONTENT[patent.id];
        if (edu) {
            eduSection.style.display = 'block';
            
            el.querySelector('.edu-what-text').innerHTML = this._highlightGlossaryTerms(edu.whatYoureLookingAt);
            
            const tryList = el.querySelector('.edu-try-list');
            tryList.innerHTML = '';
            for (const hint of (edu.tryThis || [])) {
                const li = document.createElement('li');
                li.textContent = hint;
                tryList.appendChild(li);
            }
            
            el.querySelector('.edu-analogy-text').innerHTML = this._highlightGlossaryTerms(edu.realWorldAnalogy);
            el.querySelector('.edu-deeper-text').innerHTML = this._highlightGlossaryTerms(edu.goDeeper);
            el.querySelector('.edu-factcheck-text').textContent = edu.factCheck;
        } else {
            eduSection.style.display = 'none';
        }
        
        // Apply detail level
        this._updateDetailLevel();
        
        // Show panel and move focus
        this.element.classList.add('visible');
        this.isVisible = true;
        this._previousFocus = document.activeElement;
        requestAnimationFrame(() => {
            this.element.querySelector('.info-panel-close').focus();
        });
    }
    
    /**
     * Highlight glossary terms in text with hover-able spans.
     * @param {string} text - Plain text to process.
     * @returns {string} HTML with glossary terms wrapped in spans.
     */
    _highlightGlossaryTerms(text) {
        if (!text) return '';
        let result = text;
        // Sort terms by length (longest first) to avoid partial matches
        const terms = Object.keys(GLOSSARY).sort((a, b) => b.length - a.length);
        for (const term of terms) {
            // Case-insensitive match, but only on word boundaries (rough)
            const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const regex = new RegExp(`(?<![<\\w])${escaped}(?![\\w>])`, 'gi');
            result = result.replace(regex, (match) =>
                `<span class="glossary-highlight" data-term="${term}" tabindex="0" role="button" aria-label="${term}: ${GLOSSARY[term].substring(0, 80)}...">${match}</span>`
            );
        }
        return result;
    }
    
    /**
     * Update visibility of sections based on beginner/expert mode.
     */
    _updateDetailLevel() {
        const el = this.element;
        const expert = this.expertMode;
        // In beginner mode: show real-world example prominently, show simpler features
        // In expert mode: show all technical details, hide simplified explanation
        const exampleSection = el.querySelector('.real-world-example');
        if (exampleSection && REAL_WORLD_EXAMPLES[this.currentPatent?.id]) {
            exampleSection.style.display = expert ? 'none' : 'block';
        }
        // Meta section: always visible in expert, collapsed in beginner
        const metaSection = el.querySelector('.patent-meta');
        if (metaSection) {
            metaSection.style.display = expert ? 'grid' : 'none';
        }
        // Features: always visible
        // Toggle label
        const toggle = el.querySelector('.detail-toggle');
        if (toggle) {
            toggle.querySelector('.toggle-label').textContent = expert ? 'Expert' : 'Beginner';
            toggle.classList.toggle('expert', expert);
        }
    }
    
    hide() {
        this.element.classList.remove('visible');
        this.isVisible = false;
        this.currentPatent = null;
        // Return focus to previously focused element
        if (this._previousFocus && this._previousFocus.focus) {
            this._previousFocus.focus();
        }
    }
    
    handleAction(action) {
        if (action === 'export-journey') {
            getVisitorIdentity().downloadJourney(PATENTS);
            this._showToast('Journey exported as Agent Data Pod (.ttl).');
            return;
        }
        if (!this.currentPatent) return;

        const patent = this.currentPatent;

        switch (action) {
            case 'code': {
                if (patent.file) {
                    const url = GITHUB_BASE + patent.file;
                    window.open(url, '_blank', 'noopener,noreferrer');
                    this._showToast('Opening source in new tab.');
                } else {
                    this._showToast('No code path for this patent.');
                }
                break;
            }
            case 'prior-art': {
                const query = encodeURIComponent(`${patent.name} ${patent.categoryName} research`);
                window.open(`https://scholar.google.com/scholar?q=${query}`, '_blank', 'noopener,noreferrer');
                this._showToast('Opening prior art search.');
                break;
            }
            case 'demo': {
                window.dispatchEvent(new CustomEvent('patent-demo', {
                    detail: { patentId: patent.id }
                }));
                this._showToast('Focusing exhibit in museum.');
                break;
            }
            default:
                this._showToast('Coming soon.');
        }
    }

    _showToast(message) {
        // Remove existing toast
        const existing = this.element.querySelector('.info-toast');
        if (existing) existing.remove();

        const toast = document.createElement('div');
        toast.className = 'info-toast';
        toast.textContent = message;
        toast.style.cssText = `
            position: absolute;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%) translateY(8px);
            background: rgba(103, 212, 228, 0.15);
            border: 1px solid rgba(103, 212, 228, 0.3);
            color: #C4BFBA;
            font-family: 'IBM Plex Sans', sans-serif;
            font-size: 13px;
            font-style: italic;
            padding: 10px 20px;
            border-radius: 8px;
            opacity: 0;
            transition: opacity 0.377s ease, transform 0.377s cubic-bezier(0.16, 1, 0.3, 1);
            pointer-events: none;
            white-space: nowrap;
        `;
        this.element.querySelector('.info-panel-content').appendChild(toast);

        requestAnimationFrame(() => {
            toast.style.opacity = '1';
            toast.style.transform = 'translateX(-50%) translateY(0)';
        });

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateX(-50%) translateY(-4px)';
            setTimeout(() => toast.remove(), 400);
        }, 2500);
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// GET PATENT BY ID
// ═══════════════════════════════════════════════════════════════════════════

export function getPatent(id) {
    return PATENTS.find(p => p.id === id);
}

export function getPatentsByCategory(category) {
    return PATENTS.filter(p => p.category === category);
}

export function getPatentsByPriority(priority) {
    return PATENTS.filter(p => p.priority === priority);
}

export function getPatentsByColony(colony) {
    return PATENTS.filter(p => p.colony === colony);
}


export default InfoPanel;
