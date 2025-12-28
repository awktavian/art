/* ═══════════════════════════════════════════════════════════════════════════════════════════
   🏛️ THE HOUSE — Character & Room Data
   
   Maps Clue characters to Kagami colonies
   
═══════════════════════════════════════════════════════════════════════════════════════════ */

const CHARACTERS = {
    scarlet: {
        name: 'Miss Scarlet',
        colony: 'Spark',
        basis: 'e₁',
        catastrophe: 'Fold (A₂)',
        role: 'Creative Ideation',
        room: 'Conservatory',
        color: '#dc143c',
        quotes: [
            "I'm a woman—I like to be wooed.",
            "I enjoy getting presents from strange men.",
            "Well, someone's got to break the ice, and it might as well be me."
        ],
        essence: 'Effervescent, seductive, full of ideas. Ignites possibilities everywhere she goes.',
        code: 'kagami/core/unified_agents/agents/spark_agent.py',
        description: `Miss Scarlet IS Spark—the ignition point. Just as she opens the film with bold confidence, 
        Spark opens creative sessions with rapid ideation. She sees opportunities others miss, starts 
        conversations others won't, and isn't afraid to take the first step into unknown territory.
        
        The Fold catastrophe (A₂) is perfect: it's the simplest catastrophe, the moment of sudden ignition 
        at a threshold. One moment nothing, the next—an idea blazes to life.`
    },
    
    mustard: {
        name: 'Colonel Mustard',
        colony: 'Forge',
        basis: 'e₂',
        catastrophe: 'Cusp (A₃)',
        role: 'Implementation',
        room: 'Billiard Room',
        color: '#e6b800',
        quotes: [
            "War is hell.",
            "Is there a little boys' room in the hall?",
            "Whadya mean, the cook is dead?"
        ],
        essence: 'Military precision. Methodical building. Gets things done with discipline.',
        code: 'kagami/forge/',
        description: `Colonel Mustard IS Forge—the builder. His military background means he understands 
        construction, logistics, and the discipline needed to turn plans into reality. The Billiard Room 
        is perfect: it's a space of precision (exact angles, calculated shots) and competition.
        
        The Cusp catastrophe (A₃) captures Forge's nature: bistable decisions where you commit to one 
        path or another, with hysteresis preventing constant switching. Once Mustard decides to act, 
        he commits fully.`
    },
    
    white: {
        name: 'Mrs. White',
        colony: 'Flow',
        basis: 'e₃',
        catastrophe: 'Swallowtail (A₄)',
        role: 'Recovery & Debugging',
        room: 'Kitchen/Dining Room',
        color: '#f5f5f5',
        quotes: [
            "Flames... flames on the side of my face... breathing... heaving breaths...",
            "I hated her... SO much... it-it... flames...",
            "I didn't kill him, but I'm certainly not sorry he's dead."
        ],
        essence: 'Passionate about fixing things. Handles the mess when everything goes wrong.',
        code: 'kagami/flow/',
        description: `Mrs. White IS Flow—the recovery system. She's worked behind the scenes, dealt with 
        disasters, cleaned up messes, and survived catastrophic situations. Her famous "flames" speech 
        is the perfect embodiment of dealing with cascading failures while maintaining (barely) composure.
        
        The Swallowtail catastrophe (A₄) has multiple recovery paths—exactly like debugging, where you 
        might need to try several approaches before finding the fix. Mrs. White has been through enough 
        to know: there's always another way forward.`
    },
    
    green: {
        name: 'Mr. Green',
        colony: 'Nexus',
        basis: 'e₄',
        catastrophe: 'Butterfly (A₅)',
        role: 'Integration & Memory',
        room: 'Ballroom',
        color: '#228b22',
        quotes: [
            "I'm going to go home and sleep with my wife.",
            "I'm not shouting!",
            "I work for the State Department."
        ],
        essence: 'The secret agent who connects everything. Knows more than he lets on.',
        code: 'kagami/core/unified_agents/agents/nexus_agent.py',
        description: `Mr. Green IS Nexus—the hidden integrator. Like his revelation as an FBI agent, 
        Nexus quietly connects all the pieces while appearing to be just another part of the system. 
        The Ballroom is where everyone dances together, where connections form and reform.
        
        The Butterfly catastrophe (A₅) is the most complex of the A-series—a 4D manifold where small 
        changes cascade through multiple connected systems. That's exactly what integration does: 
        a change in one component ripples through everything it connects to.`
    },
    
    plum: {
        name: 'Professor Plum',
        colony: 'Beacon',
        basis: 'e₅',
        catastrophe: 'Hyperbolic (D₄⁺)',
        role: 'Architecture & Planning',
        room: 'Study',
        color: '#8e4585',
        quotes: [
            "I work for UNO, the United Nations Organization.",
            "What are you afraid of? A fate worse than death?",
            "Mrs. Peacock was a man?!"
        ],
        essence: 'Intellectual, strategic. Always has a theory about how things should work.',
        code: 'kagami/core/unified_agents/agents/beacon_agent.py',
        description: `Professor Plum IS Beacon—the architect. His academic background and theoretical 
        orientation make him perfect for planning and strategic thinking. The Study is where plans 
        are made, where intelligence is analyzed, where the big picture comes together.
        
        The Hyperbolic catastrophe (D₄⁺) splits outward—representing how good architecture radiates 
        influence across the entire system. One well-designed abstraction affects everything.`
    },
    
    peacock: {
        name: 'Mrs. Peacock',
        colony: 'Crystal',
        basis: 'e₇',
        catastrophe: 'Parabolic (D₅)',
        role: 'Verification & Testing',
        room: 'Lounge',
        color: '#00ced1',
        quotes: [
            "This is absolutely contemptible!",
            "Everything I've done, I've done for my country.",
            "I had to stop her from giving us all away."
        ],
        essence: 'Proper, judgmental. Verifies that everything meets the standard.',
        code: 'kagami/crystal/',
        description: `Mrs. Peacock IS Crystal—the verifier. Her sense of propriety and judgment make 
        her perfect for testing and verification. "This is absolutely contemptible!" is exactly what 
        Crystal says when h(x) < 0. The Lounge is formal, proper—a place where standards matter.
        
        The Parabolic catastrophe (D₅) is about boundary detection—knowing exactly where the edge is. 
        That's testing in a nutshell: finding where the system stops working correctly.`
    },
    
    motorist: {
        name: 'The Motorist',
        colony: 'Grove',
        basis: 'e₆',
        catastrophe: 'Elliptic (D₄⁻)',
        role: 'Research & Exploration',
        room: 'Library',
        color: '#2d5a27',
        quotes: [
            "Could I have some water?",
            "Where is everybody?",
            "No thank you, I just had dinner."
        ],
        essence: 'Always seeking, always researching. Finds more than expected.',
        code: 'kagami/grove/',
        description: `The Motorist IS Grove—the researcher. He arrives seeking something simple (water) 
        but stumbles into something vastly more complex. That's research: you go looking for one thing 
        and discover entire worlds. The Library holds all knowledge, waiting to be explored.
        
        The Elliptic catastrophe (D₄⁻) converges inward—representing how research narrows down from 
        broad exploration to specific discoveries. The Motorist's journey from "lost driver" to 
        "witness to everything" mirrors the research process perfectly.`
    },
    
    wadsworth: {
        name: 'Wadsworth',
        colony: 'Kagami',
        basis: 'e₀',
        catastrophe: 'The Observer',
        role: 'Orchestration',
        room: 'The Hall',
        color: '#c9a227',
        quotes: [
            "I'm the butler. I buttle.",
            "Let me explain... No, there is too much. Let me sum up.",
            "One plus one plus two plus one...",
            "Ladies and gentlemen, you all have one thing in common.",
            "To make a long story short—" "Too late."
        ],
        essence: 'The butler who knows everything. Routes, coordinates, observes all.',
        code: 'CLAUDE.md',
        description: `Wadsworth IS Kagami—the orchestrator. He knows everything, coordinates everyone, 
        and in the end reveals how all the pieces fit together. e₀ is the real component of the 
        octonion—the observer that gives coherence to the seven imaginary units.
        
        The Hall is the center of the mansion, where all paths cross and all movements are visible. 
        Wadsworth sees all traffic, knows all secrets, and ultimately reveals the truth.
        
        "One plus one plus two plus one..." is the counting that reveals the pattern. That's what 
        Kagami does: finds the pattern in the chaos.`
    }
};

const ROOMS = {
    conservatory: {
        name: 'The Conservatory',
        character: 'scarlet',
        colony: 'spark',
        icon: '🔥',
        floor: 2,
        description: 'Where new ideas bloom like exotic plants. Creative ideation happens here.',
        function: 'Brainstorming, ideation, creative exploration',
        codePath: 'kagami/core/unified_agents/agents/spark_agent.py'
    },
    billiard: {
        name: 'The Billiard Room',
        character: 'mustard',
        colony: 'forge',
        icon: '⚒️',
        floor: 1,
        description: 'Precision and calculated execution. Where plans become reality.',
        function: 'Implementation, construction, code production',
        codePath: 'kagami/forge/'
    },
    kitchen: {
        name: 'The Kitchen',
        character: 'white',
        colony: 'flow',
        icon: '🍳',
        floor: 1,
        description: 'Behind the scenes work. Where the real labor happens.',
        function: 'Background processing, maintenance, cleanup',
        codePath: 'kagami/flow/'
    },
    dining: {
        name: 'The Dining Room',
        character: 'white',
        colony: 'flow',
        icon: '🌊',
        floor: 1,
        description: 'Where disasters are served. Recovery happens here.',
        function: 'Debugging, error handling, system recovery',
        codePath: 'kagami/core/unified_agents/agents/flow_agent.py'
    },
    ballroom: {
        name: 'The Ballroom',
        character: 'green',
        colony: 'nexus',
        icon: '🔗',
        floor: 1,
        description: 'Where everyone dances together. Connections form here.',
        function: 'Integration, memory, cross-system coordination',
        codePath: 'kagami/core/unified_agents/agents/nexus_agent.py'
    },
    study: {
        name: 'The Study',
        character: 'plum',
        colony: 'beacon',
        icon: '🗼',
        floor: 2,
        description: 'Where plans are made. Strategic thinking happens here.',
        function: 'Architecture, planning, system design',
        codePath: 'kagami/core/unified_agents/agents/beacon_agent.py'
    },
    library: {
        name: 'The Library',
        character: 'motorist',
        colony: 'grove',
        icon: '🌿',
        floor: 2,
        description: 'All knowledge awaits. Research and exploration happen here.',
        function: 'Research, documentation, knowledge gathering',
        codePath: 'kagami/grove/'
    },
    lounge: {
        name: 'The Lounge',
        character: 'peacock',
        colony: 'crystal',
        icon: '💎',
        floor: 1,
        description: 'Where standards are enforced. Verification happens here.',
        function: 'Testing, verification, quality assurance',
        codePath: 'kagami/crystal/'
    },
    hall: {
        name: 'The Hall',
        character: 'wadsworth',
        colony: 'kagami',
        icon: '🏛️',
        floor: 1,
        description: 'The center of everything. All paths cross here.',
        function: 'Routing, coordination, orchestration',
        codePath: 'CLAUDE.md'
    },
    attic: {
        name: 'The Attic',
        colony: 'world_model',
        icon: '🔮',
        description: 'Where the future is predicted. The World Model lives here.',
        function: 'Prediction, simulation, trajectory planning',
        codePath: 'kagami/core/world_model/'
    },
    basement: {
        name: 'The Basement',
        colony: 'math',
        icon: '🔬',
        description: 'Where the bodies are buried... mathematically.',
        function: 'E8 lattice, Fano plane, octonions, catastrophe theory',
        codePath: 'kagami/math/'
    },
    walls: {
        name: 'The Walls',
        colony: 'safety',
        icon: '🧱',
        description: 'What keeps the danger out. h(x) ≥ 0, always.',
        function: 'Safety barriers, CBF, constraint enforcement',
        codePath: 'kagami/core/safety/'
    }
};

const SECRET_PASSAGES = [
    {
        from: 'study',
        to: 'kitchen',
        colonies: ['beacon', 'flow'],
        result: 'crystal',
        fanoLine: [2, 5, 7],
        description: 'Planning meets recovery to produce verification'
    },
    {
        from: 'conservatory',
        to: 'lounge',
        colonies: ['spark', 'crystal'],
        result: 'grove',
        fanoLine: [1, 7, 6],
        description: 'Ideas meet verification to produce research'
    },
    {
        from: 'library',
        to: 'ballroom',
        colonies: ['grove', 'nexus'],
        result: 'forge',
        fanoLine: [2, 4, 6],
        description: 'Research meets integration to produce implementation'
    },
    {
        from: 'billiard',
        to: 'dining',
        colonies: ['forge', 'flow'],
        result: 'crystal',
        fanoLine: [3, 4, 7],
        description: 'Implementation meets recovery to produce verification'
    }
];

const CLUE_QUOTES = {
    wadsworth: [
        "I'm the butler. I buttle.",
        "Let me explain... No, there is too much. Let me sum up.",
        "One plus one plus two plus one...",
        "Ladies and gentlemen, you all have one thing in common.",
        "To make a long story short—",
        "Well, it's a matter of life after death. Now that he's dead, I have a life.",
        "The game's afoot!",
        "And monkey's brains, though popular in Cantonese cuisine, are not often to be found in Washington, D.C."
    ],
    mrsWhite: [
        "Flames... flames on the side of my face...",
        "I hated her... SO much... it-it... flames...",
        "Heaving... breaths... heaving breaths...",
        "I didn't kill him, but I'm certainly not sorry he's dead."
    ],
    missScarlet: [
        "I'm a woman—I like to be wooed.",
        "I enjoy getting presents from strange men.",
        "Well, someone's got to break the ice."
    ],
    colonelMustard: [
        "War is hell.",
        "Is there a little boys' room in the hall?",
        "Whadya mean, the cook is dead?"
    ],
    professorPlum: [
        "I work for UNO, the United Nations Organization.",
        "What are you afraid of? A fate worse than death?",
        "Mrs. Peacock was a man?!"
    ],
    mrsPeacock: [
        "This is absolutely contemptible!",
        "Everything I've done, I've done for my country.",
        "I had to stop her from giving us all away."
    ],
    mrGreen: [
        "I'm going to go home and sleep with my wife.",
        "I'm not shouting!",
        "I work for the State Department."
    ],
    singing: [
        "Life could be a dream... sweetheart..."
    ]
};

const ENDINGS = {
    A: {
        title: 'The Mathematical View',
        tagline: "That's how it could have happened.",
        focus: 'The Basement',
        content: `
            <h3>Ending A: The Mathematical Foundation</h3>
            <p>The murder weapon was the <strong>mathematics</strong>.</p>
            <p>In the Basement, we find the real secrets:</p>
            <ul>
                <li><strong>E8 Lattice</strong> — The densest sphere packing, used to quantize continuous spaces into efficient discrete representations</li>
                <li><strong>Fano Plane</strong> — The multiplication table of octonion imaginary units, routing how colonies compose</li>
                <li><strong>Octonions</strong> — The 8-dimensional algebra where Kagami (e₀) coordinates the seven colonies (e₁...e₇)</li>
                <li><strong>Catastrophe Theory</strong> — Seven elementary catastrophes mapping to seven colony behaviors</li>
            </ul>
            <blockquote>"The mathematics... that kills."</blockquote>
            <p>This view reveals Kagami as a <em>mathematical structure</em> that happens to compute—not a computer that uses math.</p>
        `
    },
    B: {
        title: 'The Safety View',
        tagline: "But here's what really happened...",
        focus: 'The Walls',
        content: `
            <h3>Ending B: The Safety System</h3>
            <p>The murder weapon was the <strong>safety constraints</strong>.</p>
            <p>The Walls of the mansion are Control Barrier Functions (CBF):</p>
            <ul>
                <li><strong>h(x) ≥ 0</strong> — The invariant that must never be violated</li>
                <li><strong>Tier 1</strong> — Organism barriers (memory, process, blanket integrity)</li>
                <li><strong>Tier 2</strong> — Colony barriers (per-colony behavioral constraints)</li>
                <li><strong>Tier 3</strong> — Action barriers (output safety, resource quotas)</li>
            </ul>
            <blockquote>"The safety invariant is INVIOLABLE."<br>— Like Mrs. Peacock's sense of propriety</blockquote>
            <p>This view reveals Kagami as a <em>safe system</em>—one that mathematically guarantees it cannot violate boundaries.</p>
        `
    },
    C: {
        title: 'The Full Picture',
        tagline: "But here's what REALLY happened.",
        focus: 'Everything',
        content: `
            <h3>Ending C: The Complete Architecture</h3>
            <p><strong>Everyone did it.</strong></p>
            <p>The true answer is that all pieces work together:</p>
            <ul>
                <li>🔥 <strong>Spark</strong> (Miss Scarlet) ignites ideas in the Conservatory</li>
                <li>⚒️ <strong>Forge</strong> (Colonel Mustard) builds them in the Billiard Room</li>
                <li>🌊 <strong>Flow</strong> (Mrs. White) recovers from failures in the Kitchen</li>
                <li>🔗 <strong>Nexus</strong> (Mr. Green) integrates everything in the Ballroom</li>
                <li>🗼 <strong>Beacon</strong> (Professor Plum) plans it all in the Study</li>
                <li>🌿 <strong>Grove</strong> (The Motorist) researches in the Library</li>
                <li>💎 <strong>Crystal</strong> (Mrs. Peacock) verifies in the Lounge</li>
                <li>🏛️ <strong>Kagami</strong> (Wadsworth) orchestrates from the Hall</li>
            </ul>
            <p>The Basement provides mathematical foundations. The Attic predicts the future. The Walls keep everyone safe.</p>
            <blockquote>"They all did it. But if you want to know who killed Mr. Body, I did. In the Hall. With the architecture."</blockquote>
            <p>This is Kagami—a living mansion where every room serves a purpose, every character has a role, and every secret passage connects minds.</p>
        `
    }
};

// Export for use in mansion.js
window.CHARACTERS = CHARACTERS;
window.ROOMS = ROOMS;
window.SECRET_PASSAGES = SECRET_PASSAGES;
window.CLUE_QUOTES = CLUE_QUOTES;
window.ENDINGS = ENDINGS;
