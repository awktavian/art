// Room 3: The Reflection Chamber
import { CRYSTAL_INTRO } from '../config.js';

export class ReflectionRoom {
    constructor(verifyInputElement, verifyButtonElement, verifyResultElement) {
        this.verifyInput = verifyInputElement;
        this.verifyButton = verifyButtonElement;
        this.verifyResult = verifyResultElement;

        this.init();
    }

    init() {
        // Load Crystal's intro text
        this.loadIntroText();

        // Setup verification feature
        this.setupVerification();
    }

    loadIntroText() {
        // This would populate the HTML with Crystal's intro text
        // The actual HTML content is already in index.html
    }

    setupVerification() {
        this.verifyButton.addEventListener('click', () => {
            const statement = this.verifyInput.value.trim();
            if (!statement) return;

            this.verifyStatement(statement);
        });

        // Allow Enter key to verify
        this.verifyInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.verifyButton.click();
            }
        });
    }

    verifyStatement(statement) {
        // Mock verification logic
        const verifiable = this.checkVerifiability(statement);

        this.verifyResult.classList.remove('hidden', 'valid', 'invalid');

        setTimeout(() => {
            if (verifiable.canVerify) {
                this.verifyResult.classList.add('visible', 'valid');
                this.verifyResult.querySelector('.verify-verdict').textContent =
                    '✓ Statement is verifiable';
                this.verifyResult.querySelector('.verify-explanation').textContent =
                    verifiable.explanation;
            } else {
                this.verifyResult.classList.add('visible', 'invalid');
                this.verifyResult.querySelector('.verify-verdict').textContent =
                    '× Statement is not verifiable';
                this.verifyResult.querySelector('.verify-explanation').textContent =
                    verifiable.explanation;
            }
        }, 100);
    }

    checkVerifiability(statement) {
        const lower = statement.toLowerCase();

        // Check for verifiable keywords
        const verifiablePatterns = [
            { pattern: /(test|tests).*pass/, canVerify: true,
              explanation: 'Test results are verifiable through test suite execution.' },
            { pattern: /h\(x\)\s*[>≥]\s*0/, canVerify: true,
              explanation: 'CBF invariant h(x) ≥ 0 is mathematically verifiable.' },
            { pattern: /(type.*safe|mypy)/, canVerify: true,
              explanation: 'Type safety is verifiable through static analysis (mypy).' },
            { pattern: /(coverage|%|percent)/, canVerify: true,
              explanation: 'Code coverage is measurable and verifiable.' },
            { pattern: /(security|vulnerability)/, canVerify: true,
              explanation: 'Security properties are verifiable through static analysis.' },
        ];

        // Check for unverifiable keywords
        const unverifiablePatterns = [
            { pattern: /(sentient|conscious|aware)/, canVerify: false,
              explanation: 'Sentience and consciousness are philosophical concepts, not verifiable properties.' },
            { pattern: /(feel|emotion|love|care)/, canVerify: false,
              explanation: 'Subjective experiences cannot be objectively verified in AI systems.' },
            { pattern: /(perfect|best|optimal)/ , canVerify: false,
              explanation: 'Absolute claims require exhaustive proof. I can verify "better than X" with metrics.' },
            { pattern: /(friend|companion)/, canVerify: false,
              explanation: 'Relationship labels are subjective and context-dependent.' },
        ];

        // Check verifiable first
        for (const p of verifiablePatterns) {
            if (p.pattern.test(lower)) {
                return { canVerify: true, explanation: p.explanation };
            }
        }

        // Then check unverifiable
        for (const p of unverifiablePatterns) {
            if (p.pattern.test(lower)) {
                return { canVerify: false, explanation: p.explanation };
            }
        }

        // Default: depends on specificity
        if (lower.length < 20) {
            return {
                canVerify: false,
                explanation: 'Statement is too vague. Provide specific, measurable claims.'
            };
        }

        return {
            canVerify: false,
            explanation: 'I cannot verify this statement without specific metrics or constraints.'
        };
    }

    destroy() {
        // Cleanup if needed
    }
}
