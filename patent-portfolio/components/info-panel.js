/**
 * Info Panel Component
 * ====================
 * 
 * Full-screen or side panel for detailed artwork information.
 * Shows patent details, interactive demos, and documentation links.
 * 
 * h(x) ≥ 0 always
 */

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
      description: 'Neural convolutions that respect Weyl group reflection symmetries, preserving algebraic structure through every layer of computation.',
      keyFeatures: ['Weyl group symmetry preservation', 'Reflection-equivariant kernels'], novelty: 3 },
    { id: 'P3-A8', name: 'Octonion-Valued Neural Layers', category: 'A', colony: 'crystal',
      description: 'Eight-dimensional non-associative algebra meets neural computation — layers that think in octonions for richer geometric reasoning.',
      keyFeatures: ['Octonion multiplication layers', 'Non-associative gradient flow'], novelty: 3 },
    { id: 'P3-B4', name: 'Safety Reward Shaping', category: 'B', colony: 'crystal',
      description: 'Sculpting reward landscapes so the safest path is also the most rewarding — aligning incentives with barrier constraints.',
      keyFeatures: ['Barrier-aware reward potentials', 'Lyapunov-guided shaping'], novelty: 2 },
    { id: 'P3-B5', name: 'Constraint Violation Recovery', category: 'B', colony: 'crystal',
      description: 'When boundaries are breached, graceful recovery protocols restore safety invariants without catastrophic intervention.',
      keyFeatures: ['Soft recovery trajectories', 'Graduated rollback'], novelty: 2 },
    { id: 'P3-B6', name: 'Safe Exploration Bounds', category: 'B', colony: 'crystal',
      description: 'Curiosity within guardrails — computing the exact frontier of safe exploration before any action is taken.',
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

export class InfoPanel {
    constructor() {
        this.element = null;
        this.isVisible = false;
        this.currentPatent = null;
        
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
                </div>
                <h2 class="patent-title"></h2>
                <p class="patent-description"></p>
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
                </div>
            </div>
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
        el.querySelector('.patent-description').textContent = patent.description;
        el.querySelector('.patent-date').textContent = patent.invented;
        el.querySelector('.patent-novelty').textContent = '★'.repeat(patent.novelty);
        el.querySelector('.patent-colony').textContent = patent.colony.charAt(0).toUpperCase() + patent.colony.slice(1);
        
        // Update features list (safe DOM construction)
        const featuresList = el.querySelector('.features-list');
        featuresList.innerHTML = '';
        for (const feature of (patent.keyFeatures || [])) {
            const li = document.createElement('li');
            li.textContent = feature;
            featuresList.appendChild(li);
        }
        
        // Show panel and move focus
        this.element.classList.add('visible');
        this.isVisible = true;
        this._previousFocus = document.activeElement;
        requestAnimationFrame(() => {
            this.element.querySelector('.info-panel-close').focus();
        });
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
        if (!this.currentPatent) return;

        const messages = {
            code: 'Kagami is still weaving this view.',
            'prior-art': 'The research threads are being gathered.',
            demo: 'This demo is dreaming itself into existence.'
        };

        const msg = messages[action] || 'Coming soon.';
        this._showToast(msg);
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
