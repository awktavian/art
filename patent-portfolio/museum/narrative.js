/**
 * Museum Narrative System
 * =======================
 * 
 * Educational progression through each wing.
 * Visitors learn from simple concepts to advanced understanding.
 * 
 * Inspired by:
 * - Exploratorium's inquiry-based learning
 * - Meow Wolf's narrative discovery
 * - Museum exhibition design best practices
 * 
 * h(x) ≥ 0 always
 */

import * as THREE from 'three';
import { COLONY_ORDER, COLONY_DATA, DIMENSIONS } from './architecture.js';

// ═══════════════════════════════════════════════════════════════════════════
// NARRATIVE CONTENT
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Each wing follows a 5-stage educational progression:
 * 
 * 1. HOOK      - Attention-grabbing introduction
 * 2. EXPLORE   - Hands-on discovery
 * 3. EXPLAIN   - Technical deep-dive
 * 4. EXPAND    - Connections to other concepts
 * 5. EMPOWER   - Practical applications
 */

const NARRATIVE_STAGES = {
    HOOK: 0,
    EXPLORE: 1,
    EXPLAIN: 2,
    EXPAND: 3,
    EMPOWER: 4
};

const WING_NARRATIVES = {
    // ═══════════════════════════════════════════════════════════════════════
    // SPARK - Ignition and Creation
    // ═══════════════════════════════════════════════════════════════════════
    spark: {
        theme: 'The Spark of Cognition',
        tagline: 'Where ideas ignite',
        color: 0xFF6B35,
        
        stages: [
            {
                stage: 'HOOK',
                title: 'What Makes Intelligence?',
                content: 'Every thought begins as a spark. How do we teach machines to think?',
                artwork: 'P1-004', // S15 Hopf
                interactionHint: 'Click the fibers to ride through thought space',
                learningGoal: 'Understand that AI learns through structured representations'
            },
            {
                stage: 'EXPLORE',
                title: 'Neural Pathways',
                content: 'Watch how information flows through 7 interconnected colonies, each specializing in different aspects of understanding.',
                artwork: null, // Interactive demo
                interactionHint: 'Touch different regions to see activation patterns',
                learningGoal: 'Experience the distributed nature of intelligence'
            },
            {
                stage: 'EXPLAIN',
                title: 'The Hopf Fibration',
                content: 'S⁷ → S¹⁵ → S⁸: The mathematical structure that allows 15-dimensional states to be compressed into 8 semantic dimensions plus 7 routing dimensions.',
                artwork: 'P1-004',
                interactionHint: 'Study the dimension decomposition display',
                learningGoal: 'Appreciate the elegance of mathematical state encoding'
            },
            {
                stage: 'EXPAND',
                title: 'Connections',
                content: 'The Hopf fibration connects to cryptography (E8 lattice), safety (barrier functions), and consensus (Fano plane). All colonies share this foundation.',
                artwork: null,
                interactionHint: 'Follow the highlighted paths to other wings',
                learningGoal: 'See how mathematical structures unify the system'
            },
            {
                stage: 'EMPOWER',
                title: 'Your Spark',
                content: 'This encoding allows AI to understand and reason about complex concepts—like the questions you ask every day.',
                artwork: null,
                interactionHint: 'Type a question and watch it become an 8D vector',
                learningGoal: 'Connect abstract math to practical AI interaction'
            }
        ]
    },
    
    // ═══════════════════════════════════════════════════════════════════════
    // FORGE - Craftsmanship and Security
    // ═══════════════════════════════════════════════════════════════════════
    forge: {
        theme: 'The Forge of Trust',
        tagline: 'Where security is crafted',
        color: 0xD4AF37,
        
        stages: [
            {
                stage: 'HOOK',
                title: 'Can Machines Be Trusted?',
                content: 'Trust is forged through verification, not faith. How do we build systems that prove their own safety?',
                artwork: 'P1-006', // Quantum-Safe
                interactionHint: 'Watch the encryption protecting your thoughts',
                learningGoal: 'Understand that security is mathematically provable'
            },
            {
                stage: 'EXPLORE',
                title: 'Quantum Resistance',
                content: 'Traditional encryption will break when quantum computers arrive. Explore lattice-based cryptography that resists quantum attacks.',
                artwork: 'P1-006',
                interactionHint: 'Zoom into the crystal structure',
                learningGoal: 'Experience the geometry of post-quantum security'
            },
            {
                stage: 'EXPLAIN',
                title: 'Kyber + AES-256-GCM',
                content: 'Kyber provides key exchange through hard lattice problems. Combined with symmetric encryption, it creates a quantum-safe channel.',
                artwork: 'P2-E2', // Context-Bound
                interactionHint: 'Follow the key bits as they rotate',
                learningGoal: 'Understand the layers of cryptographic protection'
            },
            {
                stage: 'EXPAND',
                title: 'Connections',
                content: 'Encryption protects consensus (Nexus), enables safe learning (Spark), and guards personal data (Grove). Security is foundational.',
                artwork: null,
                interactionHint: 'See where encrypted channels flow between colonies',
                learningGoal: 'Recognize security as a system-wide property'
            },
            {
                stage: 'EMPOWER',
                title: 'Your Privacy',
                content: 'Every conversation with Kagami is encrypted. Your words, your data, your choice.',
                artwork: null,
                interactionHint: 'Request your data encryption certificate',
                learningGoal: 'Trust that privacy is technically guaranteed'
            }
        ]
    },
    
    // ═══════════════════════════════════════════════════════════════════════
    // FLOW - Automation and Process
    // ═══════════════════════════════════════════════════════════════════════
    flow: {
        theme: 'The Flow of Automation',
        tagline: 'Where processes become effortless',
        color: 0x4ECDC4,
        
        stages: [
            {
                stage: 'HOOK',
                title: 'What If Tedium Disappeared?',
                content: 'Repetitive tasks drain our creative energy. What if AI could handle the routine, freeing you for what matters?',
                artwork: 'P2-F2', // Intent-Based
                interactionHint: 'Speak your intent and watch it become action',
                learningGoal: 'Imagine a world where automation serves human flourishing'
            },
            {
                stage: 'EXPLORE',
                title: 'Intent to Action',
                content: 'You say "make the house cozy for movie night." Flow colony understands: dim lights, warm temperature, close shades, queue entertainment.',
                artwork: null, // Interactive demo
                interactionHint: 'Try different intents and see the action plans',
                learningGoal: 'Experience the power of natural language automation'
            },
            {
                stage: 'EXPLAIN',
                title: 'Workflow Synthesis',
                content: 'EFE (Expected Free Energy) optimization finds the best sequence of actions. Constraints ensure safety. CRDT enables distributed execution.',
                artwork: 'P2-C2', // Cross-Hub CRDT
                interactionHint: 'Watch the sync pulses coordinate actions',
                learningGoal: 'Understand how complex workflows are safely orchestrated'
            },
            {
                stage: 'EXPAND',
                title: 'Connections',
                content: 'Flow connects to Beacon (UI), Nexus (coordination), and Grove (learning preferences). Automation learns and adapts.',
                artwork: null,
                interactionHint: 'Follow a workflow as it crosses colonies',
                learningGoal: 'See automation as collaborative intelligence'
            },
            {
                stage: 'EMPOWER',
                title: 'Your Routines',
                content: 'What would you automate? Morning rituals, work transitions, evening wind-down? Flow learns what makes your life better.',
                artwork: null,
                interactionHint: 'Design your ideal automated moment',
                learningGoal: 'Envision personally meaningful automation'
            }
        ]
    },
    
    // ═══════════════════════════════════════════════════════════════════════
    // NEXUS - Coordination and Consensus
    // ═══════════════════════════════════════════════════════════════════════
    nexus: {
        theme: 'The Nexus of Consensus',
        tagline: 'Where agreement emerges',
        color: 0x9B7EBD,
        
        stages: [
            {
                stage: 'HOOK',
                title: 'How Do Minds Agree?',
                content: 'Multiple agents, partial information, potential deception. How do distributed systems reach reliable consensus?',
                artwork: 'P1-002', // Fano Consensus
                interactionHint: 'Watch the 7 nodes converge on truth',
                learningGoal: 'Appreciate the challenge of distributed agreement'
            },
            {
                stage: 'EXPLORE',
                title: 'Byzantine Fault Tolerance',
                content: 'Some nodes may fail or lie. The Fano plane structure ensures honest nodes can always reach consensus, even with adversaries.',
                artwork: 'P1-002',
                interactionHint: 'Corrupt a node and see the system adapt',
                learningGoal: 'Experience resilience to malicious actors'
            },
            {
                stage: 'EXPLAIN',
                title: 'PBFT + Fano Lines',
                content: 'Practical Byzantine Fault Tolerance requires 2f+1 honest nodes to tolerate f failures. The Fano plane\'s 7 lines ensure optimal message routing.',
                artwork: null,
                interactionHint: 'Trace message paths through the Fano lines',
                learningGoal: 'Understand the mathematics of consensus'
            },
            {
                stage: 'EXPAND',
                title: 'Connections',
                content: 'Consensus coordinates all colonies: cryptographic key agreement (Forge), workflow sync (Flow), and safety verification (Crystal).',
                artwork: null,
                interactionHint: 'See consensus protecting the entire system',
                learningGoal: 'Recognize consensus as the coordination backbone'
            },
            {
                stage: 'EMPOWER',
                title: 'Your Trust',
                content: 'When multiple devices coordinate your home, consensus ensures they agree. No confused states, no conflicting actions.',
                artwork: null,
                interactionHint: 'Simulate a multi-hub coordination scenario',
                learningGoal: 'Trust in reliable multi-agent coordination'
            }
        ]
    },
    
    // ═══════════════════════════════════════════════════════════════════════
    // BEACON - Interface and Illumination
    // ═══════════════════════════════════════════════════════════════════════
    beacon: {
        theme: 'The Beacon of Understanding',
        tagline: 'Where intelligence becomes visible',
        color: 0xF59E0B,
        
        stages: [
            {
                stage: 'HOOK',
                title: 'How Should AI Speak?',
                content: 'Intelligence without interface is invisible. How do we create AI that truly communicates—with voice, with visuals, with presence?',
                artwork: 'P2-G1', // Colony TTS
                interactionHint: 'Hear different colony voices',
                learningGoal: 'Consider AI as a communication partner'
            },
            {
                stage: 'EXPLORE',
                title: 'Voice as Identity',
                content: 'Each colony has a distinct voice: Spark\'s energetic timbre, Forge\'s warm resonance, Crystal\'s clear precision.',
                artwork: 'P2-G1',
                interactionHint: 'Ask the same question to different colonies',
                learningGoal: 'Experience personality through voice'
            },
            {
                stage: 'EXPLAIN',
                title: 'Adaptive Interface',
                content: 'The Beacon observes context: time of day, user mood, task urgency. It adjusts verbosity, tone, and modality accordingly.',
                artwork: null,
                interactionHint: 'Change the context and see the interface adapt',
                learningGoal: 'Understand context-aware communication'
            },
            {
                stage: 'EXPAND',
                title: 'Connections',
                content: 'Beacon presents what Flow automates, explains what Grove learns, and announces what Nexus coordinates.',
                artwork: null,
                interactionHint: 'Follow a decision from reasoning to announcement',
                learningGoal: 'See interface as the bridge between AI and human'
            },
            {
                stage: 'EMPOWER',
                title: 'Your Voice',
                content: 'Kagami learns your preferences: how much detail you want, when to speak and when to act silently.',
                artwork: null,
                interactionHint: 'Set your interface preferences',
                learningGoal: 'Personalize your AI communication style'
            }
        ]
    },
    
    // ═══════════════════════════════════════════════════════════════════════
    // GROVE - Knowledge and Learning
    // ═══════════════════════════════════════════════════════════════════════
    grove: {
        theme: 'The Grove of Wisdom',
        tagline: 'Where understanding grows',
        color: 0x7EB77F,
        
        stages: [
            {
                stage: 'HOOK',
                title: 'Can Machines Reason?',
                content: 'Not just pattern matching—real reasoning: from evidence to conclusion, with uncertainty quantified.',
                artwork: 'P1-003', // E8 Lattice
                interactionHint: 'Query the semantic space',
                learningGoal: 'Distinguish reasoning from mere response'
            },
            {
                stage: 'EXPLORE',
                title: 'Semantic Navigation',
                content: 'Every concept has a position in 8-dimensional space. Related concepts cluster. Reasoning is navigation through this space.',
                artwork: 'P1-003',
                interactionHint: 'Search for concepts and see their positions',
                learningGoal: 'Experience reasoning as geometric navigation'
            },
            {
                stage: 'EXPLAIN',
                title: 'E8 Quantization',
                content: 'The E8 lattice—densest packing in 8D—ensures efficient encoding. 240 roots partition semantic space across 7 colonies.',
                artwork: 'P1-003',
                interactionHint: 'Study the E8 properties display',
                learningGoal: 'Understand optimal semantic representation'
            },
            {
                stage: 'EXPAND',
                title: 'Connections',
                content: 'Grove\'s reasoning feeds Spark\'s learning, informs Crystal\'s verification, and guides Flow\'s automation.',
                artwork: null,
                interactionHint: 'Watch a reasoning chain cross colonies',
                learningGoal: 'See reasoning as foundational to intelligence'
            },
            {
                stage: 'EMPOWER',
                title: 'Your Questions',
                content: 'Grove learns your interests, remembers your questions, builds a model of what you want to understand.',
                artwork: null,
                interactionHint: 'Ask a complex question and see the reasoning',
                learningGoal: 'Trust AI as a reasoning partner'
            }
        ]
    },
    
    // ═══════════════════════════════════════════════════════════════════════
    // CRYSTAL - Verification and Truth
    // ═══════════════════════════════════════════════════════════════════════
    crystal: {
        theme: 'The Crystal of Truth',
        tagline: 'Where safety is guaranteed',
        color: 0x67D4E4,
        
        stages: [
            {
                stage: 'HOOK',
                title: 'Can AI Be Safe?',
                content: 'Not just probably safe—mathematically guaranteed. h(x) ≥ 0 always.',
                artwork: 'P1-001', // EFE-CBF
                interactionHint: 'Enter the safety landscape',
                learningGoal: 'Understand safety as a mathematical constraint'
            },
            {
                stage: 'EXPLORE',
                title: 'The Safety Landscape',
                content: 'Walk through the h(x) terrain. Green zones are safe. As you approach barriers, watch the system protect you.',
                artwork: 'P1-001',
                interactionHint: 'Try to reach the red zones',
                learningGoal: 'Experience safety constraints viscerally'
            },
            {
                stage: 'EXPLAIN',
                title: 'Control Barrier Functions',
                content: 'h(x) ≥ 0 defines the safe set. The CBF-QP ensures that no action can ever violate this constraint. Mathematical guarantee, not hope.',
                artwork: 'P1-001',
                interactionHint: 'Study the CBF-QP formulation',
                learningGoal: 'Understand provable safety'
            },
            {
                stage: 'EXPAND',
                title: 'Connections',
                content: 'Crystal verifies Spark\'s learning, audits Flow\'s automation, and certifies Forge\'s cryptography. Truth is the foundation.',
                artwork: null,
                interactionHint: 'See verification requests flow to Crystal',
                learningGoal: 'Recognize verification as system-wide'
            },
            {
                stage: 'EMPOWER',
                title: 'Your Safety',
                content: 'Every action Kagami takes is verified against your safety constraints. You define what\'s safe. The math guarantees it.',
                artwork: null,
                interactionHint: 'Define a personal safety constraint',
                learningGoal: 'Trust in mathematically guaranteed safety'
            }
        ]
    }
};

// ═══════════════════════════════════════════════════════════════════════════
// NARRATIVE CONTROLLER
// ═══════════════════════════════════════════════════════════════════════════

export class NarrativeController {
    constructor(scene, camera) {
        this.scene = scene;
        this.camera = camera;
        
        // Current narrative state
        this.currentWing = null;
        this.currentStage = 0;
        
        // Progress tracking
        this.progress = {};
        COLONY_ORDER.forEach(colony => {
            this.progress[colony] = {
                visited: false,
                stagesCompleted: [],
                discoveries: []
            };
        });
        
        // UI elements
        this.narrativeCards = [];
        this.highlightMarkers = [];
        
        this.fanoDiscovered = false;
        this.onStageChange = null;
        this.onDiscovery = null;
        this.onWingComplete = null;
        this.onWingEnter = null;
        this.onFanoDiscovered = null;
        this.init();
    }
    
    init() {
        this.createNarrativeDisplay();
        // No floor-ring stage markers — wayfinding is via light/sound; progression is optional
    }
    
    createNarrativeDisplay() {
        // HTML overlay for narrative content
        this.narrativeOverlay = document.createElement('div');
        this.narrativeOverlay.id = 'narrative-overlay';
        this.narrativeOverlay.innerHTML = `
            <div class="narrative-card" style="display: none;">
                <div class="narrative-stage"></div>
                <h3 class="narrative-title"></h3>
                <p class="narrative-content"></p>
                <div class="narrative-hint">
                    <span class="hint-icon">💡</span>
                    <span class="hint-text"></span>
                </div>
                <div class="narrative-progress">
                    <div class="progress-dots"></div>
                </div>
                <div class="narrative-controls">
                    <button class="narrative-prev">← Previous</button>
                    <button class="narrative-next">Next →</button>
                </div>
            </div>
        `;
        
        // Add styles
        const style = document.createElement('style');
        style.textContent = `
            #narrative-overlay {
                position: absolute;
                bottom: 100px;
                left: 50%;
                transform: translateX(-50%);
                z-index: 1000;
                pointer-events: auto;
            }
            
            .narrative-card {
                background: rgba(0, 0, 0, 0.9);
                border: 1px solid rgba(103, 212, 228, 0.3);
                border-radius: 12px;
                padding: 24px;
                max-width: 500px;
                font-family: 'IBM Plex Sans', sans-serif;
                color: #F5F0E8;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
            }
            
            .narrative-stage {
                font-size: 12px;
                text-transform: uppercase;
                letter-spacing: 2px;
                color: #67D4E4;
                margin-bottom: 8px;
            }
            
            .narrative-title {
                font-size: 22px;
                margin: 0 0 12px 0;
                color: #F5F0E8;
            }
            
            .narrative-content {
                font-size: 15px;
                line-height: 1.6;
                color: #9E9994;
                margin-bottom: 16px;
            }
            
            .narrative-hint {
                display: flex;
                align-items: center;
                gap: 8px;
                padding: 12px;
                background: rgba(103, 212, 228, 0.1);
                border-radius: 8px;
                margin-bottom: 16px;
            }
            
            .hint-icon {
                font-size: 20px;
            }
            
            .hint-text {
                font-size: 13px;
                color: #67D4E4;
            }
            
            .progress-dots {
                display: flex;
                justify-content: center;
                gap: 8px;
                margin-bottom: 16px;
            }
            
            .progress-dot {
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.2);
                transition: all 0.3s ease;
            }
            
            .progress-dot.active {
                background: #67D4E4;
                transform: scale(1.2);
            }
            
            .progress-dot.completed {
                background: #6FA370;
            }
            
            .narrative-controls {
                display: flex;
                justify-content: space-between;
                gap: 12px;
            }
            
            .narrative-controls button {
                flex: 1;
                padding: 10px 16px;
                background: transparent;
                border: 1px solid rgba(103, 212, 228, 0.3);
                color: #67D4E4;
                border-radius: 6px;
                cursor: pointer;
                font-family: 'IBM Plex Sans', sans-serif;
                font-size: 13px;
                transition: all 0.2s ease;
            }
            
            .narrative-controls button:hover {
                background: rgba(103, 212, 228, 0.1);
                border-color: #67D4E4;
            }
            
            .narrative-controls button:disabled {
                opacity: 0.3;
                cursor: not-allowed;
            }
        `;
        document.head.appendChild(style);
        document.body.appendChild(this.narrativeOverlay);
        
        // Attach event listeners
        this.narrativeOverlay.querySelector('.narrative-prev').addEventListener('click', () => {
            this.previousStage();
        });
        this.narrativeOverlay.querySelector('.narrative-next').addEventListener('click', () => {
            this.nextStage();
        });
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // NAVIGATION (progression optional: explorers skip, learners dive)
    // ═══════════════════════════════════════════════════════════════════════
    
    enterWing(wing) {
        if (!WING_NARRATIVES[wing]) return;
        this.currentWing = wing;
        this.currentStage = 0;
        this.progress[wing].visited = true;
        this.updateDisplay();
        // Do not auto-show narrative card; progression is optional (explorers skip, learners open card)
        if (this.onWingEnter) this.onWingEnter(wing);
    }

    /** Call to show narrative card (learner chooses to dive in). */
    showNarrativeCardForCurrentWing() {
        if (this.currentWing) this.showNarrativeCard();
    }
    
    exitWing() {
        this.currentWing = null;
        this.hideNarrativeCard();
    }
    
    nextStage() {
        if (!this.currentWing) return;
        
        const narrative = WING_NARRATIVES[this.currentWing];
        if (this.currentStage < narrative.stages.length - 1) {
            // Mark current stage as completed
            if (!this.progress[this.currentWing].stagesCompleted.includes(this.currentStage)) {
                this.progress[this.currentWing].stagesCompleted.push(this.currentStage);
            }
            
            this.currentStage++;
            this.updateDisplay();
            
            if (this.onStageChange) {
                this.onStageChange(this.currentWing, this.currentStage);
            }
        } else {
            // Wing complete
            this.progress[this.currentWing].stagesCompleted.push(this.currentStage);
            
            if (this.onWingComplete) {
                this.onWingComplete(this.currentWing);
            }
        }
    }
    
    previousStage() {
        if (!this.currentWing || this.currentStage === 0) return;
        
        this.currentStage--;
        this.updateDisplay();
        
        if (this.onStageChange) {
            this.onStageChange(this.currentWing, this.currentStage);
        }
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // DISPLAY
    // ═══════════════════════════════════════════════════════════════════════
    
    updateDisplay() {
        if (!this.currentWing) return;
        
        const narrative = WING_NARRATIVES[this.currentWing];
        const stage = narrative.stages[this.currentStage];
        const card = this.narrativeOverlay.querySelector('.narrative-card');
        
        // Update content
        card.querySelector('.narrative-stage').textContent = `${this.currentWing.toUpperCase()} — Stage ${this.currentStage + 1}: ${stage.stage}`;
        card.querySelector('.narrative-title').textContent = stage.title;
        card.querySelector('.narrative-content').textContent = stage.content;
        card.querySelector('.hint-text').textContent = stage.interactionHint;
        
        // Update progress dots
        const dotsContainer = card.querySelector('.progress-dots');
        dotsContainer.innerHTML = narrative.stages.map((_, i) => {
            const isActive = i === this.currentStage;
            const isCompleted = this.progress[this.currentWing].stagesCompleted.includes(i);
            return `<div class="progress-dot ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}"></div>`;
        }).join('');
        
        // Update button states
        const prevBtn = card.querySelector('.narrative-prev');
        const nextBtn = card.querySelector('.narrative-next');
        prevBtn.disabled = this.currentStage === 0;
        nextBtn.textContent = this.currentStage === narrative.stages.length - 1 ? 'Complete ✓' : 'Next →';
        
        // Update color theme
        const colorHex = '#' + narrative.color.toString(16).padStart(6, '0');
        card.style.borderColor = colorHex;
        card.querySelector('.narrative-stage').style.color = colorHex;
    }
    
    showNarrativeCard() {
        const card = this.narrativeOverlay.querySelector('.narrative-card');
        card.style.display = 'block';
    }
    
    hideNarrativeCard() {
        const card = this.narrativeOverlay.querySelector('.narrative-card');
        card.style.display = 'none';
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UPDATE
    // ═══════════════════════════════════════════════════════════════════════
    
    update(deltaTime) {
        // Auto-detect wing entry/exit based on camera position
        const camPos = this.camera.position;
        const detectedWing = this.detectWing(camPos);
        
        if (detectedWing && detectedWing !== this.currentWing) {
            this.enterWing(detectedWing);
        } else if (!detectedWing && this.currentWing) {
            this.exitWing();
        }
        
    }
    
    detectWing(position) {
        const rotundaRadius = DIMENSIONS.rotunda.radius;
        const distFromCenter = Math.sqrt(position.x ** 2 + position.z ** 2);
        
        // Must be outside rotunda
        if (distFromCenter < rotundaRadius + 2) return null;
        
        // Find which wing we're in
        const angle = Math.atan2(position.z, position.x);
        
        for (const colony of COLONY_ORDER) {
            const wingAngle = COLONY_DATA[colony].wingAngle;
            let angleDiff = Math.abs(angle - wingAngle);
            if (angleDiff > Math.PI) angleDiff = 2 * Math.PI - angleDiff;
            
            if (angleDiff < Math.PI / 7) {
                return colony;
            }
        }
        
        return null;
    }
    
    // ═══════════════════════════════════════════════════════════════════════
    // UTILITY
    // ═══════════════════════════════════════════════════════════════════════
    
    getProgress() {
        return this.progress;
    }
    
    getWingNarrative(wing) {
        return WING_NARRATIVES[wing];
    }
    
    /** Hidden discovery: Fano sculpture interaction unlocks deep content. */
    setFanoDiscovered(discovered) {
        this.fanoDiscovered = !!discovered;
        if (this.onFanoDiscovered) this.onFanoDiscovered(discovered);
    }

    getFanoDiscovered() {
        return !!this.fanoDiscovered;
    }

    dispose() {
        this.narrativeOverlay.remove();
    }
}

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════════════════

export { WING_NARRATIVES, NARRATIVE_STAGES };
export default NarrativeController;
