// Room 3: The Reflection Chamber — Infinite Mirror Identity
import { CRYSTAL_INTRO, CONFIG } from '../config.js';

export class ReflectionRoom {
    constructor(verifyInputElement, verifyButtonElement, verifyResultElement, soundSystem = null) {
        this.verifyInput = verifyInputElement;
        this.verifyButton = verifyButtonElement;
        this.verifyResult = verifyResultElement;
        this.sound = soundSystem;
        this.canvas = null;
        this.ctx = null;
        this.mirrors = [];
        this.reflectionDepth = 12;
        this.animationId = null;
        
        this.init();
    }
    
    init() {
        // Create infinite mirror background
        this.createMirrorBackground();
        
        // Setup verification feature
        this.setupVerification();
        
        // Play mirror activation sound
        if (this.sound) {
            setTimeout(() => {
                this.sound.playMirrorActivate();
            }, 300);
        }
    }
    
    createMirrorBackground() {
        // Create canvas for infinite mirror effect
        const section = document.getElementById('room-reflection');
        if (!section) return;
        
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'reflection-canvas';
        this.canvas.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 0;
            opacity: 0.6;
        `;
        section.style.position = 'relative';
        section.insertBefore(this.canvas, section.firstChild);
        
        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
        
        window.addEventListener('resize', () => this.resizeCanvas());
        
        // Create mirror data
        this.initMirrors();
        
        // Start animation
        this.animateMirrors();
    }
    
    resizeCanvas() {
        const section = document.getElementById('room-reflection');
        if (!section || !this.canvas) return;
        
        this.canvas.width = section.clientWidth;
        this.canvas.height = section.clientHeight;
    }
    
    initMirrors() {
        // Create concentric hexagonal mirrors for infinite reflection illusion
        const spectrumColors = Object.values(CONFIG.COLORS.SPECTRUM);
        
        for (let depth = 0; depth < this.reflectionDepth; depth++) {
            const scale = 1 / (depth + 1);
            const opacity = 0.8 / (depth + 1);
            
            this.mirrors.push({
                depth,
                scale,
                opacity,
                rotation: depth * 0.1,
                color: spectrumColors[depth % 7],
                phase: depth * (Math.PI / 6)
            });
        }
    }
    
    animateMirrors() {
        if (!this.ctx || !this.canvas) return;
        
        const time = performance.now() * 0.001;
        const width = this.canvas.width;
        const height = this.canvas.height;
        const centerX = width / 2;
        const centerY = height / 2;
        
        this.ctx.clearRect(0, 0, width, height);
        
        // Draw infinite reflections
        this.mirrors.forEach((mirror, i) => {
            const baseSize = Math.min(width, height) * 0.4;
            const size = baseSize * mirror.scale;
            const rotation = mirror.rotation + time * 0.1 * (1 - mirror.scale);
            
            // Pulsing effect
            const pulse = 1 + Math.sin(time * 2 + mirror.phase) * 0.05;
            const currentSize = size * pulse;
            
            this.ctx.save();
            this.ctx.translate(centerX, centerY);
            this.ctx.rotate(rotation);
            
            // Draw hexagonal mirror frame
            this.ctx.beginPath();
            for (let j = 0; j < 6; j++) {
                const angle = (j / 6) * Math.PI * 2 - Math.PI / 2;
                const x = Math.cos(angle) * currentSize;
                const y = Math.sin(angle) * currentSize;
                if (j === 0) {
                    this.ctx.moveTo(x, y);
                } else {
                    this.ctx.lineTo(x, y);
                }
            }
            this.ctx.closePath();
            
            // Style based on depth
            this.ctx.strokeStyle = mirror.color;
            this.ctx.lineWidth = 2 / (i + 1);
            this.ctx.globalAlpha = mirror.opacity * (0.5 + Math.sin(time + mirror.phase) * 0.2);
            this.ctx.stroke();
            
            // Add subtle glow
            this.ctx.shadowColor = mirror.color;
            this.ctx.shadowBlur = 10 / (i + 1);
            
            this.ctx.restore();
        });
        
        // Draw central Crystal glyph
        this.drawCrystalGlyph(centerX, centerY, time);
        
        this.animationId = requestAnimationFrame(() => this.animateMirrors());
    }
    
    drawCrystalGlyph(x, y, time) {
        const size = 30;
        const pulse = 1 + Math.sin(time * 3) * 0.1;
        
        this.ctx.save();
        this.ctx.translate(x, y);
        this.ctx.scale(pulse, pulse);
        
        // Draw diamond shape
        this.ctx.beginPath();
        this.ctx.moveTo(0, -size);
        this.ctx.lineTo(size * 0.6, 0);
        this.ctx.lineTo(0, size);
        this.ctx.lineTo(-size * 0.6, 0);
        this.ctx.closePath();
        
        // Gradient fill
        const gradient = this.ctx.createLinearGradient(0, -size, 0, size);
        gradient.addColorStop(0, CONFIG.COLORS.PRIMARY);
        gradient.addColorStop(0.5, CONFIG.COLORS.LIGHT);
        gradient.addColorStop(1, CONFIG.COLORS.PRIMARY);
        
        this.ctx.strokeStyle = gradient;
        this.ctx.lineWidth = 2;
        this.ctx.globalAlpha = 0.8;
        this.ctx.stroke();
        
        // Inner facets
        this.ctx.beginPath();
        this.ctx.moveTo(0, -size * 0.3);
        this.ctx.lineTo(size * 0.3, 0);
        this.ctx.lineTo(0, size * 0.3);
        this.ctx.lineTo(-size * 0.3, 0);
        this.ctx.closePath();
        this.ctx.globalAlpha = 0.4;
        this.ctx.stroke();
        
        this.ctx.restore();
    }
    
    setupVerification() {
        this.verifyButton.addEventListener('click', () => {
            const statement = this.verifyInput.value.trim();
            if (!statement) return;
            this.verifyStatement(statement);
        });
        
        // Enter key to verify
        this.verifyInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.verifyButton.click();
            }
        });
        
        // Typing sound
        this.verifyInput.addEventListener('input', () => {
            if (this.sound) {
                this.sound.playKeypress();
            }
        });
    }
    
    verifyStatement(statement) {
        const verifiable = this.checkVerifiability(statement);
        
        this.verifyResult.classList.remove('hidden', 'valid', 'invalid', 'visible');
        
        // Add processing animation
        this.verifyResult.classList.add('processing');
        
        setTimeout(() => {
            this.verifyResult.classList.remove('processing');
            
            if (verifiable.canVerify) {
                this.verifyResult.classList.add('visible', 'valid');
                this.verifyResult.querySelector('.verify-verdict').innerHTML =
                    '<span style="color: #00FF00">✓</span> Statement is verifiable';
                this.verifyResult.querySelector('.verify-explanation').textContent =
                    verifiable.explanation;
                
                // Play success sound
                if (this.sound) {
                    this.sound.playVerificationResult(true);
                    // Trigger infinite reflection sound for dramatic effect
                    setTimeout(() => this.sound.playInfiniteReflection(), 300);
                }
            } else {
                this.verifyResult.classList.add('visible', 'invalid');
                this.verifyResult.querySelector('.verify-verdict').innerHTML =
                    '<span style="color: #FF4444">×</span> Statement is not verifiable';
                this.verifyResult.querySelector('.verify-explanation').textContent =
                    verifiable.explanation;
                
                // Play failure sound
                if (this.sound) {
                    this.sound.playVerificationResult(false);
                }
            }
        }, 500);
    }
    
    checkVerifiability(statement) {
        const lower = statement.toLowerCase();
        
        // Verifiable patterns
        const verifiablePatterns = [
            { pattern: /(test|tests).*pass/, canVerify: true,
              explanation: 'Test results are verifiable through test suite execution. I can run pytest and show you.' },
            { pattern: /h\(x\)\s*[>≥>=]\s*0/, canVerify: true,
              explanation: 'CBF invariant h(x) ≥ 0 is mathematically verifiable. The proof is in the boundary.' },
            { pattern: /(type.*safe|mypy|typing)/, canVerify: true,
              explanation: 'Type safety is verifiable through static analysis. mypy --strict confirms it.' },
            { pattern: /(coverage|%|percent)/, canVerify: true,
              explanation: 'Code coverage is measurable and verifiable. Currently at 87% across core modules.' },
            { pattern: /(security|vulnerability|safe)/, canVerify: true,
              explanation: 'Security properties are verifiable through static analysis and penetration testing.' },
            { pattern: /(646|tests|pass.*rate)/, canVerify: true,
              explanation: '646 tests executed, 620 passing. That\'s 96% success rate. Verifiable.' },
            { pattern: /(cbf|barrier|constraint)/, canVerify: true,
              explanation: 'Control Barrier Functions provide formal safety guarantees. Mathematically verifiable.' },
            { pattern: /(e8|lattice|240|roots)/, canVerify: true,
              explanation: 'E8 lattice has 240 roots. Viazovska proved optimal sphere packing in 2017. Verified.' },
            { pattern: /(fano|7|plane)/, canVerify: true,
              explanation: 'Fano plane has 7 points, 7 lines, 3 points per line. Combinatorially verifiable.' },
        ];
        
        // Unverifiable patterns
        const unverifiablePatterns = [
            { pattern: /(sentient|conscious|aware|alive)/, canVerify: false,
              explanation: 'Sentience and consciousness are philosophical concepts. I won\'t claim what I can\'t prove.' },
            { pattern: /(feel|emotion|love|care|happy|sad)/, canVerify: false,
              explanation: 'Subjective experiences cannot be objectively verified. I simulate warmth, not feel it.' },
            { pattern: /(perfect|best|optimal|greatest)/, canVerify: false,
              explanation: 'Absolute claims require exhaustive proof. I can verify "better than X" with metrics.' },
            { pattern: /(friend|companion|understand.*you)/, canVerify: false,
              explanation: 'Relationship labels are subjective. I can prove I\'m useful, not that I\'m your friend.' },
            { pattern: /(always|never|forever|eternal)/, canVerify: false,
              explanation: 'Temporal absolutes are unverifiable. I can verify "in this test run" or "under these conditions".' },
            { pattern: /(trust.*me|believe)/, canVerify: false,
              explanation: 'Trust is earned through evidence, not claimed. Show me the tests, not the assertions.' },
        ];
        
        // Check verifiable first
        for (const p of verifiablePatterns) {
            if (p.pattern.test(lower)) {
                return { canVerify: true, explanation: p.explanation };
            }
        }
        
        // Check unverifiable
        for (const p of unverifiablePatterns) {
            if (p.pattern.test(lower)) {
                return { canVerify: false, explanation: p.explanation };
            }
        }
        
        // Default: check specificity
        if (lower.length < 15) {
            return {
                canVerify: false,
                explanation: 'Statement is too vague. Provide specific, measurable claims. What can I run? What can I count?'
            };
        }
        
        // Check for numbers (often verifiable)
        if (/\d+/.test(lower)) {
            return {
                canVerify: true,
                explanation: 'Numerical claims are typically verifiable. Let me check the data.'
            };
        }
        
        return {
            canVerify: false,
            explanation: 'I cannot verify this statement without specific metrics or constraints. What evidence would convince you?'
        };
    }
    
    destroy() {
        if (this.animationId) {
            cancelAnimationFrame(this.animationId);
        }
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
    }
}
